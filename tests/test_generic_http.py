import json

import pytest

from channels.generic.http import AsyncHttpConsumer
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
async def test_per_scope_consumers():
    """
    Tests that a distinct consumer is used per scope, with AsyncHttpConsumer as
    the example consumer class.
    """

    class TestConsumer(AsyncHttpConsumer):
        async def handle(self, body):
            body = f"{self.__class__.__name__} {id(self)}"

            await self.send_response(
                200,
                body.encode("utf-8"),
                headers={b"Content-Type": b"text/plain"},
            )

    app = TestConsumer.as_asgi()

    # Open a connection
    communicator = HttpCommunicator(app, method="GET", path="/test/")
    response = await communicator.get_response()
    assert response["status"] == 200

    # And another one.
    communicator = HttpCommunicator(app, method="GET", path="/test2/")
    second_response = await communicator.get_response()
    assert second_response["status"] == 200

    assert response["body"] != second_response["body"]
