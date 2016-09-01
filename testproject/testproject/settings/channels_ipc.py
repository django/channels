# Settings for channels specifically
from testproject.settings.base import *
from testproject.asgi_for_ipc import channel_layer


INSTALLED_APPS += (
    'channels',
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": channel_layer,
        "ROUTING": "testproject.urls.channel_routing",
    },
}
