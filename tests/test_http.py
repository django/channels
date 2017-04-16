from __future__ import unicode_literals

from django.http.cookie import parse_cookie

from channels.test import ChannelTestCase, HttpClient


class HttpClientTests(ChannelTestCase):
    def test_cookies(self):
        client = HttpClient()
        client.set_cookie('foo', 'not-bar')
        client.set_cookie('foo', 'bar')
        client.set_cookie('qux', 'qu;x')

        # Django's interpretation of the serialized cookie.
        cookie_dict = parse_cookie(client.headers['cookie'].decode('ascii'))

        self.assertEqual(client.get_cookies(),
                         cookie_dict)

        self.assertEqual({'foo': 'bar',
                          'qux': 'qu;x',
                          'sessionid': client.get_cookies()['sessionid']},
                         cookie_dict)

    def test_simple_content(self):
        client = HttpClient()
        content = client._get_content(text={'key': 'value'}, path='/my/path')

        self.assertEqual(content['text'], '{"key": "value"}')
        self.assertEqual(content['path'], '/my/path')
        self.assertTrue('reply_channel' in content)
        self.assertTrue('headers' in content)

    def test_path_in_content(self):
        client = HttpClient()
        content = client._get_content(content={'path': '/my_path'}, text={'path': 'hi'}, path='/my/path')

        self.assertEqual(content['text'], '{"path": "hi"}')
        self.assertEqual(content['path'], '/my_path')
        self.assertTrue('reply_channel' in content)
        self.assertTrue('headers' in content)

    def test_session_in_headers(self):
        client = HttpClient()
        content = client._get_content()
        self.assertTrue('path' in content)
        self.assertEqual(content['path'], '/')

        self.assertTrue('headers' in content)
        self.assertTrue('cookie' in content['headers'])
        self.assertTrue('sessionid' in content['headers']['cookie'])


