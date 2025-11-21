Installation
============

Channels is available on PyPI - to install it run:

.. code-block:: sh

    python -m pip install -U 'channels[daphne]'

This will install Channels together with the Daphne ASGI application server. If
you wish to use a different application server you can ``pip install channels``,
without the optional ``daphne`` add-on.

Once that's done, you should add ``daphne`` to the beginning of your
``INSTALLED_APPS`` setting:

.. code-block:: python

    INSTALLED_APPS = (
        "daphne",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.sites",
        ...
    )

This will install the Daphne's ASGI version of the ``runserver`` management
command.

You can also add ``"channels"`` for Channel's ``runworker`` command.

Then, adjust your project's ``asgi.py`` file, e.g. ``myproject/asgi.py``, to
wrap the Django ASGI application::

      import os

      from channels.routing import ProtocolTypeRouter
      from django.core.asgi import get_asgi_application

      os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
      # Initialize Django ASGI application early to ensure the AppRegistry
      # is populated before importing code that may import ORM models.
      django_asgi_app = get_asgi_application()

      application = ProtocolTypeRouter({
          "http": django_asgi_app,
          # Just HTTP for now. (We can add other protocols later.)
      })

And finally, set your ``ASGI_APPLICATION`` setting to point to that routing
object as your root application:

.. code-block:: python

    ASGI_APPLICATION = "myproject.asgi.application"

That's it! Once enabled, ``daphne`` will integrate itself into Django and
take control of the ``runserver`` command. See :doc:`introduction` for more.

.. note::

    Please be wary of any other third-party apps that require an overloaded or
    replacement ``runserver`` command. Daphne provides a separate
    ``runserver`` command and may conflict with it. In order to solve such
    issues, make sure ``daphne`` is at the top of your ``INSTALLED_APPS`` or 
    remove the offending app altogether.
    
    However, `WhiteNoise <https://github.com/evansd/whitenoise>`_ does
    `provide support`<https://whitenoise.readthedocs.io/en/latest/django.html#using-whitenoise-in-development>
    for running ``runserver`` with Daphne, provided that
    ``whitenoise.runserver_nostatic`` is placed *above* ``daphne`` in
    ``INSTALLED_APPS`.


Type checking support
---------------------

If you want type checking support, you can install the type stubs:

.. code-block:: sh

    python -m pip install types-channels

Or install channels with type support using the ``types`` extra:

.. code-block:: sh

    python -m pip install 'channels[types]'


Installing the latest development version
-----------------------------------------

To install the latest version of Channels, clone the repo, change to the repo directory,
and pip install it into your current virtual
environment:

.. code-block:: sh

    $ git clone git@github.com:django/channels.git
    $ cd channels
    $ <activate your project’s virtual environment>
    (environment) $ pip install -e .  # the dot specifies the current repo
