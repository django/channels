from __future__ import unicode_literals

from datetime import timedelta

from django.utils import timezone

from channels import DEFAULT_CHANNEL_LAYER, Channel, channel_layers
from channels.scheduler.models import CronMessage
from channels.scheduler.worker import Worker
from channels.tests import ChannelTestCase

try:
    from unittest import mock
except ImportError:
    import mock


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

    def test_cron_message(self):
        """
        Tests the message is scheduled and dispatched when due
        """
        now = timezone.now()
        message = CronMessage(
            content='{"test": "value"}',
            cron_schedule="{} {} * * *".format(now.minute, (now.hour+1)%23),
            channel_name="test_channel",
        )
        message.save()

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        message = self.get_next_message('test_channel')
        self.assertIsNone(message)

        with mock.patch(
                'django.utils.timezone.now',
                return_value=timezone.now() + timedelta(hours=(now.hour+1)%23)):
            worker.termed = 1
            worker.run()

        message = self.get_next_message('test_channel', require=True)
        self.assertEqual(message.content, {'test': 'value'})
