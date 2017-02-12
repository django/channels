from apscheduler.job import Job
from apscheduler.jobstores.base import BaseJobStore, ConflictingIdError, JobLookupError
from apscheduler.util import datetime_to_utc_timestamp, utc_timestamp_to_datetime
from django.db import IntegrityError, transaction

from .models import ApschedulerJob

try:
    import cPickle as pickle
except ImportError:  # pragma: nocover
    import pickle


class DjangoJobStore(BaseJobStore):
    """
    Stores jobs in a database table using the Django ORM.

    Plugin alias: ``django``

    :param int pickle_protocol: pickle protocol level to use (for serialization), defaults to the
        highest available
    """

    def __init__(self, pickle_protocol=pickle.HIGHEST_PROTOCOL):
        super(DjangoJobStore, self).__init__()
        self.pickle_protocol = pickle_protocol

    def lookup_job(self, id):
        try:
            job_state = ApschedulerJob.objects.get(id=id).job_state
            return self._reconstitute_job(job_state)
        except ApschedulerJob.DoesNotExist:
            return None

    def get_due_jobs(self, now):
        timestamp = datetime_to_utc_timestamp(now)
        return self._get_jobs(
            ApschedulerJob.objects.filter(next_run_time__lte=timestamp))

    def get_next_run_time(self):
        apscheduler_job = ApschedulerJob.objects.filter(
            next_run_time__isnull=False).order_by('next_run_time').first()

        if apscheduler_job is not None:
            return utc_timestamp_to_datetime(apscheduler_job.next_run_time)
        else:
            return None

    def get_all_jobs(self):
        jobs = self._get_jobs()
        self._fix_paused_jobs_sorting(jobs)
        return jobs

    def add_job(self, job):
        try:
            ApschedulerJob.objects.create(
                id=job.id,
                next_run_time=datetime_to_utc_timestamp(job.next_run_time),
                job_state=pickle.dumps(job.__getstate__(), self.pickle_protocol),
            )
        except IntegrityError:
            raise ConflictingIdError(job.id)

    def update_job(self, job):
        try:
            with transaction.atomic():
                apscheduler_job = ApschedulerJob.objects.get(id=job.id)
                apscheduler_job.next_run_time = datetime_to_utc_timestamp(
                    job.next_run_time)
                apscheduler_job.job_state = pickle.dumps(
                    job.__getstate__(), self.pickle_protocol)
                apscheduler_job.save()
        except ApschedulerJob.DoesNotExist:
            raise JobLookupError(id)

    def remove_job(self, id):
        try:
            ApschedulerJob.objects.get(id=id).delete()
        except ApschedulerJob.DoesNotExist:
            raise JobLookupError(id)

    def remove_all_jobs(self):
        ApschedulerJob.objects.all().delete()

    def _reconstitute_job(self, job_state):
        job_state = pickle.loads(job_state)
        job_state['jobstore'] = self
        job = Job.__new__(Job)
        job.__setstate__(job_state)
        job._scheduler = self._scheduler
        job._jobstore_alias = self._alias
        return job

    def _get_jobs(self, queryset=None):
        jobs = []
        failed_ids = set()

        if queryset is not None:
            apscheduler_jobs = queryset.order_by('next_run_time')
        else:
            apscheduler_jobs = ApschedulerJob.objects.all().order_by('next_run_time')

        for apscheduler_job in apscheduler_jobs:
            try:
                jobs.append(self._reconstitute_job(apscheduler_job.job_state))
            except:
                self._logger.exception(
                    'Unable to restore job "%s" -- removing it', apscheduler_job.id)
                failed_ids.add(apscheduler_job.id)

        # Remove all the jobs we failed to restore
        if failed_ids:
            ApschedulerJob.objects.delete(id__in=failed_ids)

        return jobs
