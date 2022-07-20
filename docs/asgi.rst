ASGI
====

`ASGI <https://asgi.readthedocs.io>`_, or the
Asynchronous Server Gateway Interface, is the specification which
Channels and Daphne are built upon, designed to untie Channels apps from a
specific application server and provide a common way to write application
and middleware code.

It's a spiritual successor to WSGI, designed not only run in an asynchronous
fashion via ``asyncio``, but also supporting multiple protocols.

The full ASGI spec can be found at https://asgi.readthedocs.io


Summary
-------

ASGI is structured as a single asynchronous callable, which takes a dict ``scope``
and two callables ``receive`` and ``send``:

.. code-block:: python

    async def application(scope, receive, send):
        event = await receive()
        ...
        await send({"type": "websocket.send", ...})

The ``scope`` dict defines the properties of a connection, like its remote IP (for
HTTP) or username (for a chat protocol), and the lifetime of a connection.
Applications are *instantiated* once per scope - so, for example, once per
HTTP request, or once per open WebSocket connection.

Scopes always have a ``type`` key, which tells you what kind of connection
it is and what other keys to expect in the scope (and what sort of messages
to expect).

The ``receive`` awaitable provides events as dicts as they occur, and the
``send`` awaitable sends events back to the client in a similar dict format.

A *protocol server* sits between the client and your application code,
decoding the raw protocol into the scope and event dicts and encoding anything
you send back down onto the protocol.


Composability
-------------

ASGI applications, like WSGI ones, are designed to be composable, and this
includes Channels' routing and middleware components like ``ProtocolTypeRouter``
and ``SessionMiddleware``. These are just ASGI applications that take other
ASGI applications as arguments, so you can pass around just one top-level
application for a whole Django project and dispatch down to the right consumer
based on what sort of connection you're handling.


Protocol Specifications
-----------------------

The basic ASGI spec only outlines the interface for an ASGI app - it does not
specify how network protocols are encoded to and from scopes and event dicts.
That's the job of protocol specifications:

* HTTP and WebSocket: https://github.com/django/asgiref/blob/master/specs/www.rst
