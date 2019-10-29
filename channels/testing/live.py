import asyncio
import sys
import threading

from django.conf import settings
from django.db import connections
from django.test.testcases import LiveServerTestCase, LiveServerThread

from channels.routing import get_default_application
from channels.staticfiles import StaticFilesWrapper
from daphne.endpoints import build_endpoint_description_strings
from daphne.server import Server


class DaphneLiveServerThread(LiveServerThread):
    """
    LiveServerThread subclass that runs Daphne.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.application = self.get_application()

        # _terminate is set by main thread to ask thread to terminate
        self._terminate = threading.Event()
        # _terminated is set by thread to tell main thread it's done terminating
        self._terminated = threading.Event()

    def run(self):
        """
        Set up the live server and databases, and then loop over handling
        HTTP requests.
        """
        if self.connections_override:
            # Override this thread's database connections with the ones
            # provided by the main thread.
            for alias, conn in self.connections_override.items():
                connections[alias] = conn
        try:
            self.daphne = self._create_server()
            self.daphne.run()
        except Exception as e:
            self.error = e
            self.is_ready.set()
        finally:
            connections.close_all()
            self._terminated.set()

    def _create_server(self):
        """
        Create a daphne server with local thread asyncio event loop and twisted reactor.
        """
        # Reset reactor to use local thread's event loop
        from twisted.internet import asyncioreactor

        del sys.modules["twisted.internet.reactor"]

        try:
            event_loop = asyncio.get_event_loop()
        except RuntimeError:
            event_loop = asyncio.new_event_loop()

        asyncioreactor.install(event_loop)
        from twisted.internet import reactor

        # Create hook to check if main thread communicated with us
        reactor.callLater(1, self._on_reactor_hook, reactor)

        application = self.application
        if self.static_handler:
            application = self.static_handler(application)

        endpoints = build_endpoint_description_strings(host=self.host, port=self.port)

        def ready():
            if self.port == 0:
                self.port = self.daphne.listening_addresses[0][1]
            self.is_ready.set()

        return Server(
            application=application,
            endpoints=endpoints,
            signal_handlers=False,
            root_path=getattr(settings, "FORCE_SCRIPT_NAME", "") or "",
            ready_callable=ready,
            reactor=reactor,
        )

    def _on_reactor_hook(self, reactor):
        """
        Check for events from main thread, while within this thread.
        """
        if self._terminate.is_set():
            self.do_terminate()
            self._terminated.set()  # Notify main thread we terminated ok
            self._terminate.clear()  # Reset to allow terminating again (redundant)
        reactor.callLater(1, self._on_reactor_hook, reactor)

    def get_application(self):
        """
        Get the application Daphne will host.
        """
        application = get_default_application()
        if self.static_handler:
            application = self.static_handler(application)

        return application

    def do_terminate(self):
        """
        Stop the ASGI server, from thread.
        """
        self.daphne.stop()

    def terminate(self):
        """
        Stop thread, from main thread.
        """
        if hasattr(self, "daphne"):
            self._terminate.set()  # Request thread to stop
            self._terminated.wait()  # Wait until thread has stopped
        self.join()


class ChannelsLiveServerTestCase(LiveServerTestCase):
    """
    Does basically the same as TransactionTestCase but also launches a
    live Daphne server in a separate thread, so
    that the tests may use another test framework, such as Selenium,
    instead of the built-in dummy client.
    """

    server_thread_class = DaphneLiveServerThread
    static_handler = StaticFilesWrapper
