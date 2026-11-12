import threading

from daphne.endpoints import build_endpoint_description_strings
from daphne.testing import _reinstall_reactor
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.db import connections
from django.test.testcases import TransactionTestCase
from django.test.utils import modify_settings
from django.utils.functional import classproperty

from channels.routing import get_default_application


class ChannelsLiveServerThread(threading.Thread):
    """Thread for running a live ASGI server while the tests are running."""

    # Defaults to daphne.server.Server. It can't be imported at module level:
    # it is bound to a Twisted reactor which can't be restarted, so a fresh
    # one is installed (and daphne.server re-imported) by each thread.
    server_class = None

    def __init__(self, host, static_handler=None, connections_override=None, port=0):
        self.host = host
        self.port = port
        self.is_ready = threading.Event()
        self.error = None
        self.static_handler = static_handler
        self.connections_override = connections_override
        super().__init__()

    def run(self):
        """
        Set up the live server and then loop over handling ASGI requests.
        """
        if self.connections_override:
            # Override this thread's database connections with the ones
            # provided by the main thread.
            for alias, conn in self.connections_override.items():
                connections[alias] = conn
        try:
            # The Twisted reactor can't be restarted: install a fresh one
            # for this thread, as DaphneProcess does in its own process.
            _reinstall_reactor()
            from twisted.internet import reactor

            self.reactor = reactor
            self.httpd = self._create_server()
            # The server calls _server_is_ready() once it is listening, and
            # then blocks running the reactor until terminate() stops it.
            self.httpd.run()
            if not self.is_ready.is_set():
                raise RuntimeError("The live server stopped before being ready.")
        except Exception as e:
            self.error = e
        finally:
            connections.close_all()
            # Never leave the main thread waiting.
            self.is_ready.set()

    def _create_server(self):
        server_class = self.server_class
        if server_class is None:
            from daphne.server import Server as server_class
        endpoints = build_endpoint_description_strings(host=self.host, port=self.port)
        application = get_default_application()
        if self.static_handler is not None:
            application = self.static_handler(application)
        return server_class(
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
        reactor = getattr(self, "reactor", None)
        if reactor is not None and reactor.running:
            # Stop the ASGI server from within its own thread.
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
    static_wrapper = ASGIStaticFilesHandler
    serve_static = True

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
            cls.static_wrapper if cls.serve_static else None,
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
