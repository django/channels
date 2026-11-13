"""
ASGI routing that imports models without get_asgi_application().

Used to test ChannelsLiveServerTestCase under a fresh interpreter
(spawn, or forkserver, the default on Python 3.14): importing this
module must work even when Django has not been set up yet by the
caller, because the live server child process sets it up itself.
"""

from django.urls import path

from channels.routing import ProtocolTypeRouter, URLRouter
from tests.sample_project.sampleapp.consumers import LiveMessageConsumer

application = ProtocolTypeRouter(
    {
        "websocket": URLRouter(
            [
                path(
                    "ws/message/",
                    LiveMessageConsumer.as_asgi(),
                    name="live_message_counter",
                ),
            ]
        ),
    }
)
