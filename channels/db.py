from asgiref.sync import SyncToAsync, sync_to_async
from django.db import close_old_connections
from .signals import consumer_started, consumer_terminated, db_sync_to_async


class DatabaseSyncToAsync(SyncToAsync):
    """
    SyncToAsync version that cleans up old database connections when it exits.
    """

    def thread_handler(self, loop, *args, **kwargs):
        db_sync_to_async.send(sender=self.__class__, start=True)
        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            db_sync_to_async.send(sender=self.__class__, start=False)


# The class is TitleCased, but we want to encourage use as a callable/decorator
database_sync_to_async = DatabaseSyncToAsync


async def aclose_old_connections(**kwargs):
    return await sync_to_async(close_old_connections)()


consumer_started.connect(aclose_old_connections)
consumer_terminated.connect(aclose_old_connections)
db_sync_to_async.connect(close_old_connections)
