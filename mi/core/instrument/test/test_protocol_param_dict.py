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
import re
import os

from ooi.logging import log
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTestCase
from mi.core.instrument.test.test_strings import TestUnitStringsDict
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentParameterExpirationException
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.protocol_param_dict import ParameterDictKey
from mi.core.instrument.protocol_param_dict import Parameter, FunctionParameter, RegexParameter
from mi.core.util import dict_equal

@attr('UNIT', group='mi')
class TestUnitProtocolParameterDict(TestUnitStringsDict):
    """
    Test cases for instrument driver class. Functions in this class provide
    instrument driver unit tests and provide a tutorial on use of
    the driver interface.
    """

    __test__ = True

    @staticmethod
    def pick_byte2(input):
        """ Get the 2nd byte as an example of something tricky and
        arbitrary"""
        val = int(input) >> 8
        val = val & 255
        return val
    
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
        self.param_dict.add("pho", r'.*qux=(\d+).*',
                            lambda match : int(match.group(1)),
                            lambda x : str(x),
                            startup_param=False,
                            visibility=ParameterDictVisibility.IMMUTABLE)
        self.param_dict.add("dil", r'.*qux=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False,
                             visibility=ParameterDictVisibility.IMMUTABLE)
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
        
        self.target_schema = {
            "bar":  {
                "direct_access": False,
                "get_timeout": 10,
                "set_timeout": 10,
                "startup": True,
                "value": {
                    "default": 15
                },
                "visibility": "READ_WRITE"
            },
            "bat": {
                "description": "The bat parameter",
                "direct_access": False,
                "display_name": "Bat",
                "get_timeout": 10,
                "set_timeout": 20,
                "startup": False,
                "value": {
                    "default": 20,
                    "description": "Should be an integer between 1 and 1000",
                    "type": "int",
                    "units": "nano-batbit"
                },
                "visibility": "READ_ONLY"
            },
            "baz": {
                "description": "The baz parameter",
                "direct_access": True,
                "display_name": "Baz",
                "get_timeout": 30,
                "set_timeout": 40,
                "startup": False,
                "value": {
                    "default": 20,
                    "description": "Should be an integer between 2 and 2000",
                    "type": "int",
                    "units": "nano-bazers"
                },
                "visibility": "DIRECT_ACCESS"
            },
            "dil": {
                "direct_access": False,
                "get_timeout": 10,
                "set_timeout": 10,
                "startup": False,
                "value": {},
                "visibility": "IMMUTABLE"
            },
            "foo": {
                "direct_access": True,
                "get_timeout": 10,
                "set_timeout": 10,
                "startup": True,
                "value": {
                    "default": 10
                },
                "visibility": "READ_WRITE"
            },
            "pho": {
                "direct_access": False,
                "get_timeout": 10,
                "set_timeout": 10,
                "startup": False,
                "value": {},
                "visibility": "IMMUTABLE"
            },
            "qut": {
                "description": "The qut list parameter",
                "direct_access": True,
                "display_name": "Qut",
                "get_timeout": 10,
                "set_timeout": 20,
                "startup": False,
                "value": {
                    "default": [
                        10,
                        100
                    ],
                    "description": "Should be a 2-10 element list of integers between 2 and 2000",
                    "type": "list",
                    "units": "nano-qutters"
                },
                "visibility": "DIRECT_ACCESS"
            },
            "qux": {
                "direct_access": False,
                "get_timeout": 10,
                "set_timeout": 10,
                "startup": False,
                "value": {},
                "visibility": "READ_ONLY"
            }
        }

        self.test_yaml = '''
        parameters: {
            qut: {
            description: "QutFileDesc",
            units: "QutFileUnits",
            value_description: "QutFileValueDesc",
            type: "QutFileType",
            display_name: "QutDisplay"
            },
            extra_param: {
            description: "ExtraFileDesc",
            units: "ExtraFileUnits",
            value_description: "ExtraFileValueDesc",
            type: "ExtraFileType"    
            }
          }
          
        commands: {
          dummy: stuff
          }
        '''

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

    def test_update_specific_values(self):
        """
        test to verify we can limit update to a specific
        set of parameters
        """
        sample_input = "foo=100, bar=200"

        # First verify we can set both
        self.assertNotEquals(self.param_dict.get("foo"), 100)
        self.assertNotEquals(self.param_dict.get("bar"), 200)
        self.assertTrue(self.param_dict.update(sample_input))
        self.assertEquals(self.param_dict.get("foo"), 100)
        self.assertEquals(self.param_dict.get("bar"), 200)

        # Now let's only have it update 1 parameter with a name
        sample_input = "foo=200, bar=300"
        self.assertTrue(self.param_dict.update(sample_input, target_params = "foo"))
        self.assertEquals(self.param_dict.get("foo"), 200)
        self.assertEquals(self.param_dict.get("bar"), 200)

        # Now let's only have it update 1 parameter using a list
        sample_input = "foo=300, bar=400"
        self.assertTrue(self.param_dict.update(sample_input, target_params = ["foo"]))
        self.assertEquals(self.param_dict.get("foo"), 300)
        self.assertEquals(self.param_dict.get("bar"), 200)

        # Test our exceptions
        with self.assertRaises(KeyError):
            self.param_dict.update(sample_input, "key_does_not_exist")

        with self.assertRaises(InstrumentParameterException):
            self.param_dict.update(sample_input, {'bad': "key_does_not_exist"})

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
        lst = self.param_dict.get_visibility_list(ParameterDictVisibility.IMMUTABLE)
        lst.sort()
        self.assertEquals(lst, ["dil", "pho"])
        
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
        self.maxDiff = None
        result = self.param_dict.generate_dict()
        json_result = json.dumps(result, indent=4, sort_keys=True)
        log.debug("Expected: %s", self.target_schema)
        log.debug("Result: %s", json_result)
        self.assertEqual(result, self.target_schema)

    def test_empty_schema(self):
        self.param_dict = ProtocolParameterDict()
        result = self.param_dict.generate_dict()
        self.assertEqual(result, {})

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

    def test_get(self):
        """
        test getting values with expiration
        """
        #from mi.core.exceptions import InstrumentParameterExpirationException
        pd = ProtocolParameterDict()

        # No expiration, should work just fine
        pd.add('noexp', r'', None, None, expiration=None)
        pd.add('zeroexp', r'', None, None, expiration=0)
        pd.add('lateexp', r'', None, None, expiration=2)

        ###
        # Set and get with no expire
        ###
        pd.set_value('noexp', 1)
        self.assertEqual(pd.get('noexp'), 1)

        ###
        # Set and get with a 0 expire
        ###
        basetime = pd.get_current_timestamp()
        pd.set_value('zeroexp', 2)

        # We should fail because we are calculating exp against current time
        with self.assertRaises(InstrumentParameterExpirationException):
            pd.get('zeroexp')

        # Should succeed because exp is calculated using basetime
        self.assertEqual(pd.get('zeroexp', basetime), 2)

        ###
        # Set and get with a delayed expire
        ###
        basetime = pd.get_current_timestamp()
        futuretime = pd.get_current_timestamp(3)
        self.assertGreater(futuretime - basetime, 3)

        pd.set_value('lateexp', 2)

        # Success because data is not expired
        self.assertEqual(pd.get('lateexp', basetime), 2)

        # Fail because data is expired (simulated three seconds from now)
        with self.assertRaises(InstrumentParameterExpirationException):
            pd.get('lateexp', futuretime)
    
    def test_regex_flags(self):
        pdv = RegexParameter("foo",
                             r'.+foo=(\d+).+',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             regex_flags=re.DOTALL,
                             value=12)
        # Assert something good with dotall update()
        self.assertTrue(pdv)
        pdv.update("\n\nfoo=1212\n\n")
        self.assertEqual(pdv.get_value(), 1212)
        
        # negative test with no regex_flags
        pdv = RegexParameter("foo",
                             r'.+foo=(\d+).+',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             value=12)
        # Assert something good with dotall update()
        self.assertTrue(pdv)
        pdv.update("\n\nfoo=1212\n\n")
        self.assertEqual(pdv.get_value(), 12)
        
        self.assertRaises(TypeError,
                          RegexParameter,
                          "foo",
                          r'.*foo=(\d+).*',
                          lambda match : int(match.group(1)),
                          lambda x : str(x),
                          regex_flags="bad flag",
                          value=12)
            
    def test_format_current(self):
        self.param_dict.add("test_format", r'.*foo=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : x+5,
                             value=10)
        self.assertEqual(self.param_dict.format("test_format", 20), 25)
        self.assertEqual(self.param_dict.format("test_format"), 15)
        self.assertRaises(KeyError,
                          self.param_dict.format, "bad_name")

    def _assert_metadata_change(self):
        new_dict = self.param_dict.generate_dict()
        log.debug("Generated dictionary: %s", new_dict)
        self.assertEqual(new_dict["qut"][ParameterDictKey.DESCRIPTION], "QutFileDesc")
        self.assertEqual(new_dict["qut"][ParameterDictKey.DISPLAY_NAME], "QutDisplay")
        self.assertEqual(new_dict["qut"][ParameterDictKey.VALUE][ParameterDictKey.UNITS], "QutFileUnits")
        self.assertEqual(new_dict["qut"][ParameterDictKey.VALUE][ParameterDictKey.DESCRIPTION], "QutFileValueDesc")
        self.assertEqual(new_dict["qut"][ParameterDictKey.VALUE][ParameterDictKey.TYPE], "QutFileType")
        # Should come from hard code
        #self.assertEqual(new_dict["qut"][ParameterDictKey.DISPLAY_NAME], "QutFileName") 

        # from base hard code
        new_dict = self.param_dict.generate_dict()
        self.assertEqual(new_dict["baz"][ParameterDictKey.DESCRIPTION],
                         "The baz parameter")
        self.assertEqual(new_dict["baz"][ParameterDictKey.VALUE][ParameterDictKey.UNITS],
                         "nano-bazers")
        self.assertEqual(new_dict["baz"][ParameterDictKey.VALUE][ParameterDictKey.DESCRIPTION],
                         "Should be an integer between 2 and 2000")
        self.assertEqual(new_dict["baz"][ParameterDictKey.VALUE][ParameterDictKey.TYPE],
                         ParameterDictType.INT)
        self.assertEqual(new_dict["baz"][ParameterDictKey.DISPLAY_NAME], "Baz")
        
        self.assertTrue('extra_param' not in new_dict)
