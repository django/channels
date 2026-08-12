import asyncio

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
            self.is_streaming = True
            await self.send_headers(
                headers=[
                    (b"Cache-Control", b"no-cache"),
                    (b"Content-Type", b"text/event-stream"),
                    (b"Transfer-Encoding", b"chunked"),
                ]
            )
            asyncio.get_event_loop().create_task(self.stream())

        async def stream(self):
            for n in range(0, 3):
                if not self.is_streaming:
                    break
                payload = "data: %d\n\n" % (n + 1)
                await self.send_body(payload.encode("utf-8"), more_body=True)
                await asyncio.sleep(0.2)
            await self.send_body(b"")

        async def disconnect(self):
            self.is_streaming = False

    # Open a connection
    communicator = HttpCommunicator(TestConsumer, method="GET", path="/test/", body=b"")
    response = await communicator.get_response()
    assert response["body"] == b"data: 1\n\ndata: 2\n\ndata: 3\n\n"
    assert response["status"] == 200
