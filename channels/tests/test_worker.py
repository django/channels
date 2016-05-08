from __future__ import unicode_literals
from django.test import SimpleTestCase

try:
    from unittest import mock
except ImportError:
    import mock

from channels.worker import Worker
from channels.exceptions import ConsumeLater


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


class WorkerTests(SimpleTestCase):
    """
    Tests that the router's routing code works correctly.
    """

    def test_channel_filters(self):
        """
        Tests that the include/exclude logic works
        """
        # Include
        worker = Worker(None, only_channels=["yes.*", "maybe.*"])
        self.assertEqual(
            worker.apply_channel_filters(["yes.1", "no.1"]),
            ["yes.1"],
        )
        self.assertEqual(
            worker.apply_channel_filters(["yes.1", "no.1", "maybe.2", "yes"]),
            ["yes.1", "maybe.2"],
        )
        # Exclude
        worker = Worker(None, exclude_channels=["no.*", "maybe.*"])
        self.assertEqual(
            worker.apply_channel_filters(["yes.1", "no.1", "maybe.2", "yes"]),
            ["yes.1", "yes"],
        )
        # Both
        worker = Worker(None, exclude_channels=["no.*"], only_channels=["yes.*"])
        self.assertEqual(
            worker.apply_channel_filters(["yes.1", "no.1", "maybe.2", "yes"]),
            ["yes.1"],
        )

    def test_run_with_consume_later_error(self):

        # consumer with ConsumeLater error at first call
        def _consumer(message, **kwargs):
            if not hasattr(_consumer, '_called'):
                _consumer._called = True
                raise ConsumeLater()

        consumer = mock.Mock(side_effect=_consumer)
        chenels = ['test', ]
        channel_layer = mock.MagicMock()
        channel_layer.router.channels = chenels
        channel_layer.receive_many = mock.MagicMock(return_value=('test', {}))
        channel_layer.send = mock.MagicMock()
        channel_layer.router.match = mock.MagicMock(return_value=(consumer, {}))

        worker = PatchedWorker(channel_layer)
        worker.termed = 2  # first loop with error, second with sending

        worker.run()

        channel_layer.receive_many.assert_called_with(chenels, block=True)
        self.assertEqual(channel_layer.receive_many.call_count, 2)
        self.assertEqual(channel_layer.router.match.call_count, 2)
        self.assertEqual(consumer.call_count, 2)
        self.assertEqual(channel_layer.send.call_count, 1)

    def test_normal_run(self):
        channel_layer = mock.MagicMock()
        consumer = mock.Mock()
        chenels = ['test', ]
        channel_layer.router.channels = chenels
        channel_layer.receive_many = mock.MagicMock(return_value=('test', {}))
        channel_layer.send = mock.MagicMock()

        channel_layer.router.match = mock.MagicMock(return_value=(consumer, {}))
        worker = PatchedWorker(channel_layer)
        worker.termed = 1

        worker.run()

        channel_layer.receive_many.assert_called_once_with(chenels, block=True)
        self.assertEqual(channel_layer.router.match.call_count, 1)
        self.assertEqual(consumer.call_count, 1)
        self.assertEqual(channel_layer.send.call_count, 0)
