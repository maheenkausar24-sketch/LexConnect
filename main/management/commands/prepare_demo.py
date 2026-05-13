from datetime import time
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from main.models import Booking, Chat, Lawyer, LawyerAvailability, Payment, UserProfile
from main.services.auth import COMMON_DEMO_LAWYER_PASSWORD, reset_all_lawyer_accounts
from main.services.chat import get_or_create_chat_for_booking
from main.services.lawyer_import import import_lawyers_from_csv
from main.utils import ensure_profile_role


DEMO_CLIENT_USERNAME = "demo_client"
DEMO_CLIENT_EMAIL = "demo.client@lexconnect.local"
DEMO_CLIENT_PASSWORD = "client@123"
DEMO_LAWYER_PASSWORD = COMMON_DEMO_LAWYER_PASSWORD
DEMO_LAWYER_COUNT = 5
DEMO_ACCOUNTS_FILE = "demo_accounts.txt"
SLOT_TEMPLATES = [
    [(0, time(10, 0), time(11, 0)), (1, time(14, 0), time(15, 0)), (3, time(11, 0), time(12, 0))],
    [(0, time(12, 0), time(13, 0)), (2, time(10, 0), time(11, 0)), (4, time(16, 0), time(17, 0))],
    [(1, time(9, 30), time(10, 30)), (3, time(15, 0), time(16, 0)), (5, time(11, 0), time(12, 0))],
    [(0, time(15, 0), time(16, 0)), (2, time(12, 0), time(13, 0)), (4, time(10, 0), time(11, 0))],
    [(1, time(11, 0), time(12, 0)), (3, time(9, 30), time(10, 30)), (5, time(14, 0), time(15, 0))],
]


class Command(BaseCommand):
    help = "Prepare LexConnect with clean demo data, availability slots, and printable account credentials."

    def handle(self, *args, **options):
        output_path = Path(settings.BASE_DIR) / DEMO_ACCOUNTS_FILE

        with transaction.atomic():
            import_summary = import_lawyers_from_csv(settings.BASE_DIR)
            demo_client = self._ensure_demo_client()
            lawyer_accounts = reset_all_lawyer_accounts()
            demo_lawyers = self._ensure_demo_lawyers()
            orphan_chats_deleted = self._remove_orphan_chats()
            created_slots, updated_slots = self._seed_availability_slots(demo_lawyers)
            payments_created, bookings_normalized = self._normalize_bookings()
            linked_chats = self._ensure_booking_chats()
            output_path.write_text(self._build_accounts_file(demo_client), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("LexConnect demo data is ready."))
        self.stdout.write(
            f"CSV import: {import_summary.total_processed} processed, {import_summary.created} created, "
            f"{import_summary.updated} updated, {import_summary.skipped} skipped"
        )
        self.stdout.write(f"Demo accounts file: {output_path}")
        self.stdout.write(f"Lawyer accounts reset: {len(lawyer_accounts)}")
        self.stdout.write(f"Demo lawyers prepared: {len(demo_lawyers)}")
        self.stdout.write(f"Availability slots created: {created_slots}")
        self.stdout.write(f"Availability slots reactivated: {updated_slots}")
        self.stdout.write(f"Orphan chats removed: {orphan_chats_deleted}")
        self.stdout.write(f"Missing payments created: {payments_created}")
        self.stdout.write(f"Bookings normalized: {bookings_normalized}")
        self.stdout.write(f"Booking-linked chats ensured: {linked_chats}")

    def _ensure_demo_client(self):
        client, _ = User.objects.get_or_create(
            username=DEMO_CLIENT_USERNAME,
            defaults={"email": DEMO_CLIENT_EMAIL, "is_active": True},
        )
        client.email = DEMO_CLIENT_EMAIL
        client.is_active = True
        client.set_password(DEMO_CLIENT_PASSWORD)
        client.save()
        profile = ensure_profile_role(client, role=UserProfile.Role.CLIENT)
        if not profile.email_verified:
            profile.email_verified = True
            profile.email_verified_at = timezone.now()
            profile.save(update_fields=["email_verified", "email_verified_at"])
        return client

    def _ensure_demo_lawyers(self):
        demo_lawyers = list(
            Lawyer.objects.visible_to_clients()
            .select_related("user", "user__profile", "category")
            .order_by("id")[:DEMO_LAWYER_COUNT]
        )

        if len(demo_lawyers) < DEMO_LAWYER_COUNT:
            raise ValueError(f"Expected at least {DEMO_LAWYER_COUNT} verified lawyers for the demo.")

        for lawyer in demo_lawyers:
            user = lawyer.user
            profile = ensure_profile_role(user, role=UserProfile.Role.LAWYER)
            if not profile.is_online:
                profile.is_online = True
            if not profile.email_verified:
                profile.email_verified = True
                profile.email_verified_at = timezone.now()
            profile.last_seen = timezone.now()
            profile.save(update_fields=["role", "is_online", "last_seen", "email_verified", "email_verified_at"])

            lawyer.is_verified = True
            lawyer.is_online = True
            lawyer.save(update_fields=["is_verified", "is_online", "updated_at"])

        return demo_lawyers

    def _remove_orphan_chats(self):
        orphan_chats = Chat.objects.filter(booking__isnull=True)
        orphan_count = orphan_chats.count()
        orphan_chats.delete()
        return orphan_count

    def _seed_availability_slots(self, lawyers):
        created_slots = 0
        updated_slots = 0

        for index, lawyer in enumerate(lawyers):
            template = SLOT_TEMPLATES[index % len(SLOT_TEMPLATES)]
            for weekday, start_time, end_time in template:
                slot, created = LawyerAvailability.objects.get_or_create(
                    lawyer=lawyer,
                    weekday=weekday,
                    start_time=start_time,
                    end_time=end_time,
                    defaults={"is_active": True},
                )
                if created:
                    created_slots += 1
                    continue
                if not slot.is_active:
                    slot.is_active = True
                    slot.save(update_fields=["is_active", "updated_at"])
                    updated_slots += 1

        return created_slots, updated_slots

    def _normalize_bookings(self):
        payments_created = 0
        bookings_normalized = 0

        for booking in Booking.objects.select_related("lawyer", "payment").order_by("id"):
            payment = getattr(booking, "payment", None)
            if payment is None:
                payment = Payment.objects.create(booking=booking, amount=booking.lawyer.fee)
                payments_created += 1

            if booking.status == Booking.Status.PENDING and payment.payment_status == Payment.PaymentStatus.SUCCESS:
                booking.status = Booking.Status.CONFIRMED
                booking.save(update_fields=["status", "updated_at"])
                bookings_normalized += 1
                continue

            if booking.status in {Booking.Status.CONFIRMED, Booking.Status.COMPLETED} and payment.payment_status != Payment.PaymentStatus.SUCCESS:
                payment.payment_status = Payment.PaymentStatus.SUCCESS
                payment.provider = payment.provider or "Demo Manual"
                if not payment.transaction_id:
                    payment.transaction_id = f"DEMO-{uuid4().hex[:10].upper()}"
                if not payment.marked_paid_at:
                    payment.marked_paid_at = timezone.now()
                payment.save(update_fields=["payment_status", "provider", "transaction_id", "marked_paid_at", "updated_at"])
                bookings_normalized += 1

        return payments_created, bookings_normalized

    def _ensure_booking_chats(self):
        linked_chats = 0

        eligible_bookings = Booking.objects.filter(
            status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
            payment__payment_status=Payment.PaymentStatus.SUCCESS,
        ).select_related("client", "lawyer", "payment")

        for booking in eligible_bookings:
            chat = get_or_create_chat_for_booking(booking)
            update_fields = []
            if chat.client_id != booking.client_id:
                chat.client = booking.client
                update_fields.append("client")
            if chat.lawyer_id != booking.lawyer_id:
                chat.lawyer = booking.lawyer
                update_fields.append("lawyer")
            if update_fields:
                update_fields.append("updated_at")
                chat.save(update_fields=update_fields)
            linked_chats += 1

        return linked_chats

    def _lawyer_demo_accounts(self):
        return (
            User.objects.filter(profile__role=UserProfile.Role.LAWYER)
            .select_related("profile", "lawyer_profile")
            .order_by("email", "username")
        )

    def _build_accounts_file(self, demo_client):
        lines = [
            "LexConnect Demo Accounts",
            "========================",
            "",
            "Client login",
            f"Username: {demo_client.username}",
            f"Password: {DEMO_CLIENT_PASSWORD}",
            "",
            "Lawyer logins",
            f"Common password: {COMMON_DEMO_LAWYER_PASSWORD}",
            "",
        ]

        for user in self._lawyer_demo_accounts():
            lawyer = getattr(user, "lawyer_profile", None)
            login_identifier = user.email or (lawyer.email if lawyer else "") or user.username
            lines.append(f"{login_identifier} | role: lawyer")

        lines.extend(
            [
                "",
                "Demo flow",
                "1. Log in as the client and book a published slot.",
                "2. Mark the payment as paid to open the booking chat.",
                "3. Log in as the assigned lawyer to complete the booking.",
                "4. Log back in as the client and leave a review from the lawyer profile.",
            ]
        )
        return "\n".join(lines)
