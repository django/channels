import multiprocessing
import threading

from daphne.server import Server
from django.test.testcases import LiveServerTestCase

from .. import DEFAULT_CHANNEL_LAYER
from ..asgi import channel_layers
from ..worker import Worker

# TODO: What we need to do in the case of multiple channel layers?


class WorkerProcess(multiprocessing.Process):

    def __init__(self, is_ready):

        self.is_ready = is_ready
        super(WorkerProcess, self).__init__()
        self.daemon = True

    def run(self):

        try:
            channel_layers[DEFAULT_CHANNEL_LAYER].router.check_default()
            self.worker = Worker(
                channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER],
            )
            self.worker.ready()
            self.is_ready.set()
            self.worker.run()
        except Exception:
            self.is_ready.set()
            raise


class LiveServerProcess(multiprocessing.Process):

    def __init__(self, host, possible_ports, port_storage, is_ready):

        self.host = host
        self.possible_ports = possible_ports
        self.port_storage = port_storage
        self.is_ready = is_ready
        super(LiveServerProcess, self).__init__()
        self.daemon = True

    def run(self):

        try:
            self.server = Server(
                channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER],
                # FIXME: process all possible ports, exit after first success.
                endpoints=[
                    'tcp:interface=%s:port=%d' % (self.host,
                                                  self.possible_ports[0])
                ],
            )
            self.port_storage.value = self.possible_ports[0]
            self.is_ready.set()
            self.server.run()
        except Exception:
            self.is_ready.set()
            raise


class LiveServerStub(object):

    def __init__(self, host, possible_ports):

        self.host = host
        self.possible_ports = possible_ports
        self.is_ready = threading.Event()

    def start(self):

        self.is_ready.set()

    error = None

    def terminate(self):

        pass

    def join(self):

        pass


class ChannelLiveServerTestCase(LiveServerTestCase):

    @property
    def live_server_url(self):

        return 'http://%s:%s' % (self._server_process.host,
                                 self._port_storage.value)

    @property
    def live_server_ws_url(self):

        return 'ws://%s:%s' % (self._server_process.host,
                               self._port_storage.value)

    @classmethod
    def _create_server_thread(cls, host, possible_ports, connections_override):

        return LiveServerStub(host, possible_ports)

    def _pre_setup(self):

        super(ChannelLiveServerTestCase, self)._pre_setup()
        self._port_storage = multiprocessing.Value('i')

        server_ready = multiprocessing.Event()
        self._server_process = LiveServerProcess(
            self.server_thread.host,
            self.server_thread.possible_ports,
            self._port_storage,
            server_ready,
        )
        self._server_process.start()
        server_ready.wait()

        worker_ready = multiprocessing.Event()
        self._worker_process = WorkerProcess(worker_ready)
        self._worker_process.start()
        worker_ready.wait()

    def _post_teardown(self):

        self._server_process.terminate()
        self._server_process.join()
        self._worker_process.terminate()
        self._worker_process.join()
        super(ChannelLiveServerTestCase, self)._post_teardown()
