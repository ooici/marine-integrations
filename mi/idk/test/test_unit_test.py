#!/usr/bin/env python

"""
@package mi.idk.test.test_unit_test
@file mi.idk/test/test_unit_test.py
@author Bill French
@brief test unit test methods
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
import unittest

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.unit_test import InstrumentDriverTestCase

from mi.core.common import BaseEnum

@attr('UNIT', group='mi')
class TestSetComplete(InstrumentDriverTestCase):
    """
    Test the unit test assert method, assert_set_complete.  This has its own test
    class because we needed to overload assetTrue to test the function.
    """
    def setUp(self):
        self._true_result = False
        self._false_result = False

    # assert_set_complete uses this method to verify item exists.  We overload
    # it here so we can do some negative testing.  Then this method will simply
    # set a member variable if true or false was seen.
    def assertTrue(self, expr):
        if expr:
            self._true_result = True

        if not expr:
            self._false_result = True

    def test_assert_set_complete_same(self):
        """
        Test assertion set complete method.  This test ensures that items in
        parameter 1 dict a complete subset of parameter 2 dict.
        """
        ldict = {
            'FOO': 0,
            'BAR': 1,
            'BIZ': 2,
        }

        rdict = {
            'BAR': 1,
            'FOO': 0,
            'BIZ': 2,
        }

        self.assert_set_complete(ldict, rdict)
        self.assertFalse(self._false_result)

        # Have to use assertFalse here because we have overloaded assertTrue
        self.assertFalse(not self._true_result)

    def test_assert_set_complete_subset(self):
        """
        Test assertion set complete method.  This test ensures that items in
        parameter 1 dict a complete subset of parameter 2 dict.
        """
        ldict = {
            'FOO': 0,
            'BAR': 1,
            'BIZ': 2,
            }

        rdict = {
            'BAR': 1,
            'FOO': 0,
            'BIZ': 2,
            'BAZ': 3,
            }

        self.assert_set_complete(ldict, rdict)
        self.assertFalse(self._false_result)

        # Have to use assertFalse here because we have overloaded assertTrue
        self.assertFalse(not self._true_result)

    def test_assert_set_complete_notsubset(self):
        """
        Test assertion set complete method.  This test ensures that items in
        parameter 1 dict a complete subset of parameter 2 dict.
        """
        ldict = {
            'FOO': 0,
            'BAR': 1,
            'BIZ': 2,
            }

        rdict = {
            'FOO': 0,
            'BIZ': 2,
            }

        self.assert_set_complete(ldict, rdict)

        # This isn't a subset so we should fail
        # Have to use assertFalse here because we have overloaded assertTrue
        self.assertFalse(not self._false_result)

    def test_assert_set_complete_different_vals(self):
        """
        Test assertion set complete method.  This test ensures that items in
        parameter 1 dict a complete subset of parameter 2 dict.
        """
        ldict = {
            'FOO': 3,
            'BAR': 4,
            'BIZ': 5,
            }

        rdict = {
            'BAR': 1,
            'FOO': 0,
            'BIZ': 2,
            'BAZ': 3,
            }

        self.assert_set_complete(ldict, rdict)
        self.assertFalse(self._false_result)

        # Have to use assertFalse here because we have overloaded assertTrue
        self.assertFalse(not self._true_result)

    def test_assert_set_complete_empty(self):
        """
        Test empty dicts
        """
        ldict = {
            }

        rdict = {
            }

        self.assert_set_complete(ldict, rdict)
        self.assertFalse(self._false_result)

    def test_assert_set_complete_different_vals(self):
        """
        Test assertion set complete method.  This test ensures that items in
        parameter 1 dict a complete subset of parameter 2 dict.
        """
        ldict = {
            }

        rdict = {
            'BAR': 1,
            'FOO': 0,
            'BIZ': 2,
            'BAZ': 3,
            }

        self.assert_set_complete(ldict, rdict)
        # Have to use assertFalse here because we have overloaded assertTrue
        self.assertFalse(not self._false_result)

@attr('UNIT', group='mi')
class TestEnumHasNotDuplicates(InstrumentDriverTestCase):
    """
    Test the unit test assert method, assert_enum_has_no_duplicates.
    This has its own test class because we needed to overload assetEqual to
    test the function.
    """
    def setUp(self):
        self._true_result = False
        self._false_result = False

    # assert_set_complete uses this method to verify item exists.  We overload
    # it here so we can do some negative testing.  Then this method will simply
    # set a member variable if true or false was seen.
    def assertEqual(self, lvalue, rvalue):
        if lvalue == rvalue:
            self._true_result = True

        if lvalue != rvalue:
            self._false_result = True

    def test_assert_enum_without_dupe(self):
        """
        test the custom assert method assert_enum_has_no_duplicates with an enum
        that has no dupes.
        """
        class MyEnum(BaseEnum):
            FOO = 1
            BAR = 2

        self.assert_enum_has_no_duplicates(MyEnum)
        self.assertFalse(self._false_result)

    def test_assert_enum_with_dupe(self):
        """
        test the custom assert method assert_enum_has_no_duplicates with an enum
        that has dupes.
        """
        class MyEnum(BaseEnum):
            FOO = 1
            BAR = 1

        self.assert_enum_has_no_duplicates(MyEnum)
        self.assertTrue(self._false_result)
