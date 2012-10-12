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

from mock import Mock

from mi.core.exceptions import TestModeException
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from pyon.util.unit_test import IonUnitTestCase

@attr('UNIT', group='mi')
class TestUnitInstrumentDriver(IonUnitTestCase):
    """
    Test cases for instrument driver class. Functions in this class provide
    instrument driver unit tests and provide a tutorial on use of
    the driver interface.
    """ 
    def setUp(self):
        self.mock = DotDict()
        self.mock.port_agent = Mock(name='port_agent_client')
        self.mock.callback = Mock(name='callback')

        self.driver = SingleConnectionInstrumentDriver(self.mock.callback)

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

