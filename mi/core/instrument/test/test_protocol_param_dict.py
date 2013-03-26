#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_protocol_param_dict
@file mi/core/instrument/test/test_protocol_param_dict.py
@author Steve Foley
@brief Test cases for the base protocol parameter dictionary module
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import json
import time

from ooi.logging import log
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTestCase
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentParameterExpirationException
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import Parameter, FunctionParameter, RegexParameter

@attr('UNIT', group='mi')
class TestUnitProtocolParameterDict(MiUnitTestCase):
    @staticmethod
    def pick_byte2(input):
        """ Get the 2nd byte as an example of something tricky and
        arbitrary"""
        val = int(input) >> 8
        val = val & 255
        return val
    
    """
    Test cases for instrument driver class. Functions in this class provide
    instrument driver unit tests and provide a tutorial on use of
    the driver interface.
    """ 
    def setUp(self):
        self.param_dict = ProtocolParameterDict()
                
        self.param_dict.add("foo", r'.*foo=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             startup_param=True,
                             default_value=10,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self.param_dict.add("bar", r'.*bar=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=False,
                             startup_param=True,
                             default_value=15,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self.param_dict.add("baz", r'.*baz=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             default_value=20,
                             visibility=ParameterDictVisibility.DIRECT_ACCESS,
                             get_timeout=30,
                             set_timeout=40,
                             display_name="Baz",
                             description="The baz parameter",
                             type=ParameterDictType.INT,
                             units="nano-bazers",
                             value_description="Should be an integer between 2 and 2000")
        self.param_dict.add("bat", r'.*bat=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False,
                             default_value=20,
                             visibility=ParameterDictVisibility.READ_ONLY,
                             get_timeout=10,
                             set_timeout=20,
                             display_name="Bat",
                             description="The bat parameter",
                             type=ParameterDictType.INT,
                             units="nano-batbit",
                             value_description="Should be an integer between 1 and 1000")
        self.param_dict.add("qux", r'.*qux=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self.param_dict.add("qut", r'.*qut=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             default_value=[10, 100],
                             visibility=ParameterDictVisibility.DIRECT_ACCESS,
                             expiration=1,
                             get_timeout=10,
                             set_timeout=20,
                             display_name="Qut",
                             description="The qut list parameter",
                             type=ParameterDictType.LIST,
                             units="nano-qutters",
                             value_description="Should be a 2-10 element list of integers between 2 and 2000")
        
        self.target_schema = """{
    "parameters": {
        "bar": {
            "direct_access": false, 
            "get_timeout": 10, 
            "set_timeout": 10, 
            "startup": true, 
            "value": {
                "default": 15
            }, 
            "writable": true
        }, 
        "bat": {
            "description": "The bat parameter", 
            "direct_access": false, 
            "display_name": "Bat", 
            "get_timeout": 10, 
            "set_timeout": 20, 
            "startup": false, 
            "value": {
                "default": 20, 
                "description": "Should be an integer between 1 and 1000", 
                "type": "int", 
                "units": "nano-batbit"
            }, 
            "writable": false
        }, 
        "baz": {
            "description": "The baz parameter", 
            "direct_access": true, 
            "display_name": "Baz", 
            "get_timeout": 30, 
            "set_timeout": 40, 
            "startup": false, 
            "value": {
                "default": 20, 
                "description": "Should be an integer between 2 and 2000", 
                "type": "int", 
                "units": "nano-bazers"
            }, 
            "writable": false
        }, 
        "foo": {
            "direct_access": true, 
            "get_timeout": 10, 
            "set_timeout": 10, 
            "startup": true, 
            "value": {
                "default": 10
            }, 
            "writable": true
        }, 
        "qut": {
            "description": "The qut list parameter", 
            "direct_access": true, 
            "display_name": "Qut", 
            "get_timeout": 10, 
            "set_timeout": 20, 
            "startup": false, 
            "value": {
                "default": [
                    10, 
                    100
                ], 
                "description": "Should be a 2-10 element list of integers between 2 and 2000", 
                "type": "list", 
                "units": "nano-qutters"
            }, 
            "writable": false
        }, 
        "qux": {
            "direct_access": false, 
            "get_timeout": 10, 
            "set_timeout": 10, 
            "startup": false, 
            "value": {}, 
            "writable": false
        }
    }
}"""
        
    def test_get_direct_access_list(self):
        """
        Test to see we can get a list of direct access parameters
        """
        result = self.param_dict.get_direct_access_list()
        self.assertTrue(isinstance(result, list))
        self.assertEquals(len(result), 3)
        self.assert_("foo" in result)
        self.assert_("baz" in result)
        self.assert_("qut" in result)
        
    def test_get_startup_list(self):
        """
        Test to see we can get a list of direct access parameters
        """
        result = self.param_dict.get_startup_list()
        self.assertTrue(isinstance(result, list))
        self.assertEquals(len(result), 2)
        self.assert_("foo" in result)
        self.assert_("bar" in result)
        
    def test_set_default(self):
        """
        Test setting a default value
        """
        result = self.param_dict.get_config()
        self.assertEquals(result["foo"], None)
        self.param_dict.set_default("foo")
        self.assertEquals(self.param_dict.get("foo"), 10)
        self.param_dict.update("foo=1000")
        self.assertEquals(self.param_dict.get("foo"), 1000)
        self.param_dict.set_default("foo")
        self.assertEquals(self.param_dict.get("foo"), 10)
        
        self.assertRaises(ValueError, self.param_dict.set_default, "qux")
        
    def test_update_many(self):
        """
        Test updating of multiple variables from the same input
        """
        sample_input = """
foo=100
bar=200, baz=300
"""
        self.assertNotEquals(self.param_dict.get("foo"), 100)
        self.assertNotEquals(self.param_dict.get("bar"), 200)
        self.assertNotEquals(self.param_dict.get("baz"), 300)
        result = self.param_dict.update_many(sample_input)
        log.debug("result: %s", result)
        self.assertEquals(result["foo"], True)
        self.assertEquals(result["bar"], True)
        self.assertEquals(result["baz"], True)
        self.assertEquals(self.param_dict.get("foo"), 100)
        self.assertEquals(self.param_dict.get("bar"), 200)
        self.assertEquals(self.param_dict.get("baz"), 300)
        
    def test_visibility_list(self):
        lst = self.param_dict.get_visibility_list(ParameterDictVisibility.READ_WRITE)
        lst.sort()
        self.assertEquals(lst, ["bar", "foo"])
        lst = self.param_dict.get_visibility_list(ParameterDictVisibility.DIRECT_ACCESS)
        lst.sort()
        self.assertEquals(lst, ["baz", "qut"])
        lst = self.param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY)
        lst.sort()
        self.assertEquals(lst, ["bat", "qux"])
        
    def test_function_values(self):
        """
        Make sure we can add and update values with functions instead of patterns
        """

        self.param_dict.add_parameter(
            FunctionParameter("fn_foo",
                              self.pick_byte2,
                              lambda x : str(x),
                              direct_access=True,
                              startup_param=True,
                              value=1,
                              visibility=ParameterDictVisibility.READ_WRITE)
            )
        self.param_dict.add_parameter(
            FunctionParameter("fn_bar",
                              lambda x : bool(x&2), # bit map example
                              lambda x : str(x),
                              direct_access=True,
                              startup_param=True,
                              value=False,
                              visibility=ParameterDictVisibility.READ_WRITE)
            )
        
        # check defaults just to be safe
        val = self.param_dict.get("fn_foo")
        self.assertEqual(val, 1)
        val = self.param_dict.get("fn_bar")
        self.assertEqual(val, False)
        
        result = self.param_dict.update(1005) # just change first in list
        val = self.param_dict.get("fn_foo")
        self.assertEqual(val, 3)
        val = self.param_dict.get("fn_bar")
        self.assertEqual(val, False)
        
        # fn_bar does not get updated here
        result = self.param_dict.update_many(1205)
        self.assertEqual(result['fn_foo'], True)
        self.assertEqual(len(result), 1)
        val = self.param_dict.get("fn_foo")
        self.assertEqual(val, 4)
        val = self.param_dict.get("fn_bar")
        self.assertEqual(val, False)
        
        # both are updated now
        result = self.param_dict.update_many(6)
        self.assertEqual(result['fn_foo'], True)
        self.assertEqual(result['fn_bar'], True)
        self.assertEqual(len(result), 2)
        
        val = self.param_dict.get("fn_foo")
        self.assertEqual(val, 0)
        val = self.param_dict.get("fn_bar")
        self.assertEqual(val, True)
        
    def test_mixed_pdv_types(self):
        """ Verify we can add different types of PDVs in one container """
        self.param_dict.add_parameter(
            FunctionParameter("fn_foo",
                              self.pick_byte2,
                              lambda x : str(x),
                              direct_access=True,
                              startup_param=True,
                              value=1,
                              visibility=ParameterDictVisibility.READ_WRITE)
            )
        self.param_dict.add_parameter(
            RegexParameter("foo", r'.*foo=(\d+).*',
                           lambda match : int(match.group(1)),
                           lambda x : str(x),
                           direct_access=True,
                           startup_param=True,
                           value=10,
                           visibility=ParameterDictVisibility.READ_WRITE)
            )
        self.param_dict.add("bar", r'.*bar=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=False,
                             startup_param=True,
                             value=15,
                             visibility=ParameterDictVisibility.READ_WRITE)
        
        self.assertEqual(self.param_dict.get("fn_foo"), 1)
        self.assertEqual(self.param_dict.get("foo"), 10)
        self.assertEqual(self.param_dict.get("bar"), 15)
        
    def test_base_update(self):
        pdv = Parameter("foo",
                        lambda x : str(x),
                        value=12)
        self.assertEqual(pdv.get_value(), 12)
        result = pdv.update(1)
        self.assertEqual(result, True)
        self.assertEqual(pdv.get_value(), 1)

        # Its a base class...monkey see, monkey do
        result = pdv.update("foo=1")
        self.assertEqual(result, True)
        self.assertEqual(pdv.get_value(), "foo=1")
        
    def test_regex_val(self):
        pdv = RegexParameter("foo",
                             r'.*foo=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             value=12)
        self.assertEqual(pdv.get_value(), 12)
        result = pdv.update(1)
        self.assertEqual(result, False)
        self.assertEqual(pdv.get_value(), 12)
        result = pdv.update("foo=1")
        self.assertEqual(result, True)
        self.assertEqual(pdv.get_value(), 1)
        
    def test_function_val(self):
        pdv = FunctionParameter("foo",
                                self.pick_byte2,
                                lambda x : str(x),
                                value=12)
        self.assertEqual(pdv.get_value(), 12)
        self.assertRaises(TypeError, pdv.update(1))
        result = pdv.update("1205")
        self.assertEqual(pdv.get_value(), 4)
        self.assertEqual(result, True)
        
    def test_set_init_value(self):
        result = self.param_dict.get("foo")
        self.assertEqual(result, None)        
        self.param_dict.set_init_value("foo", 42)
        result = self.param_dict.get_init_value("foo")
        self.assertEqual(result, 42)
        
    def test_schema_generation(self):
        result = self.param_dict.generate_schema()
        # Make sure we have a reasonable length, first
        self.assert_(len(result) > 100)
        self.assertEqual(result, self.target_schema)
        
    def test_bad_descriptions(self):
        self.param_dict._param_dict["foo"].description = None
        self.param_dict._param_dict["foo"].value = None
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.get_init_value, "foo")
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.get_default_value, "foo")
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.set_default, "foo")
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.get_init_value, "foo")
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.get_menu_path_read, "foo")
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.get_submenu_read, "foo")
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.get_menu_path_write, "foo")
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.get_submenu_write, "foo")
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.format, "foo", 1)
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.get_direct_access_list)
        self.assertRaises(InstrumentParameterException,
                          self.param_dict.is_startup_param, "foo")
    
    def test_set(self):
        """
        Test a simple set of the parameter. Make sure the right values get
        called and the correct exceptions are raised.
        """
        new_param = FunctionParameter("foo",
                        self.pick_byte2,
                        lambda x : str(x),
                        direct_access=True,
                        startup_param=True,
                        value=1000,
                        visibility=ParameterDictVisibility.READ_WRITE)
        self.assertEquals(new_param.get_value(), 1000)
        self.assertEquals(self.param_dict.get("foo"), None)
        # overwrites existing param
        self.param_dict.add_parameter(new_param)
        self.assertEquals(self.param_dict.get("foo"), 1000)
        self.param_dict.set_value("foo", 2000)
        self.assertEquals(self.param_dict.get("foo"), 2000)
        
    def test_invalid_type(self):
        self.assertRaises(InstrumentParameterException,
                          FunctionParameter,
                              "fn_bar",
                              lambda x : bool(x&2), # bit map example
                              lambda x : str(x),
                              direct_access=True,
                              startup_param=True,
                              value=False,
                              type = "bad_type",
                              visibility=ParameterDictVisibility.READ_WRITE)
        
        


