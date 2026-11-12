from urllib.error import HTTPError
from urllib.request import urlopen

from django.core import mail
from django.http import HttpResponse
from django.test import override_settings
from django.urls import path

from channels.testing import ChannelsLiveServerTestCase
from tests.sample_project.sampleapp.models import Message


def send_mail_view(request):
    mail.send_mail("subject", "body", "from@example.com", ["to@example.com"])
    return HttpResponse("sent")


def count_messages_view(request):
    return HttpResponse(str(Message.objects.count()))


urlpatterns = [
    path("send-mail/", send_mail_view),
    path("count-messages/", count_messages_view),
]


@override_settings(ROOT_URLCONF=__name__)
class ChannelsLiveServerTestCaseTests(ChannelsLiveServerTestCase):
    def test_server_shares_process_state_with_tests(self):
        """
        The live server runs in a thread of the test process, so the locmem
        email outbox is visible from the test (#2194).
        """
        with urlopen(self.live_server_url + "/send-mail/") as response:
            self.assertEqual(response.read(), b"sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "subject")

    def test_server_sees_data_created_by_tests(self):
        Message.objects.create(title="title", message="message")
        with urlopen(self.live_server_url + "/count-messages/") as response:
            self.assertEqual(response.read(), b"1")

    def test_static_files_are_served_by_default(self):
        url = self.live_server_url + "/static/sampleapp/js/scripts.js"
        with urlopen(url) as response:
            self.assertEqual(response.status, 200)

    def test_live_server_urls(self):
        port = self.server_thread.port
        self.assertNotEqual(port, 0)
        self.assertEqual(self.live_server_url, f"http://localhost:{port}")
        self.assertEqual(self.live_server_ws_url, f"ws://localhost:{port}")


@override_settings(ROOT_URLCONF=__name__)
class ChannelsLiveServerTestCaseNoStaticTests(ChannelsLiveServerTestCase):
    serve_static = False

    def test_static_files_are_not_served(self):
        url = self.live_server_url + "/static/sampleapp/js/scripts.js"
        with self.assertRaises(HTTPError) as cm:
            urlopen(url)
        self.assertEqual(cm.exception.code, 404)
