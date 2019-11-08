from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.shortcuts import reverse

from channels.testing.live import ChannelsLiveServerTestCase
from selenium import webdriver


class TestChat(ChannelsLiveServerTestCase):
    """Example Test for ChannelsLiveServerTestCase"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = webdriver.Chrome()

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def test_echo(self):
        """Simple live server test"""
        message = "This is a test message"
        self.driver.get(self.live_server_url)
        self.driver.find_element_by_id("txt_message").send_keys(message)
        self.driver.find_element_by_id("btn_send").click()
        self.assertEqual(
            '{"text": "This is a test message"}\n',
            self.driver.find_element_by_id("txt_output").get_attribute("value"),
        )

    def test_get_special_data(self):
        """Test ComplexObject without mocking"""
        self.driver.get(self.live_server_url)
        self.driver.find_element_by_id("btn_get").click()
        self.assertEqual(
            '{"data": "Original Complex Data"}\n',
            self.driver.find_element_by_id("txt_output").get_attribute("value"),
        )

    @patch("chat.consumers.ComplexObject")
    def test_get_special_data_with_mocking(self, mock_complex_object):
        """Mock ComplexObject in chat consumers to return something else.

        NOTE: This test fails when using DaphneProcess.
        """
        mock_instance = mock_complex_object.return_value
        mock_instance.get_complex_data.return_value = "Custom Complex Data"

        self.driver.get(self.live_server_url)
        self.driver.find_element_by_id("btn_get").click()
        self.assertEqual(
            '{"data": "Custom Complex Data"}\n',
            self.driver.find_element_by_id("txt_output").get_attribute("value"),
        )

    def test_database(self):
        """Test database access, to ensure in-memory database works.

        NOTE: This test fails when using DaphneProcess with in-memory database.
        """
        username = "john"
        password = "pass"
        # User should not exist
        self.driver.get(self.live_server_url + reverse("admin:index"))
        self.driver.find_element_by_name("username").send_keys(username)
        self.driver.find_element_by_name("password").send_keys(password + "\n")
        self.assertIn("Please enter the correct username", self.driver.page_source)
        self.assertNotIn("Site administration", self.driver.page_source)

        # Create user
        UserModel = get_user_model()
        UserModel.objects.create_superuser(
            username=username, email="john@example.com", password=password
        )

        # User should exist
        self.driver.get(self.live_server_url + reverse("admin:index"))
        self.driver.find_element_by_name("username").send_keys(username)
        self.driver.find_element_by_name("password").send_keys(password + "\n")
        self.assertNotIn("Please enter the correct username", self.driver.page_source)
        self.assertIn("Site administration", self.driver.page_source)
