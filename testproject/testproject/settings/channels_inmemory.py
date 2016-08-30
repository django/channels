# Settings for channels specifically
from testproject.settings.base import *

INSTALLED_APPS += (
    'channels',
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "asgiref.inmemory.channel_layer",
        "ROUTING": "testproject.urls.channel_routing",
    },
}
