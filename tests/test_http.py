import re
from importlib import import_module

import django
import pytest
from django.conf import settings

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
async def test_multiple_sessions():
    """
    Create two application instances and test then out of order to verify that
    separate scopes are used.
    """

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


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_session_saves():
    """
    Saves information to a session and validates that it actually saves to the backend
    """

    class SimpleHttpApp(AsyncConsumer):
        @database_sync_to_async
        def set_fav_color(self):
            self.scope["session"]["fav_color"] = "blue"

        async def http_request(self, event):
            if django.VERSION >= (5, 1):
                await self.scope["session"].aset("fav_color", "blue")
            else:
                await self.set_fav_color()
            await self.send(
                {"type": "http.response.start", "status": 200, "headers": []}
            )
            await self.send(
                {
                    "type": "http.response.body",
                    "body": self.scope["session"].session_key.encode(),
                }
            )

    app = SessionMiddlewareStack(SimpleHttpApp.as_asgi())

    communicator = HttpCommunicator(app, "GET", "/first/")

    response = await communicator.get_response()
    session_key = response["body"].decode()

    SessionStore = import_module(settings.SESSION_ENGINE).SessionStore
    session = SessionStore(session_key=session_key)
    if django.VERSION >= (5, 1):
        session_fav_color = await session.aget("fav_color")
    else:
        session_fav_color = await database_sync_to_async(session.get)("fav_color")

    assert session_fav_color == "blue"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_session_save_update_error():
    """
    Intentionally deletes the session to ensure that SuspiciousOperation is raised
    """

    async def inner(scope, receive, send):
        send(scope["path"])

    class SimpleHttpApp(AsyncConsumer):
        @database_sync_to_async
        def set_fav_color(self):
            self.scope["session"]["fav_color"] = "blue"

        async def http_request(self, event):
            # Create a session as normal:
            await database_sync_to_async(self.scope["session"].save)()

            # Then simulate it's deletion from somewhere else:
            # (e.g. logging out from another request)
            SessionStore = import_module(settings.SESSION_ENGINE).SessionStore
            session = SessionStore(session_key=self.scope["session"].session_key)
            await database_sync_to_async(session.flush)()

            await self.send(
                {"type": "http.response.start", "status": 200, "headers": []}
            )

    app = SessionMiddlewareStack(SimpleHttpApp.as_asgi())

    communicator = HttpCommunicator(app, "GET", "/first/")

    with pytest.raises(django.core.exceptions.SuspiciousOperation):
        await communicator.get_response()
