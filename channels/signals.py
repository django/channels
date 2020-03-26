from django.dispatch import Signal

from channels.db import _close_old_connections

consumer_started = Signal(providing_args=["environ"])
consumer_finished = Signal()

# Connect connection closer to consumer finished as well
consumer_finished.connect(_close_old_connections)
