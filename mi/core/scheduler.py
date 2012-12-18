#!/usr/bin/env python

"""
@package mi.core.scheduler Event scheduler for MI drivers and tools
@file mi/core/scheduler.py
@author Bill French
@brief Provides task/event scheduling for drivers and data processes
Scheduling methods include absolute time, elapse time, cron syntax
and a minimum elapse time (polled mode).

Usage:

For triggered events:

def some_callback(self): ...

scheduler = PolledScheduler()
scheduler.start()

# An absolute time event
dt = datetime.datetime.now() + datetime.timedelta(0,1)
job = scheduler.add_date_job(some_callback, dt)

# An interval based event
job = scheduler.add_interval_job(self._callback, seconds=3)

# A cron style event
job = scheduler.add_cron_job(some_callback, second='*/3')

# A polled event with an interval
test_name = 'test_job'
min_interval = PolledScheduler.interval(seconds=1)
max_interval = PolledScheduler.interval(seconds=3)
job = scheduler.add_polled_job(some_callback, test_name, min_interval, max_interval)

For Polled events:

# max_interval is optional.  If not specified then events will only be triggered by
# by calling schedule.run_polled_job(test_name)
test_name = 'test_job'
min_interval = PolledScheduler.interval(seconds=1)
max_interval = PolledScheduler.interval(seconds=3)
job = scheduler.add_polled_job(some_callback, test_name, min_interval, max_interval)

...

scheduler.run_polled_job(test_name)

This module extends the Advanced Python Scheduler:
@see http://packages.python.org/APScheduler
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from datetime import timedelta
from datetime import datetime
from math import ceil

from apscheduler.scheduler import Scheduler
from apscheduler.scheduler import JobStoreEvent
from apscheduler.scheduler import EVENT_JOBSTORE_JOB_ADDED
from apscheduler.job import Job

from apscheduler.util import convert_to_datetime, timedelta_seconds

from mi.core.log import get_logger; log = get_logger()

class PolledScheduler(Scheduler):
    """
    Specialized advanced scheduler that allows for polled interval
    jobs.
    """

    @staticmethod
    def interval(weeks=0, days=0, hours=0, minutes=0, seconds=0):
        """
        Get an interval object
        :param weeks: number of weeks to wait
        :param days: number of days to wait
        :param hours: number of hours to wait
        :param minutes: number of minutes to wait
        :param seconds: number of seconds to wait
        :return: interval object
        """
        interval = timedelta(weeks=weeks, days=days, hours=hours,
            minutes=minutes, seconds=seconds)
        return interval


    def add_polled_job(self, func, name, min_interval, max_interval=None,
                       start_date=None, args=None, kwargs=None,
                       jobstore='default', **options):
        """
        Schedules a job to be completed on specified intervals.  Unlike most jobs
        this job needs a name so it can be found and polled.

        :param func: callable to run
        :param min_interval: minimum time to run this job
        :param max_interval: maximum time to wait before the job is run
        :param args: list of positional arguments to call func with
        :param kwargs: dict of keyword arguments to call func with
        :param name: name of the job
        :param jobstore: alias of the job store to add the job to
        :param misfire_grace_time: seconds after the designated run time that
            the job is still allowed to be run
        :rtype: :class:`~apscheduler.job.Job`
        """
        trigger = PolledIntervalTrigger(min_interval, max_interval, start_date)

        job = PolledIntervalJob(trigger, func, args or [], kwargs or {},
            options.pop('misfire_grace_time', self.misfire_grace_time),
            options.pop('coalesce', self.coalesce), name=name, **options)
        if not self.running:
            self._pending_jobs.append((job, jobstore))
            log.info('Adding job tentatively -- it will be properly '
                     'scheduled when the scheduler starts')
        else:
            self._real_add_job(job, jobstore, True)
        return job

    def run_polled_job(self, name):
        """
        Find a job in the job store and pull the trigger on the job.  If it is read to run, run it
        and return true, otherwise do nothing and return false.
        @param name: name of the job we are looking for
        @return: True if the job is run, false otherwise
        @raise LookupError if the job name isn't found in the job store or the found job isn't a
                           polled job.
        """
        self._jobstores_lock.acquire()
        log.debug("jobstores lock acquired")
        try:
            now = datetime.now()
            (job, alias, jobstore) = self.get_polled_job_tuple(name)

            if(not job):
                raise LookupError("no PolledIntervalJob found named '%s'" % name )

            if(job.ready_to_run()):
                log.debug("Job '%s' is ready to run" % job.name)
                self._threadpool.submit(self._run_job, job, [datetime.now()])
                job.compute_next_run_time(now)
                jobstore.update_job(job)
                return True
            else:
                log.debug("Job '%s' is *NOT* ready to run" % job.name)
                return False

        finally:
            self._jobstores_lock.release()
            log.debug("jobstores lock released")

    def get_polled_job_tuple(self, name):
        """
        return the PolledIntervalJob from the jobstore with then name passed to this method.
        If not found return None
        @param name: name of the job we are looking for
        @return: Tuple containing (job, alias, jobstore)
        """
        for (alias, jobstore) in self._jobstores.items():
            for job in tuple(jobstore.jobs):
                if(isinstance(job, PolledIntervalJob) and name == job.name):
                    return (job, alias, jobstore)

        return (None, None, None)

    def get_polled_job(self, name):
        """
        return the PolledIntervalJob from the jobstore with then name passed to this method.
        If not found return None
        @param name: name of the job we are looking for
        @return: PolledIntervalJob with the matching name or None if not found.
        """
        for (alias, jobstore) in self._jobstores.items():
            for job in tuple(jobstore.jobs):
                if(isinstance(job, PolledIntervalJob) and name == job.name):
                    return job

        return None

    def _process_jobs(self, now, polled=False):
        """
        Iterates through jobs in every jobstore, starts pending jobs
        and figures out the next wakeup time.
        """
        log.debug("_process_jobs started")
        next_wakeup_time = None
        next_polled_wakeup_time = None
        self._jobstores_lock.acquire()
        try:
            log.debug("_process_jobs lock acquired")
            for (alias, jobstore) in self._jobstores.items():
                for job in tuple(jobstore.jobs):
                    log.debug("_process_jobs process job %s" % job)
                    if(isinstance(job, PolledIntervalJob)):
                        next_polled_wakeup_time = self._process_polled_job(job, now, alias, jobstore)
                    else:
                        next_wakeup_time = self._process_original_job(job, now, alias, jobstore)

            log.debug("_process_jobs loop complete")
            if(next_polled_wakeup_time and next_wakeup_time):
                return min(next_polled_wakeup_time, next_wakeup_time)
            elif(next_wakeup_time == None):
                return next_polled_wakeup_time
            else:
                return next_wakeup_time
        finally:
            self._jobstores_lock.release()
            log.debug("_process_jobs lock released")


    def _process_original_job(self, job, now, alias, jobstore):
        """
        Process jobs of class Job.  This mirrors the original code in the base class
        """
        next_wakeup_time=None

        run_times = job.get_run_times(now)
        if run_times:
            self._threadpool.submit(self._run_job, job, run_times)

            # Increase the job's run count
            if job.coalesce:
                job.runs += 1
            else:
                job.runs += len(run_times)

            # Update the job, but don't keep finished jobs around
            if job.compute_next_run_time(now + timedelta(microseconds=1)):
                jobstore.update_job(job)
            else:
                self._remove_job(job, alias, jobstore)

        if not next_wakeup_time:
            next_wakeup_time = job.next_run_time
        elif job.next_run_time:
            next_wakeup_time = min(next_wakeup_time, job.next_run_time)

        return next_wakeup_time

    def _process_polled_job(self, job, now, alias, jobstore):
        """
        Process polled job which we created for this specialized scheduler
        """
        next_wakeup_time=job.trigger.get_next_fire_time()

        if not next_wakeup_time == None and next_wakeup_time <= now:
            log.debug("submit job to pool: %s" % job)
            if(not self._threadpool._shutdown):
                self._threadpool.submit(self._run_job, job, [next_wakeup_time])

            # Increase the job's run count
            if job.coalesce:
                job.runs += 1
            else:
                job.runs += len(run_times)

            # Update the job.  We don't remove any polled jobs automatically
            job.trigger.pull_trigger()
            job.compute_next_run_time(now + timedelta(microseconds=1))
            jobstore.update_job(job)

        if not next_wakeup_time:
            next_wakeup_time = job.next_run_time
        elif job.next_run_time:
            next_wakeup_time = min(next_wakeup_time, job.next_run_time)

        return next_wakeup_time

    def _real_add_job(self, job, jobstore, wakeup):
        """
        Needed to over load this method so we can ignore the never going to run
        tests because polled jobs without a max interval will never run automatically
        but they are still valid jobs.
        """
        job.compute_next_run_time(datetime.now())
        # We want to ignore this test for polled interval jobs
        if not isinstance(job, PolledIntervalJob) and not job.next_run_time:
            raise ValueError('Not adding job since it would never be run')

        # We DO want to raise an exception if we already have a polled interval job
        # with the same name as the one we are trying to add.
        if isinstance(job, PolledIntervalJob) and self.get_polled_job(job.name):
            raise ValueError("Not adding job since a job named '%s' already exists" % job.name)

        self._jobstores_lock.acquire()
        try:
            try:
                store = self._jobstores[jobstore]
            except KeyError:
                raise KeyError('No such job store: %s' % jobstore)
            store.add_job(job)
        finally:
            self._jobstores_lock.release()

        # Notify listeners that a new job has been added
        event = JobStoreEvent(EVENT_JOBSTORE_JOB_ADDED, jobstore, job)
        self._notify_listeners(event)

        log.info('Added job "%s" to job store "%s"', job, jobstore)

        # Notify the scheduler about the new job
        if wakeup:
            self._wakeup.set()

class PolledIntervalJob(Job):
    """
    Specialized Job that has additional functionality for polled jobs.
    A polled interval job is one that has a minimum time to wait before
    it can be run, but a specific request must be made to check it it
    is ready to run, i.e. it must be polled.  Optionally a maximum
    wait time can be reached in which time the event will fire
    automatically, much like a regular interval job.

    :param trigger: trigger that determines the execution times
    :param func: callable to call when the trigger is triggered
    :param args: list of positional arguments to call func with
    :param kwargs: dict of keyword arguments to call func with
    :param name: name of the job (optional)
    :param misfire_grace_time: seconds after the designated run time that
        the job is still allowed to be run
    :param coalesce: run once instead of many times if the scheduler determines
        that the job should be run more than once in succession
    :param max_runs: maximum number of times this job is allowed to be
        triggered
    :param max_instances: maximum number of concurrently running
        instances allowed for this job
    """

    def ready_to_run(self):
        """
        status notification if a job is ready to run in polled mode
        @retval true if we have reached the minimum time false otherwise
        """
        return self.trigger.pull_trigger()

    def __repr__(self):
        return '<%s (name=%s, trigger=%s)>' % (self.__class__.__name__,self.name, repr(self.trigger))

class PolledIntervalTrigger(object):
    def __init__(self, min_interval, max_interval=None, start_date=None):
        if not isinstance(min_interval, timedelta):
            raise TypeError('min_interval must be a timedelta')
        if max_interval and not isinstance(max_interval, timedelta):
            raise TypeError('max_interval must be a timedelta')
        if start_date:
            start_date = convert_to_datetime(start_date)

        self.min_interval = min_interval
        self.min_interval_length = timedelta_seconds(self.min_interval)
        if self.min_interval_length == 0:
            self.min_interval = timedelta(seconds=1)
            self.min_interval_length = 1

        self.max_interval = max_interval
        self.max_interval_length = None
        if max_interval:
            self.max_interval_length = timedelta_seconds(self.max_interval)
            if self.max_interval_length == 0:
                self.max_interval = timedelta(seconds=1)
                self.max_interval_length = 1

        if(self.max_interval and
           self.min_interval_length > self.max_interval_length):
            raise ValueError("min_interval < max_interval")

        self.next_max_date = None
        if start_date is None:
            self.next_min_date = datetime.now()
            if(self.max_interval):
                self.next_max_date = datetime.now() + self.max_interval
        else:
            self.next_min_date = convert_to_datetime(start_date)
            if(self.max_interval):
                self.next_max_date = self.next_min_date + self.max_interval

    def get_next_fire_time(self, start_date=None):
        """
        Method used by the scheduler to determine when the job should automatically run
        next.
        @param start_date: not used in this method, but needed by the calling base class
        @return: the next time a job should run automatically.  None if it shouldn't be automatic
        """
        return self.next_max_date

    def pull_trigger(self):
        """
        Method used by new scheduler mechanism for checking if a job should run when polled.
        @return: true if the trigger is fired.
        """
        now = datetime.now()

        if(self.next_min_date <= now):
            if(self.max_interval):
                self.next_max_date = now + self.max_interval
            self.next_min_date = now + self.min_interval

            log.debug("Next min date: %s" % self.next_min_date)
            log.debug("Next max date: %s" % self.next_max_date)

            return True

        return False

    def __str__(self):
        return "min_interval[%s] max_interval[%s]" % (str(self.min_interval), str(self.max_interval))

    def __repr__(self):
        return "<%s (min_interval=%s, max_interval=%s)>" % (
            self.__class__.__name__, repr(self.min_interval), repr(self.max_interval))




