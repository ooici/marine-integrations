#!/usr/bin/env python

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from mi.core.util import dict_equal
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTest

@attr('UNIT', group='mi')
class TestUtil(MiUnitTest):
    """
    Test the util functions
    """    
    def test_dict_equal(self):
        """
        Test the diff_equal function
        """
        a='a'
        b='b'
        self.assertTrue(dict_equal({}, {}))
        self.assertTrue(dict_equal({a:1}, {a:1}))
        self.assertTrue(dict_equal({a:1, b:2}, {a:1, b:2}))
        self.assertTrue(dict_equal({b:2, a:1}, {a:1, b:2}))
        self.assertFalse(dict_equal({a:1}, {}))
        self.assertFalse(dict_equal({}, {a:1}))
        self.assertFalse(dict_equal({a:1}, {a:2}))
        self.assertFalse(dict_equal({a:1, b:2}, {a:1, b:1}))
        self.assertFalse(dict_equal({a:1, b:{b}}, {a:1, b:1}))
        self.assertFalse(dict_equal({a:1, b:b}, {a:1, b:1}))
