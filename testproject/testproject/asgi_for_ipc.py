import os
from channels.asgi import get_channel_layer
import asgi_ipc

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testproject.settings.channels_ipc")
channel_layer = asgi_ipc.IPCChannelLayer(
    prefix="test",
    channel_memory=200 * 1024 * 1024,
)
