Troubleshooting
===============



ImproperlyConfigured exception
------------------------------


.. code-block:: text

    django.core.exceptions.ImproperlyConfigured: Requested setting INSTALLED_APPS, but settings are not configured.
    You must either define the environment variable DJANGO_SETTINGS_MODULE or call settings.configure() before accessing settings.


This exception occurs when your application tries to import any models before Django finishes
`its initialization process <https://docs.djangoproject.com/en/3.2/ref/applications/#initialization-process>`_ aka ``django.setup()``.


``django.setup()`` `should be called only once <https://docs.djangoproject.com/en/3.2/topics/settings/#calling-django-setup-is-required-for-standalone-django-usage>`_,
and should be called manually only in case of standalone apps.
In context of Channels usage, ``django.setup()`` is called automatically in ``get_asgi_application()``,
which means it needs to be called before any ORM models are imported.

The working code order would look like this:

.. code-block:: python

    from channels.routing import ProtocolTypeRouter, URLRouter
    from django.core.asgi import get_asgi_application
    # Initialize Django ASGI application early to ensure the AppRegistry
    # is populated before importing code that may import ORM models.
    django_asgi_app = get_asgi_application()

    # custom code may cause ORM models import
    from myapp.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
        }
    )
