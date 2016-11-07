from datetime import timedelta
import json

from django.db import models
from django.utils import timezone
from channels import Channel, channel_layers, DEFAULT_CHANNEL_LAYER


class DelayedMessageQuerySet(models.QuerySet):

    def is_due(self):
        return self.filter(due_date__lte=timezone.now())


class DelayedMessage(models.Model):

    due_date = models.DateTimeField()
    interval = models.IntegerField(null=True, blank=True)
    last_sent = models.DateTimeField(null=True, blank=True)
    channel_name = models.CharField(max_length=512)
    content = models.TextField()

    objects = DelayedMessageQuerySet.as_manager()

    def __init__(self, *args, **kwargs):
        # get optional parameters
        delay = kwargs.pop('delay', None)
        super(DelayedMessage, self).__init__(*args, **kwargs)
        if delay or self.interval:
            self._set_delay(delay or self.interval)

    def send(self, channel_layer=None):
        """
        Sends the message on the configured channel and updates the last_sent property.

        Deletes the message if there is no interval set otherwise saves the updated due date.

        Args:
            channel_layer: optional channel_layer to use
        """
        channel_layer = channel_layer or channel_layers[DEFAULT_CHANNEL_LAYER]
        Channel(self.channel_name, channel_layer=channel_layer).send(json.loads(self.content), immediately=True)
        self.last_sent = timezone.now()

        due_date = self._get_next_due_date()
        if due_date:
            self.due_date = due_date
            self.save()
        else:
            self.delete()

    def _get_next_due_date(self):
        if self.interval is None:
            return None
        return self.last_sent + timedelta(seconds=self.interval)

    def _set_delay(self, seconds):
        self.due_date = timezone.now() + timedelta(seconds=seconds)
