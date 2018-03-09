Writing your first Channels app, part 3
=======================================

This tutorial begins where :doc:`Tutorial 2 </tutorial/part_2>` left off.
We'll rewrite the consumer code to be asynchronous rather than synchronous
to improve its performance and write automated tests.

Rewrite the consumer to be asynchronous
---------------------------------------

The ``ChatConsumer`` that we have written is currently synchronous. Synchronous
consumers are convenient because they can call regular synchronous I/O functions
such as those that access Django models without writing special code. However
asynchronous consumers can provide a higher level of performance since they
don't need create additional threads when handling requests.

``ChatConsumer`` only uses async-native libraries (Channels and the channel layer)
and in particular it does not access synchronous Django models. Therefore it can
be rewritten to be asynchronous without complications.

.. note::
    Even if ``ChatConsumer`` *did* access Django models or other synchronous code it
    would still be possible to rewrite it as asynchronous. Utilities like
    :ref:`asgiref.sync.sync_to_async <sync_to_async>` and
    :doc:`channels.db.database_sync_to_async </topics/databases>` can be
    used to call synchronous code from an asynchronous consumer. The performance
    gains however would be less than if it only used async-native libraries.

Let's rewrite ``ChatConsumer`` to be asynchronous.
Put the following code in ``chat/consumers.py``::

    # chat/consumers.py
    from channels.generic.websocket import AsyncWebsocketConsumer
    import json
    
    class ChatConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            self.room_name = self.scope['url_route']['kwargs']['room_name']
            self.room_group_name = 'chat_%s' % self.room_name
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            await self.accept()
        
        async def disconnect(self, close_code):
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        
        # Receive message from WebSocket
        async def receive(self, text_data):
            text_data_json = json.loads(text_data)
            message = text_data_json['message']
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message
                }
            )
        
        # Receive message from room group
        async def chat_message(self, event):
            message = event['message']
            
            # Send message to WebSocket
            await self.send(text_data=json.dumps({
                'message': message
            }))

This new code is for ChatConsumer is very similar to the original code, with the following differences:

* ``ChatConsumer`` now inherits from ``AsyncWebsocketConsumer`` rather than
  ``WebsocketConsumer``.
* All methods are ``async def`` rather than just ``def``.
* ``await`` is used to call asynchronous functions that perform I/O.
* ``async_to_sync`` is no longer needed when calling methods on the channel layer.

Let's verify that the consumer for the ``/ws/chat/ROOM_NAME/`` path still works.
To start the Channels development server, run the following command::

    $ python3 manage.py runserver

Open a browser tab to the room page at http://127.0.0.1:8000/chat/lobby/.
Open a second browser tab to the same room page.

In the second browser tab, type the message "hello" and press enter. You should
now see "hello" echoed in the chat log in both the second browser tab and in the
first browser tab.

Now your chat server is fully asynchronous!

Testing the views
-----------------

To ensure that the chat server keeps working, we will write some tests.

We will write a suite of end-to-end tests using Selenium to control a Chrome web
browser. These tests will ensure that:

* when a chat message is posted then it is seen by everyone in the same room
* when a chat message is posted then it is not seen by anyone in a different room

`Install the Chrome web browser`_, if you do not already have it.

`Install chromedriver`_.

Install Selenium. Run the following command::

    $ pip3 install selenium

.. _Install the Chrome web browser: https://www.google.com/chrome/
.. _Install chromedriver: https://sites.google.com/a/chromium.org/chromedriver/getting-started

Create a new file ``chat/tests.py``. Your app directory should now look like::

    chat/
        __init__.py
        consumers.py
        routing.py
        templates/
            chat/
                index.html
                room.html
        tests.py
        urls.py
        views.py

Put the following code in ``chat/tests.py``::

    # chat/tests.py
    from channels.testing import ChannelsLiveServerTestCase
    from selenium import webdriver
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.wait import WebDriverWait
    
    class ChatTests(ChannelsLiveServerTestCase):
        serve_static = True  # emulate StaticLiveServerTestCase
        
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            try:
                # NOTE: Requires "chromedriver" binary to be installed in $PATH
                cls.driver = webdriver.Chrome()
            except:
                super().tearDownClass()
                raise
        
        @classmethod
        def tearDownClass(cls):
            cls.driver.quit()
            super().tearDownClass()
        
        def test_when_chat_message_posted_then_seen_by_everyone_in_same_room(self):
            try:
                self._enter_chat_room('room_1')
                
                self._open_new_window()
                self._enter_chat_room('room_1')
                
                self._switch_to_window(0)
                self._post_message('hello')
                WebDriverWait(self.driver, 2).until(lambda _:
                    'hello' in self._chat_log_value,
                    'Message was not received by window 1 from window 1')
                self._switch_to_window(1)
                WebDriverWait(self.driver, 2).until(lambda _:
                    'hello' in self._chat_log_value,
                    'Message was not received by window 2 from window 1')
            finally:
                self._close_all_new_windows()
        
        def test_when_chat_message_posted_then_not_seen_by_anyone_in_different_room(self):
            try:
                self._enter_chat_room('room_1')
                
                self._open_new_window()
                self._enter_chat_room('room_2')
                
                self._switch_to_window(0)
                self._post_message('hello')
                WebDriverWait(self.driver, 2).until(lambda _:
                    'hello' in self._chat_log_value,
                    'Message was not received by window 1 from window 1')
                
                self._switch_to_window(1)
                self._post_message('world')
                WebDriverWait(self.driver, 2).until(lambda _:
                    'world' in self._chat_log_value,
                    'Message was not received by window 2 from window 2')
                self.assertTrue('hello' not in self._chat_log_value,
                    'Message was improperly received by window 2 from window 1')
            finally:
                self._close_all_new_windows()
        
        # === Utility ===
        
        def _enter_chat_room(self, room_name):
            self.driver.get(self.live_server_url + '/chat/')
            ActionChains(self.driver).send_keys(room_name + '\n').perform()
            WebDriverWait(self.driver, 2).until(lambda _:
                room_name in self.driver.current_url)
        
        def _open_new_window(self):
            self.driver.execute_script('window.open("about:blank", "_blank");')
            self.driver.switch_to_window(self.driver.window_handles[-1])
        
        def _close_all_new_windows(self):
            while len(self.driver.window_handles) > 1:
                self.driver.switch_to_window(self.driver.window_handles[-1])
                self.driver.execute_script('window.close();')
            if len(self.driver.window_handles) == 1:
                self.driver.switch_to_window(self.driver.window_handles[0])
        
        def _switch_to_window(self, window_index):
            self.driver.switch_to_window(self.driver.window_handles[window_index])
        
        def _post_message(self, message):
            ActionChains(self.driver).send_keys(message + '\n').perform()
        
        @property
        def _chat_log_value(self):
            return self.driver.find_element_by_css_selector('#chat-log').get_property('value')

Our test suite extends ``ChannelsLiveServerTestCase`` rather than Django's usual
suites for end-to-end tests (``StaticLiveServerTestCase`` or ``LiveServerTestCase``) so
that URLs inside the Channels routing configuration like ``/ws/room/ROOM_NAME/``
will work inside the suite.

To run the tests, run the following command::

    $ python3 manage.py test chat.tests

You should see output that looks like::

    Creating test database for alias 'default'...
    System check identified no issues (0 silenced).
    ..
    ----------------------------------------------------------------------
    Ran 2 tests in 5.014s
    
    OK
    Destroying test database for alias 'default'...

You now have a tested chat server.

This is the end of the tutorial.
