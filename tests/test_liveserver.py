import websocket

from channels.routing import route
from channels.test import ChannelLiveServerTestCase, apply_routes


def connect(message):

    message.reply_channel.send({'accept': True})


def ping_pong(message):

    assert message.content['text'] == 'ping'
    message.reply_channel.send({'text': 'pong'})


ping_pong_routing = apply_routes(
    [route('websocket.connect', connect),
     route('websocket.receive', ping_pong)],
    aliases=['ipc'],
)


@ping_pong_routing
class WebSocketTest(ChannelLiveServerTestCase):
    """Send and receive messages over WebSocket."""

    def test_send_recv(self):

        ws = websocket.create_connection(self.live_server_ws_url)
        ws.send('ping')
        response = ws.recv()
        ws.close()
        self.assertEqual('pong', response)


@ping_pong_routing
class SecondWebSocketTest(ChannelLiveServerTestCase):
    """
    This class do the same as previous ones.  We made this to be sure
    we can start and stop live server several times.  Live server
    depends on twisted reactor which can be run only once during
    program live circle.
    """

    test_send_recv = WebSocketTest.test_send_recv
