import httpx
from django.conf import settings

from channels.testing import ChannelsLiveServerTestCase


def test_settings():
    assert settings.SETTINGS_MODULE == "tests.testproject.settings"


class TestLiveNoStatic(ChannelsLiveServerTestCase):
    serve_static = False

    def test_properties(self):
        # test properties
        self.assertEqual(
            self.live_server_ws_url, self.live_server_url.replace("http", "ws", 1)
        )

    def test_resolving(self):
        result = httpx.get(f"{self.live_server_url}/admin", follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        result = httpx.get(f"{self.live_server_url}/addsdsmidsdsn")
        self.assertEqual(result.status_code, 404)


class TestLiveWithStatic(ChannelsLiveServerTestCase):
    def test_properties(self):
        # test properties
        self.assertEqual(
            self.live_server_ws_url, self.live_server_url.replace("http", "ws", 1)
        )

    def test_resolving(self):
        result = httpx.get(f"{self.live_server_url}/admin", follow_redirects=True)
        self.assertEqual(result.status_code, 200)
        result = httpx.get(f"{self.live_server_url}/addsdsmidsdsn")
        self.assertEqual(result.status_code, 404)
