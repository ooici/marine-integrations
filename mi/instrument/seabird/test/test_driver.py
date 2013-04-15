"""
@package mi.instrument.seabird.sbe26plus.test.test_driver
@file marine-integrations/mi/instrument/seabird/sbe26plus/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import time

from gevent import monkey; monkey.patch_all()

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import InstrumentDriverPublicationTestCase

from mi.instrument.seabird.driver import SeaBirdProtocol
from mi.instrument.seabird.driver import SeaBirdParticle
from mi.core.exceptions import InstrumentParameterException
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.time import get_timestamp_delayed

DEFAULT_CLOCK_DIFF = 5
###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
# 1. Pick a single method within the class.                                   #
# 2. Create an instance of the class                                          #
# 3. If the method to be tested tries to call out, over-ride the offending    #
#    method with a mock                                                       #
# 4. Using above, try to cover all paths through the functions                #
# 5. Negative testing if at all possible.                                     #
###############################################################################
@attr('UNIT', group='mi')
class SeaBirdUnitTest(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_hex2value(self):
        """
        Verify the hex2value method works as expected.
        """
        value = SeaBirdParticle.hex2value("F")
        self.assertIsInstance(value, int)
        self.assertEqual(value, 15)

        value = SeaBirdParticle.hex2value("F", 2)
        self.assertIsInstance(value, float)
        self.assertEqual(value, 7.5)

        value = SeaBirdParticle.hex2value("0xF")
        self.assertIsInstance(value, int)
        self.assertEqual(value, 15)

        value = SeaBirdParticle.hex2value("0x1000")
        self.assertIsInstance(value, int)
        self.assertEqual(value, 4096)

        with self.assertRaises(InstrumentParameterException):
            SeaBirdParticle.hex2value("F", 0)

        with self.assertRaises(InstrumentParameterException):
            SeaBirdParticle.hex2value(1, 0)

    def test_sbetime2unixtime(self):
        """
        Verify the sbetime2unixtime method works as expected.
        """
        value = time.localtime(SeaBirdParticle.sbetime2unixtime(0))
        self.assertEqual("2000-01-01 00:00:00", time.strftime("%Y-%m-%d %H:%M:%S", value))

        value = time.localtime(SeaBirdParticle.sbetime2unixtime(5))
        self.assertEqual("2000-01-01 00:00:05", time.strftime("%Y-%m-%d %H:%M:%S", value))

        value = time.localtime(SeaBirdParticle.sbetime2unixtime(604800))
        self.assertEqual("2000-01-08 00:00:00", time.strftime("%Y-%m-%d %H:%M:%S", value))

        value = time.localtime(SeaBirdParticle.sbetime2unixtime(-1))
        self.assertEqual("1999-12-31 23:59:59", time.strftime("%Y-%m-%d %H:%M:%S", value))


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SeaBirdIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def assert_set_clock(self, time_param, time_override=None, time_format = "%d %b %Y %H:%M:%S", tolerance=DEFAULT_CLOCK_DIFF):
        """
        Verify that we can set the clock
        @param time_param: driver parameter
        @param time_override: use this time instead of current time.
        @param time_format: date time format
        @param tolerance: how close to the set time should the get be?
        """
        # Some seabirds tick the clock the instant you set it.  So you set
        # time 1, the get would be time 2.  Others do it correctly and wait
        # for a second before ticking. Hence the default tolerance of 1.
        if(time_override == None):
            set_time = get_timestamp_delayed(time_format)
        else:
            set_time = time.strftime(time_format, time.localtime(time_override))

        self.assert_set(time_param, set_time, no_get=True, startup=True)
        self.assertTrue(self._is_time_set(time_param, set_time, time_format, tolerance))

    def _is_time_set(self, time_param, expected_time, time_format = "%d %b %Y %H:%M:%S", tolerance=DEFAULT_CLOCK_DIFF):
        """
        Verify is what we expect it to be within a given tolerance
        @param time_param: driver parameter
        @param expected_time: what the time should be in seconds since unix epoch or formatted time string
        @param time_format: date time format
        @param tolerance: how close to the set time should the get be?
        """
        log.debug("Expected time unformatted: %s", expected_time)

        result_time = self.assert_get(time_param)
        result_time_struct = time.strptime(result_time, time_format)
        converted_time = time.mktime(result_time_struct)

        if(isinstance(expected_time, float)):
            expected_time_struct = time.localtime(expected_time)
        else:
            expected_time_struct = time.strptime(expected_time, time_format)

        log.debug("Current Time: %s, Expected Time: %s", time.strftime("%d %b %y %H:%M:%S", result_time_struct),
                  time.strftime("%d %b %y %H:%M:%S", expected_time_struct))

        log.debug("Current Time: %s, Expected Time: %s, Tolerance: %s",
                  converted_time, time.mktime(expected_time_struct), tolerance)

        # Verify the clock is set within the tolerance
        return abs(converted_time - time.mktime(expected_time_struct)) <= tolerance

    def assert_clock_set(self, time_param, sync_clock_cmd = DriverEvent.ACQUIRE_STATUS, timeout = 60, tolerance=DEFAULT_CLOCK_DIFF):
        """
        Verify the clock is set to at least the current date
        """
        log.debug("verify clock is set to the current time")

        timeout_time = time.time() + timeout

        while(not self._is_time_set(time_param, time.mktime(time.gmtime()), tolerance=tolerance)):
            log.debug("time isn't current. sleep for a bit")

            # Run acquire status command to set clock parameter
            self.assert_driver_command(sync_clock_cmd)

            log.debug("T: %s T: %s", time.time(), timeout_time)
            time.sleep(5)
            self.assertLess(time.time(), timeout_time, msg="Timeout waiting for clock sync event")

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class SeaBirdQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

###############################################################################
#                             PUBLICATION  TESTS                              #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class SeaBirdPublicationTest(InstrumentDriverPublicationTestCase):
    def setUp(self):
        InstrumentDriverPublicationTestCase.setUp(self)
