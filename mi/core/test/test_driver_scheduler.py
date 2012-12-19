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
from apscheduler.util import timedelta_seconds

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr

from mi.core.unit_test import MiUnitTest
from mi.core.driver_scheduler import DriverScheduler
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType
from mi.core.exceptions import SchedulerException

@attr('UNIT', group='mi')
class TestDriverScheduler(MiUnitTest):
    """
    Test the driver scheduler
    """    
    def setUp(self):
        """
        Setup the test case
        """
        self._scheduler = DriverScheduler()
        self._triggered = []

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

    def assert_event_triggered(self, expected_arrival = None, poll_time = 0.3, timeout = 10):
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

    ###
    #   Positive Testing For All Job Types
    ###
    def test_absolute_job(self):
        """
        Test a job scheduler using an absolute job
        """
        dt = datetime.datetime.now() + datetime.timedelta(0,1)
        config = {
            'absolute_job': {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.ABSOLUTE,
                    DriverSchedulerConfigKey.DATE: dt
                },
                DriverSchedulerConfigKey.CALLBACK: self._callback
            }
        }
        self._scheduler.add_config(config)
        self.assert_event_triggered(dt)

    def test_cron_job(self):
        """
        Test a job scheduler using an cron
        """
        config = {
            'cron_job': {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.CRON,
                    DriverSchedulerConfigKey.SECOND: '*/3'
                },
                DriverSchedulerConfigKey.CALLBACK: self._callback
            }
        }
        self._scheduler.add_config(config)
        self.assert_event_triggered()

    def test_interval_job(self):
        """
        Test a job scheduler using an absolute job
        """
        config = {
            'interval_job': {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                    DriverSchedulerConfigKey.SECONDS: 3
                },
                DriverSchedulerConfigKey.CALLBACK: self._callback
            }
        }
        self._scheduler.add_config(config)
        self.assert_event_triggered()

    def test_polled_interval_job(self):
        """
        Test a job scheduler using an absolute job
        """
        test_name = 'interval_job'
        config = {
            test_name: {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.POLLED_INTERVAL,
                    DriverSchedulerConfigKey.MINIMAL_INTERVAL: {DriverSchedulerConfigKey.SECONDS: 1},
                    DriverSchedulerConfigKey.MAXIMUM_INTERVAL: {DriverSchedulerConfigKey.SECONDS: 3},
                },
                DriverSchedulerConfigKey.CALLBACK: self._callback
            }
        }
        self._scheduler.add_config(config)

        # Verify automatic trigger
        self.assert_event_triggered()

        # Test the polled trigger
        self.assertFalse(self._scheduler.run_job(test_name))
        time.sleep(1.1)
        self.assertTrue(self._scheduler.run_job(test_name))

        # Check the automatic trigger again
        self.assert_event_triggered()

    ###
    #   Negative Testing For All Job Types
    ###
    def test_common_job_exception(self):
        """
        Test exception that occur for all types of jobs
        """
        test_name = 'some_test'
        config = {}

        # Not a dict
        with self.assertRaisesRegexp(SchedulerException, 'scheduler config not a dict'):
            self._scheduler.add_config('not_a_dict')

        # Empty config
        with self.assertRaisesRegexp(SchedulerException, 'scheduler config empty'):
            self._scheduler.add_config(config)

        # Not defined schedule config
        config[test_name] = None
        with self.assertRaisesRegexp(SchedulerException, 'job config empty'):
            self._scheduler.add_config(config)

        # schedule config not a dict
        config[test_name] = 'not_a_dict'
        with self.assertRaisesRegexp(SchedulerException, 'job config not a dict'):
            self._scheduler.add_config(config)

        # empty schedule config
        config[test_name] = {}
        with self.assertRaisesRegexp(SchedulerException, 'trigger definition missing'):
            self._scheduler.add_config(config)

        # missing trigger
        config[test_name] = { DriverSchedulerConfigKey.CALLBACK: self._callback }
        with self.assertRaisesRegexp(SchedulerException, 'trigger definition missing'):
            self._scheduler.add_config(config)

        # invalid trigger type
        config[test_name] = {
            DriverSchedulerConfigKey.TRIGGER: {
                DriverSchedulerConfigKey.TRIGGER_TYPE: 'some_type',
            },
            DriverSchedulerConfigKey.CALLBACK: self._callback
        }
        with self.assertRaisesRegexp(SchedulerException, "unknown trigger type 'some_type'"):
            self._scheduler.add_config(config)

        # missing callback
        config[test_name] = {
            DriverSchedulerConfigKey.TRIGGER: {
                DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.ABSOLUTE
            },
        }
        with self.assertRaisesRegexp(SchedulerException, 'callback definition missing'):
            self._scheduler.add_config(config)

        # invalid callback
        config[test_name] = {
            DriverSchedulerConfigKey.TRIGGER: {
                DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.ABSOLUTE
            },
            DriverSchedulerConfigKey.CALLBACK: 'not_a_method'
        }
        with self.assertRaisesRegexp(SchedulerException, 'callback incorrect type:'):
            self._scheduler.add_config(config)

    def test_absolute_job_exception(self):
        """
        Test exception that occur for absolute timed jobs.  Assumes all common exceptions
        have been tested.
        """
        test_name = 'some_test'
        config = {
            test_name: {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.ABSOLUTE
                },
                DriverSchedulerConfigKey.CALLBACK: self._callback
            }
        }

        # Missing datetime
        with self.assertRaisesRegexp(SchedulerException, 'trigger missing parameter: date'):
            self._scheduler.add_config(config)

        # Wrong parameter type
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.DATE] = 'not a date object'
        with self.assertRaisesRegexp(SchedulerException, 'failed to schedule job: Invalid date string'):
            self._scheduler.add_config(config)

    def test_cron_job_exception(self):
        """
        Test exception that occur for cron timed jobs.  Assumes all common exceptions
        have been tested.
        """
        test_name = 'some_test'
        config = {
            test_name: {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.CRON
                },
                DriverSchedulerConfigKey.CALLBACK: self._callback
            }
        }

        # Missing all cron settings
        with self.assertRaisesRegexp(SchedulerException, 'at least one cron parameter required'):
            self._scheduler.add_config(config)

        # Wrong parameter type
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.WEEK] = 'n'
        with self.assertRaisesRegexp(SchedulerException, 'failed to schedule job:'):
            self._scheduler.add_config(config)

    def test_interval_job_exception(self):
        """
        Test exception that occur for interval timed jobs.  Assumes all common exceptions
        have been tested.
        """
        test_name = 'some_test'
        config = {
            test_name: {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL
                },
                DriverSchedulerConfigKey.CALLBACK: self._callback
            }
        }

        # Missing all cron settings
        with self.assertRaisesRegexp(SchedulerException, 'at least interval parameter required'):
            self._scheduler.add_config(config)

        # Wrong parameter type
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.WEEKS] = 'n'
        with self.assertRaisesRegexp(SchedulerException, 'failed to schedule job:'):
            self._scheduler.add_config(config)

    def test_polled_interval_job_exception(self):
        """
        Test exception that occur for interval timed jobs.  Assumes all common exceptions
        have been tested.
        """
        test_name = 'some_test'
        config = {
            test_name: {
                DriverSchedulerConfigKey.TRIGGER: {
                    DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.POLLED_INTERVAL
                },
                DriverSchedulerConfigKey.CALLBACK: self._callback
            }
        }

        # Missing all cron settings
        with self.assertRaisesRegexp(SchedulerException, 'minimum_interval missing from trigger configuration'):
            self._scheduler.add_config(config)

        # None interval
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MINIMAL_INTERVAL] = None
        with self.assertRaisesRegexp(SchedulerException, 'minimum_interval missing from trigger configuration'):
            self._scheduler.add_config(config)

        # empty interval
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MINIMAL_INTERVAL] = {}
        with self.assertRaisesRegexp(SchedulerException, 'at least interval parameter required'):
            self._scheduler.add_config(config)

        # Bad interval parameter
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MINIMAL_INTERVAL][DriverSchedulerConfigKey.WEEKS] = 'n'
        with self.assertRaisesRegexp(SchedulerException, 'failed to schedule job:'):
            self._scheduler.add_config(config)

        # Bad max_interval parameter
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MAXIMUM_INTERVAL] = {}
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MAXIMUM_INTERVAL][DriverSchedulerConfigKey.WEEKS] = 'n'
        with self.assertRaisesRegexp(SchedulerException, 'failed to schedule job:'):
            self._scheduler.add_config(config)

        # Schedule a job with a min interval < max interval
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MINIMAL_INTERVAL][DriverSchedulerConfigKey.WEEKS] = 2
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MAXIMUM_INTERVAL][DriverSchedulerConfigKey.WEEKS] = 1
        with self.assertRaisesRegexp(SchedulerException, 'failed to schedule job: min_interval < max_interval'):
            self._scheduler.add_config(config)

        # Schedule a job twice
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MINIMAL_INTERVAL][DriverSchedulerConfigKey.WEEKS] = 1
        config[test_name][DriverSchedulerConfigKey.TRIGGER][DriverSchedulerConfigKey.MAXIMUM_INTERVAL][DriverSchedulerConfigKey.WEEKS] = 2
        with self.assertRaisesRegexp(SchedulerException, "failed to schedule job: Not adding job since a job named 'some_test' already exists"):
            self._scheduler.add_config(config)
            self._scheduler.add_config(config)

        # Run a job that doesn't exist
        with self.assertRaisesRegexp(LookupError, "no PolledIntervalJob found named"):
            self._scheduler.run_job('who_are_you')






























