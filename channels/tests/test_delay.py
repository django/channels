from __future__ import unicode_literals

from datetime import timedelta
import json

try:
    from unittest import mock
except ImportError:
    import mock

from django.utils import timezone

from channels import Channel, channel_layers, DEFAULT_CHANNEL_LAYER
from channels.delay.models import DelayedMessage
from channels.delay.worker import Worker
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

    def test_invalid_message(self):
        """
        Tests the worker won't delay an invalid message
        """
        Channel('channels.delay').send({'test': 'value'}, immediately=True)

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        self.assertEqual(DelayedMessage.objects.count(), 0)

    def test_delay_message(self):
        """
        Tests the message is delayed and dispatched when due
        """
        Channel('channels.delay').send({
            'channel': 'test',
            'delay': 10,
            'content': {'test': 'value'}
        }, immediately=True)

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        self.assertEqual(DelayedMessage.objects.count(), 1)

        with mock.patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(seconds=10)):
            worker.termed = 1
            worker.run()

        self.assertEqual(DelayedMessage.objects.count(), 0)

        message = self.get_next_message('test', require=True)
        self.assertEqual(message.content, {'test': 'value'})

    def test_interval_message(self):
        """
        Tests the message is sent repeatidly on an interval
        """

        Channel('channels.delay').send({
            'channel': 'test',
            'interval': 10,
            'content': {'test': 'value'}
        }, immediately=True)

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        self.assertEqual(DelayedMessage.objects.count(), 1)

        with mock.patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(seconds=10)):
            worker.termed = 1
            worker.run()

        message = self.get_next_message('test', require=True)
        self.assertEqual(message.content, {'test': 'value'})

        self.assertEqual(DelayedMessage.objects.count(), 1)

        # second time around
        with mock.patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(seconds=21)):
            worker.termed = 1
            worker.run()

        self.get_next_message('test', require=True)


class DelayedMessageTests(ChannelTestCase):

    def _create_message(self):
        kwargs = {
            'content': json.dumps({'test': 'data'}),
            'channel_name': 'test',
            'delay': 10
        }
        delayed_message = DelayedMessage(**kwargs)
        delayed_message.save()

        return delayed_message

    def test_is_due(self):
        message = self._create_message()

        self.assertEqual(DelayedMessage.objects.is_due().count(), 0)

        with mock.patch('django.utils.timezone.now', return_value=message.due_date + timedelta(seconds=10)):
            self.assertEqual(DelayedMessage.objects.is_due().count(), 1)

    def test_send(self):
        message = self._create_message()
        message.send(channel_layer=channel_layers[DEFAULT_CHANNEL_LAYER])

        self.get_next_message(message.channel_name, require=True)
