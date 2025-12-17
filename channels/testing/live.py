from functools import partial
import multiprocessing

from daphne.testing import DaphneProcess
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.backends.base.creation import TEST_DATABASE_PREFIX
from django.test.testcases import TransactionTestCase
from django.test.utils import modify_settings

from channels.routing import get_default_application


# Global queue for commands from test process to server process
_server_command_queue = None


def make_application(*, static_wrapper):
    # Module-level function for pickle-ability
    application = get_default_application()
    if static_wrapper is not None:
        application = static_wrapper(application)
    return application


def set_database_connection():
    from django.conf import settings

    test_db_name = settings.DATABASES["default"]["TEST"]["NAME"]
    if not test_db_name:
        test_db_name = TEST_DATABASE_PREFIX + settings.DATABASES["default"]["NAME"]
    settings.DATABASES["default"]["NAME"] = test_db_name


class ServerCommandMiddleware:
    """
    Middleware that processes commands from the test process.
    This is automatically added to the ASGI application in test mode.
    """
    def __init__(self, app, commands):
        self.app = app
        self.commands = commands

    async def __call__(self, scope, receive, send):
        # Process any pending server commands before handling the request
        self.process_server_commands()
        return await self.app(scope, receive, send)

    def process_server_commands(self):
        global _server_command_queue
        if _server_command_queue is None:
            return

        while not _server_command_queue.empty():
            try:
                command = _server_command_queue.get_nowait()
                if command in self.commands:
                    self.commands[command]()
            except:
                break


class ChannelsLiveServerTestCase(TransactionTestCase):
    """
    Does basically the same as TransactionTestCase but also launches a
    live Daphne server in a separate process, so
    that the tests may use another test framework, such as Selenium,
    instead of the built-in dummy client.
    """

    host = "localhost"
    ProtocolServerProcess = DaphneProcess
    static_wrapper = ASGIStaticFilesHandler
    serve_static = True
    commands = {}

    @property
    def live_server_url(self):
        return "http://%s:%s" % (self.host, self._port)

    @property
    def live_server_ws_url(self):
        return "ws://%s:%s" % (self.host, self._port)

    @classmethod
    def setUpClass(cls):
        global _server_command_queue

        for connection in connections.all():
            if cls._is_in_memory_db(connection):
                raise ImproperlyConfigured(
                    "ChannelLiveServerTestCase can not be used with in memory databases"
                )

        super().setUpClass()

        cls._live_server_modified_settings = modify_settings(
            ALLOWED_HOSTS={"append": cls.host}
        )
        cls._live_server_modified_settings.enable()

        # Create a command queue for communication with the server process
        _server_command_queue = multiprocessing.Queue()
        cls._server_command_queue = _server_command_queue

        def make_application_with_middleware(*, static_wrapper):
            application = get_default_application()
            # Wrap the application with our command processing middleware
            application = ServerCommandMiddleware(application, cls.commands)
            if static_wrapper is not None:
                application = static_wrapper(application)
            return application

        get_application = partial(
            make_application_with_middleware,
            static_wrapper=cls.static_wrapper if cls.serve_static else None,
        )
        cls._server_process = cls.ProtocolServerProcess(
            cls.host,
            get_application,
            setup=set_database_connection,
        )
        cls._server_process.start()
        while True:
            if not cls._server_process.ready.wait(timeout=1):
                if cls._server_process.is_alive():
                    continue
                raise RuntimeError("Server stopped") from None
            break
        cls._port = cls._server_process.port.value

    @classmethod
    def tearDownClass(cls):
        cls._server_process.terminate()
        cls._server_process.join()
        cls._live_server_modified_settings.disable()
        super().tearDownClass()

    def run_server_command(self, command):
        """
        Add command to server command queue.
        """
        if hasattr(self.__class__, '_server_command_queue'):
            self._server_command_queue.put(command)

    @classmethod
    def _is_in_memory_db(cls, connection):
        """
        Check if DatabaseWrapper holds in memory database.
        """
        if connection.vendor == "sqlite":
            return connection.is_in_memory_db()
