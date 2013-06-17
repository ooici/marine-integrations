"""
@package mi.instrument.teledyne.test.test_driver
@file marine-integrations/mi/instrument/teledyne/test/test_driver.py
@author Roger Unwin
@brief Driver for the teledyne family
Release notes:
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'
import time

from gevent import monkey; monkey.patch_all()

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import InstrumentDriverPublicationTestCase
from mi.core.time import get_timestamp_delayed
from mi.core.exceptions import NotImplementedException

from mi.instrument.teledyne.driver import TeledyneProtocolState
from mi.instrument.teledyne.driver import TeledyneProtocolEvent
from mi.instrument.teledyne.driver import TeledyneParameter
from mi.instrument.teledyne.driver import TeledyneScheduledJob

DEFAULT_CLOCK_DIFF = 500
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
class TeledyneUnitTest(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class TeledyneIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

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

        log.debug("RESULT TIME = " + str(result_time))
        log.debug("TIME FORMAT = " + time_format)
        result_time_struct = time.strptime(result_time, time_format)
        log.debug("GOT HERE")
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



    ###
    #   Test scheduled events
    ###
    def assert_compass_calibration(self):
        """
        Verify a calibration particle was generated
        """
        raise NotImplementedException()

    def test_scheduled_compass_calibration_command(self):
        """
        Verify the device configuration command can be triggered and run in command
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=250)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_compass_calibration_autosample(self):
        """
        Verify the device configuration command can be triggered and run in autosample
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=250,
            autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        raise NotImplementedException()

    def test_scheduled_device_configuration_command(self):
        """
        Verify the device status command can be triggered and run in command
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CONFIGURATION, self.assert_acquire_status, delay=300)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_device_configuration_autosample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CONFIGURATION, self.assert_acquire_status,
                                    autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE, delay=300)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        time.sleep(5)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)

    def assert_clock_sync(self):
        """
        Verify the clock is set to at least the current date
        """
        dt = self.assert_get(TeledyneParameter.TIME)
        lt = time.strftime("%Y/%m/%d,%H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assertTrue(lt[:13].upper() in dt.upper())

    def test_scheduled_clock_sync_command(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_scheduled_event(TeledyneScheduledJob.CLOCK_SYNC, self.assert_clock_sync, delay=350)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_scheduled_event(TeledyneScheduledJob.CLOCK_SYNC, self.assert_clock_sync, 
                                    autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE, delay=350)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)



###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class TeledyneQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

###############################################################################
#                             PUBLICATION  TESTS                              #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class TeledynePublicationTest(InstrumentDriverPublicationTestCase):
    def setUp(self):
        InstrumentDriverPublicationTestCase.setUp(self)
