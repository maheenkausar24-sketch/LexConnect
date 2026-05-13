from .admin_panel import (
    admin_bookings,
    admin_cancel_booking,
    admin_clients,
    admin_dashboard,
    admin_lawyers,
    admin_operational_events,
    admin_payments,
    admin_payment_timeline,
    admin_provider_event_detail,
    admin_provider_events,
    admin_update_lawyer_verification,
    admin_update_payment,
    admin_update_user_status,
)
from .ai import ask_lexora, chatbot
from .auth import RateLimitedPasswordResetView, lawyer_login, lawyer_register, login_page, logout_user, register, resend_verification_email, verify_email
from .bookings import (
    add_review,
    add_schedule_slot,
    cancel_booking_view,
    consult_lawyer,
    payment_page,
    request_success,
    reschedule_booking_view,
    update_booking_status,
)
from .chat import chat_messages, chat_page, send_message, start_chat, user_chats
from .media import protected_case_document, protected_certificate_file, protected_chat_file
from .notifications import mark_notification_read, notifications_view
from .operations import admin_health, admin_task_events, health_live, health_ready
from .pages import (
    client_bookings,
    client_chats,
    client_dashboard,
    dashboard,
    demo_accounts_page,
    home,
    lawyer_availability,
    lawyer_bookings,
    lawyer_chats,
    lawyer_dashboard,
    lawyer_profile,
    lawyers_by_category,
    toggle_lawyer_status,
)
from .payments import provider_webhook
