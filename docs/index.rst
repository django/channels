Django Channels
===============

Channels is a project that takes Django and extends its abilities beyond
HTTP - to handle WebSockets, chat protocols, IoT protocols, and more. It's
built on a Python specification called `ASGI <http://asgi.readthedocs.io>`_.

Channels builds upon the native ASGI support available in Django since v3.0,
and provides an implementation itself for Django v2.2. Django still handles
traditional HTTP, whilst Channels give you the choice to handle other
connections in either a synchronous or asynchronous style.

To get started understanding Channels, read our :doc:`introduction`,
which will walk through how things work. If you're upgrading from Channels 2,
take a look at :doc:`releases/3.0.0` to get an overview of the changes.

.. warning::
   This is documentation for the **3.x series** of Channels. If you are looking
   for documentation for older versions, you can select ``2.x`` or ``1.x`` from
   the versions selector in the bottom-left corner.

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
   one-to-two


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
