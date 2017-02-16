import threading

from daphne.server import Server
from django.test.testcases import LiveServerTestCase
from twisted.internet import reactor

from .. import DEFAULT_CHANNEL_LAYER
from ..asgi import channel_layers
from ..worker import Worker
from .base import ChannelTestCaseMixin


# TODO: Is ready event for this thread.
#
# TODO: What we need to do in the case of multiple channel layers?
class WorkerThread(threading.Thread):

    def run(self):

        channel_layers[DEFAULT_CHANNEL_LAYER].router.check_default()
        self.worker = Worker(
            channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER],
            signal_handlers=False,
        )
        self.worker.ready()
        self.worker.run()

    def terminate(self):

        if hasattr(self, 'worker'):
            self.worker.termed = True


# TODO: `self.connections_override` should be processed same way as in
# regular LiveServerTestCase.
class LiveServerThread(threading.Thread):

    def __init__(self,
                 host,
                 possible_ports,
                 static_handler,
                 connections_override=None):

        self.host = host
        self.possible_ports = possible_ports
        self.static_handler = static_handler
        self.connections_override = connections_override

        self.error = None
        self.is_ready = threading.Event()
        self.worker_thread = WorkerThread()
        super(LiveServerThread, self).__init__()

    def run(self):

        try:
            self.server = Server(
                channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER],
                # FIXME: process all possible ports, exit after first success.
                endpoints=[
                    'tcp:interface=%s:port=%d' % (self.host,
                                                  self.possible_ports[0])
                ],
                signal_handlers=False,
            )
            self.port = self.possible_ports[0]
            self.is_ready.set()
            self.server.run()
        except Exception as e:
            self.error = e
            self.is_ready.set()

    def terminate(self):

        if hasattr(self, 'server') and reactor.running:
            reactor.stop()


class LiveServerPool(object):

    def __init__(self,
                 host,
                 possible_ports,
                 static_handler,
                 connections_override=None):

        self.server_thread = LiveServerThread(
            host,
            possible_ports,
            static_handler,
            connections_override,
        )
        self.host = self.server_thread.host
        self.is_ready = self.server_thread.is_ready
        self.worker_thread = WorkerThread()

    @property
    def port(self):

        return self.server_thread.port

    @property
    def daemon(self):

        raise RuntimeError('You can use setter only on daemon property')

    @daemon.setter
    def daemon(self, value):

        self.server_thread.daemon = value
        self.worker_thread.daemon = value

    def start(self):

        self.server_thread.start()
        self.worker_thread.start()

    @property
    def error(self):

        return self.server_thread.error

    def terminate(self):

        self.server_thread.terminate()
        self.worker_thread.terminate()

    def join(self):

        self.server_thread.join()
        self.worker_thread.join()


class ChannelLiveServerTestCase(ChannelTestCaseMixin, LiveServerTestCase):

    @property
    def live_server_ws_url(self):
        return 'ws://%s:%s' % (self.server_thread.host,
                               self.server_thread.port)

    @classmethod
    def _create_server_thread(cls, host, possible_ports, connections_override):
        return LiveServerPool(
            host,
            possible_ports,
            cls.static_handler,
            connections_override=connections_override,
        )
