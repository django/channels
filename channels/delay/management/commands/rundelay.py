from __future__ import unicode_literals

import logging

from django.core.management import BaseCommand, CommandError

from channels import DEFAULT_CHANNEL_LAYER, channel_layers
from channels.delay.worker import Worker

logger = logging.getLogger('channels.server')


class Command(BaseCommand):

    leave_locale_alone = True

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--layer', action='store', dest='layer', default=DEFAULT_CHANNEL_LAYER,
            help='Channel layer alias to use, if not the default.',
        )
        parser.add_argument(
            '--sleep', action='store', dest='sleep', default=1, type=float,
            help='Amount of time to sleep between checks, in seconds.',
        )

    def handle(self, *args, **options):
        self.channel_layer = channel_layers[options.get("layer", DEFAULT_CHANNEL_LAYER)]
        # Check that handler isn't inmemory
        if self.channel_layer.local_only():
            raise CommandError(
                "You cannot span multiple processes with the in-memory layer. " +
                "Change your settings to use a cross-process channel layer."
            )
        self.options = options
        logger.info("Running delay against channel layer %s", self.channel_layer)
        try:
            worker = Worker(
                channel_layer=self.channel_layer,
                database_sleep_duration=options['sleep'],
            )
            worker.run()
        except KeyboardInterrupt:
            pass
