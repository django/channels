from __future__ import unicode_literals

try:
    from unittest import mock
except ImportError:
    import mock
import time

from channels import Channel, channel_layers, DEFAULT_CHANNEL_LAYER
from channels.delay import DelayedMessage, Worker
from channels.tests import ChannelTestCase


class PatchedWorker(Worker):
    """Worker with specific numbers of loops"""
    def get_termed(self):
        if not self.__iters:
            return True
        self.__iters -= 1
        return False

    def set_termed(self, value):
        self.__iters = value

    termed = property(get_termed, set_termed)


class WorkerTests(ChannelTestCase):
    """
    Tests that the worker receives messages to delay and dispatches them.
    """
    def test_invalid_message(self):
        """
        Tests the worker won't delay an invalid message
        """
        Channel('channels.delay').send({'test': 'value'}, immediately=True)

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        self.assertEqual(len(worker.delayed_messages), 0)

    def test_due_message(self):
        """
        Tests the message is dispatched when due
        """
        Channel('channels.delay').send({
            'channel': 'test',
            'delay': 10,
            'content': {'test': 'value'}
        }, immediately=True)

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        self.assertEqual(len(worker.delayed_messages), 1)

        with mock.patch('time.time', return_value=time.time() + 10):
            worker.termed = 1
            worker.run()

        message = self.get_next_message('test', require=True)
        self.assertEqual(message.content, {'test': 'value'})


class DelayedMessageTests(ChannelTestCase):

    def _create_message(self):
        content = {
            'delay': 100,
            'content': {'test': 'data'},
            'channel': 'test'
        }
        message = DelayedMessage(
            content=content,
            channel_name=content['channel'],
            channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER]
        )
        return message

    def test_is_due(self):
        message = self._create_message()

        self.assertFalse(message.is_due())

        with mock.patch('time.time', return_value=message.due_date + 1):
            self.assertTrue(message.is_due())

    def test_send(self):
        message = self._create_message()
        message.send()

        self.get_next_message(message.channel.name, require=True)
