Troubleshooting
===============



ImproperlyConfigured exception
------------------------------


.. code-block:: text

    django.core.exceptions.ImproperlyConfigured: Requested setting INSTALLED_APPS, but settings are not configured.
    You must either define the environment variable DJANGO_SETTINGS_MODULE or call settings.configure() before accessing settings.


This exception occurs when your application tries to import any models before Django finishes
`its initialization process <https://docs.djangoproject.com/en/3.2/ref/applications/#initialization-process>`_ aka ``django.setup()``.


``django.setup()`` `should be called only once <https://docs.djangoproject.com/en/3.2/topics/settings/#calling-django-setup-is-required-for-standalone-django-usage>`_, and should be called manually only in case of standalone apps.
In context of Channels usage, ``django.setup()`` is called automatically in ``get_asgi_application()``,
which means it needs to be called before any models are imported.


The most common culprit of models import is ``channels.auth`` (eg. ``AuthMiddlewareStack``, ``AuthMiddleware``) importing ``AnonymousUser``.
The working code order would look like this:


.. code-block:: python

    from django.core.asgi import get_asgi_application
    django_asgi_app = get_asgi_application() # needs to be called before models import

    from channels.auth import AuthMiddlewareStack # triggers models import
    from channels.routing import ProtocolTypeRouter, URLRouter
    from myapp.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        }
    )
