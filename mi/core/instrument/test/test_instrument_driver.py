#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_instrument_driver
@file mi/core/instrument/test/test_instrument_driver.py
@author Bill French
@brief Test cases for the base instrument driver module
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
from mi.core.log import get_logger ; log = get_logger()
from pyon.util.containers import DotDict
from pyon.util.unit_test import IonUnitTestCase
from mi.core.unit_test import MiUnitTestCase

from mock import Mock

from mi.core.exceptions import TestModeException
from mi.core.exceptions import InstrumentParameterException
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_protocol import InstrumentProtocol

@attr('UNIT', group='mi')
class TestUnitInstrumentDriver(MiUnitTestCase):
    """
    Test cases for instrument driver class. Functions in this class provide
    instrument driver unit tests and provide a tutorial on use of
    the driver interface.
    """ 
    def setUp(self):
        self.mock = DotDict()
        self.mock.port_agent = Mock(name='port_agent_client')
        self.mock.callback = Mock(name='callback')

        def mock_set(values):
            assert isinstance(values, dict)
            return_string = ""
            for key in values.keys():
                return_string += "%s=%s" % (key, values[key]) # inefficient, I know
            return return_string
        
        self.driver = SingleConnectionInstrumentDriver(self.mock.callback)

        # set some values
        self.driver._protocol = InstrumentProtocol(self.mock.callback)
        self.driver.set_resource = mock_set

        self.driver._protocol._param_dict.add("foo", r'foo=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             startup_param=True,
                             default_value=10)
        self.driver._protocol._param_dict.set_default("foo")
        self.driver._protocol._param_dict.add("bar", r'bar=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=False,
                             startup_param=True,
                             default_value=15)
        self.driver._protocol._param_dict.set_default("bar")
        self.driver._protocol._param_dict.add("baz", r'baz=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             direct_access=True,
                             default_value=30)
        self.driver._protocol._param_dict.set_default("baz")
        self.driver._protocol._param_dict.add("bat", r'bat=(.*)',
                             lambda match : int(match.group(1)),
                             lambda x : str(x),
                             startup_param=False,
                             default_value=40)
        self.driver._protocol._param_dict.set_default("bat")
                
    def test_test_mode(self):
        """
        Test driver test mode.
        Ensure driver test mode attribute is set properly and verify
        exceptions are thrown when not in test mode.
        """

        # Ensure that we default to test mode off
        self.assertFalse(self.driver._test_mode)

        exception = False
        try:
            self.driver.set_test_mode(False)
            self.driver.test_force_state(state=1)

        except(TestModeException):
            exception = True

        except(Exception):
            # ignore other exceptions
            pass


        self.assertTrue(exception)

        # Now set test mode and try to run again.
        exception = False
        try:
            self.driver.set_test_mode(True)
            self.assertTrue(self.driver._test_mode)
            self.driver.test_force_state(state=1)
        except(TestModeException):
            exception = True

        except(Exception):
            # ignore other exceptions
            pass

        self.assertFalse(exception)

    def test_direct_access_params(self):
        """
        Tests to see how direct access parameters are setup and that they are
        working properly.
        """        
        self.assertTrue(self.driver._protocol._param_dict.get("foo"), 10)
        self.assertTrue(self.driver._protocol._param_dict.get("bar"), 15)
        # use real driver sets here, the direct poke of the param dict is just
        # a test-with-base-class thing
        self.driver._protocol._param_dict.update("bar=20")
        self.assertTrue(self.driver._protocol._param_dict.get("bar"), 20)
        
        # pretend to go into direct access mode,
        running_config = self.driver._protocol.get_cached_config()
        #   make some changes to both, (foo to 100, bar to 200)
        self.driver._protocol._param_dict.update("foo=100")
        self.driver._protocol._param_dict.update("bar=200")        
        # its like we came out of DA mode
        self.driver.restore_direct_access_params(running_config)

        # confirm that the default values were set back appropriately.
        self.assertTrue(self.driver._protocol._param_dict.get("foo"), 10)
        self.assertTrue(self.driver._protocol._param_dict.get("bar"), 200)
        
    def test_get_cached_config(self):
        """
        Verifies that the driver kicks out a cached config. Not connected, but
        thats what it is headed...
        """
        running_config = self.driver.get_cached_config()
        self.assertEquals(running_config["foo"], 10)
        self.assertEquals(running_config["bar"], 15)        
        
    def test_startup_params(self):
        """
        Tests to see that startup parameters are properly set when the
        startup logic goes through.
        """
        self.assertTrue(self.driver._protocol._param_dict.get("foo"), 10)
        self.assertTrue(self.driver._protocol._param_dict.get("bar"), 15)
        # make sure some value isnt the default value
        self.driver._protocol._param_dict.update("bar=20")
        self.assertTrue(self.driver._protocol._param_dict.get("bar"), 20)
        self.driver._protocol._param_dict.update("baz=30")
        self.assertTrue(self.driver._protocol._param_dict.get("baz"), 30)
        
        # pretend to manually adjust a few things:
        self.driver._protocol._param_dict.update("foo=1000")
        self.assertTrue(self.driver._protocol._param_dict.get("foo"), 1000)
        self.driver._protocol._param_dict.update("bar=1500")
        self.assertTrue(self.driver._protocol._param_dict.get("bar"), 1500)
        self.driver._protocol._param_dict.update("baz=2000")
        self.assertTrue(self.driver._protocol._param_dict.get("baz"), 2000)
        
        # pretend to go through the motions of a startup sequence
        self.driver.set_init_params({'foo':100, "bar": 150, "baz": 200})
        self.driver.apply_startup_params()

        # check the values on the other end
        running_config = self.driver._protocol.get_cached_config()
        
        # confirm that the default values were set back appropriately.
        self.assertTrue(self.driver._protocol._param_dict.get("foo"), 100)
        self.assertTrue(self.driver._protocol._param_dict.get("bar"), 150)
        self.assertTrue(self.driver._protocol._param_dict.get("baz"), 2000)
        self.assertTrue(self.driver._protocol._param_dict.get("bat"), 40)
        
        
    ##### Integration tests for startup config in the SBE37 integration suite
        
