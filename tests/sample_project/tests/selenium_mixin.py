from django.contrib.auth import get_user_model
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class SeleniumMixin:
    """
    Mixin to provide a headless Chromium browser for
    end-to-end tests to test ChannelsLiveServerTestCase.
    """

    admin_username = "admin"
    admin_password = "password"
    email = "admin@email.com"

    @classmethod
    def get_chrome_webdriver(cls):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.page_load_strategy = "eager"
        return webdriver.Chrome(options=options)

    def _create_admin(self, username, password, email):
        User = get_user_model()
        return User.objects.create_superuser(
            username=username, password=password, email=email
        )

    def setUp(self):
        super().setUp()
        self.admin = self._create_admin(
            username=self.admin_username, password=self.admin_password, email=self.email
        )
        self.web_driver = self.get_chrome_webdriver()

    def open(self, url, html_container="#content-main", driver=None, timeout=5):
        """Opens a URL.

        Input Arguments:

        - url: URL to open
        - driver: selenium driver (default: cls.base_driver).
        - html_container: CSS selector of an HTML element to look for once
          the page is ready
        - timeout: timeout until the page is ready
        """
        driver = self.web_driver
        driver.get(f"{self.live_server_url}{url}")
        self._wait_until_page_ready(driver=driver, html_container=html_container)

    def _wait_until_page_ready(
        self, html_container="#content-main", timeout=5, driver=None
    ):
        driver = self.web_driver
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        self.wait_for_visibility(By.CSS_SELECTOR, html_container, timeout, driver)

    def get_browser_logs(self, driver=None):
        driver = self.web_driver
        return driver.get_log("browser")

    def login(self, username=None, password=None, driver=None):
        """Log in to the admin dashboard.

        Input Arguments:

        - username: username to be used for login (default:
          cls.admin_username)
        - password: password to be used for login (default:
          cls.admin_password)
        - driver: selenium driver (default: cls.web_driver).
        """
        driver = self.web_driver
        if not username:
            username = self.admin_username
        if not password:
            password = self.admin_password
        driver.get(f"{self.live_server_url}/admin/login/")
        self._wait_until_page_ready(driver=driver)
        if "admin/login" in driver.current_url:
            driver.find_element(by=By.NAME, value="username").send_keys(username)
            driver.find_element(by=By.NAME, value="password").send_keys(password)
            driver.find_element(by=By.XPATH, value='//input[@type="submit"]').click()
        self._wait_until_page_ready(driver=driver)

    def logout(self, driver=None):
        driver = self.web_driver
        driver.find_element(By.CSS_SELECTOR, ".account-button").click()
        driver.find_element(By.CSS_SELECTOR, "#logout-form button").click()

    def find_element(self, by, value, timeout=2, driver=None, wait_for="visibility"):
        driver = self.web_driver
        method = f"wait_for_{wait_for}"
        getattr(self, method)(by, value, timeout)
        return driver.find_element(by=by, value=value)

    def find_elements(self, by, value, timeout=2, driver=None, wait_for="visibility"):
        driver = self.web_driver
        method = f"wait_for_{wait_for}"
        getattr(self, method)(by, value, timeout)
        return driver.find_elements(by=by, value=value)

    def wait_for_visibility(self, by, value, timeout=2, driver=None):
        driver = self.web_driver
        return self.wait_for(
            "visibility_of_element_located", by, value, timeout, driver
        )

    def wait_for(self, method, by, value, timeout=2, driver=None):
        driver = self.web_driver
        try:
            return WebDriverWait(driver, timeout).until(
                getattr(EC, method)(((by, value)))
            )
        except TimeoutException as e:
            print(self.get_browser_logs(driver))
            self.fail(f'{method} of "{value}" failed: {e}')

    def wait_for_websocket_connection(self, substring="WebSocket connected", timeout=5):
        """
        Wait until window.websocketConnected is true, or fail after timeout.
        """
        try:
            WebDriverWait(self.web_driver, timeout).until(
                lambda d: d.execute_script("return window.websocketConnected === true")
            )
        except TimeoutException:
            logs = self.get_browser_logs()
            print("\n Browser logs on WS-flag timeout:")
            for entry in logs:
                print(f"[{entry['level']}] {entry['message']}")
            self.fail(
                f"Timed out waiting for window.websocketConnected after {timeout}s"
            )

    def tearDown(self):
        logs = self.web_driver.get_log("browser")
        severe_logs = [entry for entry in logs if entry.get("level") == "SEVERE"]

        if severe_logs:
            print("\n----Browser console SEVERE logs----")
            for entry in severe_logs:
                msg = entry.get("message")
                print(f"[SEVERE] {msg}")
        self.web_driver.quit()
        super().tearDown()
