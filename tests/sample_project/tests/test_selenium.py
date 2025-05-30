from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from channels.testing import ChannelsLiveServerTestCase
from tests.sample_project.sampleapp.models import Message

from .selenium_mixin import SeleniumMixin


class TestSampleApp(SeleniumMixin, ChannelsLiveServerTestCase):
    serve_static = True

    def setUp(self):
        super().setUp()
        self.login()
        self.open("/admin/sampleapp/message/")
        self.wait_for_websocket_connection()

    def _create_message(self, title="Test Title", message="Test Message"):
        return Message.objects.create(title=title, message=message)

    def _wait_for_exact_text(self, by, locator, exact, timeout=2):
        WebDriverWait(self.web_driver, timeout).until(
            lambda driver: driver.find_element(by, locator).text == str(exact)
        )

    def test_real_time_create_message(self):
        self.web_driver.switch_to.new_window("tab")
        tabs = self.web_driver.window_handles
        self.web_driver.switch_to.window(tabs[1])

        self.open("/admin/sampleapp/message/")
        titleInput = self.find_element(By.ID, "msgTitle")
        self.assertIsNotNone(titleInput, "Title input should be present")
        messageInput = self.find_element(By.ID, "msgTextArea")
        self.assertIsNotNone(messageInput, "Message input should be present")
        addMessageButton = self.find_element(By.ID, "sendBtn")
        self.assertIsNotNone(addMessageButton, "Send button should be present")
        titleInput.send_keys("Test Title")
        messageInput.send_keys("Test Message")
        addMessageButton.click()
        self._wait_for_exact_text(By.ID, "messageCount", 1)
        messageCount = self.find_element(By.ID, "messageCount")
        self.assertIsNotNone(messageCount, "Message count should be present")
        self.assertEqual(messageCount.text, "1")

        self.web_driver.switch_to.window(tabs[0])
        messageCount = self.find_element(By.ID, "messageCount")
        self.assertIsNotNone(messageCount, "Message count should be present")
        self.assertEqual(messageCount.text, "1")

    def test_real_time_delete_message(self):
        self._create_message()
        self.web_driver.refresh()

        messageCount = self.find_element(By.ID, "messageCount")
        self.assertIsNotNone(messageCount, "Message count should be present")
        self.assertEqual(messageCount.text, "1")

        self.web_driver.switch_to.new_window("tab")
        tabs = self.web_driver.window_handles
        self.web_driver.switch_to.window(tabs[1])

        self.open("/admin/sampleapp/message/")
        deleteButton = self.find_element(By.ID, "deleteBtn")
        self.assertIsNotNone(deleteButton, "Delete button should be present")
        deleteButton.click()
        self._wait_for_exact_text(By.ID, "messageCount", 0)

        messageCount = self.find_element(By.ID, "messageCount")
        self.assertIsNotNone(messageCount, "Message count should be present")
        self.assertEqual(messageCount.text, "0")

        self.web_driver.switch_to.window(tabs[0])
        messageCount = self.find_element(By.ID, "messageCount")
        self.assertIsNotNone(messageCount, "Message count should be present")
        self.assertEqual(messageCount.text, "0")
