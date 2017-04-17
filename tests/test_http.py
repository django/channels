from __future__ import unicode_literals

from django.http.cookie import parse_cookie

from channels import route
from channels.test import ChannelTestCase, HttpClient, apply_routes
from channels.sessions import enforce_ordering


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

    def test_ordering_in_content(self):
        client = HttpClient(ordered=True)
        content = client._get_content()
        self.assertTrue('order' in content)
        self.assertEqual(content['order'], 0)
        client.order = 2
        content = client._get_content()
        self.assertTrue('order' in content)
        self.assertEqual(content['order'], 2)

    def test_ordering(self):

        client = HttpClient(ordered=True)

        @enforce_ordering
        def consumer(message):
            message.reply_channel.send({'text': message['text']})

        with apply_routes(route('websocket.receive', consumer)):
            client.send_and_consume('websocket.receive', text='1')  # order = 0
            client.send_and_consume('websocket.receive', text='2')  # order = 1
            client.send_and_consume('websocket.receive', text='3')  # order = 2

            self.assertEqual(client.receive(), 1)
            self.assertEqual(client.receive(), 2)
            self.assertEqual(client.receive(), 3)
