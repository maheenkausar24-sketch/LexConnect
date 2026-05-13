from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import Notification


@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user)
    if request.method == "POST":
        notifications.filter(is_read=False).update(is_read=True, read_at=timezone.now())
        return redirect("notifications")
    return render(request, "notifications.html", {"notifications": notifications})


@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at"])
    return redirect(notification.url or "notifications")
