#!/usr/bin/env python

"""
@package mi.idk.test.test_nose_test
@file mi.idk/test/test_nose_test.py
@author Bill French
@brief test git
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from os.path import basename, dirname
from os import makedirs,chdir, system
from os import remove
from os.path import exists
import sys

from nose.plugins.attrib import attr
from mock import Mock
import unittest

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.nose_test import NoseTest
from mi.idk.metadata import Metadata
from mi.idk.exceptions import IDKException

TEST_DRIVER_MAKE = 'seabird'
TEST_DRIVER_MODEL = 'sbe37smb'
TEST_DRIVER_FLAVOR = 'ooicore'
DRIVER_TEST_MODULE = 'mi.instrument.seabird.sbe37smb.ooicore.test.test_driver'

@attr('UNIT', group='mi')
class TestNose(unittest.TestCase):
    """
    Test the nose_test IDK module
    """
    def setUp(self):
        """
        Setup the test case
        """
        metadata = Metadata(TEST_DRIVER_MAKE,TEST_DRIVER_MODEL,TEST_DRIVER_FLAVOR)
        self.assertTrue(metadata)
        self.nose = NoseTest(metadata)
        self.assertTrue(self.nose)


    def test_inspect_module(self):
        '''
        Test the _inspect_test_module method to verify it identifies all test classes properly.
        '''

        # Positive test.
        self.nose._inspect_driver_module(self.nose._driver_test_module())

        self.assertEqual(self.nose._unit_test_class, 'SBEUnitTestCase')
        self.assertEqual(self.nose._int_test_class, 'SBEIntTestCase')
        self.assertEqual(self.nose._qual_test_class, 'SBEQualificationTestCase')

        # Test Failure, one of the tests is not found.
        with self.assertRaises(IDKException):
            self.nose._inspect_driver_module('unittest')

    def test_nose(self):
        '''
        Verify that we can initialize a NoseTest.  What we really want to see is that we can build the nose test
        command lines properly from a test module.
        '''

        # Verify we can get the test module name and file
        self.assertEqual(self.nose._driver_test_module(), DRIVER_TEST_MODULE)
        test_file = self.nose._driver_test_module().replace('.', '/') + ".py"

        self.assertTrue(test_file in self.nose._driver_test_filename())

        self.assertEqual(self.nose._unit_test_class, 'SBEUnitTestCase')
        self.assertEqual(self.nose._int_test_class, 'SBEIntTestCase')
        self.assertEqual(self.nose._qual_test_class, 'SBEQualificationTestCase')

        self.assertEqual(self.nose._unit_test_module_param(),
                         "%s:%s" % (self.nose._driver_test_filename(), self.nose._unit_test_class))

        self.assertEqual(self.nose._int_test_module_param(),
                         "%s:%s" % (self.nose._driver_test_filename(), self.nose._int_test_class))

        self.assertEqual(self.nose._qual_test_module_param(),
                         "%s:%s" % (self.nose._driver_test_filename(), self.nose._qual_test_class))

        self.assertIsNone(self.nose._testname)


    def test_nose_with_testname(self):
        '''
        Test nose when specifying a specific test name
        '''

        metadata = Metadata(TEST_DRIVER_MAKE,TEST_DRIVER_MODEL,TEST_DRIVER_FLAVOR)
        self.assertTrue(metadata)
        self.nose = NoseTest(metadata, testname='test_autosample')
        self.assertTrue(self.nose)

        # Verify we can get the test module name and file
        self.assertEqual(self.nose._driver_test_module(), DRIVER_TEST_MODULE)
        test_file = self.nose._driver_test_module().replace('.', '/') + ".py"

        self.assertTrue(test_file in self.nose._driver_test_filename())

        self.assertEqual(self.nose._unit_test_class, 'SBEUnitTestCase')
        self.assertEqual(self.nose._int_test_class, 'SBEIntTestCase')
        self.assertEqual(self.nose._qual_test_class, 'SBEQualificationTestCase')

        self.assertEqual(self.nose._testname, 'test_autosample')

        self.assertEqual(self.nose._unit_test_module_param(),
            "%s:%s.%s" % (self.nose._driver_test_filename(), self.nose._unit_test_class, 'test_autosample'))

        self.assertEqual(self.nose._int_test_module_param(),
            "%s:%s.%s" % (self.nose._driver_test_filename(), self.nose._int_test_class, 'test_autosample'))

        self.assertEqual(self.nose._qual_test_module_param(),
            "%s:%s.%s" % (self.nose._driver_test_filename(), self.nose._qual_test_class, 'test_autosample'))







    
