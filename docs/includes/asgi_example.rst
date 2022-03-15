.. code-block:: python

    import os

    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
    from django.core.asgi import get_asgi_application
    from django.urls import path

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
    # Initialize Django ASGI application early to ensure the AppRegistry
    # is populated before importing code that may import ORM models.
    django_asgi_app = get_asgi_application()

    from chat.consumers import AdminChatConsumer, PublicChatConsumer

    application = ProtocolTypeRouter({
        # Django's ASGI application to handle traditional HTTP requests
        "http": django_asgi_app,

        # WebSocket chat handler
        "websocket": AuthMiddlewareStack(
            URLRouter([
                path("chat/admin/", AdminChatConsumer.as_asgi()),
                path("chat/", PublicChatConsumer.as_asgi()),
            ])
        ),
    })