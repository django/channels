from __future__ import unicode_literals

import logging

from asgiref.inmemory import ChannelLayer
from django.core.management import CommandError, call_command
from django.test import TestCase, mock
from six import StringIO

from channels.management.commands import runserver


class FakeChannelLayer(ChannelLayer):
    '''
    Dummy class to bypass the 'inmemory' string check.
    '''
    pass


class RunWorkerTests(TestCase):

    def setUp(self):
        import channels.log
        self.stream = StringIO()
        channels.log.handler = logging.StreamHandler(self.stream)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_runworker_no_local_only(self, mock_stdout, mock_stderr):
        with self.assertRaises(CommandError):
            call_command('runworker')

    @mock.patch('channels.management.commands.runworker.Worker')
    def test_debug(self, mocked_worker, *args, **kwargs):
        with self.settings(DEBUG=True, STATIC_URL='/static/'):
            call_command('runworker', '--layer', 'fake_channel')
            mocked_worker.assert_called_with(
                only_channels=None, exclude_channels=None, callback=None, channel_layer=mock.ANY)

    @mock.patch('channels.management.commands.runworker.Worker')
    def test_runworker(self, mocked_worker):
        call_command('runworker', '--layer', 'fake_channel')
        mocked_worker.assert_called_with(callback=None,
                                         only_channels=None,
                                         channel_layer=mock.ANY,
                                         exclude_channels=None)

    @mock.patch('channels.management.commands.runworker.Worker')
    def test_runworker_verbose(self, mocked_worker):
        call_command('runworker', '--layer',
                     'fake_channel', '--verbosity', '2')
        # Increasing verbosity adds the logger callback
        mocked_worker.assert_called_with(callback=mock.ANY,
                                         only_channels=None,
                                         channel_layer=mock.ANY,
                                         exclude_channels=None)


class RunServerTests(TestCase):

    def setUp(self):
        import channels.log
        self.stream = StringIO()
        channels.log.handler = logging.StreamHandler(self.stream)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('channels.management.commands.runserver.Server')
    @mock.patch('channels.management.commands.runworker.Worker')
    def test_runserver_basic(self, mocked_worker, mocked_server, mock_stdout, mock_stderr):
        call_command('runserver', '--noreload')
        mocked_server.assert_called_with(port=8000, signal_handlers=True, http_timeout=60,
                                         host='127.0.0.1', action_logger=mock.ANY, channel_layer=mock.ANY)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('channels.management.commands.runserver.Server')
    @mock.patch('channels.management.commands.runworker.Worker')
    def test_runserver_nostatic(self, mocked_worker, mocked_server, mock_stdout, mock_stderr):
        with self.settings(DEBUG=True, STATIC_URL='/static/'):
            call_command('runserver', '--noreload')
            mocked_server.assert_called_with(port=8000, signal_handlers=True, http_timeout=60,
                                             host='127.0.0.1', action_logger=mock.ANY, channel_layer=mock.ANY)

            call_command('runserver', '--noreload', 'localhost:8001')
            mocked_server.assert_called_with(port=8001, signal_handlers=True, http_timeout=60,
                                             host='localhost', action_logger=mock.ANY, channel_layer=mock.ANY)

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    @mock.patch('channels.management.commands.runserver.Server')
    def test_runserver_noworker(self, mocked_server, mock_stdout, mock_stderr):
        '''
        No need to Mock the Worker because it should not be used.
        '''
        call_command('runserver', '--noreload', '--noworker')

    @mock.patch('sys.stderr', new_callable=StringIO)
    @mock.patch('sys.stdout', new_callable=StringIO)
    def test_log_action(self, mock_stdout, mock_stderr):
        cmd = runserver.Command()
        test_actions = [
            (100, 'http', 'complete',
             'HTTP GET /a-path/ 100 [0.12, a-client]'),
            (200, 'http', 'complete',
             'HTTP GET /a-path/ 200 [0.12, a-client]'),
            (300, 'http', 'complete',
             'HTTP GET /a-path/ 300 [0.12, a-client]'),
            (304, 'http', 'complete',
             'HTTP GET /a-path/ 304 [0.12, a-client]'),
            (400, 'http', 'complete',
             'HTTP GET /a-path/ 400 [0.12, a-client]'),
            (404, 'http', 'complete',
             'HTTP GET /a-path/ 404 [0.12, a-client]'),
            (500, 'http', 'complete',
             'HTTP GET /a-path/ 500 [0.12, a-client]'),
            (None, 'websocket', 'connected',
             'WebSocket CONNECT /a-path/ [a-client]'),
            (None, 'websocket', 'disconnected',
             'WebSocket DISCONNECT /a-path/ [a-client]'),
            (None, 'websocket', 'something', ''),  # This shouldn't happen
        ]

        for status_code, protocol, action, output in test_actions:
            details = {'status': status_code,
                       'method': 'GET',
                       'path': '/a-path/',
                       'time_taken': 0.12345,
                       'client': 'a-client'}
            cmd.log_action(protocol, action, details)
            self.assertIn(output, mock_stderr.getvalue())
            # Clear previous output
            mock_stderr.truncate(0)
