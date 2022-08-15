Django Channels
===============

Channels is a project that takes Django and extends its abilities beyond
HTTP - to handle WebSockets, chat protocols, IoT protocols, and more. It's
built on a Python specification called `ASGI <https://asgi.readthedocs.io>`_.

Channels builds upon the native ASGI support in Django. Whilst Django still handles
traditional HTTP, Channels gives you the choice to handle other connections in
either a synchronous or asynchronous style.

To get started understanding Channels, read our :doc:`introduction`,
which will walk through how things work.

.. note::
   This is documentation for the **4.x series** of Channels. If you are looking
   for documentation for older versions, you can select ``3.x``, ``2.x``, or
   ``1.x`` from the versions selector in the bottom-left corner.

Projects
--------

Channels is comprised of several packages:

* `Channels <https://github.com/django/channels/>`_, the Django integration layer
* `Daphne <https://github.com/django/daphne/>`_, the HTTP and Websocket termination server
* `asgiref <https://github.com/django/asgiref/>`_, the base ASGI library
* `channels_redis <https://github.com/django/channels_redis/>`_, the Redis channel layer backend (optional)

This documentation covers the system as a whole; individual release notes and
instructions can be found in the individual repositories.

.. _topics:

Topics
------

.. toctree::
   :maxdepth: 2

   introduction
   installation
   tutorial/index
   topics/consumers
   topics/routing
   topics/databases
   topics/channel_layers
   topics/sessions
   topics/authentication
   topics/security
   topics/testing
   topics/worker
   deploying
   topics/troubleshooting


Reference
---------

.. toctree::
   :maxdepth: 2

   asgi
   channel_layer_spec
   community
   contributing
   support
   releases/index
