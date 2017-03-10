import multiprocessing
import os
import sys

import django
from daphne.server import Server
from django.core.exceptions import ImproperlyConfigured
from django.test.testcases import TransactionTestCase
from django.test.utils import modify_settings, override_settings
from django.utils import six

from .. import DEFAULT_CHANNEL_LAYER
from ..asgi import ChannelLayerManager
from ..worker import Worker, WorkerGroup

# NOTE: We use ChannelLayerManager to prevent layer instance sharing
# between forked process.  Some layers implementations create
# connections inside the __init__ method.  After forking child
# processes can lose the ability to use this connection and typically
# stuck on some network operation.  To prevent this we use new
# ChannelLayerManager each time we want to initiate default layer.
# This gives us guaranty that new layer instance will be created and
# new connection will be established.


class WorkerProcess(multiprocessing.Process):

    def __init__(self, is_ready, n_threads, overridden_settings,
                 modified_settings):

        self.is_ready = is_ready
        self.n_threads = n_threads
        self.overridden_settings = overridden_settings
        self.modified_settings = modified_settings
        super(WorkerProcess, self).__init__()
        self.daemon = True

    def run(self):

        try:
            django.setup(**{'set_prefix': False}
                         if django.VERSION[1] > 9 else {})

            if self.overridden_settings:
                overridden = override_settings(**self.overridden_settings)
                overridden.enable()
            if self.modified_settings:
                modified = modify_settings(self.modified_settings)
                modified.enable()

            channel_layers = ChannelLayerManager()
            channel_layers[DEFAULT_CHANNEL_LAYER].router.check_default()
            if self.n_threads == 1:
                self.worker = Worker(
                    channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER],
                    signal_handlers=False,
                )
            else:
                self.worker = WorkerGroup(
                    channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER],
                    signal_handlers=False,
                    n_threads=self.n_threads,
                )
            self.worker.ready()
            self.is_ready.set()
            self.worker.run()
        except Exception:
            self.is_ready.set()
            raise


class DaphneProcess(multiprocessing.Process):

    def __init__(self, host, possible_ports, port_storage, is_ready,
                 overridden_settings, modified_settings):

        self.host = host
        self.possible_ports = possible_ports
        self.port_storage = port_storage
        self.is_ready = is_ready
        self.overridden_settings = overridden_settings
        self.modified_settings = modified_settings
        super(DaphneProcess, self).__init__()
        self.daemon = True

    def run(self):

        try:
            django.setup(**{'set_prefix': False}
                         if django.VERSION[1] > 9 else {})

            if self.overridden_settings:
                overridden = override_settings(**self.overridden_settings)
                overridden.enable()
            if self.modified_settings:
                modified = modify_settings(self.modified_settings)
                modified.enable()

            channel_layers = ChannelLayerManager()
            # FIXME: process all possible ports, exit after first success.
            host, port = self.host, self.possible_ports[0]
            self.server = Server(
                channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER],
                endpoints=['tcp:interface=%s:port=%d' % (host, port)],
                signal_handlers=False,
            )
            self.port_storage.value = self.possible_ports[0]
            self.is_ready.set()
            self.server.run()
        except Exception:
            self.is_ready.set()
            raise


class ChannelLiveServerTestCase(TransactionTestCase):

    ProtocolServerProcess = DaphneProcess
    WorkerProcess = WorkerProcess
    worker_threads = 1

    @property
    def live_server_url(self):

        return 'http://%s:%s' % (self._server_process.host,
                                 self._port_storage.value)

    @property
    def live_server_ws_url(self):

        return 'ws://%s:%s' % (self._server_process.host,
                               self._port_storage.value)

    def _pre_setup(self):

        channel_layers = ChannelLayerManager()
        if len(channel_layers.configs) > 1:
            raise ImproperlyConfigured(
                'ChannelLiveServerTestCase does not support multiple CHANNEL_LAYERS at this time'
            )
        channel_layer = channel_layers[DEFAULT_CHANNEL_LAYER]
        if 'flush' in channel_layer.extensions:
            channel_layer.flush()
        super(ChannelLiveServerTestCase, self)._pre_setup()
        self._port_storage = multiprocessing.Value('i')

        # NOTE: Copypasted from Django's LiveServerTestCase.
        specified_address = os.environ.get(
            'DJANGO_LIVE_TEST_SERVER_ADDRESS',
            'localhost:8081',
        )
        possible_ports = []
        try:
            host, port_ranges = specified_address.split(':')
            for port_range in port_ranges.split(','):
                extremes = list(map(int, port_range.split('-')))
                assert len(extremes) in [1, 2]
                if len(extremes) == 1:
                    possible_ports.append(extremes[0])
                else:
                    for port in range(extremes[0], extremes[1] + 1):
                        possible_ports.append(port)
        except Exception:
            msg = 'Invalid address ("%s") for live server.' % specified_address
            six.reraise(
                ImproperlyConfigured,
                ImproperlyConfigured(msg),
                sys.exc_info()[2],
            )
        # NOTE: End of copypasta.

        server_ready = multiprocessing.Event()
        self._server_process = self.ProtocolServerProcess(
            host,
            possible_ports,
            self._port_storage,
            server_ready,
            self._overridden_settings,
            self._modified_settings,
        )
        self._server_process.start()
        server_ready.wait()

        worker_ready = multiprocessing.Event()
        self._worker_process = self.WorkerProcess(
            worker_ready,
            self.worker_threads,
            self._overridden_settings,
            self._modified_settings,
        )
        self._worker_process.start()
        worker_ready.wait()

    def _post_teardown(self):

        self._server_process.terminate()
        self._server_process.join()
        self._worker_process.terminate()
        self._worker_process.join()
        super(ChannelLiveServerTestCase, self)._post_teardown()
