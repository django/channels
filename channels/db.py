from django.db import close_old_connections, connections

from asgiref.sync import SyncToAsync


class DatabaseSyncToAsync(SyncToAsync):
    """
    SyncToAsync version that cleans up old database connections.
    """

    def thread_handler(self, loop, *args, **kwargs):
        close_old_connections()
        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            close_old_connections()


class DatabaseSyncToAsyncForTests(SyncToAsync):
    def __init__(self, *args, **kwargs):
        self.main_thread_connections = {name: connections[name] for name in connections}
        super().__init__(*args, **kwargs)

    def _inherit_main_thread_connections(self):
        """Copy/use DB connections in atomic block from main thread.

        This is required for tests using Django's TestCase.
        """
        from django.db import connections

        for name in self.main_thread_connections:
            if self.main_thread_connections[name].in_atomic_block:
                connections[name] = self.main_thread_connections[name]
                connections[name].inc_thread_sharing()

    def _close_old_connections(self):
        """Like django.db.close_old_connections, but skipping in_atomic_block."""
        for conn in connections.all():
            if conn.in_atomic_block:
                continue
            conn.close_if_unusable_or_obsolete()

    def thread_handler(self, loop, *args, **kwargs):
        self._inherit_main_thread_connections()
        self._close_old_connections()
        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            self._close_old_connections()


# The class is TitleCased, but we want to encourage use as a callable/decorator
database_sync_to_async = DatabaseSyncToAsync
