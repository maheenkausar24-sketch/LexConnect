from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from ..audit import audit_event, record_operational_event
from ..models import Booking, Notification, Payment
from ..utils import create_notification


REMINDER_WINDOWS = (
    ("2-hour", 120, Notification.Priority.HIGH),
    ("24-hour", 24 * 60, Notification.Priority.NORMAL),
)


def reminder_key_for_booking(booking, label):
    return f"Booking #{booking.id} {label} reminder"


def reminder_already_sent(user, booking, label):
    return Notification.objects.filter(
        user=user,
        notification_type=Notification.NotificationType.BOOKING,
        title="Upcoming consultation reminder",
        message__contains=reminder_key_for_booking(booking, label),
    ).exists()


def due_reminder_window(starts_at, now):
    minutes_until = (starts_at - now).total_seconds() / 60
    if minutes_until <= 0:
        return None
    for label, minutes, priority in REMINDER_WINDOWS:
        if minutes_until <= minutes:
            return label, priority
    return None


def reminder_message(booking, label):
    local_start = timezone.localtime(booking.appointment_starts_at)
    return (
        f"{reminder_key_for_booking(booking, label)}: your consultation with "
        f"{booking.lawyer.name} is scheduled for {local_start.strftime('%d %b %Y at %I:%M %p')}."
    )


def scan_upcoming_booking_reminders(*, now=None):
    if not getattr(settings, "LEXCONNECT_REMINDERS_ENABLED", True):
        return {"checked": 0, "sent": 0, "skipped": "disabled"}

    now = now or timezone.now()
    lookahead = timezone.timedelta(hours=getattr(settings, "LEXCONNECT_REMINDER_LOOKAHEAD_HOURS", 24))
    window_end = now + lookahead
    queryset = (
        Booking.objects.filter(
            status=Booking.Status.CONFIRMED,
            payment__payment_status=Payment.PaymentStatus.SUCCESS,
            appointment_date__gte=timezone.localdate(now),
            appointment_date__lte=timezone.localdate(window_end),
        )
        .select_related("client", "lawyer", "lawyer__user", "payment")
        .order_by("appointment_date", "appointment_time")[: getattr(settings, "LEXCONNECT_REMINDER_SCAN_LIMIT", 100)]
    )

    checked = 0
    sent = 0
    for booking in queryset:
        checked += 1
        due = due_reminder_window(booking.appointment_starts_at, now)
        if not due:
            continue
        label, priority = due
        url = reverse("client_bookings")
        sent_before_booking = sent
        for user in [booking.client, booking.lawyer.user]:
            if reminder_already_sent(user, booking, label):
                continue
            target_url = url if user == booking.client else reverse("lawyer_bookings")
            create_notification(
                user,
                "Upcoming consultation reminder",
                reminder_message(booking, label),
                target_url,
                notification_type=Notification.NotificationType.BOOKING,
                priority=priority,
            )
            sent += 1
        if sent > sent_before_booking:
            audit_event("booking_reminder_dispatched", booking_id=booking.id, reminder_window=label)

    record_operational_event(
        "task",
        "booking_reminder_scan_finished",
        summary=f"Booking reminder scan checked {checked}, sent {sent}.",
        metadata={"checked": checked, "sent": sent},
    )
    return {"checked": checked, "sent": sent}
