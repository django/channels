from concurrent.futures import ThreadPoolExecutor

from django.db import connections

from asgiref.sync import SyncToAsync

main_thread_connections = {name: connections[name] for name in connections}


def _inherit_main_thread_connections():
    """Copy/use DB connections in atomic block from main thread.

    This is required for tests using Django's TestCase.
    """
    for name in main_thread_connections:
        if main_thread_connections[name].in_atomic_block:
            connections[name] = main_thread_connections[name]
            connections[name].inc_thread_sharing()


class DatabaseSyncToAsync(SyncToAsync):
    """
    SyncToAsync version that cleans up old database connections.
    """

    executor = ThreadPoolExecutor(
        # TODO
        # max_workers=settings.N_SYNC_DATABASE_CONNECTIONS,
        thread_name_prefix="our-database-sync-to-async-",
        initializer=_inherit_main_thread_connections,
    )

    def _close_old_connections(self):
        """Like django.db.close_old_connections, but skipping in_atomic_block."""
        for conn in connections.all():
            if conn.in_atomic_block:
                continue
            conn.close_if_unusable_or_obsolete()

    def thread_handler(self, loop, *args, **kwargs):
        self._close_old_connections()
        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            self._close_old_connections()


# The class is TitleCased, but we want to encourage use as a callable/decorator
database_sync_to_async = DatabaseSyncToAsync
