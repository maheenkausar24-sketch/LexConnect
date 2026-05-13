from django.db import models

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .audit import security_event
from .models import Booking, Chat, Payment, UserProfile


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        chat_id = self.scope["url_route"]["kwargs"].get("chat_id")
        try:
            self.chat_id = int(chat_id)
        except (TypeError, ValueError):
            await self.close(code=4400)
            return
        self.group_name = f"chat_{self.chat_id}"

        if not user.is_authenticated or not await self.user_can_access_chat(user.id, self.chat_id):
            security_event("websocket_chat_denied", actor=user if user.is_authenticated else None, chat_id=self.chat_id)
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def user_can_access_chat(self, user_id, chat_id):
        return Chat.objects.filter(id=chat_id).filter(
            models.Q(
                client_id=user_id,
                lawyer__is_verified=True,
                lawyer__user__profile__role=UserProfile.Role.LAWYER,
            )
            | models.Q(
                lawyer__user_id=user_id,
                lawyer__is_verified=True,
                lawyer__user__profile__role=UserProfile.Role.LAWYER,
            )
        ).filter(
            booking__status__in=[Booking.Status.CONFIRMED, Booking.Status.COMPLETED],
            booking__payment__payment_status=Payment.PaymentStatus.SUCCESS,
        ).exists()
