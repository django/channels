from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Message


class LiveMessageConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("live_message", self.channel_name)
        await self.accept()
        await self.send_current_state()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("live_message", self.channel_name)

    @database_sync_to_async
    def _fetch_state(self):
        qs = Message.objects.order_by("-created")
        return {
            "count": qs.count(),
            "messages": list(qs.values("id", "title", "message")),
        }

    @database_sync_to_async
    def _create_message(self, title, text):
        Message.objects.create(title=title, message=text)

    @database_sync_to_async
    def _delete_message(self, msg_id):
        Message.objects.filter(id=msg_id).delete()

    async def receive_json(self, content):
        action = content.get("action", "create")

        if action == "create":
            title = content.get("title", "")
            text = content.get("message", "")
            await self._create_message(title=title, text=text)

        elif action == "delete":
            msg_id = content.get("id")
            await self._delete_message(msg_id)

        # After any action, rebroadcast current state
        await self.send_current_state()

    async def send_current_state(self):
        state = await self._fetch_state()
        await self.channel_layer.group_send(
            "live_message", {"type": "broadcast_message", **state}
        )

    async def broadcast_message(self, event):
        await self.send_json(
            {
                "count": event["count"],
                "messages": event["messages"],
            }
        )
