from __future__ import unicode_literals

from django.core.management import BaseCommand, CommandError

from channels import DEFAULT_CHANNEL_LAYER, channel_layers
from channels.log import setup_logger
from channels.worker import Worker
import threading,time

workers = []

class Command(BaseCommand):

    leave_locale_alone = True

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            '--layer', action='store', dest='layer', default=DEFAULT_CHANNEL_LAYER,
            help='Channel layer alias to use, if not the default.',
        )
        parser.add_argument(
            '--only-channels', action='append', dest='only_channels',
            help='Limits this worker to only listening on the provided channels (supports globbing).',
        )
        parser.add_argument(
            '--exclude-channels', action='append', dest='exclude_channels',
            help='Prevents this worker from listening on the provided channels (supports globbing).',
        )
        parser.add_argument(
            '--jobs', action='store', dest='jobs', default=1, type=int,
            help='Multiple start workers.',
        )


    def handle(self, *args, **options):
        # Get the backend to use
        self.verbosity = options.get("verbosity", 1)
        self.logger = setup_logger('django.channels', self.verbosity)
        self.channel_layer = channel_layers[options.get("layer", DEFAULT_CHANNEL_LAYER)]
        # Check that handler isn't inmemory
        if self.channel_layer.local_only():
            raise CommandError(
                "You cannot span multiple processes with the in-memory layer. " +
                "Change your settings to use a cross-process channel layer."
            )
        # Check a handler is registered for http reqs
        self.channel_layer.router.check_default()
        # Launch a worker
        self.logger.info("Running worker against channel layer %s", self.channel_layer)
        # Optionally provide an output callback
        callback = None
        if self.verbosity > 1:
            callback = self.consumer_called
        # Run the workers
        for id in range(options.get("jobs", 1)):
            worker = WorkerThread(
                channel_layer=self.channel_layer,
                callback=callback,
                only_channels=options.get("only_channels", None),
                exclude_channels=options.get("exclude_channels", None),
                logger=self.logger,
                id=id,
            )
            worker.daemon = True
            worker.start()
        try:
            while len(workers) > 0: time.sleep(1)
        except KeyboardInterrupt: self.logger.info("Stopping workers pool.")

    def consumer_called(self, channel, message):
        self.logger.debug("%s", channel)

class WorkerThread(threading.Thread):
    """
    Class that runs a worker
    """

    def __init__(self,channel_layer, callback, only_channels, exclude_channels, logger, id):
        super(WorkerThread, self).__init__()
        self.name = "WorkerThread-%i" % id
        self.worker = Worker(
                channel_layer=channel_layer,
                callback=callback,
                only_channels=only_channels,
                exclude_channels=exclude_channels,
                signal_handlers=False,
            )
        self.logger = logger
        self.id = id
        workers.append(self.id)


    def run(self):
        self.logger.info("Worker thread running")
        try: self.worker.run()
        except: pass
        workers.remove(self.id)
        self.logger.info("Worker thread exited")
