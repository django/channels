import copy
import random
import string
from functools import wraps

from django.test.testcases import TestCase
from channels import DEFAULT_CHANNEL_LAYER
from channels.routing import Router, include
from channels.asgi import channel_layers, ChannelLayerWrapper
from channels.message import Message
from asgiref.inmemory import ChannelLayer as InMemoryChannelLayer


class ChannelTestCase(TestCase):
    """
    TestCase subclass that provides easy methods for testing channels using
    an in-memory backend to capture messages, and assertion methods to allow
    checking of what was sent.

    Inherits from TestCase, so provides per-test transactions as long as the
    database backend supports it.
    """

    # Customizable so users can test multi-layer setups
    test_channel_aliases = [DEFAULT_CHANNEL_LAYER]

    def setUp(self):
        """
        Initialises in memory channel layer for the duration of the test
        """
        super(ChannelTestCase, self).setUp()
        self._old_layers = {}
        self._clients = {}
        for alias in self.test_channel_aliases:
            # Swap in an in memory layer wrapper and keep the old one around
            self._old_layers[alias] = channel_layers.set(
                alias,
                ChannelLayerWrapper(
                    InMemoryChannelLayer(),
                    alias,
                    channel_layers[alias].routing[:],
                )
            )
            self._clients[alias] = Client(alias)
        self.client = self._clients[DEFAULT_CHANNEL_LAYER]

    def tearDown(self):
        """
        Undoes the channel rerouting
        """
        for alias in self.test_channel_aliases:
            # Swap in an in memory layer wrapper and keep the old one around
            channel_layers.set(alias, self._old_layers[alias])
        del self._old_layers
        super(ChannelTestCase, self).tearDown()

    def get_client(self, alias=DEFAULT_CHANNEL_LAYER):
        return self._clients[alias]

    def get_next_message(self, channel, alias=DEFAULT_CHANNEL_LAYER, require=False):
        """
        Gets the next message that was sent to the channel during the test,
        or None if no message is available.

        If require is true, will fail the test if no message is received.
        """
        message = self._clients[alias].get_next_message(channel)
        if message is None:
            if require:
                self.fail("Expected a message on channel %s, got none" % channel)
            else:
                return None
        return message

    def assertInReplyChannel(self, d, alias=DEFAULT_CHANNEL_LAYER):
        self.assertDictEqual(self._clients[alias].receive(), d)


class Client(object):
    """
    Channel client abstraction that provides easy methods for testing full live cycle of message in channels
    with determined the reply channel
    """

    def __init__(self, alias=DEFAULT_CHANNEL_LAYER):
        self.reply_channel = alias + ''.join([random.choice(string.ascii_letters) for _ in range(5)])
        self.alias = alias

    @property
    def channel_layer(self):
        """Channel layer as lazy property"""
        return channel_layers[self.alias]

    def get_next_message(self, channel):
        """
        Gets the next message that was sent to the channel during the test,
        or None if no message is available.
        """
        recv_channel, content = channel_layers[self.alias].receive_many([channel])
        if recv_channel is None:
            return
        return Message(content, recv_channel, channel_layers[self.alias])

    def send(self, to, content={}):
        """
        Send a message to a channel.
        Adds reply_channel name to the message.
        """
        content = copy.deepcopy(content)
        content.setdefault('reply_channel', self.reply_channel)
        self.channel_layer.send(to, content)

    def consume(self, channel):
        """
        Get next message for channel name and run appointed consumer
        """
        message = self.get_next_message(channel)
        if message:
            consumer, kwargs = self.channel_layer.router.match(message)
            return consumer(message, **kwargs)

    def send_and_consume(self, channel, content={}):
        """
        Reproduce full live cycle of the message
        """
        self.send(channel, content)
        return self.consume(channel)

    def receive(self):
        """self.get_next_message(self.reply_channel)
        Get content of next message for reply channel if message exists
        """
        message = self.get_next_message(self.reply_channel)
        if message:
            return message.content


class apply_routes(object):
    """
    Decorator/ContextManager for rewrite layers routes in context.
    Helpful for testing group routes/consumers as isolated application

    The applying routes can be list of instances of Route or list of this lists
    """

    def __init__(self, routes, aliases=[DEFAULT_CHANNEL_LAYER]):
        self._aliases = aliases
        self.routes = routes
        self._old_routing = {}

    def enter(self):
        """
        Store old routes and apply new one
        """
        for alias in self._aliases:
            channel_layer = channel_layers[DEFAULT_CHANNEL_LAYER]
            self._old_routing[alias] = channel_layer.routing
            if isinstance(self.routes, (list, tuple)):
                if isinstance(self.routes[0], (list, tuple)):
                    routes = list(map(include, self.routes))
                else:
                    routes = self.routes

            channel_layer.routing = routes
            channel_layer.router = Router(routes)

    def exit(self, exc_type=None, exc_val=None, exc_tb=None):
        """
        Undoes rerouting
        """
        for alias in self._aliases:
            channel_layer = channel_layers[DEFAULT_CHANNEL_LAYER]
            channel_layer.routing = self._old_routing[alias]
            channel_layer.router = Router(self._old_routing[alias])

    __enter__ = enter
    __exit__ = exit

    def __call__(self, test_func):
        if isinstance(test_func, type):
            old_setup = test_func.setUp
            old_teardown = test_func.tearDown

            def new_setup(this):
                self.enter()
                old_setup(this)

            def new_teardown(this):
                self.exit()
                old_teardown(this)

            test_func.setUp = new_setup
            test_func.tearDown = new_teardown
            return test_func
        else:
            @wraps(test_func)
            def inner(*args, **kwargs):
                with self:
                    return test_func(*args, **kwargs)
            return inner