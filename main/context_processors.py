from django.conf import settings

from .models import Notification


def notification_summary(request):
    base_context = {"show_demo_accounts": getattr(settings, "LEXCONNECT_SHOW_DEMO_ACCOUNTS", False)}
    if not request.user.is_authenticated:
        return {**base_context, "unread_notifications_count": 0, "recent_notifications": []}

    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")
    unread_count = notifications.filter(is_read=False).count()
    return {
        **base_context,
        "unread_notifications_count": unread_count,
        "recent_notifications": notifications[:5],
    }
