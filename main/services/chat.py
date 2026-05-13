from django.db.models import Q
from django.http import Http404

from ..models import Booking, Chat, Message, Notification, Payment, UserProfile
from ..utils import broadcast_chat_message, create_notification, serialize_message


def get_or_create_chat_for_booking(booking):
    chat, _ = Chat.objects.get_or_create(
        booking=booking,
        defaults={"client": booking.client, "lawyer": booking.lawyer},
    )
    return chat


def _chat_access_queryset():
    return Chat.objects.select_related("client", "lawyer", "lawyer__category", "lawyer__user", "booking", "booking__payment")


def get_authorized_chat(user, chat_id):
    chat = _chat_access_queryset().filter(
        Q(client=user) | Q(lawyer__user=user),
        id=chat_id,
        lawyer__is_verified=True,
        lawyer__user__profile__role=UserProfile.Role.LAWYER,
        booking__status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
        booking__payment__payment_status=Payment.PaymentStatus.SUCCESS,
    ).first()
    if not chat:
        raise Http404("Chat not found.")
    return chat


def send_chat_message(chat, user, *, text="", file=None, client_temp_id=""):
    message = Message.objects.create(chat=chat, sender=user, text=text, file=file)
    Chat.objects.filter(id=chat.id).update(updated_at=message.timestamp)

    recipient = chat.lawyer.user if user == chat.client else chat.client
    create_notification(
        recipient,
        "New message",
        f"New chat message from {user.get_full_name() or user.username}.",
        f"/chat-room/{chat.id}/",
        notification_type=Notification.NotificationType.CHAT,
    )
    broadcast_chat_message(message, client_temp_id=client_temp_id)
    payload = serialize_message(message, user)
    if client_temp_id:
        payload["client_temp_id"] = client_temp_id
    return payload
