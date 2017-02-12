from django.db import models


class ApschedulerJob(models.Model):
    id = models.TextField(primary_key=True)
    next_run_time = models.FloatField(null=True, blank=True)
    job_state = models.BinaryField(null=True, blank=True)

    def __str__(self):
        return self.id
