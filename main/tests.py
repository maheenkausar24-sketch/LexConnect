import json
from datetime import datetime, time, timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.db import transaction
from django.core import mail
from django.core.cache import cache
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .consumers import ChatConsumer
from .models import Booking, Chat, LawCategory, Lawyer, LawyerAvailability, Notification, Payment, PaymentLedgerEntry, PaymentStatusHistory, ProviderEvent, RefundRequest, RefundStatusHistory, Review, UserProfile
from .management.commands.prepare_demo import DEMO_CLIENT_USERNAME, DEMO_LAWYER_COUNT, DEMO_LAWYER_PASSWORD
from .services import bookings as booking_services
from .services import payments as payment_services
from .services.bookings import cancel_booking, reschedule_booking, transition_booking_status, upcoming_available_slots, validate_booking_slot
from .services.payment_providers import sign_demo_payload
from .tokens import email_verification_token
from .utils import create_notification
from .validators import validate_chat_file


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class LexConnectFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = LawCategory.objects.create(name="Family Law")

    def create_client(self, username="client_user", email="client@example.com", password="ClientPass123"):
        user = User.objects.create_user(username=username, email=email, password=password)
        profile = user.profile
        profile.role = UserProfile.Role.CLIENT
        profile.save(update_fields=["role"])
        return user

    def create_admin(self, username="admin_user", email="admin@example.com", password="AdminPass123"):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        profile = user.profile
        profile.role = UserProfile.Role.CLIENT
        profile.save(update_fields=["role"])
        return user

    def create_lawyer(self, username="lawyer_user", email="lawyer@example.com", password="LawyerPass123"):
        user = User.objects.create_user(username=username, email=email, password=password, is_active=True)
        profile = user.profile
        profile.role = UserProfile.Role.LAWYER
        profile.save(update_fields=["role"])
        lawyer = Lawyer.objects.create(
            user=user,
            category=self.category,
            name="Lawyer Active",
            email=email,
            phone="9999999999",
            specialization=self.category.name,
            experience=5,
            location="Bangalore",
            fee="500.00",
            is_verified=True,
            verification_status=Lawyer.VerificationStatus.APPROVED,
            is_online=True,
        )
        LawyerAvailability.objects.create(
            lawyer=lawyer,
            weekday=(timezone.localdate() + timedelta(days=1)).weekday(),
            start_time=datetime.strptime("10:00", "%H:%M").time(),
            end_time=datetime.strptime("11:00", "%H:%M").time(),
        )
        return user, lawyer

    def create_placeholder_lawyer(self, username="placeholder_lawyer", email="placeholder@example.com"):
        user = User.objects.create(username=username, email=email, is_active=False)
        user.set_unusable_password()
        user.save()
        profile = user.profile
        profile.role = UserProfile.Role.LAWYER
        profile.save(update_fields=["role"])
        lawyer = Lawyer.objects.create(
            user=user,
            category=self.category,
            name="Lawyer Placeholder",
            email=email,
            phone="8888888888",
            specialization=self.category.name,
            experience=8,
            location="Delhi",
            fee="650.00",
            is_verified=False,
        )
        return user, lawyer

    def booking_payload(self):
        appointment_date = timezone.localdate() + timedelta(days=1)
        return {
            "issue": "Need help with a legal consultation about a custody matter and related documents.",
            "appointment_date": appointment_date.isoformat(),
            "appointment_time": "10:00",
        }

    def test_lawyer_register_claims_placeholder_account(self):
        placeholder_user, lawyer = self.create_placeholder_lawyer()

        response = self.client.post(
            reverse("lawyer_register"),
            {
                "username": "claimed_lawyer",
                "password": "ClaimPass123",
                "name": "Lawyer Placeholder",
                "email": lawyer.email,
                "phone": "7777777777",
                "location": "Mumbai",
                "experience": "10",
                "fee": "900",
                "bio": "Claimed profile",
                "category": str(self.category.id),
            },
        )

        self.assertRedirects(response, reverse("lawyer_login"))
        placeholder_user.refresh_from_db()
        lawyer.refresh_from_db()
        self.assertTrue(placeholder_user.is_active)
        self.assertEqual(placeholder_user.username, "claimed_lawyer")
        self.assertTrue(placeholder_user.check_password("ClaimPass123"))
        self.assertEqual(lawyer.user_id, placeholder_user.id)
        self.assertEqual(lawyer.location, "Mumbai")
        self.assertFalse(lawyer.is_verified)
        self.assertEqual(lawyer.verification_status, Lawyer.VerificationStatus.UNDER_REVIEW)

    def test_booking_creation_creates_pending_payment(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        self.client.force_login(client_user)

        response = self.client.post(reverse("consult_lawyer", args=[lawyer.id]), self.booking_payload())

        booking = Booking.objects.get(client=client_user, lawyer=lawyer)
        self.assertRedirects(response, reverse("payment_page", args=[booking.id]))
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.payment.payment_status, Payment.PaymentStatus.PENDING)

    def test_booking_creation_rejects_overlapping_interval(self):
        client_user = self.create_client()
        second_client = self.create_client(username="second_client", email="second@example.com")
        _, lawyer = self.create_lawyer()
        appointment_date = timezone.localdate() + timedelta(days=1)
        Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need a longer consultation about custody paperwork and hearing preparation.",
            appointment_date=appointment_date,
            appointment_time=time(10, 0),
            duration_minutes=60,
            status=Booking.Status.PENDING,
            price_snapshot=lawyer.fee,
        )

        with self.assertRaisesMessage(ValidationError, "overlaps an existing booking"):
            validate_booking_slot(lawyer, appointment_date, time(10, 30))

        with self.assertRaisesMessage(ValidationError, "overlaps an existing booking"):
            booking_services.create_booking_with_payment(
                second_client,
                lawyer,
                {
                    "issue": "Need help with a legal consultation about a custody matter and documents.",
                    "appointment_date": appointment_date,
                    "appointment_time": time(10, 30),
                },
            )

        self.assertEqual(Booking.objects.filter(lawyer=lawyer).count(), 1)
        self.assertEqual(Payment.objects.count(), 0)

    def test_adjacent_booking_interval_is_allowed(self):
        client_user = self.create_client()
        second_client = self.create_client(username="adjacent_client", email="adjacent@example.com")
        _, lawyer = self.create_lawyer()
        appointment_date = timezone.localdate() + timedelta(days=1)
        Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need a short consultation about custody paperwork and hearing preparation.",
            appointment_date=appointment_date,
            appointment_time=time(10, 0),
            duration_minutes=30,
            status=Booking.Status.PENDING,
            price_snapshot=lawyer.fee,
        )

        booking = booking_services.create_booking_with_payment(
            second_client,
            lawyer,
            {
                "issue": "Need help with a legal consultation about a custody matter and documents.",
                "appointment_date": appointment_date,
                "appointment_time": time(10, 30),
            },
        )

        self.assertEqual(booking.appointment_time, time(10, 30))
        self.assertEqual(Booking.objects.filter(lawyer=lawyer).count(), 2)

    def test_failed_overlapping_booking_creation_is_atomic(self):
        client_user = self.create_client()
        second_client = self.create_client(username="atomic_client", email="atomic@example.com")
        _, lawyer = self.create_lawyer()
        appointment_date = timezone.localdate() + timedelta(days=1)
        Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need a longer consultation about custody paperwork and hearing preparation.",
            appointment_date=appointment_date,
            appointment_time=time(10, 0),
            duration_minutes=60,
            status=Booking.Status.PENDING,
            price_snapshot=lawyer.fee,
        )

        before_booking_ids = list(Booking.objects.values_list("id", flat=True))
        with self.assertRaises(ValidationError):
            booking_services.create_booking_with_payment(
                second_client,
                lawyer,
                {
                    "issue": "Need help with a legal consultation about a custody matter and documents.",
                    "appointment_date": appointment_date,
                    "appointment_time": time(10, 30),
                },
            )

        self.assertEqual(list(Booking.objects.values_list("id", flat=True)), before_booking_ids)
        self.assertFalse(Payment.objects.exists())

    def test_booking_creation_locks_lawyer_inside_atomic_transaction(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        appointment_date = timezone.localdate() + timedelta(days=1)
        lock_calls_inside_transaction = []
        original_lock = booking_services.lock_lawyer_for_booking

        def tracking_lock(target_lawyer):
            lock_calls_inside_transaction.append(transaction.get_connection().in_atomic_block)
            return original_lock(target_lawyer)

        with patch.object(booking_services, "lock_lawyer_for_booking", side_effect=tracking_lock):
            booking_services.create_booking_with_payment(
                client_user,
                lawyer,
                {
                    "issue": "Need help with a legal consultation about a custody matter and documents.",
                    "appointment_date": appointment_date,
                    "appointment_time": time(10, 0),
                },
            )

        self.assertEqual(lock_calls_inside_transaction, [True])

    def test_cancelled_booking_releases_overlapping_slot(self):
        client_user = self.create_client()
        second_client = self.create_client(username="released_client", email="released@example.com")
        _, lawyer = self.create_lawyer()
        appointment_date = timezone.localdate() + timedelta(days=1)
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need a longer consultation about custody paperwork and hearing preparation.",
            appointment_date=appointment_date,
            appointment_time=time(10, 0),
            duration_minutes=60,
            status=Booking.Status.PENDING,
            price_snapshot=lawyer.fee,
        )

        cancelled = cancel_booking(booking, actor=client_user, reason="Client unavailable")
        self.assertEqual(cancelled.status, Booking.Status.CANCELLED)

        new_booking = booking_services.create_booking_with_payment(
            second_client,
            lawyer,
            {
                "issue": "Need help with a legal consultation about a custody matter and documents.",
                "appointment_date": appointment_date,
                "appointment_time": time(10, 30),
            },
        )

        self.assertEqual(new_booking.appointment_time, time(10, 30))

    def test_reschedule_rejects_overlapping_interval_and_preserves_original_slot(self):
        client_user = self.create_client()
        second_client = self.create_client(username="reschedule_client", email="reschedule@example.com")
        _, lawyer = self.create_lawyer()
        first_date = timezone.localdate() + timedelta(days=1)
        second_date = timezone.localdate() + timedelta(days=2)
        LawyerAvailability.objects.create(
            lawyer=lawyer,
            weekday=second_date.weekday(),
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need a longer consultation about custody paperwork and hearing preparation.",
            appointment_date=first_date,
            appointment_time=time(10, 0),
            duration_minutes=60,
            status=Booking.Status.PENDING,
            price_snapshot=lawyer.fee,
        )
        booking_to_reschedule = Booking.objects.create(
            client=second_client,
            lawyer=lawyer,
            issue="Need help with a separate legal consultation and case documents.",
            appointment_date=second_date,
            appointment_time=time(10, 0),
            duration_minutes=30,
            status=Booking.Status.PENDING,
            price_snapshot=lawyer.fee,
        )

        with self.assertRaisesMessage(ValidationError, "overlaps an existing booking"):
            reschedule_booking(
                booking_to_reschedule,
                {"appointment_date": first_date, "appointment_time": time(10, 30)},
                actor=second_client,
            )

        booking_to_reschedule.refresh_from_db()
        self.assertEqual(booking_to_reschedule.appointment_date, second_date)
        self.assertEqual(booking_to_reschedule.appointment_time, time(10, 0))

    def test_availability_generates_deterministic_slots(self):
        _, lawyer = self.create_lawyer()
        appointment_date = timezone.localdate() + timedelta(days=1)

        slots = upcoming_available_slots(lawyer, days=2, limit=4)
        slot_times = [slot["start_time"] for slot in slots if slot["date"] == appointment_date]

        self.assertIn(time(10, 0), slot_times)
        self.assertIn(time(10, 30), slot_times)
        with self.assertRaises(ValidationError):
            validate_booking_slot(lawyer, appointment_date, time(10, 15))

    def test_payment_verification_requires_admin_approval(self):
        client_user = self.create_client()
        admin_user = self.create_admin()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=datetime.strptime("10:00", "%H:%M").time(),
        )
        Payment.objects.create(booking=booking, amount=lawyer.fee)
        self.client.force_login(client_user)

        response = self.client.post(
            reverse("payment_page", args=[booking.id]),
            {"payment_status": Payment.PaymentStatus.AWAITING_VERIFICATION},
        )

        booking.refresh_from_db()
        booking.payment.refresh_from_db()
        self.assertRedirects(response, reverse("payment_page", args=[booking.id]))
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.payment.payment_status, Payment.PaymentStatus.AWAITING_VERIFICATION)
        self.assertFalse(Chat.objects.filter(booking=booking).exists())

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse("admin_update_payment", args=[booking.payment.id]),
            {"payment_status": Payment.PaymentStatus.SUCCESS},
        )

        booking.refresh_from_db()
        booking.payment.refresh_from_db()
        self.assertRedirects(response, reverse("admin_payments"))
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(booking.payment.payment_status, Payment.PaymentStatus.SUCCESS)

    def test_payment_success_retry_is_idempotent(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.PENDING,
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)

        payment, changed = payment_services.transition_payment_status(
            payment,
            Payment.PaymentStatus.SUCCESS,
            actor=client_user,
            idempotency_key="idem-success-1",
            provider="Secure Demo",
            provider_event_id="evt-success-1",
        )
        retried_payment, retried = payment_services.transition_payment_status(
            payment,
            Payment.PaymentStatus.SUCCESS,
            actor=client_user,
            idempotency_key="idem-success-1",
            provider="Secure Demo",
            provider_event_id="evt-success-1",
        )

        booking.refresh_from_db()
        self.assertTrue(changed)
        self.assertFalse(retried)
        self.assertEqual(retried_payment.payment_status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(PaymentStatusHistory.objects.filter(payment=payment).count(), 1)

    def test_duplicate_payment_idempotency_key_is_rejected(self):
        client_user = self.create_client()
        second_client = self.create_client(username="pay_client_two", email="pay2@example.com")
        _, lawyer = self.create_lawyer()
        booking_one = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
        )
        booking_two = Booking.objects.create(
            client=second_client,
            lawyer=lawyer,
            issue="Need help with a second consultation and related documents.",
            appointment_date=timezone.localdate() + timedelta(days=2),
            appointment_time=time(10, 0),
        )
        payment_one = Payment.objects.create(booking=booking_one, amount=lawyer.fee)
        payment_two = Payment.objects.create(booking=booking_two, amount=lawyer.fee)

        payment_services.transition_payment_status(
            payment_one,
            Payment.PaymentStatus.SUCCESS,
            idempotency_key="duplicate-idem-key",
            provider="Secure Demo",
        )

        with self.assertRaisesMessage(ValidationError, "idempotency key has already been used"):
            payment_services.transition_payment_status(
                payment_two,
                Payment.PaymentStatus.SUCCESS,
                idempotency_key="duplicate-idem-key",
                provider="Secure Demo",
            )

    def test_invalid_payment_transitions_are_rejected(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)
        payment_services.transition_payment_status(payment, Payment.PaymentStatus.SUCCESS, provider="Secure Demo")
        payment.refresh_from_db()

        with self.assertRaisesMessage(ValidationError, "cannot move from success to failed"):
            payment_services.transition_payment_status(payment, Payment.PaymentStatus.FAILED, provider="Secure Demo")

        payment_services.transition_payment_status(payment, Payment.PaymentStatus.REFUNDED, provider="Secure Demo")
        payment.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "cannot move from refunded to success"):
            payment_services.transition_payment_status(payment, Payment.PaymentStatus.SUCCESS, provider="Secure Demo")

    def test_cancelled_booking_cannot_accept_successful_payment(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.CANCELLED,
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)

        with self.assertRaisesMessage(ValidationError, "cannot be completed"):
            payment_services.transition_payment_status(payment, Payment.PaymentStatus.SUCCESS, provider="Secure Demo")

        payment.refresh_from_db()
        self.assertEqual(payment.payment_status, Payment.PaymentStatus.PENDING)
        self.assertFalse(PaymentStatusHistory.objects.filter(payment=payment).exists())

    def test_refunded_payment_marks_booking_refunded_and_blocks_completion_retry(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)

        payment_services.transition_payment_status(payment, Payment.PaymentStatus.SUCCESS, provider="Secure Demo")
        payment_services.transition_payment_status(payment, Payment.PaymentStatus.REFUNDED, provider="Secure Demo")
        booking.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(payment.payment_status, Payment.PaymentStatus.REFUNDED)
        self.assertEqual(booking.status, Booking.Status.REFUNDED)
        with self.assertRaisesMessage(ValidationError, "cannot move from refunded to success"):
            payment_services.transition_payment_status(payment, Payment.PaymentStatus.SUCCESS, provider="Secure Demo")

    def test_completed_booking_rejects_invalid_payment_state(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.COMPLETED,
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.SUCCESS)

        with self.assertRaisesMessage(ValidationError, "cannot move from success to failed"):
            payment_services.mark_payment_failed(payment)
        with self.assertRaisesMessage(ValidationError, "cannot move from success to pending"):
            payment_services.mark_payment_pending(payment)

    def test_provider_webhook_processes_payment_success_once(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.PENDING,
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)
        payload = {
            "event_id": "evt-webhook-success-1",
            "event_type": "payment.success",
            "payment_reference": str(payment.payment_reference),
            "provider_payment_id": "prov-pay-1",
            "idempotency_key": "webhook-idem-1",
        }

        provider_event, processed = payment_services.process_provider_webhook(
            "Secure Demo",
            payload,
            signature=sign_demo_payload(payload),
        )
        replay_event, replay_processed = payment_services.process_provider_webhook(
            "Secure Demo",
            payload,
            signature=sign_demo_payload(payload),
        )

        booking.refresh_from_db()
        payment.refresh_from_db()
        replay_event.refresh_from_db()
        self.assertTrue(processed)
        self.assertFalse(replay_processed)
        self.assertEqual(provider_event.id, replay_event.id)
        self.assertEqual(replay_event.replay_count, 1)
        self.assertEqual(replay_event.processing_status, ProviderEvent.ProcessingStatus.PROCESSED)
        self.assertEqual(payment.payment_status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(payment.provider_payment_id, "prov-pay-1")
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(PaymentStatusHistory.objects.filter(payment=payment, provider_event_id="evt-webhook-success-1").count(), 1)
        self.assertEqual(PaymentLedgerEntry.objects.filter(payment=payment, entry_type=PaymentLedgerEntry.EntryType.PAYMENT_CAPTURED).count(), 1)

    def test_provider_webhook_rejects_invalid_signature_without_recording_event(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)
        payload = {
            "event_id": "evt-webhook-bad-signature",
            "event_type": "payment.success",
            "payment_reference": str(payment.payment_reference),
        }

        with self.assertRaisesMessage(ValidationError, "could not be verified"):
            payment_services.process_provider_webhook("Secure Demo", payload, signature="bad-signature")

        payment.refresh_from_db()
        self.assertEqual(payment.payment_status, Payment.PaymentStatus.PENDING)
        self.assertFalse(ProviderEvent.objects.filter(event_id="evt-webhook-bad-signature").exists())

    def test_provider_webhook_view_returns_replay_status(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)
        payload = {
            "event_id": "evt-webhook-view-1",
            "event_type": "payment.success",
            "payment_reference": str(payment.payment_reference),
        }

        response = self.client.post(
            reverse("provider_webhook", args=["Secure Demo"]),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_LEXCONNECT_SIGNATURE=sign_demo_payload(payload),
        )
        replay_response = self.client.post(
            reverse("provider_webhook", args=["Secure Demo"]),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_LEXCONNECT_SIGNATURE=sign_demo_payload(payload),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(replay_response.status_code, 200)
        self.assertTrue(response.json()["processed"])
        self.assertFalse(replay_response.json()["processed"])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, LEXCONNECT_ASYNC_WEBHOOKS=True)
    def test_async_provider_webhook_view_uses_local_eager_fallback(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)
        payload = {
            "event_id": "evt-webhook-async-view-1",
            "event_type": "payment.success",
            "payment_reference": str(payment.payment_reference),
        }

        response = self.client.post(
            reverse("provider_webhook", args=["Secure Demo"]),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_LEXCONNECT_SIGNATURE=sign_demo_payload(payload),
        )

        payment.refresh_from_db()
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["accepted"])
        self.assertEqual(payment.payment_status, Payment.PaymentStatus.SUCCESS)
        self.assertTrue(ProviderEvent.objects.filter(event_id="evt-webhook-async-view-1").exists())

    def test_refund_request_processing_is_idempotent_and_reconciled(self):
        client_user = self.create_client()
        admin_user = self.create_admin()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.PENDING,
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)
        payment_services.transition_payment_status(payment, Payment.PaymentStatus.SUCCESS, provider="Secure Demo")
        payment.refresh_from_db()

        refund_request, created = payment_services.request_refund(
            payment,
            actor=admin_user,
            reason="Client cancellation approved",
            idempotency_key="refund-idem-1",
        )
        retry_refund, retry_created = payment_services.request_refund(
            payment,
            actor=admin_user,
            reason="Client cancellation approved",
            idempotency_key="refund-idem-1",
        )
        processed_refund, processed = payment_services.process_refund(refund_request, actor=admin_user)
        retry_processed_refund, retry_processed = payment_services.process_refund(processed_refund, actor=admin_user)

        booking.refresh_from_db()
        payment.refresh_from_db()
        self.assertTrue(created)
        self.assertFalse(retry_created)
        self.assertEqual(refund_request.id, retry_refund.id)
        self.assertTrue(processed)
        self.assertFalse(retry_processed)
        self.assertEqual(processed_refund.id, retry_processed_refund.id)
        self.assertEqual(processed_refund.status, RefundRequest.RefundStatus.PROCESSED)
        self.assertEqual(payment.payment_status, Payment.PaymentStatus.REFUNDED)
        self.assertEqual(booking.status, Booking.Status.REFUNDED)
        self.assertTrue(processed_refund.provider_refund_id.startswith("DEMO-REFUND-"))
        self.assertEqual(RefundStatusHistory.objects.filter(refund_request=processed_refund).count(), 3)
        self.assertEqual(PaymentLedgerEntry.objects.filter(payment=payment, entry_type=PaymentLedgerEntry.EntryType.PAYMENT_REFUNDED).count(), 1)
        self.assertTrue(payment_services.reconcile_payment_ledger(payment)["is_balanced"])

    def test_refund_request_rejects_unsuccessful_payment(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
        )
        payment = Payment.objects.create(booking=booking, amount=lawyer.fee)

        with self.assertRaisesMessage(ValidationError, "Only successful payments can be refunded"):
            payment_services.request_refund(payment, actor=client_user, idempotency_key="refund-pending-1")

        self.assertFalse(RefundRequest.objects.filter(payment=payment).exists())

    def test_chat_requires_confirmed_paid_booking(self):
        client_user = self.create_client()
        lawyer_user, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=datetime.strptime("10:00", "%H:%M").time(),
            status=Booking.Status.PENDING,
        )
        Payment.objects.create(booking=booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.PENDING)
        self.client.force_login(client_user)

        blocked_response = self.client.get(reverse("start_chat", args=[lawyer.id]))
        self.assertRedirects(blocked_response, reverse("lawyer_profile", args=[lawyer.id]))
        self.assertFalse(Chat.objects.exists())

        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status"])
        booking.payment.payment_status = Payment.PaymentStatus.SUCCESS
        booking.payment.save(update_fields=["payment_status"])

        allowed_response = self.client.get(reverse("start_chat", args=[lawyer.id]))
        chat = Chat.objects.get(booking=booking)
        self.assertRedirects(allowed_response, reverse("chat_page", args=[chat.id]))

        self.client.force_login(lawyer_user)
        chat_page = self.client.get(reverse("chat_page", args=[chat.id]))
        self.assertEqual(chat_page.status_code, 200)

    def test_review_is_tied_to_completed_booking(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=datetime.strptime("10:00", "%H:%M").time(),
            status=Booking.Status.COMPLETED,
        )
        Payment.objects.create(booking=booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.SUCCESS)
        self.client.force_login(client_user)

        response = self.client.post(
            reverse("add_review", args=[lawyer.id]),
            {"booking_id": booking.id, "rating": "5", "comment": "Helpful and clear advice."},
        )

        self.assertRedirects(response, reverse("lawyer_profile", args=[lawyer.id]))
        review = Review.objects.get(booking=booking)
        self.assertEqual(review.client, client_user)
        self.assertEqual(review.lawyer, lawyer)

    def test_pending_booking_cannot_skip_directly_to_completed(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=datetime.strptime("10:00", "%H:%M").time(),
            status=Booking.Status.PENDING,
        )
        Payment.objects.create(booking=booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.PENDING)

        with self.assertRaises(ValidationError):
            transition_booking_status(booking, Booking.Status.COMPLETED)

    def test_completed_booking_cannot_be_cancelled_or_rescheduled(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=datetime.strptime("10:00", "%H:%M").time(),
            status=Booking.Status.CONFIRMED,
        )
        Payment.objects.create(booking=booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.SUCCESS)
        transition_booking_status(booking, Booking.Status.COMPLETED)

        with self.assertRaises(ValidationError):
            cancel_booking(booking, actor=client_user)

        with self.assertRaises(ValidationError):
            reschedule_booking(
                booking,
                {
                    "appointment_date": timezone.localdate() + timedelta(days=2),
                    "appointment_time": datetime.strptime("10:00", "%H:%M").time(),
                },
                actor=client_user,
            )

    def test_illegal_booking_transitions_are_rejected(self):
        client_user = self.create_client()
        _, lawyer = self.create_lawyer()
        cancelled_booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.CANCELLED,
        )
        completed_booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=2),
            appointment_time=time(10, 0),
            status=Booking.Status.COMPLETED,
        )
        Payment.objects.create(booking=completed_booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.SUCCESS)

        with self.assertRaisesMessage(ValidationError, "cannot move from cancelled to completed"):
            transition_booking_status(cancelled_booking, Booking.Status.COMPLETED)
        with self.assertRaisesMessage(ValidationError, "cannot move from completed to pending"):
            transition_booking_status(completed_booking, Booking.Status.PENDING)

    def test_prepare_demo_command_cleans_data_and_seeds_demo_slots(self):
        client_user = self.create_client(username="demo_case_client", email="demo_case_client@example.com")
        lawyers = []
        for index in range(DEMO_LAWYER_COUNT):
            lawyer_user = User.objects.create_user(
                username=f"demo_lawyer_{index}",
                email=f"demo_lawyer_{index}@example.com",
                password="TempPass123",
                is_active=True,
            )
            lawyer_profile = lawyer_user.profile
            lawyer_profile.role = UserProfile.Role.LAWYER
            lawyer_profile.save(update_fields=["role"])
            lawyers.append(
                Lawyer.objects.create(
                    user=lawyer_user,
                    category=self.category,
                    name=f"Demo Lawyer {index}",
                    email=f"demo_lawyer_{index}@example.com",
                    phone="9999999999",
                    specialization=self.category.name,
                    experience=5 + index,
                    location="Bangalore",
                    fee="500.00",
                    is_verified=True,
                    verification_status=Lawyer.VerificationStatus.APPROVED,
                )
            )

        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyers[0],
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.CONFIRMED,
        )
        Payment.objects.create(booking=booking, amount=lawyers[0].fee, payment_status=Payment.PaymentStatus.SUCCESS)
        Chat.objects.create(client=client_user, lawyer=lawyers[1])

        call_command("prepare_demo")

        self.assertTrue(User.objects.filter(username=DEMO_CLIENT_USERNAME).exists())
        self.assertEqual(Chat.objects.filter(booking__isnull=True).count(), 0)
        self.assertTrue(Chat.objects.filter(booking=booking).exists())
        self.assertGreaterEqual(
            LawyerAvailability.objects.filter(lawyer__in=lawyers).count(),
            DEMO_LAWYER_COUNT * 3,
        )
        for lawyer in lawyers:
            lawyer.user.refresh_from_db()
            self.assertTrue(lawyer.user.check_password(DEMO_LAWYER_PASSWORD))

    def test_reset_lawyer_passwords_command_resets_all_lawyer_accounts(self):
        lawyer_user_one, _ = self.create_lawyer(username="lawyer_one", email="lawyer_one@example.com", password="OldPass123")
        lawyer_user_two, _ = self.create_lawyer(username="lawyer_two", email="lawyer_two@example.com", password="OldPass456")
        lawyer_user_two.is_active = False
        lawyer_user_two.save(update_fields=["is_active"])

        call_command("reset_lawyer_passwords")

        lawyer_user_one.refresh_from_db()
        lawyer_user_two.refresh_from_db()
        self.assertTrue(lawyer_user_one.check_password(DEMO_LAWYER_PASSWORD))
        self.assertTrue(lawyer_user_two.check_password(DEMO_LAWYER_PASSWORD))
        self.assertTrue(lawyer_user_two.is_active)

    def test_login_redirects_by_role(self):
        client_user = self.create_client(username="client_redirect", email="client_redirect@example.com")
        lawyer_user, _ = self.create_lawyer(username="lawyer_redirect", email="lawyer_redirect@example.com")
        admin_user = self.create_admin(username="admin_redirect", email="admin_redirect@example.com")

        client_response = self.client.post(reverse("login"), {"username": client_user.username, "password": "ClientPass123"})
        self.assertRedirects(client_response, reverse("client_dashboard"))

        self.client.logout()
        lawyer_response = self.client.post(reverse("login"), {"username": lawyer_user.username, "password": "LawyerPass123"})
        self.assertRedirects(lawyer_response, reverse("lawyer_dashboard"))

        self.client.logout()
        admin_response = self.client.post(reverse("login"), {"username": admin_user.username, "password": "AdminPass123"})
        self.assertRedirects(admin_response, reverse("admin_dashboard"))

    def test_non_admin_cannot_access_custom_admin_panel(self):
        client_user = self.create_client(username="client_blocked", email="client_blocked@example.com")
        self.client.force_login(client_user)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertRedirects(response, reverse("client_dashboard"))

    def test_login_rate_limit_blocks_repeated_failures(self):
        for _ in range(8):
            response = self.client.post(reverse("login"), {"username": "missing", "password": "bad"})
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(reverse("login"), {"username": "missing", "password": "bad"})

        self.assertEqual(blocked.status_code, 429)

    def test_chat_message_rate_limit_returns_json_429(self):
        client_user = self.create_client(username="spam_client", email="spam_client@example.com")
        _, lawyer = self.create_lawyer(username="spam_lawyer", email="spam_lawyer@example.com")
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.CONFIRMED,
        )
        Payment.objects.create(booking=booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.SUCCESS)
        chat = Chat.objects.create(client=client_user, lawyer=lawyer, booking=booking)
        self.client.force_login(client_user)

        for index in range(20):
            response = self.client.post(reverse("send_message", args=[chat.id]), {"text": f"message {index}"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(reverse("send_message", args=[chat.id]), {"text": "blocked"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(blocked.status_code, 429)
        self.assertIn("error", blocked.json())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_verification_flow_marks_profile_verified(self):
        user = self.create_client(username="verify_client", email="verify_client@example.com")
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)

        response = self.client.get(reverse("verify_email", args=[uid, token]))

        user.profile.refresh_from_db()
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(user.profile.email_verified)
        self.assertIsNotNone(user.profile.email_verified_at)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_is_rate_limited(self):
        self.create_client(username="reset_client", email="reset_client@example.com")

        for _ in range(4):
            response = self.client.post(reverse("password_reset"), {"email": "reset_client@example.com"})
            self.assertRedirects(response, reverse("password_reset_done"))

        blocked = self.client.post(reverse("password_reset"), {"email": "reset_client@example.com"})

        self.assertEqual(blocked.status_code, 429)
        self.assertGreaterEqual(len(mail.outbox), 1)

    def test_upload_validation_rejects_svg_and_mime_mismatch(self):
        svg = SimpleUploadedFile("unsafe.svg", b"<svg></svg>", content_type="image/svg+xml")
        fake_png = SimpleUploadedFile("fake.png", b"not a png", content_type="image/png")

        with self.assertRaises(ValidationError):
            validate_chat_file(svg)
        with self.assertRaises(ValidationError):
            validate_chat_file(fake_png)

    def test_protected_chat_file_requires_chat_participant(self):
        client_user = self.create_client(username="file_client", email="file_client@example.com")
        stranger = self.create_client(username="file_stranger", email="file_stranger@example.com")
        _, lawyer = self.create_lawyer(username="file_lawyer", email="file_lawyer@example.com")
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.CONFIRMED,
        )
        Payment.objects.create(booking=booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.SUCCESS)
        chat = Chat.objects.create(client=client_user, lawyer=lawyer, booking=booking)
        message = chat.messages.create(
            sender=client_user,
            text="see file",
            file=SimpleUploadedFile("note.txt", b"hello", content_type="text/plain"),
        )

        self.client.force_login(stranger)
        forbidden = self.client.get(reverse("protected_chat_file", args=[message.id]))

        self.assertEqual(forbidden.status_code, 404)

        self.client.force_login(client_user)
        allowed = self.client.get(reverse("protected_chat_file", args=[message.id]))

        self.assertEqual(allowed.status_code, 200)

    def test_websocket_chat_authorization_rejects_non_participant(self):
        client_user = self.create_client(username="ws_client", email="ws_client@example.com")
        stranger = self.create_client(username="ws_stranger", email="ws_stranger@example.com")
        _, lawyer = self.create_lawyer(username="ws_lawyer", email="ws_lawyer@example.com")
        booking = Booking.objects.create(
            client=client_user,
            lawyer=lawyer,
            issue="Need help with a custody matter and legal documentation review.",
            appointment_date=timezone.localdate() + timedelta(days=1),
            appointment_time=time(10, 0),
            status=Booking.Status.CONFIRMED,
        )
        Payment.objects.create(booking=booking, amount=lawyer.fee, payment_status=Payment.PaymentStatus.SUCCESS)
        chat = Chat.objects.create(client=client_user, lawyer=lawyer, booking=booking)
        consumer = ChatConsumer()

        self.assertTrue(async_to_sync(consumer.user_can_access_chat)(client_user.id, chat.id))
        self.assertFalse(async_to_sync(consumer.user_can_access_chat)(stranger.id, chat.id))

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True, LEXCONNECT_ASYNC_NOTIFICATIONS=True)
    def test_async_notification_uses_local_eager_fallback(self):
        user = self.create_client(username="notify_client", email="notify@example.com")

        result = create_notification(user, "Async notice", "Queued locally.", "/notifications/")

        self.assertIsNotNone(result)
        self.assertTrue(Notification.objects.filter(user=user, title="Async notice").exists())
