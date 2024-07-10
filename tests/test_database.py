from django import db
from django.test import TestCase

from channels.db import database_sync_to_async
from channels.generic.http import AsyncHttpConsumer
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.testing import HttpCommunicator, WebsocketCommunicator


@database_sync_to_async
def basic_query():
    with db.connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1234")
        return cursor.fetchone()[0]


class WebsocketConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await basic_query()
        await self.accept("fun")


class HttpConsumer(AsyncHttpConsumer):
    async def handle(self, body):
        await basic_query()
        await self.send_response(
            200,
            b"",
            headers={b"Content-Type": b"text/plain"},
        )


class ConnectionClosingTests(TestCase):
    async def test_websocket(self):
        self.assertNotRegex(
            db.connections["default"].settings_dict.get("NAME"),
            "memorydb",
            "This bug only occurs when the database is materialized on disk",
        )
        communicator = WebsocketCommunicator(WebsocketConsumer.as_asgi(), "/")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        self.assertEqual(subprotocol, "fun")

    async def test_http(self):
        self.assertNotRegex(
            db.connections["default"].settings_dict.get("NAME"),
            "memorydb",
            "This bug only occurs when the database is materialized on disk",
        )
        communicator = HttpCommunicator(
            HttpConsumer.as_asgi(), method="GET", path="/test/"
        )
        connected = await communicator.get_response()
        self.assertTrue(connected)
