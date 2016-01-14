# -*- coding: utf-8 -*-

from django.test import TestCase

from ..handler import AsgiRequest
from ..message import Message


class TestAsgiRequest(TestCase):

    def test_stream_is_readable(self):
        text = '...'
        message = Message({text: text}, None, None)
        request = AsgiRequest(message)
        self.assertEqual(request.read(), text)
