from django.urls import path

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from chat.consumers import ChatConsumer

application = ProtocolTypeRouter(
    {"websocket": AuthMiddlewareStack(URLRouter([path("chat/", ChatConsumer),]),),}
)
