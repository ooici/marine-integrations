#!/usr/bin/env python

"""
@package mi.core.test.test_scheduler Event scheduler tests
@file mi/core/test/test_scheduler.py
@author Bill French
@brief Unit tests for the event scheduler
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import datetime
import time

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr

from mi.core.unit_test import MiUnitTest
from mi.core.scheduler import PolledScheduler
from mi.core.scheduler import PolledIntervalTrigger
from mi.core.scheduler import PolledIntervalJob
from apscheduler.util import timedelta_seconds

@attr('UNIT', group='mi')
class TestScheduler(MiUnitTest):
    """
    Test the scheduler
    """    
    def setUp(self):
        """
        Setup the test case
        """
        self._scheduler = PolledScheduler()
        self._scheduler.start()
        self._triggered =[]

        self.assertTrue(self._scheduler.daemonic)

    def _callback(self):
        """
        event callback for event processing
        """
        log.debug("Event triggered.")
        self._triggered.append(datetime.datetime.now())

    def assert_datetime_close(self, ldate, rdate, delta_seconds=0.1):
        """
        compare two date time objects to see if they are equal within delta_seconds
        param: ldate left hand date
        param: rdate right hand date
        param: delta_seconds tolerance
        """
        delta = ldate - rdate
        seconds = timedelta_seconds(delta)
        self.assertLessEqual(abs(seconds), delta_seconds)

    def assert_event_triggered(self, expected_arrival = None, poll_time = 0.5, timeout = 10):
        """
        Verify a timer was triggered within the timeout, and if
        if expected arrival is set, check the date time arrived for a match
        too.
        @param expected_arival datetime object with time we expect the triggered event to fire
        @param poll_time time to sleep between arrival queue checks, also sets the precision of
                         expected_arrival
        @param timeout seconds to wait for an event
        """
        endtime = datetime.datetime.now() + datetime.timedelta(0,timeout)

        while(len(self._triggered) == 0 and datetime.datetime.now() < endtime):
            log.trace("Wait for event.")
            time.sleep(poll_time)

        log.debug("Out of test loop")
        self.assertGreater(len(self._triggered), 0)
        arrival_time = self._triggered.pop()
        self.assertIsNotNone(arrival_time)
        if(not expected_arrival == None):
            self.assert_datetime_close(arrival_time, expected_arrival, poll_time)

    def test_absolute_time(self):
        """
        Test with absolute time.  Not an exhaustive test because it's implemented in the library
        not our code.
        """
        dt = datetime.datetime.now() + datetime.timedelta(0,1)
        job = self._scheduler.add_date_job(self._callback, dt)
        self.assert_event_triggered(dt)

    def test_elapse_time(self):
        """
        Test with elapse time.  Not an exhaustive test because it's implemented in the library
        not our code.
        """
        now = datetime.datetime.now()
        interval = PolledScheduler.interval(seconds=3)

        job = self._scheduler.add_interval_job(self._callback, seconds=3)
        self.assert_event_triggered(now + interval)
        self.assert_event_triggered(now + interval + interval)
        self.assert_event_triggered(now + interval + interval + interval)

    def test_cron_syntax(self):
        """
        Test with cron syntax.  Not an exhaustive test because it's implemented in the library
        not our code.
        """
        job = self._scheduler.add_cron_job(self._callback, second='*/3')
        self.assert_event_triggered()
        self.assert_event_triggered()

    @unittest.skip("TODO, fix this test.  Failing on buildbot not in dev")
    def test_polled_time(self):
        """
        Test a polled job with an interval.  Also test some exceptions
        """
        now = datetime.datetime.now()
        test_name = 'test_job'
        min_interval = PolledScheduler.interval(seconds=1)
        max_interval = PolledScheduler.interval(seconds=3)

        # Verify that triggered events work.
        job = self._scheduler.add_polled_job(self._callback, test_name, min_interval, max_interval)
        self.assertEqual(len(self._scheduler.get_jobs()), 1)
        self.assert_event_triggered(now+max_interval)

        # after a triggered event the min time should be extended.
        self.assertFalse(self._scheduler.run_polled_job(test_name))
        time.sleep(1)
        self.assertTrue(self._scheduler.run_polled_job(test_name))
        self.assert_event_triggered(now + min_interval + max_interval)

        # after a polled event the wait time should also be exited
        self.assert_event_triggered(now + min_interval + max_interval + max_interval)

        # Test exceptions. Job name doesn't exist
        with self.assertRaises(LookupError):
            self._scheduler.run_polled_job('foo')

        # Verify that an exception is raised if we try to add a job with the same name
        with self.assertRaises(ValueError):
            job = self._scheduler.add_polled_job(self._callback, test_name, min_interval, max_interval)

    def test_polled_time_no_interval(self):
        """
        Test the scheduler with a polled job with no interval
        """
        now = datetime.datetime.now()
        test_name = 'test_job'
        min_interval = PolledScheduler.interval(seconds=1)

        # Verify that triggered events work.
        job = self._scheduler.add_polled_job(self._callback, test_name, min_interval)

        self.assertEqual(len(self._scheduler.get_jobs()), 1)

        self.assertTrue(self._scheduler.run_polled_job(test_name))
        self.assertFalse(self._scheduler.run_polled_job(test_name))
        time.sleep(2)
        self.assertTrue(self._scheduler.run_polled_job(test_name))

    def test_polled_time_no_interval_not_started(self):
        """
        Try to setup some jobs with the scheduler before the scheduler has been started.
        Then try to startup and see if the job is setup properly.
        """
        now = datetime.datetime.now()
        test_name = 'test_job'
        min_interval = PolledScheduler.interval(seconds=1)

        self._scheduler = PolledScheduler()
        self.assertFalse(self._scheduler.running)

        # Verify that triggered events work.
        job = self._scheduler.add_polled_job(self._callback, test_name, min_interval)
        self.assertIsNotNone(job)
        self.assertEqual(len(self._scheduler.get_jobs()), 0)
        self.assertEqual(len(self._scheduler._pending_jobs), 1)

        self._scheduler.start()

        log.debug("JOBS: %s" % self._scheduler.get_jobs())
        self.assertEqual(len(self._scheduler.get_jobs()), 1)

        self.assertTrue(self._scheduler.run_polled_job(test_name))
        self.assertFalse(self._scheduler.run_polled_job(test_name))
        time.sleep(2)
        self.assertTrue(self._scheduler.run_polled_job(test_name))


####################################################################################################
#  Test our new polled trigger
####################################################################################################
    def test_polled_interval_trigger(self):
        """
        test the trigger mechanism.
        """
        ###
        # Test all constructors and exceptions
        ###
        trigger = PolledIntervalTrigger(PolledScheduler.interval(seconds=1))
        self.assertEqual(trigger.min_interval_length, 1)
        self.assertIsNone(trigger.max_interval)
        self.assertIsNone(trigger.max_interval_length)
        self.assertIsInstance(trigger.next_min_date, datetime.datetime)
        self.assertIsNone(trigger.next_max_date)

        trigger = PolledIntervalTrigger(
            PolledScheduler.interval(seconds=1),
            PolledScheduler.interval(seconds=3)
        )
        self.assertEqual(trigger.min_interval_length, 1)
        self.assertEqual(trigger.max_interval_length, 3)

        trigger = PolledIntervalTrigger(
            PolledScheduler.interval(seconds=1),
            PolledScheduler.interval(seconds=3),
            datetime.datetime.now()
        )
        self.assertEqual(trigger.min_interval_length, 1)
        self.assertEqual(trigger.max_interval_length, 3)

        # Test Type Error Exception
        with self.assertRaises(TypeError):
            trigger = PolledIntervalTrigger('boom')

        with self.assertRaises(TypeError):
            trigger = PolledIntervalTrigger(
                PolledScheduler.interval(seconds=3),
                'boom'
            )

        # Test Value Error Exception
        with self.assertRaises(ValueError):
            trigger = PolledIntervalTrigger(
                PolledScheduler.interval(seconds=3),
                PolledScheduler.interval(seconds=1)
            )

        ###
        # Verify min and max dates are incremented correctly.
        ###
        now = datetime.datetime.now()
        log.debug("Now: %s" % now)
        min_interval = PolledScheduler.interval(seconds=1)
        max_interval = PolledScheduler.interval(seconds=3)

        trigger = PolledIntervalTrigger(min_interval, max_interval, now)

        # Initialized correctly?
        self.assert_datetime_close(trigger.next_min_date, now)
        self.assert_datetime_close(trigger.next_max_date, now + max_interval)
        self.assert_datetime_close(trigger.get_next_fire_time(now), now + max_interval)

        # First call should be successful, but second should not.
        self.assertTrue(trigger.pull_trigger())
        self.assertFalse(trigger.pull_trigger())

        self.assert_datetime_close(trigger.next_min_date, now + min_interval)
        self.assert_datetime_close(trigger.next_max_date, now + max_interval)
        self.assert_datetime_close(trigger.get_next_fire_time(now), now + max_interval)

        # Wait for the minimum interval and it should succeed again!
        time.sleep(2)
        now = datetime.datetime.now()
        self.assertTrue(trigger.pull_trigger())
        self.assertFalse(trigger.pull_trigger())

        ###
        # Now do the same sequence, but with no max_interval
        ###
        now = datetime.datetime.now()
        log.debug("Now: %s" % now)
        min_interval = PolledScheduler.interval(seconds=1)
        max_interval = None

        trigger = PolledIntervalTrigger(min_interval, max_interval, now)

        # Initialized correctly?
        self.assert_datetime_close(trigger.next_min_date, now)
        self.assertIsNone(trigger.next_max_date)
        self.assertIsNone(trigger.get_next_fire_time(now))

        # First call should be successful, but second should not.
        self.assertTrue(trigger.pull_trigger())
        self.assertFalse(trigger.pull_trigger())

        self.assert_datetime_close(trigger.next_min_date, now + min_interval)
        self.assertIsNone(trigger.next_max_date)
        self.assertIsNone(trigger.get_next_fire_time(now))

        # Wait for the minimum interval and it should succeed again!
        time.sleep(2)
        now = datetime.datetime.now()
        self.assertTrue(trigger.pull_trigger())
        self.assertFalse(trigger.pull_trigger())

    def test_trigger_string(self):
        """
        test the str and repr methods
        """
        now = datetime.datetime.now()
        trigger = PolledIntervalTrigger(
            PolledScheduler.interval(seconds=1),
            PolledScheduler.interval(seconds=3),
            now)

        self.assertEqual(str(trigger), "min_interval[0:00:01] max_interval[0:00:03]")
        self.assertEqual(repr(trigger), "<PolledIntervalTrigger (min_interval=datetime.timedelta(0, 1), max_interval=datetime.timedelta(0, 3))>")

        trigger = PolledIntervalTrigger(PolledScheduler.interval(seconds=1), None, now)
        self.assertEqual(str(trigger), "min_interval[0:00:01] max_interval[None]")
        self.assertEqual(repr(trigger), "<PolledIntervalTrigger (min_interval=datetime.timedelta(0, 1), max_interval=None)>")

####################################################################################################
#  Test our new polled job
####################################################################################################
    def test_polled_job(self):
        """
        Test features of the specialized job class that we overloaded.
        """
        now = datetime.datetime.now()
        min_interval = PolledScheduler.interval(seconds=1)
        max_interval = PolledScheduler.interval(seconds=3)
        trigger = PolledIntervalTrigger(min_interval, max_interval, now)

        job = PolledIntervalJob(trigger, self._callback, [], {}, 1, 1, name='test_job')
        self.assertIsNotNone(job)
        log.debug("H: %s" % repr(job))
        next_time = job.compute_next_run_time(now)
        self.assert_datetime_close(next_time, now + max_interval)
        self.assertEqual(job.name, 'test_job')

        self.assertTrue(job.ready_to_run())
        next_time = job.compute_next_run_time(now)
        self.assertFalse(job.ready_to_run())
        self.assert_datetime_close(next_time, now + max_interval)

        time.sleep(2)
        now = datetime.datetime.now()
        self.assertTrue(job.ready_to_run())

        next_time = job.compute_next_run_time(now)
        self.assertFalse(job.ready_to_run())
        self.assert_datetime_close(next_time, now + max_interval)

