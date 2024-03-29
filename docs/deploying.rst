Deploying
=========

Channels (ASGI) applications deploy similarly to WSGI applications - you load
them into a server, like Daphne, and you can scale the number of server
processes up and down.

The one optional extra requirement for a Channels project is to provision a
:doc:`channel layer </topics/channel_layers>`. Both steps are covered below.


Configuring the ASGI application
--------------------------------

As discussed in :doc:`installation` and :doc:`/topics/routing`, you will have a
file like ``myproject/asgi.py`` that will define your *root application*. This
is almost certainly going to be your top-level (Protocol Type) router.

Here's an example of what that ``asgi.py`` might look like:

.. include:: ./includes/asgi_example.rst


Setting up a channel backend
----------------------------

.. note::

    This step is optional. If you aren't using the channel layer, skip this
    section.

Typically a channel backend will connect to one or more central servers that
serve as the communication layer - for example, the Redis backend connects
to a Redis server. All this goes into the ``CHANNEL_LAYERS`` setting;
here's an example for a remote Redis server:

.. code-block:: python

    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [("redis-server-name", 6379)],
            },
        },
    }

To use the Redis backend you have to install it:

.. code-block:: sh

    pip install -U channels_redis


Run protocol servers
--------------------

In order to talk to the outside world, your Channels/ASGI application needs
to be loaded into a *protocol server*. These can be like WSGI servers and run
your application in a HTTP mode, but they can also bridge to any number of
other protocols (chat protocols, IoT protocols, even radio networks).

All these servers have their own configuration options, but they all have one
thing in common - they will want you to pass them an ASGI application to run.
All you need to do is pass the ``application`` object inside your project's
``asgi.py`` file to your protocol server as the application it should run:

.. code-block:: sh

    daphne -p 8001 myproject.asgi:application


HTTP and WebSocket
------------------

While ASGI is a general protocol and we can't cover all possible servers here,
it's very likely you will want to deploy a Channels project to work over HTTP
and potentially WebSocket, so we'll cover that in some more detail.

The Channels project maintains an official ASGI HTTP/WebSocket server, `Daphne
<https://github.com/django/daphne>`_, and it's this that we'll talk about
configuring. Other HTTP/WebSocket ASGI servers are possible and will work just
as well provided they follow the spec, but will have different configuration.

You can choose to either use Daphne for all requests - HTTP and WebSocket -
or if you are conservative about stability, keep running standard HTTP requests
through a WSGI server and use Daphne only for things WSGI cannot do, like
HTTP long-polling and WebSockets. If you do split, you'll need to put something
in front of Daphne and your WSGI server to work out what requests to send to
each (using HTTP path or domain) - that's not covered here, just know you can
do it.

If you use Daphne for all traffic, it auto-negotiates between HTTP and
WebSocket, so there's no need to have your WebSockets on a separate domain or
path (and they'll be able to share cookies with your normal view code, which
isn't possible if you separate by domain rather than path).

To run Daphne, it just needs to be supplied with an application, much like
a WSGI server would need to be. Make sure you have an ``asgi.py`` file as
outlined above.

Then, you can run Daphne and supply the ASGI application as the argument:

.. code-block:: sh

    daphne myproject.asgi:application

You should run Daphne inside either a process supervisor (systemd, supervisord)
or a container orchestration system (kubernetes, nomad) to ensure that it
gets restarted if needed and to allow you to scale the number of processes.

If you want to bind multiple Daphne instances to the same port on a machine,
use a process supervisor that can listen on ports and pass the file descriptors
to launched processes, and then pass the file descriptor with ``--fd NUM``.

You can also specify the port and IP that Daphne binds to:

.. code-block:: sh

    daphne -b 0.0.0.0 -p 8001 myproject.asgi:application

You can see more about Daphne and its options
`on GitHub <https://github.com/django/daphne>`_.

Alternative Web Servers
-----------------------

There are also alternative `ASGI <https://asgi.readthedocs.io>`_ servers
that you can use for serving Channels.

To some degree ASGI web servers should be interchangeable, they should all have
the same basic functionality in terms of serving HTTP and WebSocket requests.

Aspects where servers may differ are in their configuration and defaults,
performance characteristics, support for resource limiting, differing protocol
and socket support, and approaches to process management.

You can see more alternative servers, such as Uvicorn, in the `ASGI
implementations documentation
<https://asgi.readthedocs.io/en/latest/implementations.html#servers>`_.


Example Setups
--------------

These are examples of possible setups - they are not guaranteed to work out of
the box, and should be taken more as a guide than a direct tutorial.


Nginx/Supervisor (Ubuntu)
~~~~~~~~~~~~~~~~~~~~~~~~~

This example sets up a Django site on an Ubuntu server, using Nginx as the
main webserver and supervisord to run and manage Daphne.

First, install Nginx and Supervisor:

.. code-block:: sh

    $ sudo apt install nginx supervisor

Now, you will need to create the supervisor configuration file (often located
in ``/etc/supervisor/conf.d/`` - here, we're making Supervisor listen on the
TCP port and then handing that socket off to the child processes so they can
all share the same bound port:

.. code-block:: ini

    [fcgi-program:asgi]
    # TCP socket used by Nginx backend upstream
    socket=tcp://localhost:8000

    # Directory where your site's project files are located
    directory=/my/app/path

    # Each process needs to have a separate socket file, so we use process_num
    # Make sure to update "mysite.asgi" to match your project name
    command=daphne -u /run/daphne/daphne%(process_num)d.sock --fd 0 --access-log - --proxy-headers mysite.asgi:application

    # Number of processes to startup, roughly the number of CPUs you have
    numprocs=4

    # Give each process a unique name so they can be told apart
    process_name=asgi%(process_num)d

    # Automatically start and recover processes
    autostart=true
    autorestart=true

    # Choose where you want your log to go
    stdout_logfile=/your/log/asgi.log
    redirect_stderr=true

Create the run directory for the sockets referenced in the supervisor
configuration file.

.. code-block:: sh

    $ sudo mkdir /run/daphne/

When running the supervisor fcgi-program under a different user, change the
owner settings of the run directory.

.. code-block:: sh

    $ sudo chown <user>.<group> /run/daphne/

The /run/ folder is cleared on a server reboot. To make the /run/daphne folder
persistent create a file ``/usr/lib/tmpfiles.d/daphne.conf`` with the contents
below.

.. code-block:: text

    $ d /run/daphne 0755 <user> <group>

Have supervisor reread and update its jobs:

.. code-block:: sh

    $ sudo supervisorctl reread
    $ sudo supervisorctl update

.. note::
    Running the daphne command with ``--fd 0`` in the commandline will fail and
    result in *[Errno 88] Socket operation on non-socket*.

    Supervisor will automatically create the socket, bind, and listen before
    forking the first child in a group. The socket will be passed to each child
    on file descriptor number 0 (zero). See
    https://supervisord.org/configuration.html#fcgi-program-x-section-settings

Next, Nginx has to be told to proxy traffic to the running Daphne instances.
Setup your nginx upstream conf file for your project:

.. code-block:: text

    upstream channels-backend {
        server localhost:8000;
    }
    ...
    server {
        ...
        location / {
            try_files $uri @proxy_to_app;
        }
        ...
        location @proxy_to_app {
            proxy_pass http://channels-backend;

            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            proxy_redirect off;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Host $server_name;
        }
        ...
    }

Reload nginx to apply the changes:

.. code-block:: sh

    $ sudo service nginx reload

