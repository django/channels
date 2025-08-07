from contextlib import asynccontextmanager

from asgiref.testing import ApplicationCommunicator as BaseApplicationCommunicator
from channels.db import aclose_old_connections
from channels.signals import consumer_started, consumer_terminated, db_sync_to_async
from django.db import close_old_connections


class ApplicationCommunicator(BaseApplicationCommunicator):

    @asynccontextmanager
    async def handle_db(self):
        consumer_started.disconnect(aclose_old_connections)
        consumer_terminated.disconnect(aclose_old_connections)
        db_sync_to_async.disconnect(close_old_connections)
        try:
            yield
        finally:
            consumer_started.connect(aclose_old_connections)
            consumer_terminated.connect(aclose_old_connections)
            db_sync_to_async.connect(close_old_connections)
