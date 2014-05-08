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
import datetime as dt
import unittest

from gevent import monkey; monkey.patch_all()

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr
from mi.core.common import BaseEnum
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
from mi.core.common import BaseEnum
DEFAULT_CLOCK_DIFF = 500

from mi.core.instrument.instrument_driver import ResourceAgentState

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

    _tested = {}

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
        log.debug("IN test_scheduled_compass_calibration_command")
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=100) #250
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_compass_calibration_autosample(self):
        """
        Verify the device configuration command can be triggered and run in autosample
        """
        log.debug("IN test_scheduled_compass_calibration_autosample")
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=100, # 250
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
        log.debug("IN test_scheduled_device_configuration_command")
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CONFIGURATION, self.assert_acquire_status, delay=120)
        self.assert_current_state(TeledyneProtocolState.COMMAND)


    def test_scheduled_device_configuration_autosample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
        log.debug("IN test_scheduled_device_configuration_autosample")
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CONFIGURATION, self.assert_acquire_status,
                                    autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE, delay=100)
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
        log.debug("IN test_scheduled_clock_sync_command")
        self.assert_scheduled_event(TeledyneScheduledJob.CLOCK_SYNC, self.assert_clock_sync, delay=350)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """

        log.debug("IN test_scheduled_clock_sync_autosample")
        self.assert_scheduled_event(TeledyneScheduledJob.CLOCK_SYNC, self.assert_clock_sync, 
                                    autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE, delay=350)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)

    def _test_set_instrument_id(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for INSTRUMENT_ID ======")

        # INSTRUMENT_ID -- Int 0-255
        self.assert_set(TeledyneParameter.INSTRUMENT_ID, 255)
        self.assert_set(TeledyneParameter.INSTRUMENT_ID, 1)
        self.assert_set_exception(TeledyneParameter.INSTRUMENT_ID, 256)
        self.assert_set_exception(TeledyneParameter.INSTRUMENT_ID, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.INSTRUMENT_ID, -1)
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.INSTRUMENT_ID, self._driver_parameter_defaults[TeledyneParameter.INSTRUMENT_ID])
        self.assert_set(TeledyneParameter.INSTRUMENT_ID, self._driver_parameters[TeledyneParameter.INSTRUMENT_ID][self.VALUE])
        self._tested[TeledyneParameter.INSTRUMENT_ID] = True

    def _test_set_xmit_power(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for XMIT_POWER ======")

        # XMIT_POWER:  -- Int 0-255
        self.assert_set(TeledyneParameter.XMIT_POWER, 0)
        self.assert_set(TeledyneParameter.XMIT_POWER, 128)
        self.assert_set(TeledyneParameter.XMIT_POWER, 254)

        self.assert_set_exception(TeledyneParameter.XMIT_POWER, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.XMIT_POWER, 256)
        self.assert_set_exception(TeledyneParameter.XMIT_POWER, -1)
        self.assert_set_exception(TeledyneParameter.XMIT_POWER, 3.1415926)
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.XMIT_POWER, self._driver_parameter_defaults[TeledyneParameter.XMIT_POWER])
        self.assert_set(TeledyneParameter.XMIT_POWER, self._driver_parameters[TeledyneParameter.XMIT_POWER][self.VALUE])
        self._tested[TeledyneParameter.XMIT_POWER] = True

    def _test_set_speed_of_sound(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SPEED_OF_SOUND ======")

        # SPEED_OF_SOUND:  -- Int 1485 (1400 - 1600)
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, 1400)
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, 1450)
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, 1500)
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, 1550)
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, 1600)

        self.assert_set_exception(TeledyneParameter.SPEED_OF_SOUND, 0)
        self.assert_set_exception(TeledyneParameter.SPEED_OF_SOUND, 1399)

        self.assert_set_exception(TeledyneParameter.SPEED_OF_SOUND, 1601)
        self.assert_set_exception(TeledyneParameter.SPEED_OF_SOUND, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.SPEED_OF_SOUND, -256)
        self.assert_set_exception(TeledyneParameter.SPEED_OF_SOUND, -1)
        self.assert_set_exception(TeledyneParameter.SPEED_OF_SOUND, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.SPEED_OF_SOUND, self._driver_parameter_defaults[TeledyneParameter.SPEED_OF_SOUND])
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, self._driver_parameters[TeledyneParameter.SPEED_OF_SOUND][self.VALUE])
        self._tested[TeledyneParameter.SPEED_OF_SOUND] = True

    def _test_set_salinity(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SALINITY ======")

        # SALINITY:  -- Int (0 - 40)
        self.assert_set(TeledyneParameter.SALINITY, 1)
        self.assert_set(TeledyneParameter.SALINITY, 10)
        self.assert_set(TeledyneParameter.SALINITY, 20)
        self.assert_set(TeledyneParameter.SALINITY, 30)
        self.assert_set(TeledyneParameter.SALINITY, 40)

        self.assert_set_exception(TeledyneParameter.SALINITY, "LEROY JENKINS")

        # AssertionError: Unexpected exception: ES no value match (40 != -1)
        self.assert_set_exception(TeledyneParameter.SALINITY, -1)

        # AssertionError: Unexpected exception: ES no value match (35 != 41)
        self.assert_set_exception(TeledyneParameter.SALINITY, 41)

        self.assert_set_exception(TeledyneParameter.SALINITY, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.SALINITY, self._driver_parameter_defaults[TeledyneParameter.SALINITY])
        self.assert_set(TeledyneParameter.SALINITY, self._driver_parameters[TeledyneParameter.SALINITY][self.VALUE])
        self._tested[TeledyneParameter.SALINITY] = True

    def _test_set_sensor_source(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SENSOR_SOURCE ======")

        # SENSOR_SOURCE:  -- (0/1) for 7 positions.
        # note it lacks capability to have a 1 in the #6 position
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "0000000")
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1111101")
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1010101")
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "0101000")
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1100100")

        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1111101")

        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, 2)
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, -1)
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, "1111112")
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, "11111112")
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.SENSOR_SOURCE, self._driver_parameter_defaults[TeledyneParameter.SENSOR_SOURCE])
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, self._driver_parameters[TeledyneParameter.SENSOR_SOURCE][self.VALUE])
        self._tested[TeledyneParameter.SENSOR_SOURCE] = True

    def _test_set_time_per_ensemble(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TIME_PER_ENSEMBLE ======")

        # TIME_PER_ENSEMBLE:  -- String 01:00:00.00 (hrs:min:sec.sec/100)
        self.assert_set(TeledyneParameter.TIME_PER_ENSEMBLE, "00:00:00.00")
        self.assert_set(TeledyneParameter.TIME_PER_ENSEMBLE, "00:00:01.00")
        self.assert_set(TeledyneParameter.TIME_PER_ENSEMBLE, "00:01:00.00")

        self.assert_set_exception(TeledyneParameter.TIME_PER_ENSEMBLE, '30:30:30.30')
        self.assert_set_exception(TeledyneParameter.TIME_PER_ENSEMBLE, '59:59:59.99')
        self.assert_set_exception(TeledyneParameter.TIME_PER_ENSEMBLE, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.TIME_PER_ENSEMBLE, 2)
        self.assert_set_exception(TeledyneParameter.TIME_PER_ENSEMBLE, -1)
        self.assert_set_exception(TeledyneParameter.TIME_PER_ENSEMBLE, '99:99:99.99')
        self.assert_set_exception(TeledyneParameter.TIME_PER_ENSEMBLE, '-1:-1:-1.+1')
        self.assert_set_exception(TeledyneParameter.TIME_PER_ENSEMBLE, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.TIME_PER_ENSEMBLE, self._driver_parameter_defaults[TeledyneParameter.TIME_PER_ENSEMBLE])
        self.assert_set(TeledyneParameter.TIME_PER_ENSEMBLE, self._driver_parameters[TeledyneParameter.TIME_PER_ENSEMBLE][self.VALUE])
        self._tested[TeledyneParameter.TIME_PER_ENSEMBLE] = True

    def _test_set_time_of_first_ping_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TIME_OF_FIRST_PING ====== READONLY")

        # Test read only raise exceptions on set.        # TIME_OF_FIRST_PING:  -- str ****/**/**,**:**:** (CCYY/MM/DD,hh:mm:ss)
        now_1_hour = (dt.datetime.utcnow() + dt.timedelta(hours=1)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_10 = (dt.datetime.utcnow() + dt.timedelta(days=10)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_1month = (dt.datetime.utcnow() + dt.timedelta(days=31)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_6month = (dt.datetime.utcnow() + dt.timedelta(days=183)).strftime("%Y/%m/%d,%H:%m:%S")

        self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, now_1_hour)
        self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, today_plus_10)
        self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, today_plus_1month)
        self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, today_plus_6month)
        self._tested[TeledyneParameter.TIME_OF_FIRST_PING] = True

    def _test_set_time_per_ping(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TIME_PER_PING ======")

        # TIME_PER_PING: '00:01.00'
        self.assert_set(TeledyneParameter.TIME_PER_PING, '01:00.00')
        self.assert_set(TeledyneParameter.TIME_PER_PING, '59:59.99')
        self.assert_set(TeledyneParameter.TIME_PER_PING, '30:30.30')

        self.assert_set_exception(TeledyneParameter.TIME_PER_PING, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.TIME_PER_PING, 2)
        self.assert_set_exception(TeledyneParameter.TIME_PER_PING, -1)
        self.assert_set_exception(TeledyneParameter.TIME_PER_PING, '99:99.99')
        self.assert_set_exception(TeledyneParameter.TIME_PER_PING, '-1:-1.+1')
        self.assert_set_exception(TeledyneParameter.TIME_PER_PING, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.TIME_PER_PING, self._driver_parameter_defaults[TeledyneParameter.TIME_PER_PING])
        self.assert_set(TeledyneParameter.TIME_PER_PING, self._driver_parameters[TeledyneParameter.TIME_PER_PING][self.VALUE])
        self._tested[TeledyneParameter.TIME_PER_PING] = True

    def _test_set_false_target_threshold(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for FALSE_TARGET_THRESHOLD ======")

        # FALSE_TARGET_THRESHOLD: string of 0-255,0-255
        self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, "000,000")
        self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, "255,000")
        self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, "000,255")
        self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, "255,255")

        self.assert_set_exception(TeledyneParameter.FALSE_TARGET_THRESHOLD, "256,000")
        self.assert_set_exception(TeledyneParameter.FALSE_TARGET_THRESHOLD, "256,255")
        self.assert_set_exception(TeledyneParameter.FALSE_TARGET_THRESHOLD, "000,256")
        self.assert_set_exception(TeledyneParameter.FALSE_TARGET_THRESHOLD, "255,256")
        self.assert_set_exception(TeledyneParameter.FALSE_TARGET_THRESHOLD, -1)

        self.assert_set_exception(TeledyneParameter.FALSE_TARGET_THRESHOLD, "LEROY JENKINS")

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, self._driver_parameter_defaults[TeledyneParameter.FALSE_TARGET_THRESHOLD])
        self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, self._driver_parameters[TeledyneParameter.FALSE_TARGET_THRESHOLD][self.VALUE])
        self._tested[TeledyneParameter.FALSE_TARGET_THRESHOLD] = True

    def _test_set_bandwidth_control(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BANDWIDTH_CONTROL ======")

        # BANDWIDTH_CONTROL: 0/1,
        self.assert_set(TeledyneParameter.BANDWIDTH_CONTROL, 1)

        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, -1)
        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, 2)
        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.BANDWIDTH_CONTROL, self._driver_parameter_defaults[TeledyneParameter.BANDWIDTH_CONTROL])
        self.assert_set(TeledyneParameter.BANDWIDTH_CONTROL, self._driver_parameters[TeledyneParameter.BANDWIDTH_CONTROL][self.VALUE])
        self._tested[TeledyneParameter.BANDWIDTH_CONTROL] = True

    def _test_set_correlation_threshold(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for CORRELATION_THRESHOLD ======")

        # CORRELATION_THRESHOLD: int 064, 0 - 255
        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, 50)
        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, 100)
        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, 150)
        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, 200)
        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, 255)

        self.assert_set_exception(TeledyneParameter.CORRELATION_THRESHOLD, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.CORRELATION_THRESHOLD, -256)
        self.assert_set_exception(TeledyneParameter.CORRELATION_THRESHOLD, -1)
        self.assert_set_exception(TeledyneParameter.CORRELATION_THRESHOLD, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, self._driver_parameter_defaults[TeledyneParameter.CORRELATION_THRESHOLD])
        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, self._driver_parameters[TeledyneParameter.CORRELATION_THRESHOLD][self.VALUE])
        self._tested[TeledyneParameter.CORRELATION_THRESHOLD] = True

    def _test_set_error_velocity_threshold(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for ERROR_VELOCITY_THRESHOLD ======")

        # ERROR_VELOCITY_THRESHOLD: int (0-5000 mm/s) NOTE it enforces 0-9999
        # decimals are truncated to ints
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 0)
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 128)
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 1000)
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 3000)
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 4000)
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 5000)

        self.assert_set_exception(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, -1)
        self.assert_set_exception(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 10000)
        self.assert_set_exception(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, -3.1415926)
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, self._driver_parameter_defaults[TeledyneParameter.ERROR_VELOCITY_THRESHOLD])
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, self._driver_parameters[TeledyneParameter.ERROR_VELOCITY_THRESHOLD][self.VALUE])
        self._tested[TeledyneParameter.ERROR_VELOCITY_THRESHOLD] = True

    def _test_set_blank_after_transmit(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BLANK_AFTER_TRANSMIT ======")

        # BLANK_AFTER_TRANSMIT: int 704, (0 - 9999)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 0)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 128)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 1000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 2000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 3000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 4000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 5000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 6000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 7000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 8000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 9000)
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 9999)

        self.assert_set_exception(TeledyneParameter.BLANK_AFTER_TRANSMIT, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.BLANK_AFTER_TRANSMIT, -1)
        self.assert_set_exception(TeledyneParameter.BLANK_AFTER_TRANSMIT, 10000)
        self.assert_set_exception(TeledyneParameter.BLANK_AFTER_TRANSMIT, -3.1415926)
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, self._driver_parameter_defaults[TeledyneParameter.BLANK_AFTER_TRANSMIT])
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, self._driver_parameters[TeledyneParameter.BLANK_AFTER_TRANSMIT][self.VALUE])
        self._tested[TeledyneParameter.BLANK_AFTER_TRANSMIT] = True

    def _test_set_clip_data_past_bottom(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for CLIP_DATA_PAST_BOTTOM ======")

        # CLIP_DATA_PAST_BOTTOM: True/False,
        self.assert_set(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, True)
        self.assert_set_exception(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, "LEROY JENKINS")

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, self._driver_parameter_defaults[TeledyneParameter.CLIP_DATA_PAST_BOTTOM])
        self.assert_set(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, self._driver_parameters[TeledyneParameter.CLIP_DATA_PAST_BOTTOM][self.VALUE])
        self._tested[TeledyneParameter.CLIP_DATA_PAST_BOTTOM] = True

    def _test_set_receiver_gain_select(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for RECEIVER_GAIN_SELECT ======")

        # RECEIVER_GAIN_SELECT: (0/1),
        self.assert_set(TeledyneParameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set(TeledyneParameter.RECEIVER_GAIN_SELECT, 1)

        self.assert_set_exception(TeledyneParameter.RECEIVER_GAIN_SELECT, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.RECEIVER_GAIN_SELECT, 2)
        self.assert_set_exception(TeledyneParameter.RECEIVER_GAIN_SELECT, -1)
        self.assert_set_exception(TeledyneParameter.RECEIVER_GAIN_SELECT, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.RECEIVER_GAIN_SELECT, self._driver_parameter_defaults[TeledyneParameter.RECEIVER_GAIN_SELECT])
        self.assert_set(TeledyneParameter.RECEIVER_GAIN_SELECT, self._driver_parameters[TeledyneParameter.RECEIVER_GAIN_SELECT][self.VALUE])
        self._tested[TeledyneParameter.RECEIVER_GAIN_SELECT] = True

    def _test_set_receiver_gain_select_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BLANK_AFTER_TRANSMIT ====== READONLY")

        # Test read only raise exceptions on set.
        self.assert_set_exception(TeledyneParameter.RECEIVER_GAIN_SELECT, 0)
        self._tested[TeledyneParameter.RECEIVER_GAIN_SELECT] = True

    def _test_set_number_of_depth_cells(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for NUMBER_OF_DEPTH_CELLS ======")

        # NUMBER_OF_DEPTH_CELLS:  -- int (1-255) 100,
        self.assert_set(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 1)
        self.assert_set(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 128)
        self.assert_set(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 254)

        self.assert_set_exception(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 256)
        self.assert_set_exception(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 0)
        self.assert_set_exception(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, -1)
        self.assert_set_exception(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 3.1415926)

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, self._driver_parameter_defaults[TeledyneParameter.NUMBER_OF_DEPTH_CELLS])
        self.assert_set(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, self._driver_parameters[TeledyneParameter.NUMBER_OF_DEPTH_CELLS][self.VALUE])
        self._tested[TeledyneParameter.NUMBER_OF_DEPTH_CELLS] = True

    def _test_set_pings_per_ensemble(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for PINGS_PER_ENSEMBLE ======")

        # PINGS_PER_ENSEMBLE: -- int  (0-16384) 1,
        self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, 16384)

        self.assert_set_exception(TeledyneParameter.PINGS_PER_ENSEMBLE, 16385)
        self.assert_set_exception(TeledyneParameter.PINGS_PER_ENSEMBLE, -1)
        self.assert_set_exception(TeledyneParameter.PINGS_PER_ENSEMBLE, 32767)
        self.assert_set_exception(TeledyneParameter.PINGS_PER_ENSEMBLE, 3.1415926)
        self.assert_set_exception(TeledyneParameter.PINGS_PER_ENSEMBLE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, self._driver_parameter_defaults[TeledyneParameter.PINGS_PER_ENSEMBLE])
        self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, self._driver_parameters[TeledyneParameter.PINGS_PER_ENSEMBLE][self.VALUE])
        self._tested[TeledyneParameter.PINGS_PER_ENSEMBLE] = True

    def _test_set_depth_cell_size(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for DEPTH_CELL_SIZE ======")

        # DEPTH_CELL_SIZE: int 80 - 3200
        self.assert_set(TeledyneParameter.DEPTH_CELL_SIZE, 80)
        self.assert_set(TeledyneParameter.DEPTH_CELL_SIZE, 3200)

        self.assert_set_exception(TeledyneParameter.DEPTH_CELL_SIZE, 3201)
        self.assert_set_exception(TeledyneParameter.DEPTH_CELL_SIZE, -1)
        self.assert_set_exception(TeledyneParameter.DEPTH_CELL_SIZE, 2)
        self.assert_set_exception(TeledyneParameter.DEPTH_CELL_SIZE, 3.1415926)
        self.assert_set_exception(TeledyneParameter.DEPTH_CELL_SIZE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.DEPTH_CELL_SIZE, self._driver_parameter_defaults[TeledyneParameter.DEPTH_CELL_SIZE])
        self.assert_set(TeledyneParameter.DEPTH_CELL_SIZE, self._driver_parameters[TeledyneParameter.DEPTH_CELL_SIZE][self.VALUE])
        self._tested[TeledyneParameter.DEPTH_CELL_SIZE] = True

    def _test_set_transmit_length(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TRANSMIT_LENGTH ======")

        # TRANSMIT_LENGTH: int 0 to 3200
        self.assert_set(TeledyneParameter.TRANSMIT_LENGTH, 80)
        self.assert_set(TeledyneParameter.TRANSMIT_LENGTH, 3200)

        self.assert_set_exception(TeledyneParameter.TRANSMIT_LENGTH, 3201)
        self.assert_set_exception(TeledyneParameter.TRANSMIT_LENGTH, -1)
        self.assert_set_exception(TeledyneParameter.TRANSMIT_LENGTH, 3.1415926)
        self.assert_set_exception(TeledyneParameter.TRANSMIT_LENGTH, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.TRANSMIT_LENGTH, self._driver_parameter_defaults[TeledyneParameter.TRANSMIT_LENGTH])
        self.assert_set(TeledyneParameter.TRANSMIT_LENGTH, self._driver_parameters[TeledyneParameter.TRANSMIT_LENGTH][self.VALUE])
        self._tested[TeledyneParameter.TRANSMIT_LENGTH] = True

    def _test_set_ping_weight(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for PING_WEIGHT ======")

        # PING_WEIGHT: (0/1),
        self.assert_set(TeledyneParameter.PING_WEIGHT, 0)
        self.assert_set(TeledyneParameter.PING_WEIGHT, 1)

        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, 2)
        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, -1)
        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, 3.1415926)
        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.PING_WEIGHT, self._driver_parameter_defaults[TeledyneParameter.PING_WEIGHT])
        self.assert_set(TeledyneParameter.PING_WEIGHT, self._driver_parameters[TeledyneParameter.PING_WEIGHT][self.VALUE])
        self._tested[TeledyneParameter.PING_WEIGHT] = True

    def _test_set_ambiguity_velocity(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for AMBIGUITY_VELOCITY ======")

        # AMBIGUITY_VELOCITY: int 2 - 700
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 2)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 111)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 222)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 333)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 444)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 555)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 666)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 700)

        self.assert_set_exception(TeledyneParameter.AMBIGUITY_VELOCITY, 0)
        self.assert_set_exception(TeledyneParameter.AMBIGUITY_VELOCITY, 1)
        self.assert_set_exception(TeledyneParameter.AMBIGUITY_VELOCITY, -1)
        self.assert_set_exception(TeledyneParameter.AMBIGUITY_VELOCITY, 3.1415926)
        self.assert_set_exception(TeledyneParameter.AMBIGUITY_VELOCITY, "LEROY JENKINS")

        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, self._driver_parameter_defaults[TeledyneParameter.AMBIGUITY_VELOCITY])
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, self._driver_parameters[TeledyneParameter.AMBIGUITY_VELOCITY][self.VALUE])
        self._tested[TeledyneParameter.AMBIGUITY_VELOCITY] = True

    def _test_set_blank_after_transmit_readonly(self):
            ###
            #   test get set of a variety of parameter ranges
            ###
            log.debug("====== Testing ranges for BLANK_AFTER_TRANSMIT ====== READONLY")

            # Test read only raise exceptions on set.
            self.assert_set_exception(TeledyneParameter.BLANK_AFTER_TRANSMIT, 0)
            self._tested[TeledyneParameter.BLANK_AFTER_TRANSMIT] = True

    def _test_set_bandwidth_control_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BANDWIDTH_CONTROL ====== READONLY")

        # Test read only raise exceptions on set.
        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, 0)
        self._tested[TeledyneParameter.BANDWIDTH_CONTROL] = True

    def _test_set_serial_data_out_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SERIAL_DATA_OUT ======")

        # Test read only raise exceptions on set.
        self.assert_set(TeledyneParameter.SERIAL_DATA_OUT, '000 000 111')
        self._tested[TeledyneParameter.SERIAL_DATA_OUT] = True

    def _test_set_serial_out_fw_switches_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SERIAL_OUT_FW_SWITCHES ======")

        # Test read only raise exceptions on set.
        #self.assert_set_exception(TeledyneParameter.SERIAL_OUT_FW_SWITCHES, '110100100')
        self._tested[TeledyneParameter.SERIAL_OUT_FW_SWITCHES] = True

    def _test_set_water_profiling_mode_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for WATER_PROFILING_MODE ======")

        # Test read only raise exceptions on set.

        self.assert_set_exception(TeledyneParameter.WATER_PROFILING_MODE, 0)
        self._tested[TeledyneParameter.WATER_PROFILING_MODE] = True

    def _test_set_parameter_test(self):
        self.assert_set(TeledyneParameter.HEADING_ALIGNMENT, "+10000")
        self.assert_set_exception(TeledyneParameter.HEADING_ALIGNMENT, "+40000")
        self._tested[TeledyneParameter.HEADING_ALIGNMENT] = True

        self.assert_set(TeledyneParameter.ENSEMBLE_PER_BURST, 600)
        self.assert_set_exception(TeledyneParameter.ENSEMBLE_PER_BURST, 70000)
        self._tested[TeledyneParameter.ENSEMBLE_PER_BURST] = True

        self.assert_set(TeledyneParameter.LATENCY_TRIGGER, 1)
        self._tested[TeledyneParameter.LATENCY_TRIGGER] = True

        self.assert_set(TeledyneParameter.DATA_STREAM_SELECTION, 10)
        self.assert_set_exception(TeledyneParameter.DATA_STREAM_SELECTION, 19)
        self._tested[TeledyneParameter.DATA_STREAM_SELECTION] = True

        self.assert_set(TeledyneParameter.BUFFERED_OUTPUT_PERIOD, "00:00:11")
        self._tested[TeledyneParameter.BUFFERED_OUTPUT_PERIOD] = True

        self.assert_set(TeledyneParameter.TRANSDUCER_DEPTH, 60000)
        self.assert_set_exception(TeledyneParameter.TRANSDUCER_DEPTH, 70000)
        self._tested[TeledyneParameter.TRANSDUCER_DEPTH] = True

        self.assert_set(TeledyneParameter.SAMPLE_AMBIENT_SOUND, 1)
        self._tested[TeledyneParameter.SAMPLE_AMBIENT_SOUND] = True


    def _test_set_coordinate_transformation(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for COORDINATE_TRANSFORMATION ======")

        # COORDINATE_TRANSFORMATION:  -- (5 bits 0 or 1)
        self.assert_set(TeledyneParameter.COORDINATE_TRANSFORMATION, '11000')
        self.assert_set(TeledyneParameter.COORDINATE_TRANSFORMATION, '11111')
        self.assert_set(TeledyneParameter.COORDINATE_TRANSFORMATION, '11101')

        self.assert_set(TeledyneParameter.COORDINATE_TRANSFORMATION, '00000')
        self.assert_set(TeledyneParameter.COORDINATE_TRANSFORMATION, '00111')
        self.assert_set(TeledyneParameter.COORDINATE_TRANSFORMATION, '00101')

        self.assert_set_exception(TeledyneParameter.COORDINATE_TRANSFORMATION, -1)
        self.assert_set_exception(TeledyneParameter.COORDINATE_TRANSFORMATION, 3)
        self.assert_set_exception(TeledyneParameter.COORDINATE_TRANSFORMATION, 3.1415926)
        self.assert_set_exception(TeledyneParameter.COORDINATE_TRANSFORMATION, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(WorkhorseParameter.COORDINATE_TRANSFORMATION, self._driver_parameter_defaults[WorkhorseParameter.COORDINATE_TRANSFORMATION])
        self.assert_set(TeledyneParameter.COORDINATE_TRANSFORMATION, self._driver_parameters[TeledyneParameter.COORDINATE_TRANSFORMATION][self.VALUE])
        self._tested[TeledyneParameter.COORDINATE_TRANSFORMATION] = True


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class TeledyneQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_disconnect(self):
        """
        Verify that a disconnection from the DA server transitions the agent back to
        command mode.
        """
        self.assert_enter_command_mode()

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.disconnect()

        self.assert_state_change(ResourceAgentState.COMMAND, TeledyneProtocolState.COMMAND, 30)

    def test_direct_access_telnet_timeout(self):
        """
        Verify that DA timesout as expected and transistions back to command mode.
        """
        self.assert_enter_command_mode()

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=30)
        self.assertTrue(self.tcp_client)

        self.assert_state_change(ResourceAgentState.COMMAND, TeledyneProtocolState.COMMAND, 90)


###############################################################################
#                             PUBLICATION  TESTS                              #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class TeledynePublicationTest(InstrumentDriverPublicationTestCase):
    def setUp(self):
        InstrumentDriverPublicationTestCase.setUp(self)
