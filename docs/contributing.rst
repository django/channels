Contributing
============

If you're looking to contribute to Channels, then please read on - we encourage
contributions both large and small, from both novice and seasoned developers.


What can I work on?
-------------------

We're looking for help with the following areas:

 * Documentation and tutorial writing
 * Bugfixing and testing
 * Feature polish and occasional new feature design
 * Case studies and writeups

You can find what we're looking to work on in the GitHub issues list for each
of the Channels sub-projects:

 * `Channels issues <https://github.com/django/channels/issues/>`_, for the Django integration and overall project efforts
 * `Daphne issues <https://github.com/django/daphne/issues/>`_, for the HTTP and Websocket termination
 * `asgiref issues <https://github.com/django/asgiref/issues/>`_, for the base ASGI library/memory backend
 * `channels_redis issues <https://github.com/django/channels_redis/issues/>`_, for the Redis channel backend

Issues are categorized by difficulty level:

 * ``exp/beginner``: Easy issues suitable for a first-time contributor.
 * ``exp/intermediate``: Moderate issues that need skill and a day or two to solve.
 * ``exp/advanced``: Difficult issues that require expertise and potentially weeks of work.

They are also classified by type:

 * ``documentation``: Documentation issues. Pick these if you want to help us by writing docs.
 * ``bug``: A bug in existing code. Usually easier for beginners as there's a defined thing to fix.
 * ``enhancement``: A new feature for the code; may be a bit more open-ended.

You should filter the issues list by the experience level and type of work
you'd like to do, and then if you want to take something on leave a comment
and assign yourself to it. If you want advice about how to take on a bug,
leave a comment asking about it and we'll be happy to help.

The issues are also just a suggested list - any offer to help is welcome as
long as it fits the project goals, but you should make an issue for the thing
you wish to do and discuss it first if it's relatively large (but if you just
found a small bug and want to fix it, sending us a pull request straight away
is fine).


I'm a novice contributor/developer - can I help?
------------------------------------------------

Of course! The issues labelled with ``exp/beginner`` are a perfect place to get
started, as they're usually small and well defined. If you want help with one
of them, jump in and comment on the ticket if you need input or assistance.


How do I get started and run the tests?
---------------------------------------

First, you should first clone the git repository to a local directory:

.. code-block:: sh

    git clone https://github.com/django/channels.git channels

Next, you may want to make a virtual environment to run the tests and develop
in; you can use either ``virtualenvwrapper``, ``pipenv`` or just plain
``virtualenv`` for this.

Then, ``cd`` into the ``channels`` directory and install it editable into
your environment:

.. code-block:: sh

    cd channels/
    python -m pip install -e .[tests]

Note the ``[tests]`` section there; that tells ``pip`` that you want to install
the ``tests`` extra, which will bring in testing dependencies like
``pytest-django``.

Then, you can run the tests:

.. code-block:: sh

    pytest

Also, there is a tox.ini file at the root of the repository. Example commands:

.. code-block:: sh

    $ tox -l
    py37-dj32
    py38-dj32
    py39-dj32
    py310-dj32
    py38-dj40
    py38-dj41
    py38-djmain
    py39-dj40
    py39-dj41
    py39-djmain
    py310-dj40
    py310-dj41
    py310-djmain
    qa

   # run the test with Python 3.10, on Django 4.1 and Django main branch
   $ tox -e py310-dj41,py310-djmain

Note that tox can also forward arguments to pytest. When using pdb with pytest,
forward the ``-s`` option to pytest as such:

.. code-block:: sh

   tox -e py310-dj41 -- -s

The ``qa`` environment runs the various linters used by the project.

How do I do a release?
----------------------

If you have commit access, a release involves the following steps:

* Create a new entry in the CHANGELOG.txt file and summarise the changes
* Create a new release page in the docs under ``docs/releases`` and add the
  changelog there with more information where necessary
* Add a link to the new release notes in ``docs/releases/index.rst``
* Set the new version in ``__init__.py``
* Roll all of these up into a single commit and tag it with the new version
  number. Push the commit and tag.
* To upload you will need to be added as a maintainer on PyPI.
  Run `python setup.py sdist bdist_wheel`, and `twine upload`.

The release process for ``channels-redis`` and ``daphne`` is similar, but
they don't have the two steps in ``docs/``.
