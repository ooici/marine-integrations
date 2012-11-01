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
from pyon.util.unit_test import IonUnitTestCase
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict

@attr('UNIT', group='mi')
class TestUnitProtocolParameterDict(IonUnitTestCase):
    """
    Test cases for instrument driver class. Functions in this class provide
    instrument driver unit tests and provide a tutorial on use of
    the driver interface.
    """ 
    def setUp(self):
        self.param_dict = ProtocolParameterDict()
                
        self.param_dict.add("foo", r'foo=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             startup_param=True,
                             default_value=10)
        self.param_dict.add("bar", r'bar=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=False,
                             startup_param=True,
                             default_value=15)
        self.param_dict.add("baz", r'baz=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             default_value=20)
        self.param_dict.add("bat", r'bat=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False,
                             default_value=20)
        self.param_dict.add("qux", r'qux=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False)
        
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