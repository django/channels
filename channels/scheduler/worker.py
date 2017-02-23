from __future__ import unicode_literals

import logging
import signal
import sys
import time

from django.db import transaction

from .models import CronMessage

logger = logging.getLogger('django.channels')


class Worker(object):
    """Worker class that listens to asgi.schedule messages and dispatches
    messages"""

    def __init__(
            self,
            channel_layer,
            signal_handlers=True,
    ):
        self.channel_layer = channel_layer
        self.signal_handlers = signal_handlers
        self.termed = False
        self.in_job = False

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

        while not self.termed:
            self.in_job = True

            # First update message.next_run_time in a transaction to enforce at
            # most once semantics
            try:
                with transaction.atomic():
                    messages = CronMessage.objects.select_for_update().due()
                    for message in messages:
                        # Advances message.next_run_time, as next_run_time lies in
                        # the past for due messages
                        message.save()
            except Exception as error:
                logger.warn(
                    "Unable to set advance next_run_time for due messages, got "
                    "%s", error)
            else:
                for message in messages:
                    message.send(channel_layer=self.channel_layer)

            self.in_job = False

            # Sleep for a short interval so we don't idle hot.
            time.sleep(0.1)
