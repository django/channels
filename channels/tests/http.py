
import copy
from django.apps import apps
from django.conf import settings


from ..asgi import channel_layers
from ..message import Message
from ..sessions import session_for_reply_channel
from .base import Client


class HttpClient(Client):
    """
    Channel http/ws client abstraction that provides easy methods for testing full live cycle of message in channels
    with determined reply channel, auth opportunity and so on
    """

    def __init__(self, **kwargs):
        super(HttpClient, self).__init__(**kwargs)
        self._session = None

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
        content.setdefault('path', '/')
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
