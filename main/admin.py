from django.contrib import admin

from .models import (
    Booking,
    BookingStatusHistory,
    Chat,
    ClientCase,
    LawCategory,
    Lawyer,
    LawyerAvailability,
    LawyerAvailabilityBreak,
    LawyerBlockedDate,
    LegalDocument,
    Message,
    Notification,
    Payment,
    PaymentLedgerEntry,
    Review,
    ProviderEvent,
    RefundRequest,
    RefundStatusHistory,
    UserProfile,
)


@admin.register(LawCategory)
class LawCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "email_verified", "is_online", "last_seen")
    list_filter = ("role", "email_verified", "is_online")
    search_fields = ("user__username", "user__email")


@admin.register(Lawyer)
class LawyerAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "city", "experience", "fee", "rating_avg", "is_online", "verification_status", "is_verified")
    list_filter = ("category", "is_online", "is_verified", "verification_status")
    search_fields = ("name", "email", "city", "location")


@admin.register(LawyerAvailability)
class LawyerAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("lawyer", "weekday", "start_time", "end_time", "slot_duration_minutes", "is_active")
    list_filter = ("weekday", "is_active")
    search_fields = ("lawyer__name",)


@admin.register(LawyerAvailabilityBreak)
class LawyerAvailabilityBreakAdmin(admin.ModelAdmin):
    list_display = ("availability", "start_time", "end_time", "reason")
    search_fields = ("availability__lawyer__name", "reason")


@admin.register(LawyerBlockedDate)
class LawyerBlockedDateAdmin(admin.ModelAdmin):
    list_display = ("lawyer", "date", "reason")
    search_fields = ("lawyer__name", "reason")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "lawyer", "appointment_date", "appointment_time", "duration_minutes", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("client__username", "lawyer__name")


@admin.register(BookingStatusHistory)
class BookingStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("booking", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status", "created_at")
    search_fields = ("booking__client__username", "booking__lawyer__name", "reason")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("booking", "amount", "currency", "payment_status", "transaction_id", "provider", "marked_paid_at")
    list_filter = ("payment_status", "provider")
    search_fields = ("transaction_id", "booking__client__username", "booking__lawyer__name")


@admin.register(ProviderEvent)
class ProviderEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "event_type", "processing_status", "payment", "refund_request", "replay_count", "created_at")
    list_filter = ("provider", "event_type", "processing_status", "created_at")
    search_fields = ("event_id", "payment__transaction_id", "refund_request__provider_refund_id")
    readonly_fields = ("payload_hash", "payload", "replay_count", "processed_at", "created_at", "updated_at")


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ("payment", "amount", "currency", "status", "provider", "provider_refund_id", "processed_at")
    list_filter = ("status", "provider", "created_at")
    search_fields = ("provider_refund_id", "payment__transaction_id", "payment__booking__client__username")


@admin.register(RefundStatusHistory)
class RefundStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("refund_request", "from_status", "to_status", "actor", "provider", "provider_event_id", "created_at")
    list_filter = ("to_status", "provider", "created_at")
    search_fields = ("refund_request__provider_refund_id", "reason", "provider_event_id")


@admin.register(PaymentLedgerEntry)
class PaymentLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("payment", "refund_request", "entry_type", "amount", "currency", "provider", "provider_event_id", "created_at")
    list_filter = ("entry_type", "provider", "created_at")
    search_fields = ("payment__transaction_id", "provider_event_id", "idempotency_key")


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "lawyer", "booking", "updated_at")
    search_fields = ("client__username", "lawyer__name")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("chat", "sender", "timestamp", "is_read")
    list_filter = ("is_read", "timestamp")
    search_fields = ("sender__username", "text")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("client", "lawyer", "booking", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("client__username", "lawyer__name", "comment")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "notification_type", "priority", "is_read", "created_at")
    list_filter = ("is_read", "notification_type", "priority")
    search_fields = ("user__username", "title", "message")


@admin.register(ClientCase)
class ClientCaseAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "lawyer", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "client__username", "lawyer__name")


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "case", "uploaded_by", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "case__title", "uploaded_by__username")
