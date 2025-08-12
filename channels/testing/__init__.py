from channels.db import aclose_old_connections
from channels.signals import consumer_started, consumer_terminated, db_sync_to_async
from django.db import close_old_connections
from asgiref.testing import ApplicationCommunicator  # noqa
from .http import HttpCommunicator  # noqa
from .live import ChannelsLiveServerTestCase  # noqa
from .websocket import WebsocketCommunicator  # noqa

__all__ = [
    "ApplicationCommunicator",
    "HttpCommunicator",
    "ChannelsLiveServerTestCase",
    "WebsocketCommunicator",
    "ConsumerTestMixin",
]


class ConsumerTestMixin:
    """
    Mixin to be applied to Django `TestCase` or `TransactionTestCase` to ensure
    that database connections are not closed by consumers during test execution.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        consumer_started.disconnect(aclose_old_connections)
        consumer_terminated.disconnect(aclose_old_connections)
        db_sync_to_async.disconnect(close_old_connections)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        consumer_started.connect(aclose_old_connections)
        consumer_terminated.connect(aclose_old_connections)
        db_sync_to_async.connect(close_old_connections)

