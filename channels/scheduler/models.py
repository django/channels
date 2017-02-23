import json
from datetime import datetime

from croniter import croniter

from django.db import models
from django.utils import timezone

from channels import DEFAULT_CHANNEL_LAYER, Channel, channel_layers

from .validators import validate_json_string


class CronMessageManager(models.Manager):
    def due(self):
        return self.filter(next_run_time__lte=timezone.now())


class CronMessage(models.Model):

    content = models.TextField(validators=[validate_json_string])
    cron_schedule = models.TextField()
    next_run_time = models.DateTimeField(default=timezone.now)
    channel_name = models.CharField(max_length=199)

    objects = CronMessageManager()

    class Meta:
        ordering = ['-next_run_time']

    def __str__(self):
        return self.cron_schedule

    def save(self, *args, **kwargs):
        self.next_run_time = croniter(
            self.cron_schedule, self.next_run_time).get_next(ret_type=datetime)
        super(CronMessage, self).save(*args, **kwargs)

    def send(self, channel_layer=None):
        """
        Sends the message on the configured channel with the stored content.

        Args:
            channel_layer: optional channel_layer to use
        """
        channel_layer = channel_layer or channel_layers[DEFAULT_CHANNEL_LAYER]
        Channel(self.channel_name, channel_layer=channel_layer).send(json.loads(self.content), immediately=True)
