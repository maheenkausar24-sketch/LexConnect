from datetime import timedelta
from pathlib import Path

from asgiref.sync import async_to_sync
from django.conf import settings
from channels.layers import get_channel_layer
from django.urls import reverse
from django.utils import timezone

from .models import Lawyer, Notification, UserProfile


ONLINE_WINDOW = timedelta(minutes=5)


def ensure_profile(user, *, is_lawyer=None):
    role = None
    if is_lawyer is not None:
        role = UserProfile.Role.LAWYER if is_lawyer else UserProfile.Role.CLIENT
    return ensure_profile_role(user, role=role)


def ensure_profile_role(user, *, role=None):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if role is not None and profile.role != role:
        profile.role = role
        profile.save(update_fields=["role"])
    return profile


def is_lawyer_account(user):
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    profile = ensure_profile_role(user)
    return profile.role == UserProfile.Role.LAWYER and hasattr(user, "lawyer_profile")


def mark_user_online(user):
    profile = ensure_profile_role(user)
    profile.is_online = True
    profile.last_seen = timezone.now()
    profile.save(update_fields=["is_online", "last_seen"])
    Lawyer.objects.filter(user=user).update(is_online=True)


def mark_user_offline(user):
    profile = ensure_profile_role(user)
    profile.is_online = False
    profile.last_seen = timezone.now()
    profile.save(update_fields=["is_online", "last_seen"])
    Lawyer.objects.filter(user=user).update(is_online=False)


def mark_stale_users_offline():
    threshold = timezone.now() - ONLINE_WINDOW
    stale_profiles = UserProfile.objects.filter(is_online=True, last_seen__lt=threshold)
    stale_user_ids = list(stale_profiles.values_list("user_id", flat=True))
    stale_profiles.update(is_online=False)
    if stale_user_ids:
        Lawyer.objects.filter(user_id__in=stale_user_ids).update(is_online=False)


def create_notification_record(user, title, message, url="", *, notification_type=Notification.NotificationType.GENERAL, priority=Notification.Priority.NORMAL):
    if not user:
        return None
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        url=url,
        notification_type=notification_type,
        priority=priority,
    )


def create_notification(user, title, message, url="", *, notification_type=Notification.NotificationType.GENERAL, priority=Notification.Priority.NORMAL):
    if not user:
        return None
    if getattr(settings, "LEXCONNECT_ASYNC_NOTIFICATIONS", False):
        from .tasks import create_notification_task

        return create_notification_task.delay(user.id, title, message, url, notification_type, priority)
    return create_notification_record(
        user,
        title,
        message,
        url,
        notification_type=notification_type,
        priority=priority,
    )


def serialize_message(message, current_user=None):
    file_name = message.file.name.split("/")[-1] if message.file else ""
    file_ext = Path(file_name.lower()).suffix
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
    return {
        "id": message.id,
        "text": message.text,
        "file_url": reverse("protected_chat_file", args=[message.id]) if message.file else "",
        "file_name": file_name,
        "file_is_image": file_ext in image_extensions,
        "timestamp": timezone.localtime(message.timestamp).strftime("%d %b %I:%M %p"),
        "sender_id": message.sender_id,
        "sender_name": message.sender.get_full_name() or message.sender.username,
        "is_self": current_user.id == message.sender_id if current_user else False,
    }


def broadcast_chat_message(message, *, client_temp_id=""):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    payload = serialize_message(message)
    if client_temp_id:
        payload["client_temp_id"] = client_temp_id
    async_to_sync(channel_layer.group_send)(
        f"chat_{message.chat_id}",
        {
            "type": "chat.message",
            "payload": payload,
        },
    )
