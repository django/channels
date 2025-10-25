import threading

from daphne.endpoints import build_endpoint_description_strings
from daphne.server import Server
from daphne.testing import _reinstall_reactor
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.db import connections
from django.db.backends.base.creation import TEST_DATABASE_PREFIX
from django.test.testcases import TransactionTestCase
from django.test.utils import modify_settings
from django.utils.functional import classproperty
from django.utils.version import PY311

from channels.routing import get_default_application

if not PY311:
    # Backport of unittest.case._enter_context() from Python 3.11.
    def _enter_context(cm, addcleanup):
        # Look up the special methods on the type to match the with statement.
        cls = type(cm)
        try:
            enter = cls.__enter__
            exit = cls.__exit__
        except AttributeError:
            raise TypeError(
                f"'{cls.__module__}.{cls.__qualname__}' object does not support the "
                f"context manager protocol"
            ) from None
        result = enter(cm)
        addcleanup(exit, cm, None, None, None)
        return result


def set_database_connection():
    from django.conf import settings

    test_db_name = settings.DATABASES["default"]["TEST"]["NAME"]
    if not test_db_name:
        test_db_name = TEST_DATABASE_PREFIX + settings.DATABASES["default"]["NAME"]
    settings.DATABASES["default"]["NAME"] = test_db_name


class ChannelsLiveServerThread(threading.Thread):
    """Thread for running a live ASGI server while the tests are running."""

    server_class = Server

    def __init__(self, host, static_handler, connections_override=None, port=0):
        self.host = host
        self.port = port
        self.is_ready = threading.Event()
        self.error = None
        self.static_handler = static_handler
        self.connections_override = connections_override
        super().__init__()

    def run(self):
        """
        Set up the live server and databases, and then loop over handling
        ASGI requests.
        """
        if self.connections_override:
            # Override this thread's database connections with the ones
            # provided by the main thread.
            for alias, conn in self.connections_override.items():
                connections[alias] = conn
        try:
            # Reinstall the reactor for this thread (same as DaphneProcess)
            _reinstall_reactor()

            self.httpd = self._create_server(
                connections_override=self.connections_override,
            )

            # Run database setup
            set_database_connection()

            # The server will call ready_callable when ready
            self.httpd.run()
        except Exception as e:
            self.error = e
            self.is_ready.set()
        finally:
            connections.close_all()

    def _create_server(self, connections_override=None):
        endpoints = build_endpoint_description_strings(host=self.host, port=self.port)
        # Create the handler for serving static files
        application = self.static_handler(get_default_application())
        return self.server_class(
            application=application,
            endpoints=endpoints,
            signal_handlers=False,
            ready_callable=self._server_is_ready,
            verbosity=0,
        )

    def _server_is_ready(self):
        """Called by Daphne when the server is ready and listening."""
        # If binding to port zero, assign the port allocated by the OS.
        if self.port == 0:
            self.port = self.httpd.listening_addresses[0][1]
        self.is_ready.set()

    def terminate(self):
        if hasattr(self, "httpd"):
            # Stop the ASGI server
            from twisted.internet import reactor

            if reactor.running:
                reactor.callFromThread(reactor.stop)
        self.join(timeout=5)


class ChannelsLiveServerTestCase(TransactionTestCase):
    """
    Do basically the same as TransactionTestCase but also launch a live ASGI
    server in a separate thread so that the tests may use another testing
    framework, such as Selenium for example, instead of the built-in dummy
    client.
    It inherits from TransactionTestCase instead of TestCase because the
    threads don't share the same transactions (unless if using in-memory
    sqlite) and each thread needs to commit all their transactions so that the
    other thread can see the changes.
    """

    host = "localhost"
    port = 0
    server_thread_class = ChannelsLiveServerThread
    static_handler = ASGIStaticFilesHandler

    if not PY311:
        # Backport of unittest.TestCase.enterClassContext() from Python 3.11.
        @classmethod
        def enterClassContext(cls, cm):
            return _enter_context(cm, cls.addClassCleanup)

    @classproperty
    def live_server_url(cls):
        return "http://%s:%s" % (cls.host, cls.server_thread.port)

    @classproperty
    def live_server_ws_url(cls):
        return "ws://%s:%s" % (cls.host, cls.server_thread.port)

    @classproperty
    def allowed_host(cls):
        return cls.host

    @classmethod
    def _make_connections_override(cls):
        connections_override = {}
        for conn in connections.all():
            # If using in-memory sqlite databases, pass the connections to
            # the server thread.
            if conn.vendor == "sqlite" and conn.is_in_memory_db():
                connections_override[conn.alias] = conn
        return connections_override

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.enterClassContext(
            modify_settings(ALLOWED_HOSTS={"append": cls.allowed_host})
        )
        cls._start_server_thread()

    @classmethod
    def _start_server_thread(cls):
        connections_override = cls._make_connections_override()
        for conn in connections_override.values():
            # Explicitly enable thread-shareability for this connection.
            conn.inc_thread_sharing()

        cls.server_thread = cls._create_server_thread(connections_override)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        cls.addClassCleanup(cls._terminate_thread)

        # Wait for the live server to be ready
        cls.server_thread.is_ready.wait()
        if cls.server_thread.error:
            raise cls.server_thread.error

    @classmethod
    def _create_server_thread(cls, connections_override):
        return cls.server_thread_class(
            cls.host,
            cls.static_handler,
            connections_override=connections_override,
            port=cls.port,
        )

    @classmethod
    def _terminate_thread(cls):
        # Terminate the live server's thread.
        cls.server_thread.terminate()
        # Restore shared connections' non-shareability.
        for conn in cls.server_thread.connections_override.values():
            conn.dec_thread_sharing()
