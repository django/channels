import itertools
from concurrent.futures import TimeoutError
from urllib.parse import unquote

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from channels.auth import AuthMiddlewareStack, get_user
from channels.consumer import AsyncConsumer
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer, WebsocketConsumer
from channels.testing import HttpCommunicator, WebsocketCommunicator
from channels.testing.base import AuthCommunicator

# A counter used to guarantee unique database fields
counter = itertools.count()


@database_sync_to_async
def create_user(username=None, password="password", **kwargs):
    """
    Returns a new user instance.
    """
    if username is None:
        # Needed because the database isn't cleaned up after each test
        # in an async context
        username = "u{}".format(next(counter))
    return get_user_model().objects.create_user(username, password, **kwargs)


@pytest.fixture
async def user(db):
    """
    Unique user fixture.
    """
    return await create_user()


class SimpleHttpApp(AsyncConsumer):
    """
    Barebones HTTP ASGI app for testing.
    """

    async def http_request(self, event):
        assert self.scope["path"] == "/test/"
        assert self.scope["method"] == "GET"
        await self.send({
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        })
        await self.send({
            "type": "http.response.body",
            "body": b"test response",
        })


@pytest.mark.parametrize(
    "application",
    (SimpleHttpApp, AuthMiddlewareStack(SimpleHttpApp)),
)
@pytest.mark.asyncio
async def test_auth_communicator(user, application):
    """
    Tests that the authentication communicator methods work.
    """
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/test/",
        "headers": [],
    }
    communicator = AuthCommunicator(application, scope, user=user)
    assert communicator.scope["user"] is user
    assert "session" in communicator.scope
    assert await get_user(communicator.scope) == AnonymousUser()
    assert await get_user(communicator.instance.scope) == AnonymousUser()
    # Login
    await communicator.login()
    assert await get_user(communicator.scope) == user
    assert await get_user(communicator.instance.scope) == user
    # Logout
    await communicator.logout()
    assert communicator.scope["user"] == AnonymousUser()
    assert await get_user(communicator.scope) == AnonymousUser()
    app_user = AnonymousUser() if application is SimpleHttpApp else user
    assert communicator.instance.scope["user"] == app_user
    assert await get_user(communicator.instance.scope) == AnonymousUser()


@pytest.mark.asyncio
async def test_http_communicator():
    """
    Tests that the HTTP communicator class works at a basic level.
    """
    communicator = HttpCommunicator(SimpleHttpApp, "GET", "/test/")
    response = await communicator.get_response()
    assert response["body"] == b"test response"
    assert response["status"] == 200


@pytest.mark.asyncio
async def test_http_communicator_with_user(user):
    """
    Tests that the HTTP communicator class works with a user parameter.
    """
    communicator = HttpCommunicator(SimpleHttpApp, "GET", "/test/", user=user)
    response = await communicator.get_response()
    assert response["status"] == 200
    assert await get_user(communicator.scope) == user


class SimpleWebsocketApp(WebsocketConsumer):
    """
    Barebones WebSocket ASGI app for testing.
    """

    def connect(self):
        assert self.scope["path"] == "/testws/"
        self.accept()

    def receive(self, text_data=None, bytes_data=None):
        self.send(text_data=text_data, bytes_data=bytes_data)


class ErrorWebsocketApp(WebsocketConsumer):
    """
    Barebones WebSocket ASGI app for error testing.
    """

    def receive(self, text_data=None, bytes_data=None):
        pass


@pytest.mark.asyncio
async def test_websocket_communicator():
    """
    Tests that the WebSocket communicator class works at a basic level.
    """
    communicator = WebsocketCommunicator(SimpleWebsocketApp, "/testws/")
    # Test connection
    connected, subprotocol = await communicator.connect()
    assert connected
    assert subprotocol is None
    # Test sending text
    await communicator.send_to(text_data="hello")
    response = await communicator.receive_from()
    assert response == "hello"
    # Test sending bytes
    await communicator.send_to(bytes_data=b"w\0\0\0")
    response = await communicator.receive_from()
    assert response == b"w\0\0\0"
    # Test sending JSON
    await communicator.send_json_to({"hello": "world"})
    response = await communicator.receive_json_from()
    assert response == {"hello": "world"}
    # Close out
    await communicator.disconnect()


class AuthWebsocketApp(AsyncWebsocketConsumer):
    """
    WebSocket ASGI app with required login for testing.
    """

    async def connect(self):
        assert self.scope["user"].is_authenticated
        user = await get_user(self.scope)
        assert user.is_authenticated
        await self.accept()


@pytest.mark.asyncio
async def test_websocket_communicator_with_user(user):
    """
    Tests that the WebSocket communicator class works with a user parameter.
    """
    communicator = WebsocketCommunicator(AuthWebsocketApp, "/ws/", user=user)
    connected, subprotocol = await communicator.connect()
    assert connected
    assert await get_user(communicator.scope) == user
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_websocket_communicator_with_user_and_middleware(user):
    """
    Tests that the WebSocket communicator works with middleware and
    a user parameter.
    """
    communicator = WebsocketCommunicator(
        AuthMiddlewareStack(AuthWebsocketApp),
        "/testws/",
        user=user,
    )
    connected, subprotocol = await communicator.connect()
    assert connected
    assert await get_user(communicator.scope) == user
    await communicator.disconnect()


@pytest.mark.asyncio
async def test_timeout_disconnect():
    """
    Tests that disconnect() still works after a timeout.
    """
    communicator = WebsocketCommunicator(ErrorWebsocketApp, "/testws/")
    # Test connection
    connected, subprotocol = await communicator.connect()
    assert connected
    assert subprotocol is None
    # Test sending text (will error internally)
    await communicator.send_to(text_data="hello")
    with pytest.raises(TimeoutError):
        await communicator.receive_from()
    # Close out
    await communicator.disconnect()


class ConnectionScopeValidator(WebsocketConsumer):
    """
    Tests ASGI specification for the connection scope.
    """
    def connect(self):
        assert self.scope["type"] == "websocket"
        # check if path is a unicode string
        assert isinstance(self.scope["path"], str)
        # check if path has percent escapes decoded
        assert self.scope["path"] == unquote(self.scope["path"])
        # check if query_string is a bytes sequence
        assert isinstance(self.scope["query_string"], bytes)
        self.accept()


paths = [
    "user:pass@example.com:8080/p/a/t/h?query=string#hash",
    "wss://user:pass@example.com:8080/p/a/t/h?query=string#hash",
    "ws://www.example.com/%E9%A6%96%E9%A1%B5/index.php?foo=%E9%A6%96%E9%A1%B5&spam=eggs",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", paths)
async def test_connection_scope(path):
    """
    Tests ASGI specification for the the connection scope.
    """
    communicator = WebsocketCommunicator(ConnectionScopeValidator, path)
    connected, _ = await communicator.connect()
    assert connected
    await communicator.disconnect()
