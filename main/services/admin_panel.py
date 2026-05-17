from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.utils import timezone

from ..models import Booking, Lawyer, OperationalEvent, Payment, ProviderEvent, RefundRequest, UserProfile
from ..utils import create_notification, ensure_profile_role, mark_user_offline
from .bookings import cancel_booking
from .payments import mark_payment_failed, mark_payment_pending, mark_payment_refunded, mark_payment_success


def admin_lawyers_queryset():
    return Lawyer.objects.select_related("user", "user__profile", "category").order_by("verification_status", "name")


def admin_clients_queryset():
    return (
        User.objects.filter(profile__role=UserProfile.Role.CLIENT)
        .select_related("profile")
        .annotate(booking_count=Count("bookings", distinct=True))
        .order_by("username")
    )


def admin_bookings_queryset():
    return Booking.objects.select_related("client", "lawyer", "payment").order_by("-created_at")


def admin_payments_queryset():
    return (
        Payment.objects.select_related("booking", "booking__client", "booking__lawyer")
        .prefetch_related("refund_requests", "provider_events", "status_history")
        .order_by("-created_at")
    )


def admin_refunds_queryset():
    return RefundRequest.objects.select_related("payment", "payment__booking", "payment__booking__client", "payment__booking__lawyer").order_by("-created_at")


def admin_operational_events_queryset():
    return OperationalEvent.objects.select_related("actor").order_by("-created_at")


def admin_provider_events_queryset():
    return (
        ProviderEvent.objects.select_related(
            "payment",
            "payment__booking",
            "payment__booking__client",
            "payment__booking__lawyer",
            "refund_request",
        )
        .order_by("-created_at")
    )


def paginate_queryset(queryset, page_number, per_page=20):
    return Paginator(queryset, per_page).get_page(page_number)


def filter_admin_lawyers_queryset(queryset, params):
    query = (params.get("q") or "").strip()
    verification = (params.get("verification") or "").strip()
    active = (params.get("active") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(user__username__icontains=query)
            | Q(category__name__icontains=query)
        )
    if verification:
        queryset = queryset.filter(verification_status=verification)
    if active == "active":
        queryset = queryset.filter(user__is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(user__is_active=False)
    return queryset


def filter_admin_clients_queryset(queryset, params):
    query = (params.get("q") or "").strip()
    active = (params.get("active") or "").strip()
    if query:
        queryset = queryset.filter(Q(username__icontains=query) | Q(email__icontains=query))
    if active == "active":
        queryset = queryset.filter(is_active=True)
    elif active == "inactive":
        queryset = queryset.filter(is_active=False)
    return queryset


def filter_admin_bookings_queryset(queryset, params):
    query = (params.get("q") or "").strip()
    status = (params.get("status") or "").strip()
    payment_status = (params.get("payment_status") or "").strip()
    if query:
        search_filter = Q(client__username__icontains=query) | Q(lawyer__name__icontains=query)
        if query.isdigit():
            search_filter |= Q(id=int(query))
        queryset = queryset.filter(search_filter)
    if status:
        queryset = queryset.filter(status=status)
    if payment_status:
        queryset = queryset.filter(payment__payment_status=payment_status)
    return queryset


def filter_admin_payments_queryset(queryset, params):
    query = (params.get("q") or "").strip()
    payment_status = (params.get("payment_status") or "").strip()
    provider = (params.get("provider") or "").strip()
    if query:
        search_filter = (
            Q(booking__client__username__icontains=query)
            | Q(booking__lawyer__name__icontains=query)
            | Q(transaction_id__icontains=query)
            | Q(provider__icontains=query)
            | Q(provider_order_id__icontains=query)
            | Q(provider_payment_id__icontains=query)
            | Q(refund_requests__provider_refund_id__icontains=query)
        )
        if query.isdigit():
            search_filter |= Q(booking_id=int(query))
        queryset = queryset.filter(search_filter).distinct()
    if payment_status:
        queryset = queryset.filter(payment_status=payment_status)
    if provider:
        queryset = queryset.filter(provider=provider)
    return queryset


def filter_operational_events_queryset(queryset, params):
    query = (params.get("q") or "").strip()
    source = (params.get("source") or "").strip()
    level = (params.get("level") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(event__icontains=query)
            | Q(summary__icontains=query)
            | Q(actor__username__icontains=query)
            | Q(path__icontains=query)
        )
    if source:
        queryset = queryset.filter(source=source)
    if level:
        queryset = queryset.filter(level=level)
    return queryset


def filter_provider_events_queryset(queryset, params):
    query = (params.get("q") or "").strip()
    status = (params.get("status") or "").strip()
    provider = (params.get("provider") or "").strip()
    if query:
        queryset = queryset.filter(
            Q(event_id__icontains=query)
            | Q(event_type__icontains=query)
            | Q(error_message__icontains=query)
            | Q(payment__booking__client__username__icontains=query)
            | Q(payment__booking__lawyer__name__icontains=query)
            | Q(refund_request__provider_refund_id__icontains=query)
        )
    if status:
        queryset = queryset.filter(processing_status=status)
    if provider:
        queryset = queryset.filter(provider=provider)
    return queryset


def payment_timeline(payment):
    payment = (
        Payment.objects.select_related("booking", "booking__client", "booking__lawyer")
        .prefetch_related("status_history__actor", "provider_events", "refund_requests__status_history__actor", "ledger_entries")
        .get(id=payment.id)
    )
    items = []
    for history in payment.status_history.all():
        items.append(
            {
                "timestamp": history.created_at,
                "kind": "Payment status",
                "status": history.to_status,
                "summary": f"{history.from_status or 'created'} -> {history.to_status}",
                "detail": history.reason,
                "actor": history.actor,
            }
        )
    for provider_event in payment.provider_events.all():
        items.append(
            {
                "timestamp": provider_event.created_at,
                "kind": "Provider event",
                "status": provider_event.processing_status,
                "summary": f"{provider_event.provider}:{provider_event.event_id}",
                "detail": provider_event.error_message or provider_event.event_type,
                "actor": None,
            }
        )
    for refund in payment.refund_requests.all():
        items.append(
            {
                "timestamp": refund.created_at,
                "kind": "Refund",
                "status": refund.status,
                "summary": f"Refund #{refund.id} {refund.get_status_display()}",
                "detail": refund.reason or refund.failure_reason,
                "actor": refund.requested_by,
            }
        )
        for history in refund.status_history.all():
            items.append(
                {
                    "timestamp": history.created_at,
                    "kind": "Refund status",
                    "status": history.to_status,
                    "summary": f"{history.from_status or 'created'} -> {history.to_status}",
                    "detail": history.reason,
                    "actor": history.actor,
                }
            )
    for ledger in payment.ledger_entries.all():
        items.append(
            {
                "timestamp": ledger.created_at,
                "kind": "Ledger",
                "status": ledger.entry_type,
                "summary": f"{ledger.get_entry_type_display()} {ledger.amount} {ledger.currency}",
                "detail": ledger.description,
                "actor": None,
            }
        )
    return payment, sorted(items, key=lambda item: item["timestamp"], reverse=True)


def admin_dashboard_stats():
    payment_totals = Payment.objects.aggregate(
        pending=Count("id", filter=Q(payment_status=Payment.PaymentStatus.PENDING)),
        awaiting=Count("id", filter=Q(payment_status=Payment.PaymentStatus.AWAITING_VERIFICATION)),
        success=Count("id", filter=Q(payment_status=Payment.PaymentStatus.SUCCESS)),
        failed=Count("id", filter=Q(payment_status=Payment.PaymentStatus.FAILED)),
        refunded=Count("id", filter=Q(payment_status=Payment.PaymentStatus.REFUNDED)),
        revenue=Sum("amount", filter=Q(payment_status=Payment.PaymentStatus.SUCCESS)),
    )
    booking_totals = Booking.objects.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status=Booking.Status.PENDING)),
        confirmed=Count("id", filter=Q(status=Booking.Status.CONFIRMED)),
        completed=Count("id", filter=Q(status=Booking.Status.COMPLETED)),
        cancelled=Count("id", filter=Q(status=Booking.Status.CANCELLED)),
    )
    return {
        "total_users": User.objects.count(),
        "total_clients": User.objects.filter(profile__role=UserProfile.Role.CLIENT).count(),
        "total_lawyers": User.objects.filter(profile__role=UserProfile.Role.LAWYER).count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "verified_lawyers": Lawyer.objects.filter(is_verified=True).count(),
        "total_bookings": booking_totals["total"],
        "pending_bookings": booking_totals["pending"],
        "confirmed_bookings": booking_totals["confirmed"],
        "completed_bookings": booking_totals["completed"],
        "cancelled_bookings": booking_totals["cancelled"],
        "pending_lawyer_verifications": Lawyer.objects.filter(
            verification_status__in=[Lawyer.VerificationStatus.PENDING, Lawyer.VerificationStatus.UNDER_REVIEW]
        ).count(),
        "pending_payments": payment_totals["pending"],
        "awaiting_payments": payment_totals["awaiting"],
        "successful_payments": payment_totals["success"],
        "failed_payments": payment_totals["failed"],
        "refunded_payments": payment_totals["refunded"],
        "total_revenue": payment_totals["revenue"] or Decimal("0.00"),
        "open_refunds": RefundRequest.objects.filter(status__in=[RefundRequest.RefundStatus.REQUESTED, RefundRequest.RefundStatus.PROCESSING]).count(),
        "failed_provider_events": ProviderEvent.objects.filter(processing_status=ProviderEvent.ProcessingStatus.FAILED).count(),
        "failed_tasks": OperationalEvent.objects.filter(source=OperationalEvent.Source.TASK, level=OperationalEvent.Level.ERROR).count(),
        "security_warnings": OperationalEvent.objects.filter(source=OperationalEvent.Source.SECURITY).count(),
        "recent_operations": OperationalEvent.objects.count(),
    }


def set_lawyer_verification(lawyer, *, is_verified):
    lawyer.is_verified = is_verified
    if is_verified:
        lawyer.verification_status = Lawyer.VerificationStatus.APPROVED
        lawyer.verified_at = timezone.now()
        lawyer.verification_notes = ""
    else:
        lawyer.verification_status = Lawyer.VerificationStatus.REJECTED
        lawyer.verified_at = None
        lawyer.is_online = False
        if lawyer.user_id:
            mark_user_offline(lawyer.user)
    lawyer.save(update_fields=["is_verified", "verification_status", "verified_at", "verification_notes", "is_online", "updated_at"])
    if lawyer.user_id:
        create_notification(
            lawyer.user,
            "Lawyer verification updated",
            f"Your lawyer account is now {'verified' if is_verified else 'unverified'}.",
            "/lawyer/dashboard/",
        )
    return lawyer


def set_user_active_state(user, *, is_active):
    user.is_active = is_active
    user.save(update_fields=["is_active"])
    profile = ensure_profile_role(user)
    if not is_active:
        mark_user_offline(user)
        if hasattr(user, "lawyer_profile"):
            user.lawyer_profile.is_online = False
            user.lawyer_profile.save(update_fields=["is_online", "updated_at"])
    return user


def admin_force_cancel_booking(booking, *, actor, reason="Cancelled by admin"):
    if booking.status == Booking.Status.CANCELLED:
        raise ValidationError("Booking is already cancelled.")
    if booking.status == Booking.Status.COMPLETED:
        raise ValidationError("Completed bookings cannot be force-cancelled.")
    return cancel_booking(booking, actor=actor, reason=reason)


def admin_update_payment_status(payment, *, next_status, actor=None):
    booking = payment.booking

    if booking.status == Booking.Status.COMPLETED and next_status not in {
        Payment.PaymentStatus.SUCCESS,
        Payment.PaymentStatus.REFUNDED,
    }:
        raise ValidationError("Completed bookings must keep a successful payment record.")

    if next_status == payment.payment_status:
        if next_status == Payment.PaymentStatus.SUCCESS:
            return mark_payment_success(payment, actor=actor)
        return payment

    if next_status == Payment.PaymentStatus.SUCCESS:
        return mark_payment_success(payment, actor=actor)

    if next_status == Payment.PaymentStatus.FAILED:
        return mark_payment_failed(payment)

    if next_status == Payment.PaymentStatus.REFUNDED:
        return mark_payment_refunded(payment, actor=actor)

    return mark_payment_pending(payment)
