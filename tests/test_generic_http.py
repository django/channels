import asyncio
import json

import pytest

from channels.generic.http import AsyncHttpConsumer
from channels.testing import HttpCommunicator
from django.test import override_settings
from channels.layers import get_channel_layer


@pytest.mark.asyncio
async def test_async_http_consumer():
    """
    Tests that AsyncHttpConsumer is implemented correctly.
    """

    class TestConsumer(AsyncHttpConsumer):
        async def handle(self, body):
            data = json.loads(body.decode("utf-8"))
            await self.send_response(
                200,
                json.dumps({"value": data["value"]}).encode("utf-8"),
                headers={b"Content-Type": b"application/json"},
            )

    # Open a connection
    communicator = HttpCommunicator(
        TestConsumer,
        method="POST",
        path="/test/",
        body=json.dumps({"value": 42, "anything": False}).encode("utf-8"),
    )
    response = await communicator.get_response()
    assert response["body"] == b'{"value": 42}'
    assert response["status"] == 200
    assert response["headers"] == [(b"Content-Type", b"application/json")]


@pytest.mark.asyncio
async def test_async_http_consumer_with_channel_layer():
    """
    Tests that AsyncHttpConsumer is implemented correctly.
    """

    class TestConsumer(AsyncHttpConsumer):
        """
        Abstract consumer that provides a method that handles running a command and getting a response on a
        device.
        """

        groups = ['test_group']

        async def handle(self, body):
            print("Latest Channel ID: ")
            await self.send_headers(
                status=200,
                headers=[
                    (b"Content-Type", b"application/json"),
                ],
            )

        async def send_to_long_poll(self, event):
            print("RunCommandConsumer: Event received on send to long poll.")
            command_output = str(event['data']).encode('utf8')
            await self.send_body(command_output, more_body=False)

    channel_layers_setting = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }
    with override_settings(CHANNEL_LAYERS=channel_layers_setting):
        # Open a connection
        communicator = HttpCommunicator(
            TestConsumer,
            method="POST",
            path="/test/",
            body=json.dumps({"value": 42, "anything": False}).encode("utf-8"),
        )

        def send_to_channel_layer():
            print("send to channel layer called")
            channel_layer = get_channel_layer()
            # Test that the websocket channel was added to the group on connect
            message = {"type": "send.to.long.poll", "data": "hello"}
            asyncio.ensure_future(channel_layer.group_send("chat", message))

        asyncio.get_event_loop().call_later(3, send_to_channel_layer)
        print("Making http requests.")
        response = await communicator.get_response(timeout=10)
        assert True
