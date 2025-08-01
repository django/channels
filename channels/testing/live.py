from functools import partial

from daphne.testing import DaphneProcess
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.backends.base.creation import TEST_DATABASE_PREFIX
from django.test.testcases import TransactionTestCase
from django.test.utils import modify_settings

from channels.routing import get_default_application


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

    @property
    def live_server_url(self):
        return "http://%s:%s" % (self.host, self._port)

    @property
    def live_server_ws_url(self):
        return "ws://%s:%s" % (self.host, self._port)

    @classmethod
    def setUpClass(cls):
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

        get_application = partial(
            make_application,
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

    @classmethod
    def _is_in_memory_db(cls, connection):
        """
        Check if DatabaseWrapper holds in memory database.
        """
        if connection.vendor == "sqlite":
            return connection.is_in_memory_db()
