import re

import pytest

from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
from channels.sessions import CookieMiddleware, SessionMiddlewareStack
from channels.testing import HttpCommunicator


class SimpleHttpApp(AsyncConsumer):
    """
    Barebones HTTP ASGI app for testing.
    """

    async def http_request(self, event):
        await database_sync_to_async(self.scope["session"].save)()
        assert self.scope["path"] == "/test/"
        assert self.scope["method"] == "GET"
        await self.send({"type": "http.response.start", "status": 200, "headers": []})
        await self.send({"type": "http.response.body", "body": b"test response"})


@pytest.mark.asyncio
async def test_set_cookie():
    message = {}
    CookieMiddleware.set_cookie(message, "Testing-Key", "testing-value")
    assert message == {
        "headers": [(b"Set-Cookie", b"Testing-Key=testing-value; Path=/; SameSite=lax")]
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_sessions():
    app = SimpleHttpApp()

    communicator = HttpCommunicator(SessionMiddlewareStack(app), "GET", "/test/")
    response = await communicator.get_response()
    headers = response.get("headers", [])

    assert len(headers) == 1
    name, value = headers[0]

    assert name == b"Set-Cookie"
    value = value.decode("utf-8")

    assert re.compile(r"sessionid=").search(value) is not None

    assert re.compile(r"expires=").search(value) is not None

    assert re.compile(r"HttpOnly").search(value) is not None

    assert re.compile(r"Max-Age").search(value) is not None

    assert re.compile(r"Path").search(value) is not None

    samesite = re.compile(r"SameSite=(\w+)").search(value)
    assert samesite is not None
    assert samesite.group(1) == "Lax"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_session_samesite(samesite, settings):
    app = SimpleHttpApp()

    communicator = HttpCommunicator(SessionMiddlewareStack(app), "GET", "/test/")
    response = await communicator.get_response()
    headers = response.get("headers", [])

    assert len(headers) == 1
    name, value = headers[0]

    assert name == b"Set-Cookie"
    value = value.decode("utf-8")

    samesite = re.compile(r"SameSite=(\w+)").search(value)
    assert samesite is not None
    assert samesite.group(1) == settings.SESSION_COOKIE_SAMESITE


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_session_samesite_invalid(samesite_invalid):
    app = SimpleHttpApp()

    communicator = HttpCommunicator(SessionMiddlewareStack(app), "GET", "/test/")

    with pytest.raises(AssertionError):
        await communicator.get_response()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_muliple_sessions():
    """
    Create two application instances and test then out of order to verify that
    separate scopes are used.
    """

    async def inner(scope, receive, send):
        send(scope["path"])

    class SimpleHttpApp(AsyncConsumer):
        async def http_request(self, event):
            await database_sync_to_async(self.scope["session"].save)()
            assert self.scope["method"] == "GET"
            await self.send(
                {"type": "http.response.start", "status": 200, "headers": []}
            )
            await self.send(
                {"type": "http.response.body", "body": self.scope["path"].encode()}
            )

    app = SessionMiddlewareStack(SimpleHttpApp.as_asgi())

    first_communicator = HttpCommunicator(app, "GET", "/first/")
    second_communicator = HttpCommunicator(app, "GET", "/second/")

    second_response = await second_communicator.get_response()
    assert second_response["body"] == b"/second/"

    first_response = await first_communicator.get_response()
    assert first_response["body"] == b"/first/"
