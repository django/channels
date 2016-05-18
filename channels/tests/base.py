import copy
import random
import string

from django.test.testcases import TestCase
from django.apps import apps
from django.conf import settings
from channels import DEFAULT_CHANNEL_LAYER
from channels.asgi import channel_layers, ChannelLayerWrapper
from channels.message import Message
from channels.sessions import session_for_reply_channel
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
    with determined reply channel, auth opportunity and so on
    """

    def __init__(self, alias=DEFAULT_CHANNEL_LAYER):
        self.reply_channel = alias + ''.join([random.choice(string.ascii_letters) for _ in range(5)])
        self._session = None
        self.alias = alias

    @property
    def session(self):
        """Session as Lazy property: check that django.contrib.sessions is installed"""
        if not apps.is_installed('django.contrib.sessions'):
            raise EnvironmentError('Add django.contrib.sessions to the INSTALLED_APPS to use session')
        if not self._session:
            self._session = session_for_reply_channel(self.reply_channel)
        return self._session

    @property
    def channel_layer(self):
        """Channel layer as lazy property"""
        return channel_layers[self.alias]

    def get_next_message(self, channel):
        """
        Gets the next message that was sent to the channel during the test,
        or None if no message is available.

        If require is true, will fail the test if no message is received.
        """
        recv_channel, content = channel_layers[self.alias].receive_many([channel])
        if recv_channel is None:
            return
        return Message(content, recv_channel, channel_layers[self.alias])

    def send(self, to, content={}):
        """
        Send a message to a channel.
        Adds reply_channel name and channel_session to the message.
        """
        content = copy.deepcopy(content)
        if apps.is_installed('django.contrib.sessions'):
            if '.' in to and to.split('.')[1] == 'connect':
                content.setdefault('headers', {
                    'cookie': ('%s=%s' % (settings.SESSION_COOKIE_NAME, self.session.session_key)).encode("ascii")
                })
            content.setdefault('channel_session', self.session)
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

    def login(self, **credentials):
        """
        Stolen from django
        Returns True if login is possible; False if the provided credentials
        are incorrect, or the user is inactive, or if the sessions framework is
        not available.
        """
        from django.contrib.auth import authenticate
        user = authenticate(**credentials)
        if user and user.is_active and apps.is_installed('django.contrib.sessions'):
            self._login(user)
            return True
        else:
            return False

    def force_login(self, user, backend=None):
        if backend is None:
            backend = settings.AUTHENTICATION_BACKENDS[0]
        user.backend = backend
        self._login(user)

    def _login(self, user):
        from django.contrib.auth import login

        # Fake http request
        request = type('FakeRequest', (object, ), {'session': self.session, 'META': {}})
        login(request, user)

        # Save the session values.
        self.session.save()
