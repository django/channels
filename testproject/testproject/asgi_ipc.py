import os
from channels.asgi import get_channel_layer
from asgi_ipc import IPCChannelLayer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testproject.settings.channels_ipc")
channel_layer = IPCChannelLayer(
    prefix="test-ipc",
    channel_memory=200 * 1024 * 1024,
)
