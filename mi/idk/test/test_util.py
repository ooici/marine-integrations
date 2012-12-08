#!/usr/bin/env python

"""
@package mi.idk.test.test_util
@file mi.idk/test/test_util.py
@author Bill French
@brief test util functions
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
import unittest
from mi.core.unit_test import MiUnitTest

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.idk.util import convert_enum_to_dict

@attr('UNIT', group='mi')
class TestUnitTest(MiUnitTest):
    """
    Test the util functions
    """    
    def setUp(self):
        """
        Setup the test case
        """
        
    def test_convert_enum_to_dict(self):
        """
        Test convert enum to dict method
        """
        class MyEnum(BaseEnum):
            FOO = 1
            BAR = 2

        dict = convert_enum_to_dict(MyEnum);

        self.assertEqual(dict.get('FOO'), MyEnum.FOO)
        self.assertEqual(dict.get('BAR'), MyEnum.BAR)
        self.assertEqual(len(dict), 2)

