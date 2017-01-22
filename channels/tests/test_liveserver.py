import websocket

from channels.tests import ChannelLiveServerTestCase


class WebSocketTest(ChannelLiveServerTestCase):
    """Send and receive messages over WebSocket."""

    def test_send_recv(self):

        ws = websocket.create_connection(self.live_server_ws_url)
        ws.send('test')
        response = ws.recv()
        ws.close()
        self.assertEqual('test', response)
