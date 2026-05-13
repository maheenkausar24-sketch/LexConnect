from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import Notification
from ..rate_limit import rate_limit


@login_required
@rate_limit("notifications_action", limit=60, period=300)
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user)
    if request.method == "POST":
        notifications.filter(is_read=False).update(is_read=True, read_at=timezone.now())
        return redirect("notifications")
    unread_notifications = notifications.filter(is_read=False)
    read_notifications = notifications.filter(is_read=True)
    return render(
        request,
        "notifications.html",
        {
            "notifications": notifications,
            "unread_notifications": unread_notifications,
            "read_notifications": read_notifications,
            "unread_total": unread_notifications.count(),
            "read_total": read_notifications.count(),
        },
    )


@login_required
@rate_limit("notification_read", limit=120, period=300)
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at"])
    return redirect(notification.url or "notifications")
