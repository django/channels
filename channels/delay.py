from __future__ import unicode_literals

import heapq
import logging
import time
import signal
import sys

from .message import Message


logger = logging.getLogger('django.channels')


class Worker(object):
    """Worker class that listens to channels.delay messages and dispatches messages"""

    def __init__(
            self,
            channel_layer,
            signal_handlers=True,
    ):
        self.channel_layer = channel_layer
        self.signal_handlers = signal_handlers
        self.termed = False
        self.in_job = False
        self.delayed_messages = []

    def install_signal_handler(self):
        signal.signal(signal.SIGTERM, self.sigterm_handler)
        signal.signal(signal.SIGINT, self.sigterm_handler)

    def sigterm_handler(self, signo, stack_frame):
        self.termed = True
        if self.in_job:
            logger.info("Shutdown signal received while busy, waiting for loop termination")
        else:
            logger.info("Shutdown signal received while idle, terminating immediately")
            sys.exit(0)

    def run(self):
        if self.signal_handlers:
            self.install_signal_handler()

        logger.info("Listening on channels.delay")

        while not self.termed:
            self.in_job = False
            channel, content = self.channel_layer.receive_many(['channels.delay'])
            self.in_job = True

            if channel is not None:
                logger.debug("Got message on channels.delay")

                if 'channel' not in content or \
                   'delay' not in content or \
                   'content' not in content:
                    logger.error("Invalid message received, it must contain keys 'channel', 'content', and 'delay'.")
                    break

                message = DelayedMessage(
                    content=content,
                    channel_name=content['channel'],
                    channel_layer=self.channel_layer
                )
                heapq.heappush(self.delayed_messages, (message.due_date, message))
            # check for messages to send
            if not self.delayed_messages:
                logger.debug("No delayed messages waiting.")
                time.sleep(0.01)
                continue

            due_date, message = heapq.heappop(self.delayed_messages)

            if message.is_due():
                logger.info("Delayed message due. Sending message to channel %s", message.channel.name)
                message.send()
            else:
                logger.debug("Message is not due.")
                heapq.heappush(self.delayed_messages, (due_date, message))


class DelayedMessage(Message):
    """
    Represents a message to be sent after a given delay.
    """

    def __init__(self, *args, **kwargs):
        super(DelayedMessage, self).__init__(*args, **kwargs)
        self.delay = self.content['delay']
        self.due_date = time.time() + self.delay

    def is_due(self):
        return self.due_date - time.time() < 0

    def send(self):
        self.channel.send(self.content['content'], immediately=True)
