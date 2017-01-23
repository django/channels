import websocket

from channels.routing import route
from channels.tests import ChannelLiveServerTestCase, apply_routes


def ping_pong(message):
    assert message.content['text'] == 'ping'
    message.reply_channel.send({'text': 'pong'})


@apply_routes([
    route('websocket.receive', ping_pong),
])
class WebSocketTest(ChannelLiveServerTestCase):
    """Send and receive messages over WebSocket."""

    def test_send_recv(self):

        ws = websocket.create_connection(self.live_server_ws_url)
        ws.send('ping')
        response = ws.recv()
        ws.close()
        self.assertEqual('pong', response)
