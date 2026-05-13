from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.utils.text import get_valid_filename


def normalize_category_name(name):
    return " ".join(word.capitalize() for word in (name or "").split())


def default_appointment_time():
    return timezone.localtime().time().replace(second=0, microsecond=0)


def secure_upload_path(root, filename):
    extension = Path(filename or "").suffix.lower()
    safe_stem = get_valid_filename(Path(filename or "upload").stem)[:48] or "upload"
    return f"{root}/{uuid4().hex}/{safe_stem}{extension}"


def certificate_upload_path(instance, filename):
    return secure_upload_path("private/certificates", filename)


def chat_file_upload_path(instance, filename):
    return secure_upload_path("private/chat_files", filename)


def case_document_upload_path(instance, filename):
    return secure_upload_path("private/case_documents", filename)


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        abstract = True


class LawCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.name = normalize_category_name(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    class Role(models.TextChoices):
        CLIENT = "client", "Client"
        LAWYER = "lawyer", "Lawyer"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} profile"

    @property
    def is_lawyer(self):
        return self.role == self.Role.LAWYER

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT


class LawyerQuerySet(models.QuerySet):
    def with_login_account(self):
        return self.filter(
            user__isnull=False,
            is_verified=True,
            user__profile__role=UserProfile.Role.LAWYER,
        )

    def visible_to_clients(self):
        return self.with_login_account()

    def online_for_clients(self):
        return self.with_login_account().filter(is_online=True)


class Lawyer(TimestampedModel):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="lawyer_profile",
    )
    category = models.ForeignKey(LawCategory, on_delete=models.CASCADE, related_name="lawyers")
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    specialization = models.CharField(max_length=100, blank=True)
    experience = models.PositiveIntegerField(default=0)
    city = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    certification = models.CharField(max_length=200, blank=True)
    certificate_file = models.FileField(upload_to=certificate_upload_path, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    verification_notes = models.TextField(blank=True)
    verification_submitted_at = models.DateTimeField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    suspended_at = models.DateTimeField(blank=True, null=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("500.00"))
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))
    review_count = models.PositiveIntegerField(default=0)
    is_online = models.BooleanField(default=False)
    objects = LawyerQuerySet.as_manager()

    class Meta:
        ordering = ["-is_online", "-rating_avg", "name"]
        indexes = [
            models.Index(fields=["verification_status", "is_verified"], name="lawyer_verification_idx"),
            models.Index(fields=["category", "city"], name="lawyer_category_city_idx"),
            models.Index(fields=["rating_avg", "review_count"], name="lawyer_rating_idx"),
        ]

    def __str__(self):
        return self.name

    def refresh_rating_stats(self):
        aggregate = self.reviews.aggregate(avg_rating=Avg("rating"), total_reviews=Count("id"))
        self.rating_avg = aggregate["avg_rating"] or Decimal("0.00")
        self.review_count = aggregate["total_reviews"] or 0
        self.save(update_fields=["rating_avg", "review_count"])

    @property
    def status_label(self):
        if not self.has_login_account:
            return "Unavailable"
        if self.is_online:
            return "Online"
        if self.user and hasattr(self.user, "profile") and self.user.profile.last_seen:
            return f"Last seen {timezone.localtime(self.user.profile.last_seen).strftime('%d %b %I:%M %p')}"
        return "Offline"

    @property
    def has_login_account(self):
        profile = getattr(self.user, "profile", None) if self.user_id else None
        return bool(self.user_id and self.is_verified and profile and profile.role == UserProfile.Role.LAWYER)


class LawyerAvailability(TimestampedModel):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    lawyer = models.ForeignKey(Lawyer, on_delete=models.CASCADE, related_name="availability_slots")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(15), MaxValueValidator(240)],
    )
    timezone_name = models.CharField(max_length=64, default="Asia/Kolkata")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        indexes = [
            models.Index(fields=["lawyer", "weekday", "is_active"], name="availability_lookup_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["lawyer", "weekday", "start_time", "end_time"],
                name="unique_lawyer_availability_slot",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=models.F("start_time")),
                name="availability_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.lawyer.name} - {self.get_weekday_display()} {self.start_time} to {self.end_time}"


class LawyerAvailabilityBreak(TimestampedModel):
    availability = models.ForeignKey(LawyerAvailability, on_delete=models.CASCADE, related_name="breaks")
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=models.F("start_time")),
                name="availability_break_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.availability} break {self.start_time} to {self.end_time}"


class LawyerBlockedDate(TimestampedModel):
    lawyer = models.ForeignKey(Lawyer, on_delete=models.CASCADE, related_name="blocked_dates")
    date = models.DateField()
    reason = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["lawyer", "date"], name="unique_lawyer_blocked_date"),
        ]

    def __str__(self):
        return f"{self.lawyer.name} blocked on {self.date}"


class Booking(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"
        RESCHEDULED = "rescheduled", "Rescheduled"

    class ConsultationMode(models.TextChoices):
        CHAT = "chat", "Chat"
        VIDEO = "video", "Video"
        PHONE = "phone", "Phone"

    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    lawyer = models.ForeignKey(Lawyer, on_delete=models.CASCADE, related_name="bookings")
    issue = models.TextField()
    appointment_date = models.DateField(default=timezone.localdate)
    appointment_time = models.TimeField(default=default_appointment_time)
    duration_minutes = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(15), MaxValueValidator(240)])
    timezone_name = models.CharField(max_length=64, default="Asia/Kolkata")
    consultation_mode = models.CharField(max_length=20, choices=ConsultationMode.choices, default=ConsultationMode.CHAT)
    meeting_link = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    last_rescheduled_at = models.DateTimeField(blank=True, null=True)
    client_notes = models.TextField(blank=True)
    lawyer_notes = models.TextField(blank=True)
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "status", "appointment_date"], name="booking_client_status_idx"),
            models.Index(fields=["lawyer", "status", "appointment_date", "appointment_time"], name="booking_lawyer_slot_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["lawyer", "appointment_date", "appointment_time"],
                condition=Q(status__in=["pending", "confirmed"]),
                name="unique_active_lawyer_booking_slot",
            ),
        ]

    def __str__(self):
        client_name = self.client.username if self.client_id else "Unknown client"
        return f"{client_name} -> {self.lawyer.name}"

    @property
    def appointment_starts_at(self):
        return timezone.make_aware(
            datetime.combine(self.appointment_date, self.appointment_time),
            timezone.get_current_timezone(),
        )


class Payment(TimestampedModel):
    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        AWAITING_VERIFICATION = "awaiting_verification", "Awaiting verification"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="payment")
    payment_reference = models.UUIDField(default=uuid4, db_index=True, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    payment_status = models.CharField(max_length=30, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    transaction_id = models.CharField(max_length=100, blank=True)
    provider = models.CharField(max_length=50, default="Demo Manual")
    provider_order_id = models.CharField(max_length=120, blank=True, db_index=True)
    provider_payment_id = models.CharField(max_length=120, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=120, blank=True, db_index=True)
    marked_paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["payment_status", "created_at"], name="payment_status_created_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="unique_payment_idempotency_key",
            ),
        ]

    def __str__(self):
        return f"{self.booking_id} - {self.payment_status}"


class PaymentStatusHistory(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_status_changes")
    reason = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=120, blank=True)
    provider = models.CharField(max_length=50, blank=True)
    provider_event_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["payment", "created_at"], name="payment_history_lookup_idx"),
            models.Index(fields=["provider", "provider_event_id"], name="payment_provider_event_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_event_id"],
                condition=~Q(provider_event_id=""),
                name="unique_payment_provider_event",
            ),
        ]

    def __str__(self):
        return f"Payment #{self.payment_id}: {self.from_status} -> {self.to_status}"


class ProviderEvent(TimestampedModel):
    class ProcessingStatus(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        IGNORED = "ignored", "Ignored"
        FAILED = "failed", "Failed"

    provider = models.CharField(max_length=50)
    event_id = models.CharField(max_length=120, db_index=True)
    event_type = models.CharField(max_length=80)
    payload_hash = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="provider_events")
    refund_request = models.ForeignKey("RefundRequest", on_delete=models.SET_NULL, null=True, blank=True, related_name="provider_events")
    processing_status = models.CharField(max_length=20, choices=ProcessingStatus.choices, default=ProcessingStatus.RECEIVED)
    replay_count = models.PositiveIntegerField(default=0)
    processed_at = models.DateTimeField(blank=True, null=True)
    error_message = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "event_id"], name="provider_event_lookup_idx"),
            models.Index(fields=["processing_status", "created_at"], name="provider_event_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["provider", "event_id"], name="unique_provider_event"),
        ]

    def __str__(self):
        return f"{self.provider}:{self.event_id} ({self.processing_status})"


class RefundRequest(TimestampedModel):
    class RefundStatus(models.TextChoices):
        REQUESTED = "requested", "Requested"
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="refund_requests")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.REQUESTED)
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="requested_refunds")
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_refunds")
    provider = models.CharField(max_length=50, default="Secure Demo")
    provider_refund_id = models.CharField(max_length=120, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=120, blank=True, db_index=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["payment", "status"], name="refund_payment_status_idx"),
            models.Index(fields=["provider", "provider_refund_id"], name="refund_provider_refund_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="unique_refund_idempotency_key",
            ),
            models.UniqueConstraint(
                fields=["provider", "provider_refund_id"],
                condition=~Q(provider_refund_id=""),
                name="unique_refund_provider_refund",
            ),
        ]

    def __str__(self):
        return f"Refund #{self.id} for payment #{self.payment_id}: {self.status}"


class RefundStatusHistory(models.Model):
    refund_request = models.ForeignKey(RefundRequest, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="refund_status_changes")
    reason = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=50, blank=True)
    provider_event_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["refund_request", "created_at"], name="refund_history_lookup_idx"),
            models.Index(fields=["provider", "provider_event_id"], name="refund_provider_event_idx"),
        ]

    def __str__(self):
        return f"Refund #{self.refund_request_id}: {self.from_status} -> {self.to_status}"


class PaymentLedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        PAYMENT_CAPTURED = "payment_captured", "Payment captured"
        PAYMENT_REFUNDED = "payment_refunded", "Payment refunded"
        RECONCILIATION_NOTE = "reconciliation_note", "Reconciliation note"

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="ledger_entries")
    refund_request = models.ForeignKey(RefundRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries")
    entry_type = models.CharField(max_length=30, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    provider = models.CharField(max_length=50, blank=True)
    provider_event_id = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["payment", "created_at"], name="ledger_payment_lookup_idx"),
            models.Index(fields=["provider", "provider_event_id"], name="ledger_provider_event_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_event_id", "entry_type"],
                condition=~Q(provider_event_id=""),
                name="unique_ledger_provider_event_type",
            ),
            models.UniqueConstraint(
                fields=["idempotency_key", "entry_type"],
                condition=~Q(idempotency_key=""),
                name="unique_ledger_idem_type",
            ),
        ]

    def __str__(self):
        return f"{self.entry_type} payment #{self.payment_id} {self.amount} {self.currency}"


class Chat(TimestampedModel):
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="client_chats")
    lawyer = models.ForeignKey(Lawyer, on_delete=models.CASCADE, related_name="chats")
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="chat", null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["client", "updated_at"], name="chat_client_updated_idx"),
            models.Index(fields=["lawyer", "updated_at"], name="chat_lawyer_updated_idx"),
        ]

    def __str__(self):
        client_name = self.client.username if self.client_id else "Unknown client"
        return f"{client_name} - {self.lawyer.name}"


class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    text = models.TextField(blank=True)
    file = models.FileField(upload_to=chat_file_upload_path, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["chat", "timestamp"], name="message_chat_time_idx"),
            models.Index(fields=["chat", "is_read"], name="message_chat_read_idx"),
        ]

    def __str__(self):
        return f"Message #{self.pk} in chat {self.chat_id}"


class Review(models.Model):
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    lawyer = models.ForeignKey(Lawyer, on_delete=models.CASCADE, related_name="reviews")
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="review", null=True, blank=True)
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["lawyer", "created_at"], name="review_lawyer_created_idx"),
        ]

    def __str__(self):
        return f"{self.client.username} rated {self.lawyer.name}"


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        GENERAL = "general", "General"
        BOOKING = "booking", "Booking"
        PAYMENT = "payment", "Payment"
        CHAT = "chat", "Chat"
        VERIFICATION = "verification", "Verification"
        MODERATION = "moderation", "Moderation"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices, default=NotificationType.GENERAL)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"], name="notification_user_read_idx"),
            models.Index(fields=["notification_type", "priority"], name="notification_type_priority_idx"),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.title}"


class OperationalEvent(models.Model):
    class Source(models.TextChoices):
        AUDIT = "audit", "Audit"
        SECURITY = "security", "Security"
        WEBHOOK = "webhook", "Webhook"
        TASK = "task", "Task"
        SYSTEM = "system", "System"

    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    source = models.CharField(max_length=30, choices=Source.choices, db_index=True)
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.INFO, db_index=True)
    event = models.CharField(max_length=120, db_index=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="operational_events")
    path = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=12, blank=True)
    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=180, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source", "level", "created_at"], name="op_event_source_level_idx"),
            models.Index(fields=["event", "created_at"], name="op_event_name_idx"),
            models.Index(fields=["actor", "created_at"], name="op_event_actor_idx"),
        ]

    def __str__(self):
        return f"{self.source}:{self.event}"


class BookingStatusHistory(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="booking_status_changes")
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "created_at"], name="booking_history_lookup_idx"),
        ]

    def __str__(self):
        return f"Booking #{self.booking_id}: {self.from_status} -> {self.to_status}"


class ClientCase(TimestampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        CLOSED = "closed", "Closed"

    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="legal_cases")
    lawyer = models.ForeignKey(Lawyer, on_delete=models.SET_NULL, null=True, blank=True, related_name="client_cases")
    booking = models.OneToOneField(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name="case")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["client", "status"], name="case_client_status_idx"),
            models.Index(fields=["lawyer", "status"], name="case_lawyer_status_idx"),
        ]

    def __str__(self):
        return self.title


class LegalDocument(TimestampedModel):
    class DocumentStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"
        FLAGGED = "flagged", "Flagged"

    case = models.ForeignKey(ClientCase, on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="uploaded_legal_documents")
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to=case_document_upload_path)
    status = models.CharField(max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.ACTIVE, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["case", "status"], name="document_case_status_idx"),
        ]

    def __str__(self):
        return self.title
