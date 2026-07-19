from django.dispatch import Signal

consumer_started = Signal()
consumer_terminated = Signal()
db_sync_to_async = Signal()
