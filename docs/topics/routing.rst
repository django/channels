Routing
=======

While consumers are valid :doc:`ASGI </asgi>` applications, you don't want
to just write one and have that be the only thing you can give to protocol
servers like Daphne. Channels provides routing classes that allow you to
combine and stack your consumers (and any other valid ASGI application) to
dispatch based on what the connection is.

.. important::

    Channels routers only work on the *scope* level, not on the level of
    individual *events*, which means you can only have one consumer for any
    given connection. Routing is to work out what single consumer to give a
    connection, not how to spread events from one connection across
    multiple consumers.

Routers are themselves valid ASGI applications, and it's possible to nest them.
We suggest that you have a ``ProtocolTypeRouter`` as the root application of
your project - the one that you pass to protocol servers - and nest other,
more protocol-specific routing underneath there.

Channels expects you to be able to define a single *root application*, and
provide the path to it as the ``ASGI_APPLICATION`` setting (think of this as
being analogous to the ``ROOT_URLCONF`` setting in Django). There's no fixed
rule as to where you need to put the routing and the root application, but we
recommend following Django's conventions and putting them in a project-level
file called ``asgi.py``, next to ``urls.py``. You can read more about deploying
Channels projects and settings in :doc:`/deploying`.

Here's an example of what that ``asgi.py`` might look like:

.. code-block:: python

    import os

    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
    from django.conf.urls import url
    from django.core.asgi import get_asgi_application

    from chat.consumers import AdminChatConsumer, PublicChatConsumer

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

    application = ProtocolTypeRouter({
        # Django's ASGI application to handle traditional HTTP requests
        "http": get_asgi_application(),

        # WebSocket chat handler
        "websocket": AuthMiddlewareStack(
            URLRouter([
                url(r"^chat/admin/$", AdminChatConsumer.as_asgi()),
                url(r"^chat/$", PublicChatConsumer.as_asgi()),
            ])
        ),
    })

.. note::
  We call the ``as_asgi()`` classmethod when routing our consumers. This
  returns an ASGI wrapper application that will instantiate a new consumer
  instance for each connection or scope. This is similar to Django's
  ``as_view()``, which plays the same role for per-request instances of
  class-based views.

It's possible to have routers from third-party apps, too, or write your own,
but we'll go over the built-in Channels ones here.


ProtocolTypeRouter
------------------

``channels.routing.ProtocolTypeRouter``

This should be the top level of your ASGI application stack and the main entry
in your routing file.

It lets you dispatch to one of a number of other ASGI applications based on the
``type`` value present in the ``scope``. Protocols will define a fixed type
value that their scope contains, so you can use this to distinguish between
incoming connection types.

It takes a single argument - a dictionary mapping type names to ASGI
applications that serve them:

.. code-block:: python

    ProtocolTypeRouter({
        "http": some_app,
        "websocket": some_other_app,
    })

If you want to split HTTP handling between long-poll handlers and Django views,
use a URLRouter using Django's ``get_asgi_application()`` specified as the last
entry with a match-everything pattern.

.. _urlrouter:

URLRouter
---------

``channels.routing.URLRouter``

Routes ``http`` or ``websocket`` type connections via their HTTP path. Takes a
single argument, a list of Django URL objects (either ``path()`` or
``re_path()``):

.. code-block:: python

    URLRouter([
        re_path(r"^longpoll/$", LongPollConsumer.as_asgi()),
        re_path(r"^notifications/(?P<stream>\w+)/$", LongPollConsumer.as_asgi()),
        re_path(r"", get_asgi_application()),
    ])

Any captured groups will be provided in ``scope`` as the key ``url_route``, a
dict with a ``kwargs`` key containing a dict of the named regex groups and
an ``args`` key with a list of positional regex groups. Note that named
and unnamed groups cannot be mixed: Positional groups are discarded as soon
as a single named group is matched.

For example, to pull out the named group ``stream`` in the example above, you
would do this:

.. code-block:: python

    stream = self.scope["url_route"]["kwargs"]["stream"]

Please note that ``URLRouter`` nesting will not work properly with
``path()`` routes if inner routers are wrapped by additional middleware.
See `Issue #1428 <https://github.com/django/channels/issues/1428>`__.


ChannelNameRouter
-----------------

``channels.routing.ChannelNameRouter``

Routes ``channel`` type scopes based on the value of the ``channel`` key in
their scope. Intended for use with the :doc:`/topics/worker`.

It takes a single argument - a dictionary mapping channel names to ASGI
applications that serve them:

.. code-block:: python

    ChannelNameRouter({
        "thumbnails-generate": some_app,
        "thumbnails-delete": some_other_app,
    })
