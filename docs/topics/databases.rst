Database Access
===============

The Django ORM is a synchronous piece of code, and so if you want to access
it from asynchronous code you need to do special handling to make sure its
connections are closed properly.

If you're using ``SyncConsumer``, or anything based on it - like
``JsonWebsocketConsumer`` - you don't need to do anything special, as all your
code is already run in a synchronous mode and Channels will do the cleanup
for you as part of the ``SyncConsumer`` code.

If you are writing asynchronous code, however, you will need to call
database methods in a safe, synchronous context, using ``database_sync_to_async``
or by using the asynchronous methods prefixed with ``a`` like ``Model.objects.aget()``.


Database Connections
--------------------

Channels can potentially open a lot more database connections than you may be used to if you are using threaded consumers (synchronous ones) - it can open up to one connection per thread.

If you wish to control the maximum number of threads used, set the
``ASGI_THREADS`` environment variable to the maximum number you wish to allow.
By default, the number of threads is set to "the number of CPUs * 5" for 
Python 3.7 and below, and `min(32, os.cpu_count() + 4)` for Python 3.8+. 

To avoid having too many threads idling in connections, you can instead rewrite your code to use async consumers and only dip into threads when you need to use Django's ORM (using ``database_sync_to_async``).

When using async consumers Channels will automatically call Django's ``close_old_connections`` method when a new connection is started, when a connection is closed, and whenever anything is received from the client.
This mirrors Django's logic for closing old connections at the start and end of a request, to the extent possible. Connections are *not* automatically closed when sending data from a consumer since Channels has no way
to determine if this is a one-off send (and connections could be closed) or a series of sends (in which closing connections would kill performance). Instead, if you have a long-lived async consumer you should
periodically call ``aclose_old_connections`` (see below).


database_sync_to_async
----------------------

``channels.db.database_sync_to_async`` is a version of ``asgiref.sync.sync_to_async``
that also cleans up database connections on exit.

To use it, write your ORM queries in a separate function or method, and then
call it with ``database_sync_to_async`` like so:

.. code-block:: python

    from channels.db import database_sync_to_async

    async def connect(self):
        self.username = await database_sync_to_async(self.get_name)()

    def get_name(self):
        return User.objects.all()[0].name

You can also use it as a decorator:

.. code-block:: python

    from channels.db import database_sync_to_async

    async def connect(self):
        self.username = await self.get_name()

    @database_sync_to_async
    def get_name(self):
        return User.objects.all()[0].name

aclose_old_connections
----------------------

``django.db.aclose_old_connections`` is an async wrapper around Django's
``close_old_connections``. When using a long-lived ``AsyncConsumer`` that
calls the Django ORM it is important to call this function periodically.

Preferrably, this function should be called before making the first query
in a while. For example, it should be called if the Consumer is woken up
by a channels layer event and needs to make a few ORM queries to determine
what to send to the client. This function should be called *before* making
those queries. Calling this function more than necessary is not necessarily
a bad thing, but it does require a context switch to synchronous code and
so incurs a small penalty.