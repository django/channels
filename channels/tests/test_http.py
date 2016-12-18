from __future__ import unicode_literals

from django.http.cookie import parse_cookie
from six.moves.urllib.parse import unquote

from channels.tests.http import HttpClient
from channels.tests import ChannelTestCase

class HttpClientTests(ChannelTestCase):
    def test_cookies(self):
        client = HttpClient()
        client.set_cookie('foo', 'b;ar')

        # Django's interpretation of the serialized cookie.
        cookie_dict = parse_cookie(client.headers['cookie'].decode('ascii'))

        self.assertEqual(client.get_cookies(),
                         {k: unquote(v)
                          for k, v in cookie_dict.items()})

        self.assertEqual({'foo': 'b%3Bar',
                          'sessionid': client.get_cookies()['sessionid']},
                         cookie_dict)
