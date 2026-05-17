import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ..forms import MessageForm
from ..models import Booking
from ..rate_limit import rate_limit
from ..services.auth import get_dashboard_route, is_client_user, is_lawyer_user
from ..services.bookings import eligible_booking_for_chat
from ..services.chat import booking_is_chat_eligible, ensure_chat_for_booking, get_authorized_chat, send_chat_message
from ..services.lawyers import visible_lawyers_queryset
from ..utils import serialize_message


chat_logger = logging.getLogger("main.realtime")


def _booking_chat_redirect(user):
    if is_lawyer_user(user):
        return "lawyer_chats"
    if is_client_user(user):
        return "client_chats"
    return get_dashboard_route(user)


def _get_booking_for_chat_access(user, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("client", "lawyer", "lawyer__user", "payment", "chat"),
        id=booking_id,
    )
    if booking.client_id == user.id:
        return booking
    if is_lawyer_user(user) and booking.lawyer_id == user.lawyer_profile.id:
        return booking
    return None


@login_required
def start_chat_for_booking(request, booking_id):
    booking = _get_booking_for_chat_access(request.user, booking_id)
    if booking is None:
        messages.error(request, "You do not have access to this consultation chat.")
        return redirect(_booking_chat_redirect(request.user))

    if not booking_is_chat_eligible(booking):
        payment_status = getattr(getattr(booking, "payment", None), "payment_status", "unknown")
        chat_logger.info(
            {
                "event": "chat_access_denied",
                "booking_id": booking.id,
                "user_id": request.user.id,
                "booking_status": booking.status,
                "payment_status": payment_status,
            }
        )
        if payment_status == "success" and booking.status == Booking.Status.PENDING:
            messages.error(request, "Payment succeeded but the booking is not confirmed yet. Refresh in a moment or contact support.")
        else:
            messages.error(request, "Chat unlocks after payment is successful and the booking is confirmed.")
        if is_client_user(request.user):
            return redirect("client_bookings")
        return redirect("lawyer_bookings")

    chat = ensure_chat_for_booking(booking)
    chat_logger.info(
        {
            "event": "chat_opened",
            "chat_id": chat.id,
            "booking_id": booking.id,
            "user_id": request.user.id,
        }
    )
    return redirect("chat_page", chat_id=chat.id)


@login_required
def start_chat(request, lawyer_id):
    if not is_client_user(request.user):
        messages.info(request, "Only clients can open consultation chats from lawyer profiles.")
        return redirect(get_dashboard_route(request.user))

    lawyer = get_object_or_404(visible_lawyers_queryset(), id=lawyer_id)
    booking = eligible_booking_for_chat(request.user, lawyer)
    if not booking:
        messages.error(request, "Chat becomes available after payment is successful and the booking is confirmed.")
        return redirect("lawyer_profile", lawyer_id=lawyer.id)

    return redirect("start_chat_for_booking", booking_id=booking.id)


@login_required
def user_chats(request):
    return redirect("lawyer_chats" if is_lawyer_user(request.user) else "client_chats")


@login_required
def chat_page(request, chat_id):
    chat = get_authorized_chat(request.user, chat_id)
    if chat.booking:
        ensure_chat_for_booking(chat.booking)
    chat.messages.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
    return render(
        request,
        "chat.html",
        {
            "chat": chat,
            "chat_messages": chat.messages.select_related("sender"),
            "ws_path": f"/ws/chat/{chat.id}/",
            "send_message_url": reverse("send_message", args=[chat.id]),
            "messages_url": reverse("chat_messages", args=[chat.id]),
        },
    )


@login_required
@rate_limit("chat_poll", limit=120, period=60, methods=("GET",), json_response=True)
def chat_messages(request, chat_id):
    chat = get_authorized_chat(request.user, chat_id)
    after = request.GET.get("after", "").strip()
    messages_qs = chat.messages.select_related("sender")

    if after.isdigit():
        messages_qs = messages_qs.filter(id__gt=int(after))

    payload = [serialize_message(message, request.user) for message in messages_qs]
    messages_qs.exclude(sender=request.user).filter(is_read=False).update(is_read=True)
    return JsonResponse({"messages": payload})


@login_required
@rate_limit("chat_message", limit=20, period=60, json_response=True)
def send_message(request, chat_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST only."}, status=405)

    chat = get_authorized_chat(request.user, chat_id)
    form = MessageForm(request.POST, request.FILES)
    client_temp_id = request.POST.get("client_temp_id", "").strip()

    if not form.is_valid():
        return JsonResponse({"error": form.first_error() or "Unable to send message."}, status=400)

    payload = send_chat_message(
        chat,
        request.user,
        text=form.cleaned_data["text"],
        file=form.cleaned_data["file"],
        client_temp_id=client_temp_id,
    )
    return JsonResponse({"message": payload})
