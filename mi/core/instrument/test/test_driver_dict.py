#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_protocol_cmd_dict
@file mi/core/instrument/test/test_protocol_cmd_dict.py
@author Steve Foley
@brief Test cases for the base protocol command dictionary module
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import json

from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTestCase
from mi.core.instrument.driver_dict import DriverDict, DriverDictKey

from mi.core.log import get_logger ; log = get_logger()


@attr('UNIT', group='mi')
class TestUnitProtocolCommandDict(MiUnitTestCase):

    """
    Test cases for instrument driver class. Functions in this class provide
    instrument driver unit tests and provide a tutorial on use of
    the driver interface.
    """ 
    def setUp(self):
        self.driver_dict = DriverDict()
                
        self.driver_dict.add(DriverDictKey.VENDOR_SW_COMPATIBLE, True)

        self.target_dict = {DriverDictKey.VENDOR_SW_COMPATIBLE:True}
        self.target_schema = '{"vendor_sw_compatible": true}'
        
    def test_schema_generation(self):
        result = self.driver_dict.generate_dict()
        self.assertEqual(result, self.target_dict)
        self.assertEqual(json.dumps(result), self.target_schema)
        
    def test_empty_schema(self):
        self.driver_dict = DriverDict()
        result = self.driver_dict.generate_dict()
        self.assertEqual(result, {})
        
    def test_add_get(self):
        self.assertEquals(self.driver_dict.get_value("vendor_sw_compatible"),
                          True)
        self.driver_dict.add("good_val", 12)
        self.assertEquals(self.driver_dict.get_value("good_val"), 12)
        self.driver_dict.add("good_val", 21)
        self.assertEquals(self.driver_dict.get_value("good_val"), 21)
        self.driver_dict.add("good_val")
        self.assertEquals(self.driver_dict.get_value("good_val"), None)

        self.assertRaises(KeyError,
                          self.driver_dict.get_value, "missing_val")
        self.assertRaises(KeyError,
                          self.driver_dict.get_value, None)
