from __future__ import unicode_literals

from django.http.cookie import parse_cookie

from channels.tests.http import HttpClient
from channels.tests import ChannelTestCase

class HttpClientTests(ChannelTestCase):
    def test_cookies(self):
        client = HttpClient()
        client.set_cookie('foo', 'bar')

        # Django's interpretation of the serialized cookie.
        cookie_dict = parse_cookie(client.headers['cookie'].decode('ascii'))

        self.assertEqual(client.get_cookies(),
                         cookie_dict)

        self.assertEqual({'foo': 'bar',
                          'sessionid': client.get_cookies()['sessionid']},
                         cookie_dict)
