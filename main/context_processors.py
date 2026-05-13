from .models import Notification


def notification_summary(request):
    if not request.user.is_authenticated:
        return {"unread_notifications_count": 0, "recent_notifications": []}

    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")
    unread_count = notifications.filter(is_read=False).count()
    return {
        "unread_notifications_count": unread_count,
        "recent_notifications": notifications[:5],
    }
