import logging
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from ..audit import record_operational_event
from ..models import Notification


email_logger = logging.getLogger("main.email")


def absolute_url(path=""):
    if not path:
        return getattr(settings, "LEXCONNECT_SITE_URL", "http://127.0.0.1:8000")
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urljoin(f"{getattr(settings, 'LEXCONNECT_SITE_URL', 'http://127.0.0.1:8000')}/", path.lstrip("/"))


def email_notifications_enabled():
    return bool(getattr(settings, "LEXCONNECT_EMAIL_NOTIFICATIONS", True))


def notification_email_allowed(notification):
    if not email_notifications_enabled() or not notification or not notification.user_id:
        return False
    if not notification.user.email:
        return False
    allowed_types = set(getattr(settings, "LEXCONNECT_EMAIL_NOTIFICATION_TYPES", ["booking", "payment", "chat"]))
    return notification.notification_type in allowed_types


def dispatch_email(subject, message, recipient_list, *, html_message="", from_email=None, metadata=None):
    recipients = [recipient for recipient in recipient_list if recipient]
    if not recipients:
        return 0

    try:
        if getattr(settings, "LEXCONNECT_ASYNC_EMAIL", False):
            from ..tasks import send_email_task

            send_email_task.delay(subject, message, recipients, from_email or settings.DEFAULT_FROM_EMAIL, html_message)
            return len(recipients)

        sent = send_mail(
            subject,
            message,
            from_email or settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
            html_message=html_message or None,
        )
        email_logger.info({"event": "email_sent", "recipient_count": len(recipients), "sent": sent, **(metadata or {})})
        return sent
    except Exception as exc:
        email_logger.warning(
            {
                "event": "email_send_failed",
                "error": exc.__class__.__name__,
                "recipient_count": len(recipients),
                **(metadata or {}),
            }
        )
        record_operational_event(
            "task",
            "email_send_failed",
            level="warning",
            summary=f"Email dispatch failed: {exc.__class__.__name__}",
            metadata={"recipient_count": len(recipients), **(metadata or {})},
        )
        return 0


def dispatch_template_email(template_name, subject, recipient_list, context, *, from_email=None):
    message = render_to_string(f"emails/{template_name}.txt", context).strip()
    html_message = render_to_string(f"emails/{template_name}.html", context)
    return dispatch_email(
        subject,
        message,
        recipient_list,
        html_message=html_message,
        from_email=from_email,
        metadata={"template": template_name},
    )


def send_notification_email(notification):
    if not notification_email_allowed(notification):
        return 0
    context = {
        "notification": notification,
        "recipient": notification.user,
        "action_url": absolute_url(notification.url or reverse("notifications")),
        "site_url": absolute_url(),
    }
    subject = f"LexConnect: {notification.title}"
    return dispatch_template_email(
        "notification",
        subject,
        [notification.user.email],
        context,
        from_email=settings.DEFAULT_FROM_EMAIL,
    )


def send_verification_template_email(request, user, verify_url):
    context = {
        "recipient": user,
        "verify_url": verify_url,
        "site_url": absolute_url(),
    }
    return dispatch_template_email(
        "verification",
        "Verify your LexConnect email",
        [user.email],
        context,
        from_email=settings.DEFAULT_FROM_EMAIL,
    )


def send_password_reset_template_email(subject, message, recipient_list, html_message=""):
    return dispatch_email(
        subject,
        message,
        recipient_list,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        metadata={"template": "password_reset"},
    )
