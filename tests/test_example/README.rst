Django Channels Test Example
============================

This is a very simple example package to demonstrate
``ChannelsLiveServerTestCase`` that uses a thread instead of separate process.
Because of this, ``DaphneProcess`` is no longer used by Channels.

Setup Instructions
------------------

#. Setup a virtual environment if needed.
#. Download ``ChromeDriver`` for the Selenium tests at
   https://chromedriver.chromium.org/downloads and ensure it's on your ``PATH``.
#. Install required packages::

    $ pip install -r requirements.txt

#. Install local versions of ``daphne`` and ``channels``::

    $ cd /path/to/daphne
    $ pip install -e .[tests]

    $ cd /path/to/channels
    $ pip install -e .[tests]

Running the example manually
----------------------------

#. Go to the ``test_example`` directory where this README is located.
#. Run migrations::

    $ python3 manage.py migrate

#. Run the server::

    $ python3 manage.py runserver

#. Visit http://localhost:8000/

    * You may type text in the first input and click ``Send`` to see an echoed
      response in the bottom output box.
    * Clicking the ``Get Special Data`` button will send a request to the socket
      for some "complex" data.
    * The ``Clear`` button will clear the output box.

Running the tests
-----------------

The tests will use Selenium and Chrome. It has the following tests:

* Test echo function of socket consumer.
* Test "complex" data can be returned from socket consumer.
* Test mocked "complex" data can be returned from socket consumer.
    * NOTE: This fails with ``DaphneProcess``.
* Test the database can be modified and the test still passes with the
  in-memory database. A user is added mid-test and then logged in.

    * NOTE: This fails with ``DaphneProcess``.

To run the tests, execute::

    $ pytest

Example output::

    =========================== test session starts ============================
    platform linux -- Python 3.7.5, pytest-4.6.6, py-1.8.0, pluggy-0.13.0
    hypothesis profile 'default' -> database=DirectoryBasedExampleDatabase('/home/steven/projects/channels/tests/test_example/.hypothesis/examples')
    Django settings: myproject.settings (from ini file)
    rootdir: /home/steven/projects/channels/tests/test_example, inifile: pytest.ini
    plugins: hypothesis-4.23.0, asyncio-0.10.0, django-3.6.0
    collected 4 items

    chat/tests.py ....                                                   [100%]

    ========================= 4 passed in 3.20 seconds =========================