from functools import partial

from daphne.testing import DaphneProcess
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.testcases import TransactionTestCase
from django.test.utils import modify_settings

from channels.routing import get_default_application
from django.core.management import call_command


def make_application(*, static_wrapper):
    # Module-level function for pickle-ability
    application = get_default_application()
    if static_wrapper is not None:
        application = static_wrapper(application)
    return application

# add fixtures in the child process
def get_available_database_names(db, include_mirrors=True):
    return [
            alias for alias in connections
            if alias in db and (
                include_mirrors or not connections[alias].settings_dict['TEST']['MIRROR']
            )
        ]

def setup_fixtures(databases, fixtures):
    dbs = get_available_database_names(databases)
    for db_name in dbs:
        call_command('loaddata', fixtures, \
                **{'verbosity': 0, 'database': db_name})


def teardown_fixtures(databases, available_apps, serialized_rollback):
    inhibit_post_migrate = (
            available_apps is not None or
            (   # Inhibit the post_migrate signal when using serialized
                # rollback to avoid trying to recreate the serialized data.
                serialized_rollback and
                hasattr(connections[db_name], '_test_serialized_contents')
            )
        )
    dbs = get_available_database_names(databases)

    for db_name in dbs:
        call_command('flush', verbosity=0, interactive=False,
            database=db_name, reset_sequences=False,
            allow_cascade=available_apps is not None,
            inhibit_post_migrate=inhibit_post_migrate)


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

    def _pre_setup(self):
        for connection in connections.all():
            if self._is_in_memory_db(connection):
                raise ImproperlyConfigured(
                    "ChannelLiveServerTestCase can not be used with in memory databases"
                )

        super(ChannelsLiveServerTestCase, self)._pre_setup()

        self._live_server_modified_settings = modify_settings(
            ALLOWED_HOSTS={"append": self.host}
        )
        self._live_server_modified_settings.enable()

        get_application = partial(
            make_application,
            static_wrapper=self.static_wrapper if self.serve_static else None,
        )

        setup = partial(
            setup_fixtures, 
            self.databases,
            self.fixtures
        )

        teardown = partial(
            teardown_fixtures, 
            self.databases, 
            self.available_apps,
            self.serialized_rollback
        )

        self._server_process = self.ProtocolServerProcess(self.host, get_application, \
                                                          setup=setup, teardown=teardown)
        self._server_process.start()
        self._server_process.ready.wait()
        self._port = self._server_process.port.value

    def _post_teardown(self):
        self._server_process.terminate()
        self._server_process.join()
        self._live_server_modified_settings.disable()
        super(ChannelsLiveServerTestCase, self)._post_teardown()

    def _is_in_memory_db(self, connection):
        """
        Check if DatabaseWrapper holds in memory database.
        """
        if connection.vendor == "sqlite":
            return connection.is_in_memory_db()
