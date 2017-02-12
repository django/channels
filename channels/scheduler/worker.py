from __future__ import unicode_literals

import logging
import signal
import sys
import time

from apscheduler.jobstores.base import ConflictingIdError
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings

from channels import Channel

from .django_jobstore import DjangoJobStore
from .forms import ScheduleMessageForm

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

        jobstores = {
            'default': DjangoJobStore(),
        }
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores, timezone=settings.TIME_ZONE)

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

    @staticmethod
    def send_message(channel_layer_alias, reply_channel, content):
        """
        Callable for apscheduler

        Needs to be a staticmethod as callables for apscheduler need to be
        globally accessible.
        """
        Channel(reply_channel, alias=channel_layer_alias).send(
            content, immediately=True)

    def run(self):
        if self.signal_handlers:
            self.install_signal_handler()

        self.scheduler.start()

        logger.info("Listening on asgi.schedule")

        while not self.termed:
            self.in_job = False
            channel, content = self.channel_layer.receive(['asgi.schedule'], block=False)
            self.in_job = True

            if channel is not None:
                logger.debug("Got message on asgi.schedule")

                message = ScheduleMessageForm(content)

                if message.is_valid() is False:
                    logger.error(
                        "Invalid message received: %s",
                        message.errors,
                    )
                    continue

                message_data = message.cleaned_data
                method = message_data.pop("method")
                if method == 'add':
                    args = [self.channel_layer.alias, message_data.pop("reply_channel"), message_data.pop("content")]
                    kwargs = dict(
                        (key, value) for key, value in message_data.items() if value is not None
                    )
                    kwargs['args'] = args

                    try:
                        self.scheduler.add_job(self.send_message, **kwargs)
                    except ConflictingIdError as error:
                        logger.error(error)
                        continue
                elif method == 'remove':
                    self.scheduler.remove_job(message_data.get("id"))

            else:
                # Sleep for a short interval so we don't idle hot.
                time.sleep(0.1)

        self.scheduler.shutdown()
