import asyncio

import pytest

from channels.generic.websocket import AsyncWebsocketConsumer, WebsocketMultiplexer
from channels.testing import WebsocketCommunicator


class EchoConsumer(AsyncWebsocketConsumer):
    """
    Basic echo consumer for testing.
    """

    results = {}

    async def connect(self):
        self.results["connected"] = True
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        await self.send(text_data=text_data, bytes_data=bytes_data)

    async def disconnect(self, code):
        self.results["disconnected"] = True


@pytest.mark.asyncio
async def test_multiplexer():
    """
    Tests that WebsocketConsumer is implemented correctly.
    """
    text_multiplexer = WebsocketMultiplexer({
        "echo": EchoConsumer,
    })
    # Test a normal connection
    communicator = WebsocketCommunicator(text_multiplexer, "/")
    connected, _ = await communicator.connect()
    await asyncio.sleep(0.5)
    assert connected
    assert "connected" in EchoConsumer.results
    # Test sending basic payload
    # await communicator.send_json_to({"stream": "echo", "payload": 42})
    # response = await communicator.receive_json_from()
    # assert response == {"stream": "echo", "payload": 42}
    # # Close out
    # await communicator.disconnect()
    # assert "disconnected" in EchoConsumer.results
