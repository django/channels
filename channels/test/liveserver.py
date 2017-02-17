import multiprocessing

from daphne.server import Server
from django.test.testcases import LiveServerTestCase

from .. import DEFAULT_CHANNEL_LAYER
from ..asgi import channel_layers
from ..worker import Worker

DEFAULT_CHANNEL_LAYER = 'ipc'  # FIXME: override in test


# TODO: Is ready event for this process.
#
# TODO: What we need to do in the case of multiple channel layers?
class WorkerProcess(multiprocessing.Process):

    def run(self):

        channel_layers[DEFAULT_CHANNEL_LAYER].router.check_default()
        self.worker = Worker(
            channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER],
        )
        self.worker.ready()
        self.worker.run()


# TODO: `self.connections_override` should be processed same way as in
# regular LiveServerTestCase.
class LiveServerProcess(multiprocessing.Process):

    def __init__(self, host, possible_ports, static_handler,
                 connections_override, port_storage, is_ready):

        self.host = host
        self.possible_ports = possible_ports
        self.static_handler = static_handler
        self.connections_override = connections_override
        self.port_storage = port_storage
        self.is_ready = is_ready
        super(LiveServerProcess, self).__init__()

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
        except Exception as e:
            self.is_ready.set()


class LiveServerPool(object):

    def __init__(self,
                 host,
                 possible_ports,
                 static_handler,
                 connections_override=None):

        self.host = host
        self.port_storage = multiprocessing.Value('i')
        self.is_ready = multiprocessing.Event()
        self.server_process = LiveServerProcess(
            host, possible_ports, static_handler, connections_override,
            self.port_storage, self.is_ready)
        self.worker_process = WorkerProcess()

    @property
    def port(self):

        return self.port_storage.value

    @property
    def daemon(self):

        raise RuntimeError('You can use setter only on daemon property')

    @daemon.setter
    def daemon(self, value):

        self.server_process.daemon = value
        self.worker_process.daemon = value

    def start(self):

        self.server_process.start()
        self.worker_process.start()

    @property
    def error(self):

        error = self.server_process.exitcode
        if error:
            return Exception('Daphne process exitcode is %d' % error)
        error = self.worker_process.exitcode
        if error:
            return Exception('Worker process exitcode is %d' % error)

    def terminate(self):

        self.server_process.terminate()
        self.worker_process.terminate()

    def join(self):

        self.server_process.join()
        self.worker_process.join()


class ChannelLiveServerTestCase(LiveServerTestCase):

    @property
    def live_server_ws_url(self):
        return 'ws://%s:%s' % (self.server_thread.host,
                               self.server_thread.port)

    @classmethod
    def _create_server_thread(cls, host, possible_ports, connections_override):
        return LiveServerPool(host, possible_ports, cls.static_handler,
                              connections_override)
