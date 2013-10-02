#!/usr/bin/env python

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from os.path import basename, dirname
from os import makedirs
from os.path import exists
import sys

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr
from mi.core.time import *
import unittest
from mi.core.unit_test import MiUnitTest
import datetime
import time as system_time
from mi.idk.exceptions import InvalidParameters

@attr('UNIT', group='mi')
class TestTime(MiUnitTest):
    """
    Test the time functions
    """    
    def setUp(self):
        """
        Setup the test case
        """

    def test_timestamp(self):
        """
        Test the creation of a timestamp string but generation
        """
        stamp = get_timestamp("%H:%M:%S")
        self.assertTrue(stamp)


    def test_delayed_timestamp(self):
        """
        Test the creation of a timestamp string but generation is
        delayed to the edge of a second.
        """
        stamp = get_timestamp_delayed("%H:%M:%S")
        now = datetime.datetime.utcnow()
        self.assertLess(now.microsecond, 200);

        # test for an empty format string
        raised = False
        try:
            stamp = get_timestamp_delayed(None)
        except ValueError as e:
            raised = True
        self.assertTrue(raised)


    @unittest.skip("This test fails regularly on the buildbot system, gevent maybe?")
    def test_extended_delayed_timestamp(self):
        """
        Test the creation of a timestamp string but generation is
        delayed to the edge of a second.  Run multiple tests.
        """
        for x in range(0, 20):
            stamp = get_timestamp_delayed("%H:%M:%S")
            now = datetime.datetime.utcnow()
            self.assertLess(now.microsecond, 100)
            system_time.sleep(0.1)
