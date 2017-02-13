from __future__ import unicode_literals

from datetime import timedelta

from django.utils import timezone

from channels import DEFAULT_CHANNEL_LAYER, Channel, channel_layers
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


@mock.patch('channels.scheduler.worker.BackgroundScheduler')
class WorkerTests(ChannelTestCase):

    def test_assert_invalid_message_is_not_scheduled(self, _):
        """
        Tests the worker won't schedule an invalid message
        """
        Channel('asgi.schedule').send({'test': 'value'}, immediately=True)

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        worker.scheduler.add_job.assert_not_called()

    def test_assert_schedule_add_date_message_arguments_are_passed(self, _):
        """
        Tests that apscheduler add_job() is invoked with the provided arguments
        in the channels message
        """
        message = {
            'method': 'add',
            'reply_channel': 'test',
            'trigger': 'date',
            'run_date': timezone.now(),
            'content': {'test': 'value'},
        }
        Channel('asgi.schedule').send(message, immediately=True)

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        worker.scheduler.add_job.assert_called_once()
        args, kwargs = worker.scheduler.add_job.call_args
        self.assertEqual(args[0], worker.send_message)
        self.assertEqual(kwargs.pop('trigger'), message['trigger'])
        self.assertEqual(kwargs.pop('args'), [DEFAULT_CHANNEL_LAYER, message['reply_channel'], message['content']]),
        self.assertEqual(kwargs.pop('run_date'), message['run_date'])

        for value in kwargs.values():
            self.assertEqual(value, None)

    def test_assert_schedule_add_job_all_arguments_are_passed(self, _):
        """
        Tests that all possible arguments are passed to apscheduler add_job()
        """
        message = {
            'method': 'add',
            'reply_channel': 'test',
            'content': {'test': 'value'},
            'id': 'unique_identifier',
            'trigger': 'date',
            'year': '1',
            'month': '2',
            'day': '3',
            'week': '4',
            'day_of_week': '5',
            'hour': '6',
            'minute': '7',
            'second': '8',
            'run_date': timezone.now(),
            'weeks': 9,
            'days': 10,
            'hours': 11,
            'minutes': 12,
            'seconds': 13,
            'start_date': timezone.now() + timedelta(minutes=1),
            'end_date': timezone.now() + timedelta(minutes=2),
        }
        Channel('asgi.schedule').send(message, immediately=True)

        worker = PatchedWorker(channel_layers[DEFAULT_CHANNEL_LAYER])
        worker.termed = 1

        worker.run()

        worker.scheduler.add_job.assert_called_once()
        args, kwargs = worker.scheduler.add_job.call_args
        self.assertEqual(args[0], worker.send_message)
        self.assertEqual(
            kwargs['args'],
            [DEFAULT_CHANNEL_LAYER, message.pop('reply_channel'), message.pop('content')])

        message.pop('method')
        for key, value in message.items():
            self.assertEqual(value, kwargs[key])
