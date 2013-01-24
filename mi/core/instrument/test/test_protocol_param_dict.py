#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_protocol_param_dict
@file mi/core/instrument/test/test_protocol_param_dict.py
@author Steve Foley
@brief Test cases for the base protocol parameter dictionary module
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

from ooi.logging import log
from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTestCase
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictVal, FunctionParamDictVal, RegexParamDictVal

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
                             visibility=ParameterDictVisibility.DIRECT_ACCESS)
        self.param_dict.add("bat", r'.*bat=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False,
                             default_value=20,
                             visibility=ParameterDictVisibility.READ_ONLY)
        self.param_dict.add("qux", r'.*qux=(\d+).*',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False,
                             visibility=ParameterDictVisibility.READ_ONLY)
        
    def test_get_direct_access_list(self):
        """
        Test to see we can get a list of direct access parameters
        """
        result = self.param_dict.get_direct_access_list()
        self.assertTrue(isinstance(result, list))
        self.assertEquals(len(result), 2)
        self.assert_("foo" in result)
        self.assert_("baz" in result)
        
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
        self.assertEquals(lst, ["foo", "bar"])
        lst = self.param_dict.get_visibility_list(ParameterDictVisibility.DIRECT_ACCESS)
        self.assertEquals(lst, ["baz"])
        lst = self.param_dict.get_visibility_list(ParameterDictVisibility.READ_ONLY)
        self.assertEquals(lst, ["bat", "qux"])
        
    def test_function_values(self):
        """
        Make sure we can add and update values with functions instead of patterns
        """

        self.param_dict.add_paramdictval(
            FunctionParamDictVal(
                "fn_foo",
                self.pick_byte2,
                lambda x : str(x),
                direct_access=True,
                startup_param=True,
                value=1,
                visibility=ParameterDictVisibility.READ_WRITE)
            )
        self.param_dict.add_paramdictval(
            FunctionParamDictVal(
                "fn_bar",
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
        self.assertEqual(result, 'fn_foo')
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
        self.param_dict.add_paramdictval(
            FunctionParamDictVal(
                "fn_foo",
                self.pick_byte2,
                lambda x : str(x),
                direct_access=True,
                startup_param=True,
                value=1,
                visibility=ParameterDictVisibility.READ_WRITE)
            )
        self.param_dict.add_paramdictval(
            RegexParamDictVal("foo", r'.*foo=(\d+).*',
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
        pdv = ParameterDictVal("foo",
                               lambda x : str(x),
                               value=12)
        self.assertEqual(pdv.value, 12)
        result = pdv.update(1)
        self.assertEqual(result, True)
        self.assertEqual(pdv.value, 1)

        # Its a base class...monkey see, monkey do
        result = pdv.update("foo=1")
        self.assertEqual(result, True)
        self.assertEqual(pdv.value, "foo=1")
        
    def test_regex_val(self):
        pdv = RegexParamDictVal("foo",
                               r'.*foo=(\d+).*',
                               lambda match : int(match.group(1)),
                               lambda x : str(x),
                               value=12)
        self.assertEqual(pdv.value, 12)
        result = pdv.update(1)
        self.assertEqual(result, False)
        self.assertEqual(pdv.value, 12)
        result = pdv.update("foo=1")
        self.assertEqual(result, True)
        self.assertEqual(pdv.value, 1)
        
    def test_function_val(self):
        pdv = FunctionParamDictVal("foo",
                               self.pick_byte2,
                               lambda x : str(x),
                               value=12)
        self.assertEqual(pdv.value, 12)
        self.assertRaises(TypeError, pdv.update(1))
        result = pdv.update("1205")
        self.assertEqual(pdv.value, 4)
        self.assertEqual(result, True)
