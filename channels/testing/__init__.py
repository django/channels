import asyncio
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from functools import wraps

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
    "keep_db_open",
]


class DatabaseWrapper(AbstractAsyncContextManager, AbstractContextManager):
    """
    Wrapper which can be used as both context-manager or decorator to ensure
    that database connections are not closed during test execution.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._counter = 0

    def _disconnect(self):
        if self._counter == 0:
            consumer_started.disconnect(aclose_old_connections)
            consumer_terminated.disconnect(aclose_old_connections)
            db_sync_to_async.disconnect(close_old_connections)

        self._counter += 1

    def _connect(self):
        self._counter -= 1
        if self._counter <= 0:
            consumer_started.connect(aclose_old_connections)
            consumer_terminated.connect(aclose_old_connections)
            db_sync_to_async.connect(close_old_connections)

    def __enter__(self):
        self._disconnect()

    def __exit__(self, exc_type, exc_value, traceback):
        self._disconnect()

    # in async mode also use a lock to reduce concurrency issue
    # with the inner counter value
    async def __aenter__(self):
        async with self._lock:
            self._disconnect()

    async def __aexit__(self, exc_type, exc_value, traceback):
        async with self._lock:
            self._connect()

    def __call__(self, func):
        if asyncio.iscoroutinefunction(func):

            async def wrapper(*args, **kwargs):
                async with self:
                    return await func(*args, **kwargs)

        else:

            def wrapper(*args, **kwargs):
                with self:
                    return func(*args, **kwargs)

        return wraps(func)(wrapper)


keep_db_open = DatabaseWrapper()
