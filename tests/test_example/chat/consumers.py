from channels.generic.websocket import AsyncJsonWebsocketConsumer
from chat.utils import ComplexObject


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.complex_object = ComplexObject()
        await self.accept()

    async def receive_json(self, content):
        action = content.get("action")
        if action == "special":
            data = self.complex_object.get_complex_data()
            await self.send_json({"data": data})
        else:
            # Echo
            await self.send_json(content)
