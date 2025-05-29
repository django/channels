"""
ASGI config for sample_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

from django.core.asgi import get_asgi_application
from django.urls import path

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from tests.sample_project.sampleapp.consumers import LiveMessageConsumer

application = ProtocolTypeRouter(
    {
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(
                    [
                        path(
                            "ws/message/",
                            LiveMessageConsumer.as_asgi(),
                            name="live_message_counter",
                        ),
                    ]
                )
            )
        ),
        "http": get_asgi_application(),
    }
)
