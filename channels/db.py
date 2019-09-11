import django
from django.db import connections

from asgiref.sync import SyncToAsync

HAS_INC_THREAD_SHARING = django.VERSION >= (2, 2)


class DatabaseSyncToAsync(SyncToAsync):
    """
    SyncToAsync version that cleans up old database connections.
    """
    def __init__(self, *args, **kwargs):
        self.main_thread_connections = {name: connections[name] for name in connections}
        super().__init__(*args, **kwargs)

    def _inherit_main_thread_connections(self):
        """Copy/use DB connections in atomic block from main thread.

        This is required for tests using Django's TestCase.
        """
        restore_allow_thread_sharing = []

        for name in self.main_thread_connections:
            if self.main_thread_connections[name].in_atomic_block:
                connections[name] = self.main_thread_connections[name]
                if HAS_INC_THREAD_SHARING:
                    connections[name].inc_thread_sharing()
                elif not connections[name].allow_thread_sharing:
                    restore_allow_thread_sharing.append(name)
                    connections[name].allow_thread_sharing = True
        return restore_allow_thread_sharing

    def _close_old_connections(self):
        """Like django.db.close_old_connections, but skipping in_atomic_block.

        Ref: https://github.com/django/django/pull/11769
        """
        for conn in connections.all():
            if not conn.in_atomic_block:
                conn.close_if_unusable_or_obsolete()

    def thread_handler(self, loop, *args, **kwargs):
        restore_allow_thread_sharing = self._inherit_main_thread_connections()
        self._close_old_connections()
        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            self._close_old_connections()
            for name in restore_allow_thread_sharing:
                connections[name].allow_thread_sharing = False


# The class is TitleCased, but we want to encourage use as a callable/decorator
database_sync_to_async = DatabaseSyncToAsync
