import logging
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ..audit import audit_event, record_operational_event
from ..models import Booking, BookingStatusHistory, Notification, Payment, PaymentLedgerEntry, PaymentStatusHistory, ProviderEvent, RefundRequest, RefundStatusHistory
from .bookings import BOOKING_CHAT_STATUSES, transition_booking_status
from .chat import booking_is_chat_eligible, ensure_chat_for_booking
from .payment_providers import get_payment_provider, payload_hash, verify_provider_event as provider_event_verified
from ..utils import create_notification


payment_logger = logging.getLogger("main.payments")
webhook_logger = logging.getLogger("main.webhooks")

ALLOWED_PAYMENT_TRANSITIONS = {
    Payment.PaymentStatus.PENDING: {
        Payment.PaymentStatus.AWAITING_VERIFICATION,
        Payment.PaymentStatus.SUCCESS,
        Payment.PaymentStatus.FAILED,
    },
    Payment.PaymentStatus.AWAITING_VERIFICATION: {
        Payment.PaymentStatus.SUCCESS,
        Payment.PaymentStatus.FAILED,
        Payment.PaymentStatus.REFUNDED,
    },
    Payment.PaymentStatus.SUCCESS: {Payment.PaymentStatus.REFUNDED},
    Payment.PaymentStatus.FAILED: set(),
    Payment.PaymentStatus.REFUNDED: set(),
}
DEMO_PROVIDERS = {"Demo Manual", "Secure Demo"}
PROVIDER_PAYMENT_EVENT_STATUS_MAP = {
    "payment.success": Payment.PaymentStatus.SUCCESS,
    "payment.failed": Payment.PaymentStatus.FAILED,
    "payment.refunded": Payment.PaymentStatus.REFUNDED,
}
REFUND_FINAL_STATUSES = {RefundRequest.RefundStatus.PROCESSED, RefundRequest.RefundStatus.CANCELLED}
REFUND_ACTIVE_STATUSES = {RefundRequest.RefundStatus.REQUESTED, RefundRequest.RefundStatus.PROCESSING}


def ensure_payment(booking):
    return Payment.objects.get_or_create(
        booking=booking,
        defaults={"amount": booking.price_snapshot or booking.lawyer.fee},
    )


def verify_provider_event(provider, *, payload=None, signature=""):
    try:
        return provider_event_verified(provider, payload=payload, signature=signature)
    except ValidationError:
        return False


def _locked_payment_and_booking(payment):
    locked_payment = (
        Payment.objects.select_for_update()
        .select_related("booking", "booking__client", "booking__lawyer", "booking__lawyer__user")
        .get(id=payment.id)
    )
    booking = (
        Booking.objects.select_for_update()
        .select_related("client", "lawyer", "lawyer__user")
        .get(id=locked_payment.booking_id)
    )
    locked_payment.booking = booking
    return locked_payment, booking


def confirm_booking_for_successful_payment(payment, booking, *, actor=None, reason="Payment verified"):
    """Move a payable active booking to CONFIRMED when payment is SUCCESS."""
    payment_logger.info(
        {
            "event": "payment_success_booking_confirm_attempt",
            "payment_id": payment.id,
            "booking_id": booking.id,
            "payment_status": payment.payment_status,
            "booking_status": booking.status,
        }
    )
    if payment.payment_status != Payment.PaymentStatus.SUCCESS:
        payment_logger.info(
            {
                "event": "payment_success_booking_confirm_skipped",
                "payment_id": payment.id,
                "booking_id": booking.id,
                "reason": "payment_not_success",
            }
        )
        return booking, False

    booking.refresh_from_db(fields=["status", "updated_at"])
    confirmable_statuses = {Booking.Status.PENDING, Booking.Status.RESCHEDULED}
    if booking.status not in confirmable_statuses:
        payment_logger.info(
            {
                "event": "payment_success_booking_confirm_skipped",
                "payment_id": payment.id,
                "booking_id": booking.id,
                "reason": "booking_not_confirmable",
                "booking_status": booking.status,
            }
        )
        return booking, False

    transition_booking_status(
        booking,
        Booking.Status.CONFIRMED,
        actor=actor,
        reason=reason,
        payment=payment,
    )
    booking.refresh_from_db(fields=["status", "updated_at"])
    payment_logger.info(
        {
            "event": "payment_success_booking_confirmed",
            "payment_id": payment.id,
            "booking_id": booking.id,
            "booking_status": booking.status,
        }
    )
    return booking, True


def _ensure_chat_after_successful_payment(payment, booking):
    booking.refresh_from_db(fields=["status", "updated_at"])
    if booking.status not in BOOKING_CHAT_STATUSES:
        return None
    chat = ensure_chat_for_booking(booking)
    payment_logger.info(
        {
            "event": "payment_success_chat_unlock_check",
            "payment_id": payment.id,
            "booking_id": booking.id,
            "booking_status": booking.status,
            "payment_status": payment.payment_status,
            "chat_eligible": booking_is_chat_eligible(booking),
            "chat_id": chat.id if chat else None,
        }
    )
    return chat


def _processed_provider_event(provider, provider_event_id):
    if not provider_event_id:
        return None
    return PaymentStatusHistory.objects.filter(provider=provider, provider_event_id=provider_event_id).first()


def _validate_idempotency(payment, idempotency_key):
    if not idempotency_key:
        return
    duplicate = Payment.objects.filter(idempotency_key=idempotency_key).exclude(id=payment.id).exists()
    if duplicate:
        raise ValidationError("This payment idempotency key has already been used.")
    if payment.idempotency_key and payment.idempotency_key != idempotency_key:
        raise ValidationError("This payment was already processed with a different idempotency key.")


def _find_payment_for_provider_event(event):
    queryset = Payment.objects.select_related("booking", "booking__client", "booking__lawyer", "booking__lawyer__user")
    if event.payment_reference:
        try:
            return queryset.get(payment_reference=event.payment_reference)
        except (Payment.DoesNotExist, ValueError, ValidationError):
            pass
    if event.provider_payment_id:
        payment = queryset.filter(provider_payment_id=event.provider_payment_id).first()
        if payment:
            return payment
    if event.provider_order_id:
        payment = queryset.filter(provider_order_id=event.provider_order_id).first()
        if payment:
            return payment
    raise ValidationError("Provider event could not be matched to a payment.")


def _update_provider_identifiers(payment, event):
    update_fields = []
    if event.provider_payment_id and not payment.provider_payment_id:
        payment.provider_payment_id = event.provider_payment_id
        update_fields.append("provider_payment_id")
    if event.provider_order_id and not payment.provider_order_id:
        payment.provider_order_id = event.provider_order_id
        update_fields.append("provider_order_id")
    if update_fields:
        update_fields.append("updated_at")
        payment.save(update_fields=update_fields)


def _record_ledger_entry(
    payment,
    entry_type,
    amount,
    *,
    refund_request=None,
    provider="",
    provider_event_id="",
    idempotency_key="",
    description="",
):
    defaults = {
        "payment": payment,
        "refund_request": refund_request,
        "amount": amount,
        "currency": payment.currency,
        "provider": provider,
        "provider_event_id": provider_event_id,
        "idempotency_key": idempotency_key,
        "description": description,
    }
    if provider_event_id:
        entry, _ = PaymentLedgerEntry.objects.get_or_create(
            provider=provider,
            provider_event_id=provider_event_id,
            entry_type=entry_type,
            defaults=defaults,
        )
        return entry
    if idempotency_key:
        entry, _ = PaymentLedgerEntry.objects.get_or_create(
            idempotency_key=idempotency_key,
            entry_type=entry_type,
            defaults=defaults,
        )
        return entry
    return PaymentLedgerEntry.objects.create(entry_type=entry_type, **defaults)


def _record_refund_history(refund_request, previous_status, *, actor=None, reason="", provider="", provider_event_id=""):
    RefundStatusHistory.objects.create(
        refund_request=refund_request,
        from_status=previous_status,
        to_status=refund_request.status,
        actor=actor,
        reason=reason,
        provider=provider,
        provider_event_id=provider_event_id,
    )


def validate_payment_transition(payment, next_status, booking):
    try:
        next_status = Payment.PaymentStatus(next_status)
    except ValueError as exc:
        raise ValidationError("Invalid payment status transition.") from exc

    if next_status == payment.payment_status:
        return False

    allowed_next_statuses = ALLOWED_PAYMENT_TRANSITIONS.get(payment.payment_status, set())
    if next_status not in allowed_next_statuses:
        raise ValidationError(
            f"Payment cannot move from {Payment.PaymentStatus(payment.payment_status).label.lower()} to {next_status.label.lower()}."
        )

    if next_status == Payment.PaymentStatus.SUCCESS and booking.status in {
        Booking.Status.CANCELLED,
        Booking.Status.COMPLETED,
        Booking.Status.REFUNDED,
    }:
        raise ValidationError("Payment cannot be completed for cancelled, completed, or refunded bookings.")

    if next_status in {Payment.PaymentStatus.PENDING, Payment.PaymentStatus.AWAITING_VERIFICATION, Payment.PaymentStatus.FAILED}:
        if booking.status in {Booking.Status.COMPLETED, Booking.Status.REFUNDED}:
            raise ValidationError("Completed or refunded bookings cannot move to an invalid payment state.")

    return True


def transition_payment_status(
    payment,
    next_status,
    *,
    actor=None,
    reason="",
    idempotency_key="",
    provider="Demo Manual",
    provider_event_id="",
    ledger_refund_request=None,
):
    if provider_event_id and not verify_provider_event(provider):
        raise ValidationError("Payment provider event could not be verified.")

    with transaction.atomic():
        payment, booking = _locked_payment_and_booking(payment)
        _validate_idempotency(payment, idempotency_key)

        processed_event = _processed_provider_event(provider, provider_event_id)
        if processed_event:
            if processed_event.payment_id != payment.id:
                raise ValidationError("This provider event has already been processed for another payment.")
            if payment.payment_status == Payment.PaymentStatus.SUCCESS:
                confirm_booking_for_successful_payment(
                    payment,
                    booking,
                    actor=actor,
                    reason=reason or "Payment already successful",
                )
                _ensure_chat_after_successful_payment(payment, booking)
            return payment, False

        should_change = validate_payment_transition(payment, next_status, booking)
        if not should_change:
            if idempotency_key and not payment.idempotency_key:
                payment.idempotency_key = idempotency_key
                payment.save(update_fields=["idempotency_key", "updated_at"])
            if payment.payment_status == Payment.PaymentStatus.SUCCESS:
                confirm_booking_for_successful_payment(
                    payment,
                    booking,
                    actor=actor,
                    reason=reason or "Payment already successful",
                )
                _ensure_chat_after_successful_payment(payment, booking)
            return payment, False

        previous_status = payment.payment_status
        payment.payment_status = Payment.PaymentStatus(next_status)
        update_fields = ["payment_status", "updated_at"]

        if idempotency_key and not payment.idempotency_key:
            payment.idempotency_key = idempotency_key
            update_fields.append("idempotency_key")

        if provider:
            payment.provider = provider
            update_fields.append("provider")

        if payment.payment_status == Payment.PaymentStatus.SUCCESS:
            if not payment.transaction_id:
                payment.transaction_id = f"LX-{uuid4().hex[:12].upper()}"
                update_fields.append("transaction_id")
            if not payment.marked_paid_at:
                payment.marked_paid_at = timezone.now()
                update_fields.append("marked_paid_at")

        payment.save(update_fields=update_fields)
        PaymentStatusHistory.objects.create(
            payment=payment,
            from_status=previous_status,
            to_status=payment.payment_status,
            actor=actor,
            reason=reason,
            idempotency_key=idempotency_key,
            provider=provider,
            provider_event_id=provider_event_id,
        )
        if payment.payment_status == Payment.PaymentStatus.SUCCESS:
            _record_ledger_entry(
                payment,
                PaymentLedgerEntry.EntryType.PAYMENT_CAPTURED,
                payment.amount,
                provider=provider,
                provider_event_id=provider_event_id,
                idempotency_key=idempotency_key,
                description="Payment marked successful",
            )
        elif payment.payment_status == Payment.PaymentStatus.REFUNDED:
            _record_ledger_entry(
                payment,
                PaymentLedgerEntry.EntryType.PAYMENT_REFUNDED,
                payment.amount,
                refund_request=ledger_refund_request,
                provider=provider,
                provider_event_id=provider_event_id,
                description="Payment marked refunded",
            )

        if payment.payment_status == Payment.PaymentStatus.SUCCESS:
            confirm_booking_for_successful_payment(payment, booking, actor=actor, reason="Payment verified")
        elif payment.payment_status == Payment.PaymentStatus.FAILED and booking.status == Booking.Status.CONFIRMED:
            booking.status = Booking.Status.PENDING
            booking.save(update_fields=["status", "updated_at"])
            BookingStatusHistory.objects.create(
                booking=booking,
                from_status=Booking.Status.CONFIRMED,
                to_status=Booking.Status.PENDING,
                actor=actor,
                reason="Payment failed",
            )
        elif payment.payment_status == Payment.PaymentStatus.REFUNDED and booking.status in {
            Booking.Status.PENDING,
            Booking.Status.CONFIRMED,
            Booking.Status.COMPLETED,
        }:
            previous_booking_status = booking.status
            booking.status = Booking.Status.REFUNDED
            booking.save(update_fields=["status", "updated_at"])
            BookingStatusHistory.objects.create(
                booking=booking,
                from_status=previous_booking_status,
                to_status=Booking.Status.REFUNDED,
                actor=actor,
                reason="Payment refunded",
            )

        if payment.payment_status == Payment.PaymentStatus.SUCCESS:
            _ensure_chat_after_successful_payment(payment, booking)

    return payment, True


def _get_or_record_provider_event(provider, normalized_event, payload):
    event_hash = payload_hash(payload)
    provider_event, created = ProviderEvent.objects.get_or_create(
        provider=provider,
        event_id=normalized_event.event_id,
        defaults={
            "event_type": normalized_event.event_type,
            "payload_hash": event_hash,
            "payload": payload,
        },
    )
    if not created:
        if provider_event.payload_hash != event_hash:
            raise ValidationError("Provider event payload does not match the original event.")
        provider_event.replay_count += 1
        provider_event.save(update_fields=["replay_count", "updated_at"])
    return provider_event, created


def process_provider_webhook(provider, payload, *, signature="", trusted_stored_event=False):
    provider_client = get_payment_provider(provider)
    if not trusted_stored_event and not provider_client.verify_event(payload=payload, signature=signature):
        webhook_logger.warning({"event": "provider_webhook_signature_invalid", "provider": provider})
        raise ValidationError("Payment provider event could not be verified.")

    normalized_event = provider_client.normalize_event(payload)
    webhook_logger.info(
        {
            "event": "provider_webhook_received",
            "provider": provider,
            "provider_event_id": normalized_event.event_id,
            "event_type": normalized_event.event_type,
        }
    )
    with transaction.atomic():
        provider_event, created = _get_or_record_provider_event(provider, normalized_event, payload)
        if not created and provider_event.processing_status in {
            ProviderEvent.ProcessingStatus.PROCESSED,
            ProviderEvent.ProcessingStatus.IGNORED,
        }:
            webhook_logger.info(
                {
                    "event": "provider_webhook_replay_ignored",
                    "provider": provider,
                    "provider_event_id": provider_event.event_id,
                    "status": provider_event.processing_status,
                    "replay_count": provider_event.replay_count,
                }
            )
            return provider_event, False

        try:
            if normalized_event.event_type in PROVIDER_PAYMENT_EVENT_STATUS_MAP:
                payment = _find_payment_for_provider_event(normalized_event)
                _update_provider_identifiers(payment, normalized_event)
                payment, _changed = transition_payment_status(
                    payment,
                    PROVIDER_PAYMENT_EVENT_STATUS_MAP[normalized_event.event_type],
                    reason=f"Provider webhook {normalized_event.event_type}",
                    idempotency_key=normalized_event.idempotency_key,
                    provider=provider,
                    provider_event_id=normalized_event.event_id,
                )
                provider_event.payment = payment
            elif normalized_event.event_type == "refund.processed":
                refund_request, _changed = process_provider_refund_event(
                    provider,
                    normalized_event.provider_refund_id,
                    provider_event_id=normalized_event.event_id,
                )
                provider_event.payment = refund_request.payment
                provider_event.refund_request = refund_request
            elif normalized_event.event_type == "refund.failed":
                refund_request, _changed = fail_refund_from_provider_event(
                    provider,
                    normalized_event.provider_refund_id,
                    provider_event_id=normalized_event.event_id,
                    reason="Provider refund failed",
                )
                provider_event.payment = refund_request.payment
                provider_event.refund_request = refund_request
            else:
                provider_event.processing_status = ProviderEvent.ProcessingStatus.IGNORED
                provider_event.processed_at = timezone.now()
                provider_event.save(update_fields=["processing_status", "processed_at", "updated_at"])
                return provider_event, True
        except ValidationError as exc:
            provider_event.processing_status = ProviderEvent.ProcessingStatus.FAILED
            provider_event.error_message = str(exc)
            provider_event.save(update_fields=["processing_status", "error_message", "updated_at"])
            record_operational_event(
                "webhook",
                "provider_webhook_processing_failed",
                level="error",
                summary=f"{provider} {provider_event.event_id} failed: {str(exc)[:160]}",
                metadata={
                    "provider": provider,
                    "provider_event_id": provider_event.event_id,
                    "event_type": provider_event.event_type,
                    "error": str(exc),
                },
            )
            webhook_logger.exception(
                {
                    "event": "provider_webhook_processing_failed",
                    "provider": provider,
                    "provider_event_id": provider_event.event_id,
                    "event_type": provider_event.event_type,
                }
            )
            raise

        provider_event.processing_status = ProviderEvent.ProcessingStatus.PROCESSED
        provider_event.error_message = ""
        provider_event.processed_at = timezone.now()
        provider_event.save(update_fields=["payment", "refund_request", "processing_status", "error_message", "processed_at", "updated_at"])
        audit_event("provider_webhook_processed", provider=provider, provider_event_id=provider_event.event_id, event_type=provider_event.event_type)
        payment_logger.info(
            {
                "event": "provider_webhook_processed",
                "provider": provider,
                "provider_event_id": provider_event.event_id,
                "event_type": provider_event.event_type,
                "payment_id": provider_event.payment_id,
            }
        )
        return provider_event, True


def request_demo_payment_verification(payment, *, actor):
    payment = Payment.objects.select_related("booking", "booking__client", "booking__lawyer", "booking__lawyer__user").get(id=payment.id)
    booking = payment.booking
    if actor != booking.client:
        raise ValidationError("Only the booking client can request payment verification.")
    if booking.status in {Booking.Status.CANCELLED, Booking.Status.COMPLETED, Booking.Status.REFUNDED}:
        raise ValidationError("Payment cannot be requested for this booking state.")
    if payment.payment_status in {Payment.PaymentStatus.AWAITING_VERIFICATION, Payment.PaymentStatus.SUCCESS}:
        return payment

    payment, changed = transition_payment_status(
        payment,
        Payment.PaymentStatus.AWAITING_VERIFICATION,
        actor=actor,
        reason="Demo payment verification requested",
        provider="Secure Demo",
    )
    if not changed:
        return payment
    if not payment.transaction_id:
        payment.transaction_id = f"DEMO-REQUEST-{uuid4().hex[:10].upper()}"
        payment.save(update_fields=["transaction_id", "updated_at"])
    audit_event("payment_verification_requested", actor=actor, booking_id=booking.id, payment_id=payment.id)

    create_notification(
        booking.lawyer.user,
        "Payment awaiting verification",
        f"{booking.client.username} requested demo payment verification for booking #{booking.id}.",
        reverse("lawyer_dashboard"),
        notification_type=Notification.NotificationType.PAYMENT,
        priority=Notification.Priority.HIGH,
    )
    for admin_user in booking.client.__class__.objects.filter(is_staff=True, is_active=True):
        create_notification(
            admin_user,
            "Payment review needed",
            f"Booking #{booking.id} is awaiting demo payment verification.",
            reverse("admin_payments"),
            notification_type=Notification.NotificationType.PAYMENT,
            priority=Notification.Priority.HIGH,
        )
    return payment


def request_refund(payment, *, actor=None, reason="", idempotency_key="", amount=None):
    if idempotency_key:
        existing = RefundRequest.objects.filter(idempotency_key=idempotency_key).select_related("payment").first()
        if existing:
            if existing.payment_id != payment.id:
                raise ValidationError("This refund idempotency key has already been used.")
            return existing, False

    with transaction.atomic():
        payment, booking = _locked_payment_and_booking(payment)
        refund_amount = amount if amount is not None else payment.amount
        if Decimal(refund_amount) <= Decimal("0.00"):
            raise ValidationError("Refund amount must be greater than zero.")
        if Decimal(refund_amount) != payment.amount:
            raise ValidationError("Only full demo refunds are supported.")
        if payment.payment_status != Payment.PaymentStatus.SUCCESS:
            raise ValidationError("Only successful payments can be refunded.")

        existing = (
            RefundRequest.objects.select_for_update()
            .filter(
                payment=payment,
                status__in=[
                    RefundRequest.RefundStatus.REQUESTED,
                    RefundRequest.RefundStatus.PROCESSING,
                    RefundRequest.RefundStatus.PROCESSED,
                ],
            )
            .first()
        )
        if existing:
            return existing, False

        refund_request = RefundRequest.objects.create(
            payment=payment,
            amount=refund_amount,
            currency=payment.currency,
            reason=reason,
            requested_by=actor,
            provider=payment.provider or "Secure Demo",
            idempotency_key=idempotency_key,
        )
        _record_refund_history(refund_request, "", actor=actor, reason=reason)
        audit_event("refund_requested", actor=actor, booking_id=booking.id, payment_id=payment.id, refund_request_id=refund_request.id)
        return refund_request, True


def process_refund(refund_request, *, actor=None, provider_event_id=""):
    with transaction.atomic():
        refund_request = (
            RefundRequest.objects.select_for_update()
            .select_related("payment", "payment__booking", "payment__booking__client", "payment__booking__lawyer", "payment__booking__lawyer__user")
            .get(id=refund_request.id)
        )
        payment = refund_request.payment
        if refund_request.status == RefundRequest.RefundStatus.PROCESSED:
            return refund_request, False
        if refund_request.status == RefundRequest.RefundStatus.CANCELLED:
            raise ValidationError("Cancelled refunds cannot be processed.")
        if payment.payment_status not in {Payment.PaymentStatus.SUCCESS, Payment.PaymentStatus.REFUNDED}:
            raise ValidationError("Refunds can only be processed for successful payments.")

        if refund_request.status != RefundRequest.RefundStatus.PROCESSING:
            previous_status = refund_request.status
            refund_request.status = RefundRequest.RefundStatus.PROCESSING
            refund_request.failure_reason = ""
            refund_request.save(update_fields=["status", "failure_reason", "updated_at"])
            _record_refund_history(refund_request, previous_status, actor=actor, reason="Refund processing started")

        provider_client = get_payment_provider(refund_request.provider)
        result = provider_client.refund_payment(refund_request, idempotency_key=refund_request.idempotency_key)

        previous_status = refund_request.status
        refund_request.status = RefundRequest.RefundStatus.PROCESSED
        refund_request.provider_refund_id = result.refund_id
        refund_request.processed_by = actor
        refund_request.processed_at = timezone.now()
        refund_request.failure_reason = ""
        refund_request.save(
            update_fields=[
                "status",
                "provider_refund_id",
                "processed_by",
                "processed_at",
                "failure_reason",
                "updated_at",
            ]
        )
        _record_refund_history(
            refund_request,
            previous_status,
            actor=actor,
            reason="Refund processed",
            provider=refund_request.provider,
            provider_event_id=provider_event_id,
        )

        if payment.payment_status != Payment.PaymentStatus.REFUNDED:
            payment, _changed = transition_payment_status(
                payment,
                Payment.PaymentStatus.REFUNDED,
                actor=actor,
                reason="Refund processed",
                provider=refund_request.provider,
                provider_event_id=provider_event_id,
                ledger_refund_request=refund_request,
            )
        else:
            _record_ledger_entry(
                payment,
                PaymentLedgerEntry.EntryType.PAYMENT_REFUNDED,
                refund_request.amount,
                refund_request=refund_request,
                provider=refund_request.provider,
                provider_event_id=provider_event_id,
                idempotency_key=refund_request.idempotency_key,
                description="Refund processed",
            )

        audit_event(
            "refund_processed",
            actor=actor,
            booking_id=payment.booking.id,
            payment_id=payment.id,
            refund_request_id=refund_request.id,
        )
        create_notification(
            payment.booking.client,
            "Payment refunded",
            f"Refund for booking #{payment.booking.id} has been processed.",
            reverse("client_bookings"),
            notification_type=Notification.NotificationType.PAYMENT,
        )
        return refund_request, True


def _refund_for_provider_refund_id(provider, provider_refund_id):
    if not provider_refund_id:
        raise ValidationError("Provider refund id is required.")
    try:
        return RefundRequest.objects.select_related("payment", "payment__booking", "payment__booking__client").get(
            provider=provider,
            provider_refund_id=provider_refund_id,
        )
    except RefundRequest.DoesNotExist as exc:
        raise ValidationError("Provider refund event could not be matched to a refund request.") from exc


def process_provider_refund_event(provider, provider_refund_id, *, provider_event_id=""):
    with transaction.atomic():
        refund_request = RefundRequest.objects.select_for_update().get(id=_refund_for_provider_refund_id(provider, provider_refund_id).id)
        if refund_request.status == RefundRequest.RefundStatus.PROCESSED:
            return refund_request, False
        previous_status = refund_request.status
        refund_request.status = RefundRequest.RefundStatus.PROCESSED
        refund_request.processed_at = timezone.now()
        refund_request.failure_reason = ""
        refund_request.save(update_fields=["status", "processed_at", "failure_reason", "updated_at"])
        _record_refund_history(refund_request, previous_status, reason="Provider refund processed", provider=provider, provider_event_id=provider_event_id)

        if refund_request.payment.payment_status != Payment.PaymentStatus.REFUNDED:
            transition_payment_status(
                refund_request.payment,
                Payment.PaymentStatus.REFUNDED,
                reason="Provider refund processed",
                provider=provider,
                provider_event_id=provider_event_id,
                ledger_refund_request=refund_request,
            )
        return refund_request, True


def fail_refund_from_provider_event(provider, provider_refund_id, *, provider_event_id="", reason=""):
    with transaction.atomic():
        refund_request = RefundRequest.objects.select_for_update().get(id=_refund_for_provider_refund_id(provider, provider_refund_id).id)
        if refund_request.status in REFUND_FINAL_STATUSES:
            return refund_request, False
        previous_status = refund_request.status
        refund_request.status = RefundRequest.RefundStatus.FAILED
        refund_request.failure_reason = reason or "Provider refund failed"
        refund_request.save(update_fields=["status", "failure_reason", "updated_at"])
        _record_refund_history(refund_request, previous_status, reason=refund_request.failure_reason, provider=provider, provider_event_id=provider_event_id)
        return refund_request, True


def reconcile_payment_ledger(payment):
    payment = Payment.objects.prefetch_related("ledger_entries").get(id=payment.id)
    captured = sum(
        (entry.amount for entry in payment.ledger_entries.all() if entry.entry_type == PaymentLedgerEntry.EntryType.PAYMENT_CAPTURED),
        Decimal("0.00"),
    )
    refunded = sum(
        (entry.amount for entry in payment.ledger_entries.all() if entry.entry_type == PaymentLedgerEntry.EntryType.PAYMENT_REFUNDED),
        Decimal("0.00"),
    )
    expected_refunded = payment.amount if payment.payment_status == Payment.PaymentStatus.REFUNDED else Decimal("0.00")
    return {
        "payment_id": payment.id,
        "captured": captured,
        "refunded": refunded,
        "expected_captured": payment.amount if payment.payment_status in {Payment.PaymentStatus.SUCCESS, Payment.PaymentStatus.REFUNDED} else Decimal("0.00"),
        "expected_refunded": expected_refunded,
        "is_balanced": captured in {Decimal("0.00"), payment.amount} and refunded == expected_refunded,
    }


def mark_payment_success(payment, *, actor=None):
    payment, changed = transition_payment_status(payment, Payment.PaymentStatus.SUCCESS, actor=actor, reason="Payment marked successful")
    payment.refresh_from_db()
    booking = Booking.objects.select_related("client", "lawyer", "lawyer__user", "payment").get(id=payment.booking_id)
    booking, booking_confirmed = confirm_booking_for_successful_payment(
        payment,
        booking,
        actor=actor,
        reason="Payment marked successful",
    )
    if booking_confirmed:
        booking.refresh_from_db(fields=["status", "updated_at"])
    chat = _ensure_chat_after_successful_payment(payment, booking)
    if not changed and not booking_confirmed:
        return payment
    audit_event("payment_marked_success", actor=actor, booking_id=booking.id, payment_id=payment.id)
    chat_path = reverse("start_chat_for_booking", args=[booking.id])
    create_notification(
        booking.lawyer.user,
        "Payment confirmed",
        f"Booking #{booking.id} is now confirmed.",
        chat_path,
        notification_type=Notification.NotificationType.PAYMENT,
        priority=Notification.Priority.HIGH,
    )
    create_notification(
        booking.client,
        "Payment recorded",
        f"Your payment for booking #{booking.id} has been recorded. Consultation chat is ready.",
        chat_path,
        notification_type=Notification.NotificationType.PAYMENT,
        priority=Notification.Priority.HIGH,
    )
    if chat:
        payment_logger.info(
            {
                "event": "consultation_chat_ready",
                "booking_id": booking.id,
                "chat_id": chat.id,
                "payment_id": payment.id,
            }
        )
    return payment


def mark_payment_failed(payment):
    payment, changed = transition_payment_status(payment, Payment.PaymentStatus.FAILED, reason="Payment marked failed")
    if not changed:
        return payment
    audit_event("payment_marked_failed", booking_id=payment.booking.id, payment_id=payment.id)
    create_notification(
        payment.booking.client,
        "Payment update",
        f"Payment for booking #{payment.booking.id} is marked as failed.",
        reverse("payment_page", args=[payment.booking.id]),
        notification_type=Notification.NotificationType.PAYMENT,
        priority=Notification.Priority.HIGH,
    )
    return payment


def mark_payment_pending(payment):
    payment, changed = transition_payment_status(payment, Payment.PaymentStatus.PENDING, reason="Payment marked pending")
    if changed:
        audit_event("payment_marked_pending", booking_id=payment.booking.id, payment_id=payment.id)
    return payment


def mark_payment_refunded(payment, *, actor=None):
    payment, changed = transition_payment_status(payment, Payment.PaymentStatus.REFUNDED, actor=actor, reason="Payment marked refunded")
    if changed:
        audit_event("payment_marked_refunded", actor=actor, booking_id=payment.booking.id, payment_id=payment.id)
    return payment
