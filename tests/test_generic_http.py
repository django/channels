import json

import pytest
from django.test import override_settings

from channels.generic.http import AsyncHttpConsumer
from channels.layers import get_channel_layer
from channels.testing import HttpCommunicator


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

    app = TestConsumer()

    # Open a connection
    communicator = HttpCommunicator(
        app,
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

        channel_layer_alias = "testlayer"

        async def handle(self, body):
            # Add consumer to a known test group that we will use to send events to.
            await self.channel_layer.group_add("test_group", self.channel_name)
            await self.send_headers(
                status=200, headers=[(b"Content-Type", b"application/json")]
            )

        async def send_to_long_poll(self, event):
            received_data = str(event["data"]).encode("utf8")
            # We just echo what we receive, and close the response.
            await self.send_body(received_data, more_body=False)

    channel_layers_setting = {
        "testlayer": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

    with override_settings(CHANNEL_LAYERS=channel_layers_setting):
        # Open a connection
        communicator = HttpCommunicator(
            TestConsumer,
            method="POST",
            path="/test/",
            body=json.dumps({"value": 42, "anything": False}).encode("utf-8"),
        )

        # We issue the HTTP request
        await communicator.send_request()

        # Gets the response start (status and headers)
        response_start = await communicator.get_response_start(timeout=1)

        # Make sure that the start of the response looks good so far.
        assert response_start["status"] == 200
        assert response_start["headers"] == [(b"Content-Type", b"application/json")]

        # Send now a message to the consumer through the channel layer. Using the known test_group.
        channel_layer = get_channel_layer("testlayer")
        await channel_layer.group_send(
            "test_group",
            {"type": "send.to.long.poll", "data": "hello from channel layer"},
        )

        # Now we should be able to get the message back on the remaining chunk of body.
        body = await communicator.get_body_chunk(timeout=1)
        assert body == b"hello from channel layer"
