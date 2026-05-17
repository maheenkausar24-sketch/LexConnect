import logging

from django.db.models import Q
from django.http import Http404

from ..models import Booking, Chat, Message, Notification, Payment, UserProfile
from ..utils import broadcast_chat_message, create_notification, serialize_message
from .bookings import BOOKING_CHAT_STATUSES


chat_logger = logging.getLogger("main.realtime")


def booking_is_chat_eligible(booking):
    payment = getattr(booking, "payment", None)
    return bool(
        booking.status in BOOKING_CHAT_STATUSES
        and payment is not None
        and payment.payment_status == Payment.PaymentStatus.SUCCESS
    )


def get_or_create_chat_for_booking(booking):
    chat, created = Chat.objects.get_or_create(
        booking=booking,
        defaults={"client": booking.client, "lawyer": booking.lawyer},
    )
    update_fields = []
    if chat.client_id != booking.client_id:
        chat.client = booking.client
        update_fields.append("client")
    if chat.lawyer_id != booking.lawyer_id:
        chat.lawyer = booking.lawyer
        update_fields.append("lawyer")
    if update_fields:
        update_fields.append("updated_at")
        chat.save(update_fields=update_fields)
    if created:
        chat_logger.info(
            {
                "event": "chat_created_for_booking",
                "chat_id": chat.id,
                "booking_id": booking.id,
                "client_id": booking.client_id,
                "lawyer_id": booking.lawyer_id,
            }
        )
    return chat


def ensure_chat_for_booking(booking):
    if not booking_is_chat_eligible(booking):
        chat_logger.info(
            {
                "event": "chat_not_eligible",
                "booking_id": booking.id,
                "booking_status": booking.status,
                "payment_status": getattr(getattr(booking, "payment", None), "payment_status", None),
            }
        )
        return None
    return get_or_create_chat_for_booking(booking)


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
