# -*- coding: utf-8 -*-

from django.test import TestCase
try:
    from unittest import mock
except ImportError:
    import mock

from ..handler import AsgiRequest


class TestAsgiRequest(TestCase):

    def test_stream_is_readable(self):
        body = b'...'
        message = {"body": body,
                   "reply_channel": mock.Mock(),
                   "path": "/",
                   "method": "POST"}
        request = AsgiRequest(message)
        self.assertEqual(request.read(), body)
