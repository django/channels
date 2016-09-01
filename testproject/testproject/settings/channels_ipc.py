# Settings for channels specifically
from testproject.settings.base import *


INSTALLED_APPS += (
    'channels',
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": 'testproject.asgi_for_ipc.channel_layer',
        "ROUTING": "testproject.urls.channel_routing",
    },
}
