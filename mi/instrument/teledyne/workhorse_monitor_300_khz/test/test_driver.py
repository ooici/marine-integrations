"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.rsn.test.test_driver
@author Roger Unwin
@brief Test cases for rsn driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import socket

import unittest
import time as time
import datetime as dt
from mi.core.time import get_timestamp_delayed

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.log import get_logger; log = get_logger()

# MI imports.
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey

from mi.instrument.teledyne.test.test_driver import TeledyneUnitTest
from mi.instrument.teledyne.test.test_driver import TeledyneIntegrationTest
from mi.instrument.teledyne.test.test_driver import TeledyneQualificationTest
from mi.instrument.teledyne.test.test_driver import TeledynePublicationTest

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorseInstrumentDriver

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorseProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorseParameter

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorseScheduledJob
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import WorkhorsePrompt
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import NEWLINE

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle

#from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import SAMPLE_RAW_DATA 
#from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import CALIBRATION_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import PS0_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import PS3_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import FD_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import PT200_RAW_DATA

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException
from pyon.core.exception import Conflict
from pyon.agent.agent import ResourceAgentEvent

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import ResourceAgentState
from random import randint

from mi.idk.unit_test import AGENT_DISCOVER_TIMEOUT
from mi.idk.unit_test import GO_ACTIVE_TIMEOUT
from mi.idk.unit_test import GET_TIMEOUT
from mi.idk.unit_test import SET_TIMEOUT
from mi.idk.unit_test import EXECUTE_TIMEOUT

from mi.instrument.teledyne.driver import TeledyneParameter as Parameter
from mi.instrument.teledyne.driver import TeledyneProtocolEvent as ProtocolEvent
from mi.instrument.teledyne.driver import TeledyneProtocolState as ProtocolState
from mi.instrument.teledyne.driver import TeledyneScheduledJob as ScheduledJob
from mi.instrument.teledyne.driver import TeledynePrompt as Prompt

#AGENT_DISCOVER_TIMEOUT=3600
#GO_ACTIVE_TIMEOUT=3600 # i have a slow instrument
#GET_TIMEOUT=3000
#SET_TIMEOUT=9000
#EXECUTE_TIMEOUT=3000

#tolerance = 500

# Globals
#raw_stream_received = False
#parsed_stream_received = False






#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
############

###############################################################################
#                                UNIT TESTS                                   #
###############################################################################
@attr('UNIT', group='mi')
class WorkhorseDriverUnitTest(TeledyneUnitTest):
    def setUp(self):
        TeledyneUnitTest.setUp(self)


###############################################################################
#                            INTEGRATION TESTS                                #
###############################################################################
@attr('INT', group='mi')
class WorkhorseDriverIntegrationTest(TeledyneIntegrationTest):
    # test if this can pre-set, and be overridden by mixin
    # TODO: does this work
    #

    _tested = {}

    _driver_parameter_defaults = {
        #Parameter.SERIAL_DATA_OUT: None,
        Parameter.INSTRUMENT_ID: 0,
        Parameter.XMIT_POWER: 255,
        Parameter.SPEED_OF_SOUND: 1500,
        Parameter.SALINITY: 35,
        Parameter.COORDINATE_TRANSFORMATION: '11111',
        Parameter.SENSOR_SOURCE: "1111101",
        Parameter.TIME_PER_ENSEMBLE: '00:00:00.00',
        Parameter.TIME_OF_FIRST_PING: None,
        Parameter.TIME_PER_PING: '00:01.00',
        #Parameter.TIME: False,
        Parameter.FALSE_TARGET_THRESHOLD: '050,001',
        Parameter.BANDWIDTH_CONTROL: 0,
        Parameter.CORRELATION_THRESHOLD: 64,
        Parameter.SERIAL_OUT_FW_SWITCHES: '111100000',
        Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
        Parameter.BLANK_AFTER_TRANSMIT: 704,
        Parameter.CLIP_DATA_PAST_BOTTOM: 0,
        Parameter.RECEIVER_GAIN_SELECT: 1,
        Parameter.WATER_REFERENCE_LAYER: '001,005',
        Parameter.WATER_PROFILING_MODE: 1,
        Parameter.NUMBER_OF_DEPTH_CELLS: 100,
        Parameter.PINGS_PER_ENSEMBLE: 1,
        Parameter.DEPTH_CELL_SIZE: 800,
        Parameter.TRANSMIT_LENGTH: 0,
        Parameter.PING_WEIGHT: 0,
        Parameter.AMBIGUITY_VELOCITY: 175,
    }

    def setUp(self):
        TeledyneIntegrationTest.setUp(self)

    def assert_compass_calibration(self):
        """
        Verify a calibration particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_COMPASS_CALIBRATION, self.assert_particle_compass_calibration, timeout=700)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_SYSTEM_CONFIGURATION, self.assert_particle_system_configuration, timeout=300)

    ###
    #    Add instrument specific integration tests
    ###
    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

    def _test_set_instrument_id(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for INSTRUMENT_ID ======")

        # INSTRUMENT_ID -- Int 0-255
        self.assert_set(Parameter.INSTRUMENT_ID, 255)
        self.assert_set(Parameter.INSTRUMENT_ID, 1)
        self.assert_set_exception(Parameter.INSTRUMENT_ID, 256)
        self.assert_set_exception(Parameter.INSTRUMENT_ID, "LEROY JENKINS")
        self.assert_set_exception(Parameter.INSTRUMENT_ID, -1)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.INSTRUMENT_ID, self._driver_parameter_defaults[Parameter.INSTRUMENT_ID])
        self._tested[Parameter.INSTRUMENT_ID] = True

    def _test_set_sleep_enable(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SLEEP_ENABLE ======")

        # SLEEP_ENABLE:  -- (0,1,2)
        self.assert_set(Parameter.SLEEP_ENABLE, 1)
        self.assert_set(Parameter.SLEEP_ENABLE, 2)

        self.assert_set_exception(Parameter.SLEEP_ENABLE, -1)
        self.assert_set_exception(Parameter.SLEEP_ENABLE, 3)
        self.assert_set_exception(Parameter.SLEEP_ENABLE, 3.1415926)
        self.assert_set_exception(Parameter.SLEEP_ENABLE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SLEEP_ENABLE, self._driver_parameter_defaults[Parameter.SLEEP_ENABLE])
        self._tested[Parameter.SLEEP_ENABLE] = True

    def _test_set_polled_mode(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for POLLED_MODE ======")
 
        # POLLED_MODE:  -- (True/False)
        self.assert_set(Parameter.POLLED_MODE, True)
        self.assert_set_exception(Parameter.POLLED_MODE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.POLLED_MODE, self._driver_parameter_defaults[Parameter.POLLED_MODE])
        self._tested[Parameter.POLLED_MODE] = True

    def _test_set_xmit_power(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for XMIT_POWER ======")

        # XMIT_POWER:  -- Int 0-255
        self.assert_set(Parameter.XMIT_POWER, 0)
        self.assert_set(Parameter.XMIT_POWER, 128)
        self.assert_set(Parameter.XMIT_POWER, 254)

        self.assert_set_exception(Parameter.XMIT_POWER, "LEROY JENKINS")
        self.assert_set_exception(Parameter.XMIT_POWER, 256)
        self.assert_set_exception(Parameter.XMIT_POWER, -1)
        self.assert_set_exception(Parameter.XMIT_POWER, 3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.XMIT_POWER, self._driver_parameter_defaults[Parameter.XMIT_POWER])
        self._tested[Parameter.XMIT_POWER] = True

    def _test_set_speed_of_sound(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SPEED_OF_SOUND ======")

        # SPEED_OF_SOUND:  -- Int 1485 (1400 - 1600)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1400)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1450)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1500)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1550)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1600)

        self.assert_set_exception(Parameter.SPEED_OF_SOUND, 0)
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, 1399)

        self.assert_set_exception(Parameter.SPEED_OF_SOUND, 1601)
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, "LEROY JENKINS")
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, -256)
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, -1)
        self.assert_set_exception(Parameter.SPEED_OF_SOUND, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SPEED_OF_SOUND, self._driver_parameter_defaults[Parameter.SPEED_OF_SOUND])
        self._tested[Parameter.SPEED_OF_SOUND] = True

    def _test_set_pitch(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for PITCH ======")

        # PITCH:  -- Int -6000 to 6000
        self.assert_set(Parameter.PITCH, -6000)
        self.assert_set(Parameter.PITCH, -4000)
        self.assert_set(Parameter.PITCH, -2000)
        self.assert_set(Parameter.PITCH, -1)
        self.assert_set(Parameter.PITCH, 0)
        self.assert_set(Parameter.PITCH, 1)
        self.assert_set(Parameter.PITCH, 2000)
        self.assert_set(Parameter.PITCH, 4000)
        self.assert_set(Parameter.PITCH, 6000)

        self.assert_set_exception(Parameter.PITCH, "LEROY JENKINS")
        self.assert_set_exception(Parameter.PITCH, -6001)
        self.assert_set_exception(Parameter.PITCH, 6001)
        self.assert_set_exception(Parameter.PITCH, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.PITCH, self._driver_parameter_defaults[Parameter.PITCH])
        self._tested[Parameter.PITCH] = True

    def _test_set_roll(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for ROLL ======")

        # ROLL:  -- Int -6000 to 6000
        self.assert_set(Parameter.ROLL, -6000)
        self.assert_set(Parameter.ROLL, -4000)
        self.assert_set(Parameter.ROLL, -2000)
        self.assert_set(Parameter.ROLL, -1)
        self.assert_set(Parameter.ROLL, 0)
        self.assert_set(Parameter.ROLL, 1)
        self.assert_set(Parameter.ROLL, 2000)
        self.assert_set(Parameter.ROLL, 4000)
        self.assert_set(Parameter.ROLL, 6000)

        self.assert_set_exception(Parameter.ROLL, "LEROY JENKINS")
        self.assert_set_exception(Parameter.ROLL, -6001)
        self.assert_set_exception(Parameter.ROLL, 6001)
        self.assert_set_exception(Parameter.ROLL, 3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.ROLL, self._driver_parameter_defaults[Parameter.ROLL])
        self._tested[Parameter.ROLL] = True

    def _test_set_salinity(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SALINITY ======")

        # SALINITY:  -- Int (0 - 40)
        self.assert_set(Parameter.SALINITY, 0)
        self.assert_set(Parameter.SALINITY, 10)
        self.assert_set(Parameter.SALINITY, 20)
        self.assert_set(Parameter.SALINITY, 30)
        self.assert_set(Parameter.SALINITY, 40)

        self.assert_set_exception(Parameter.SALINITY, "LEROY JENKINS")

        # AssertionError: Unexpected exception: ES no value match (40 != -1)
        self.assert_set_exception(Parameter.SALINITY, -1)

        # AssertionError: Unexpected exception: ES no value match (35 != 41)
        self.assert_set_exception(Parameter.SALINITY, 41)

        self.assert_set_exception(Parameter.SALINITY, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SALINITY, self._driver_parameter_defaults[Parameter.SALINITY])
        self._tested[Parameter.SALINITY] = True

    def _test_set_sensor_source(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SENSOR_SOURCE ======")

        # SENSOR_SOURCE:  -- (0/1) for 7 positions.
        # note it lacks capability to have a 1 in the #6 position
        self.assert_set(Parameter.SENSOR_SOURCE, "0000000")
        self.assert_set(Parameter.SENSOR_SOURCE, "1111101")
        self.assert_set(Parameter.SENSOR_SOURCE, "1010101")
        self.assert_set(Parameter.SENSOR_SOURCE, "0101000")
        self.assert_set(Parameter.SENSOR_SOURCE, "1100100")

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SENSOR_SOURCE, "1111101")

        self.assert_set_exception(Parameter.SENSOR_SOURCE, "LEROY JENKINS")
        self.assert_set_exception(Parameter.SENSOR_SOURCE, 2)
        self.assert_set_exception(Parameter.SENSOR_SOURCE, -1)
        self.assert_set_exception(Parameter.SENSOR_SOURCE, "1111112")
        self.assert_set_exception(Parameter.SENSOR_SOURCE, "11111112")
        self.assert_set_exception(Parameter.SENSOR_SOURCE, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.SENSOR_SOURCE, self._driver_parameter_defaults[Parameter.SENSOR_SOURCE])
        self._tested[Parameter.SENSOR_SOURCE] = True

    def _test_set_time_per_ensemble(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TIME_PER_ENSEMBLE ======")

        # TIME_PER_ENSEMBLE:  -- String 01:00:00.00 (hrs:min:sec.sec/100)
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, "00:00:00.00")
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, "00:00:01.00")
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, "00:01:00.00")

        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, '30:30:30.30')
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, '59:59:59.99')
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, "LEROY JENKINS")
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, 2)
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, -1)
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, '99:99:99.99')
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, '-1:-1:-1.+1')
        self.assert_set_exception(Parameter.TIME_PER_ENSEMBLE, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, self._driver_parameter_defaults[Parameter.TIME_PER_ENSEMBLE])
        self._tested[Parameter.TIME_PER_ENSEMBLE] = True

    def _test_set_time_of_first_ping(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TIME_OF_FIRST_PING ======")

        # TIME_OF_FIRST_PING:  -- str ****/**/**,**:**:** (CCYY/MM/DD,hh:mm:ss)
        now_1_hour = (dt.datetime.utcnow() + dt.timedelta(hours=1)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_10 = (dt.datetime.utcnow() + dt.timedelta(days=10)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_1month = (dt.datetime.utcnow() + dt.timedelta(days=31)).strftime("%Y/%m/%d,%H:%m:%S")
        today_plus_6month = (dt.datetime.utcnow() + dt.timedelta(days=183)).strftime("%Y/%m/%d,%H:%m:%S")

        self.assert_set(Parameter.TIME_OF_FIRST_PING, now_1_hour)
        self.assert_set(Parameter.TIME_OF_FIRST_PING, today_plus_10)
        self.assert_set(Parameter.TIME_OF_FIRST_PING, today_plus_1month)
        self.assert_set(Parameter.TIME_OF_FIRST_PING, today_plus_6month)

        # AssertionError: Unexpected exception: TG no value match (2013/06/06,06:06:06 != LEROY JENKINS)
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, "LEROY JENKINS")

        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, 2)
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, -1)
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, '99:99.99')
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, '-1:-1.+1')
        self.assert_set_exception(Parameter.TIME_OF_FIRST_PING, 3.1415926)
        #
        # Reset to good value.
        #
        # Ideally send a break to reset it...
        self._tested[Parameter.TIME_OF_FIRST_PING] = True

    def _test_set_time_per_ping(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TIME_PER_PING ======")

        # TIME_PER_PING: '00:01.00'
        self.assert_set(Parameter.TIME_PER_PING, '01:00.00')
        self.assert_set(Parameter.TIME_PER_PING, '59:59.99')
        self.assert_set(Parameter.TIME_PER_PING, '30:30.30')

        self.assert_set_exception(Parameter.TIME_PER_PING, "LEROY JENKINS")
        self.assert_set_exception(Parameter.TIME_PER_PING, 2)
        self.assert_set_exception(Parameter.TIME_PER_PING, -1)
        self.assert_set_exception(Parameter.TIME_PER_PING, '99:99.99')
        self.assert_set_exception(Parameter.TIME_PER_PING, '-1:-1.+1')
        self.assert_set_exception(Parameter.TIME_PER_PING, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.TIME_PER_PING, self._driver_parameter_defaults[Parameter.TIME_PER_PING])
        self._tested[Parameter.TIME_PER_PING] = True

    def _test_set_false_target_threshold(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for FALSE_TARGET_THRESHOLD ======")

        # FALSE_TARGET_THRESHOLD: string of 0-255,0-255
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "000,000")
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "255,000")
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "000,255")
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, "255,255")

        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "256,000")
        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "256,255")
        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "000,256")
        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "255,256")
        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, -1)

        self.assert_set_exception(Parameter.FALSE_TARGET_THRESHOLD, "LEROY JENKINS")

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, self._driver_parameter_defaults[Parameter.FALSE_TARGET_THRESHOLD])
        self._tested[Parameter.FALSE_TARGET_THRESHOLD] = True

    def _test_set_bandwidth_control(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BANDWIDTH_CONTROL ======")

        # BANDWIDTH_CONTROL: 0/1,
        self.assert_set(Parameter.BANDWIDTH_CONTROL, 1)

        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, -1)
        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, 2)
        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, "LEROY JENKINS")
        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.BANDWIDTH_CONTROL, self._driver_parameter_defaults[Parameter.BANDWIDTH_CONTROL])
        self._tested[Parameter.BANDWIDTH_CONTROL] = True

    def _test_set_bandwidth_control_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BANDWIDTH_CONTROL ====== READONLY")

        # Test read only raise exceptions on set.
        self.assert_set_exception(Parameter.BANDWIDTH_CONTROL, 0)
        self._tested[Parameter.BANDWIDTH_CONTROL] = True

    def _test_set_correlation_threshold(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for CORRELATION_THRESHOLD ======")

        # CORRELATION_THRESHOLD: int 064, 0 - 255
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 50)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 100)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 150)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 200)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 255)

        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, "LEROY JENKINS")
        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, -256)
        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, -1)
        self.assert_set_exception(Parameter.CORRELATION_THRESHOLD, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.CORRELATION_THRESHOLD, self._driver_parameter_defaults[Parameter.CORRELATION_THRESHOLD])
        self._tested[Parameter.CORRELATION_THRESHOLD] = True

    def _test_set_error_velocity_threshold(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for ERROR_VELOCITY_THRESHOLD ======")

        # ERROR_VELOCITY_THRESHOLD: int (0-5000 mm/s) NOTE it enforces 0-9999
        # decimals are truncated to ints
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 0)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 128)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 1000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 3000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 4000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 5000)

        self.assert_set_exception(Parameter.ERROR_VELOCITY_THRESHOLD, "LEROY JENKINS")
        self.assert_set_exception(Parameter.ERROR_VELOCITY_THRESHOLD, -1)
        self.assert_set_exception(Parameter.ERROR_VELOCITY_THRESHOLD, 10000)
        self.assert_set_exception(Parameter.ERROR_VELOCITY_THRESHOLD, -3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, self._driver_parameter_defaults[Parameter.ERROR_VELOCITY_THRESHOLD])
        self._tested[Parameter.ERROR_VELOCITY_THRESHOLD] = True

    def _test_set_blank_after_transmit(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BLANK_AFTER_TRANSMIT ======")

        # BLANK_AFTER_TRANSMIT: int 704, (0 - 9999)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 0)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 128)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 1000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 2000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 3000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 4000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 5000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 6000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 7000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 8000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 9000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 9999)

        self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, "LEROY JENKINS")
        self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, -1)
        self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, 10000)
        self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, -3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, self._driver_parameter_defaults[Parameter.BLANK_AFTER_TRANSMIT])
        self._tested[Parameter.BLANK_AFTER_TRANSMIT] = True

    def _test_set_blank_after_transmit_readonly(self):
            ###
            #   test get set of a variety of parameter ranges
            ###
            log.debug("====== Testing ranges for BLANK_AFTER_TRANSMIT ====== READONLY")

            # Test read only raise exceptions on set.
            self.assert_set_exception(Parameter.BLANK_AFTER_TRANSMIT, 0)
            self._tested[Parameter.BLANK_AFTER_TRANSMIT] = True

    def _test_set_clip_data_past_bottom(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for CLIP_DATA_PAST_BOTTOM ======")

        # CLIP_DATA_PAST_BOTTOM: True/False,
        self.assert_set(Parameter.CLIP_DATA_PAST_BOTTOM, True)
        self.assert_set_exception(Parameter.CLIP_DATA_PAST_BOTTOM, "LEROY JENKINS")

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.CLIP_DATA_PAST_BOTTOM, self._driver_parameter_defaults[Parameter.CLIP_DATA_PAST_BOTTOM])
        self._tested[Parameter.CLIP_DATA_PAST_BOTTOM] = True

    def _test_set_receiver_gain_select(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for RECEIVER_GAIN_SELECT ======")

        # RECEIVER_GAIN_SELECT: (0/1),
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, 1)

        self.assert_set_exception(Parameter.RECEIVER_GAIN_SELECT, "LEROY JENKINS")
        self.assert_set_exception(Parameter.RECEIVER_GAIN_SELECT, 2)
        self.assert_set_exception(Parameter.RECEIVER_GAIN_SELECT, -1)
        self.assert_set_exception(Parameter.RECEIVER_GAIN_SELECT, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, self._driver_parameter_defaults[Parameter.RECEIVER_GAIN_SELECT])
        self._tested[Parameter.RECEIVER_GAIN_SELECT] = True

    def _test_set_water_reference_layer(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for WATER_REFERENCE_LAYER ======")

        # WATER_REFERENCE_LAYER:  -- int Begin Cell (0=OFF), End Cell  (0-100)
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, "000,001")
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, "000,100")
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, "000,100")

        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "255,000")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "000,000")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "001,000")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "100,000")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "000,101")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "100,101")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, -1)
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, 2)
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, "LEROY JENKINS")
        self.assert_set_exception(Parameter.WATER_REFERENCE_LAYER, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, self._driver_parameter_defaults[Parameter.WATER_REFERENCE_LAYER])
        self._tested[Parameter.WATER_REFERENCE_LAYER] = True

    def _test_set_number_of_depth_cells(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for NUMBER_OF_DEPTH_CELLS ======")

        # NUMBER_OF_DEPTH_CELLS:  -- int (1-255) 100,
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 1)
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 128)
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 254)

        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, "LEROY JENKINS")
        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, 256)
        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, 0)
        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, -1)
        self.assert_set_exception(Parameter.NUMBER_OF_DEPTH_CELLS, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, self._driver_parameter_defaults[Parameter.NUMBER_OF_DEPTH_CELLS])
        self._tested[Parameter.NUMBER_OF_DEPTH_CELLS] = True

    def _test_set_pings_per_ensemble(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for PINGS_PER_ENSEMBLE ======")

        # PINGS_PER_ENSEMBLE: -- int  (0-16384) 1,
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 16384)

        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, 16385)
        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, -1)
        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, 32767)
        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, 3.1415926)
        self.assert_set_exception(Parameter.PINGS_PER_ENSEMBLE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, self._driver_parameter_defaults[Parameter.PINGS_PER_ENSEMBLE])
        self._tested[Parameter.PINGS_PER_ENSEMBLE] = True

    def _test_set_depth_cell_size(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for DEPTH_CELL_SIZE ======")

        # DEPTH_CELL_SIZE: int 80 - 3200
        self.assert_set(Parameter.DEPTH_CELL_SIZE, 80)
        self.assert_set(Parameter.DEPTH_CELL_SIZE, 3200)

        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, 3201)
        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, -1)
        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, 2)
        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, 3.1415926)
        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.DEPTH_CELL_SIZE, self._driver_parameter_defaults[Parameter.DEPTH_CELL_SIZE])
        self._tested[Parameter.DEPTH_CELL_SIZE] = True

    def _test_set_transmit_length(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TRANSMIT_LENGTH ======")

        # TRANSMIT_LENGTH: int 0 to 3200
        self.assert_set(Parameter.TRANSMIT_LENGTH, 80)
        self.assert_set(Parameter.TRANSMIT_LENGTH, 3200)

        self.assert_set_exception(Parameter.TRANSMIT_LENGTH, 3201)
        self.assert_set_exception(Parameter.TRANSMIT_LENGTH, -1)
        self.assert_set_exception(Parameter.TRANSMIT_LENGTH, 3.1415926)
        self.assert_set_exception(Parameter.TRANSMIT_LENGTH, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.TRANSMIT_LENGTH, self._driver_parameter_defaults[Parameter.TRANSMIT_LENGTH])
        self._tested[Parameter.TRANSMIT_LENGTH] = True

    def _test_set_ping_weight(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for PING_WEIGHT ======")

        # PING_WEIGHT: (0/1),
        self.assert_set(Parameter.PING_WEIGHT, 0)
        self.assert_set(Parameter.PING_WEIGHT, 1)

        self.assert_set_exception(Parameter.PING_WEIGHT, 2)
        self.assert_set_exception(Parameter.PING_WEIGHT, -1)
        self.assert_set_exception(Parameter.PING_WEIGHT, 3.1415926)
        self.assert_set_exception(Parameter.PING_WEIGHT, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(Parameter.PING_WEIGHT, self._driver_parameter_defaults[Parameter.PING_WEIGHT])
        self._tested[Parameter.PING_WEIGHT] = True

    def _test_set_ambiguity_velocity(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for AMBIGUITY_VELOCITY ======")

        # AMBIGUITY_VELOCITY: int 2 - 700
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 2)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 111)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 222)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 333)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 444)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 555)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 666)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 700)

        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, 0)
        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, 1)
        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, -1)
        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, 3.1415926)
        self.assert_set_exception(Parameter.AMBIGUITY_VELOCITY, "LEROY JENKINS")

        #
        # Reset to good value.
        #
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, self._driver_parameter_defaults[Parameter.AMBIGUITY_VELOCITY])
        self._tested[Parameter.AMBIGUITY_VELOCITY] = True

    def _test_set_serial_data_out_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SERIAL_DATA_OUT ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(Parameter.SERIAL_DATA_OUT, '000 000 111')
        self._tested[Parameter.SERIAL_DATA_OUT] = True

    def _test_set_serial_flow_control_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SERIAL_FLOW_CONTROL ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(Parameter.SERIAL_FLOW_CONTROL, '10110')
        self._tested[Parameter.SERIAL_FLOW_CONTROL] = True

    def _test_set_save_nvram_to_recorder_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SAVE_NVRAM_TO_RECORDER ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(Parameter.SAVE_NVRAM_TO_RECORDER, False)
        self._tested[Parameter.SAVE_NVRAM_TO_RECORDER] = True

    def _test_set_serial_out_fw_switches_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for SERIAL_OUT_FW_SWITCHES ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(Parameter.SERIAL_OUT_FW_SWITCHES, '110100100')
        self._tested[Parameter.SERIAL_OUT_FW_SWITCHES] = True

    def _test_set_water_profiling_mode_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for WATER_PROFILING_MODE ======")

        # Test read only raise exceptions on set.

        self.assert_set_exception(Parameter.WATER_PROFILING_MODE, 0)
        self._tested[Parameter.WATER_PROFILING_MODE] = True

    def _test_set_banner_readonly(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for BANNER ======")

        # Test read only raise exceptions on set.
        self.assert_set_exception(Parameter.BANNER, True)
        self._tested[Parameter.BANNER] = True

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()
        ####
        # First test in command mode
        ####

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        self.assert_driver_command(ProtocolEvent.GET_CALIBRATION)
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION)

        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.SEND_LAST_SAMPLE, regex='^\x7f\x7fh.*')
        self.assert_driver_command(ProtocolEvent.SAVE_SETUP_TO_RAM, expected="Parameters saved as USER defaults")
        self.assert_driver_command(ProtocolEvent.GET_ERROR_STATUS_WORD, regex='^........')
        self.assert_driver_command(ProtocolEvent.CLEAR_ERROR_STATUS_WORD, regex='^Error Status Word Cleared')
        self.assert_driver_command(ProtocolEvent.GET_FAULT_LOG, regex='^Total Unique Faults   =.*')
        self.assert_driver_command(ProtocolEvent.CLEAR_FAULT_LOG, expected='FC ..........\r\n Fault Log Cleared.\r\nClearing buffer @0x00801000\r\nDone [i=2048].\r\n')
        self.assert_driver_command(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, regex='^Beam Width:')
        self.assert_driver_command(ProtocolEvent.RUN_TEST_200, regex='^  Ambient  Temperature =')

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command_exception(ProtocolEvent.SEND_LAST_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.SAVE_SETUP_TO_RAM, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.CLEAR_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.CLEAR_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.RUN_TEST_200, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command_exception(ProtocolEvent.CLOCK_SYNC, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.GET_CALIBRATION, regex=r'Calibration date and time:')
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION, regex=r' Instrument S/N')
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)


    # This needs reworking...

    def test_startup_params(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.

        since nose orders the tests by ascii value this should run first.
        """
        log.error("BEFORE INITIALZIE")
        self.assert_initialize_driver()
        log.error("AFTER INITIALZIE")

        """
        get_values = {
            #Parameter.SERIAL_FLOW_CONTROL: '11110',
            #Parameter.BANNER: False,
            Parameter.INSTRUMENT_ID: 0,
            #Parameter.SLEEP_ENABLE: 0,
            #Parameter.SAVE_NVRAM_TO_RECORDER: True,
            #Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1500,
            #Parameter.PITCH: 0,
            #Parameter.ROLL: 0,
            Parameter.SALINITY: 35,
            Parameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            Parameter.TIME_PER_PING: '00:01.00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            #Parameter.BANDWIDTH_CONTROL: 0,
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.SERIAL_OUT_FW_SWITCHES: '111100000',
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            #Parameter.BLANK_AFTER_TRANSMIT: 704,
            Parameter.CLIP_DATA_PAST_BOTTOM: 0,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.WATER_PROFILING_MODE: 1,
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
        }
        Should be able to use the _driver_parameter_defaults instead of aboev
        """
        get_values = self._driver_parameter_defaults

        # Change the values of these parameters to something before the
        # driver is reinitalized.  They should be blown away on reinit.
        new_values = {
            Parameter.INSTRUMENT_ID: 1,
            Parameter.XMIT_POWER: 250,
            Parameter.SPEED_OF_SOUND: 1400,
            Parameter.SALINITY: 37,
            Parameter.COORDINATE_TRANSFORMATION: '11111',
            Parameter.SENSOR_SOURCE: "1111101",
            Parameter.TIME_PER_ENSEMBLE: '00:01:00.00',
            Parameter.TIME_PER_PING: '00:02.00',
            Parameter.FALSE_TARGET_THRESHOLD: '051,002',
            #RO#Parameter.BANDWIDTH_CONTROL: 1,
            Parameter.CORRELATION_THRESHOLD: 60,
            #RO#Parameter.SERIAL_OUT_FW_SWITCHES: '101010101',
            Parameter.ERROR_VELOCITY_THRESHOLD: 1900,
            #RO#Parameter.BLANK_AFTER_TRANSMIT: 710,
            Parameter.CLIP_DATA_PAST_BOTTOM: 1,
            Parameter.RECEIVER_GAIN_SELECT: 0,
            Parameter.WATER_REFERENCE_LAYER: '002,006',
            #RO#Parameter.WATER_PROFILING_MODE: 0,
            Parameter.NUMBER_OF_DEPTH_CELLS: 80,
            Parameter.PINGS_PER_ENSEMBLE: 2,
            Parameter.DEPTH_CELL_SIZE: 600,
            Parameter.TRANSMIT_LENGTH: 1,
            Parameter.PING_WEIGHT: 1,
            Parameter.AMBIGUITY_VELOCITY: 100,
        }
        """
            Parameter.INSTRUMENT_ID: 1,
            #Parameter.SLEEP_ENABLE: 1,
            #Parameter.POLLED_MODE: True,
            Parameter.XMIT_POWER: 250,
            Parameter.SPEED_OF_SOUND: 1400,
            #Parameter.PITCH: 1,
            #Parameter.ROLL: 1,
            Parameter.SALINITY: 37,
            Parameter.TIME_PER_ENSEMBLE: '00:01:00.00',
            Parameter.TIME_PER_PING: '00:02.00',
            Parameter.FALSE_TARGET_THRESHOLD: '051,001',
            #Parameter.BANDWIDTH_CONTROL: 1,
            Parameter.CORRELATION_THRESHOLD: 60,
            Parameter.ERROR_VELOCITY_THRESHOLD: 1900,
            #Parameter.BLANK_AFTER_TRANSMIT: 710,
            Parameter.CLIP_DATA_PAST_BOTTOM: 1,
            Parameter.RECEIVER_GAIN_SELECT: 0,
            Parameter.WATER_REFERENCE_LAYER: '002,006',
            Parameter.NUMBER_OF_DEPTH_CELLS: 80,
            Parameter.PINGS_PER_ENSEMBLE: 2,
            Parameter.DEPTH_CELL_SIZE: 600,
            Parameter.TRANSMIT_LENGTH: 1,
            Parameter.PING_WEIGHT: 1,
            Parameter.AMBIGUITY_VELOCITY: 100,
        """
        
        
        self.assert_startup_parameters(self.assert_driver_parameters, new_values, get_values)



###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class WorkhorseDriverQualificationTest(TeledyneQualificationTest):
    def setUp(self):
        TeledyneQualificationTest.setUp(self)

    def assert_configuration(self, data_particle, verify_values = False):
        '''
        Verify assert_compass_calibration particle
        @param data_particle:  ADCP_COMPASS_CALIBRATION data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(ADCP_SYSTEM_CONFIGURATION_KEY, self._system_configuration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)
        self.assert_data_particle_parameters(data_particle, self._system_configuration_data_parameters, verify_values)

    def assert_compass_calibration(self, data_particle, verify_values = False):
        '''
        Verify assert_compass_calibration particle
        @param data_particle:  ADCP_COMPASS_CALIBRATION data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(ADCP_COMPASS_CALIBRATION_KEY, self._calibration_data_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    def test_cycle(self):
        """
        Verify we can bounce between command and streaming.  We try it a few times to see if we can find a timeout.
        """
        self.assert_enter_command_mode()

        self.assert_cycle()
        self.assert_cycle()
        self.assert_cycle()
        self.assert_cycle()

    # need to override this because we are slow and dont feel like modifying the base class lightly
    def assert_set_parameter(self, name, value, verify=True):
        '''
        verify that parameters are set correctly.  Assumes we are in command mode.
        '''
        setParams = { name : value }
        getParams = [ name ]

        self.instrument_agent_client.set_resource(setParams, timeout=300)

        if(verify):
            result = self.instrument_agent_client.get_resource(getParams, timeout=300)
            self.assertEqual(result[name], value)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """

        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1487)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)

        self.tcp_client.send_data("%sEC1488%s" % (NEWLINE, NEWLINE))

        self.tcp_client.expect(Prompt.COMMAND)

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1488)

    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)

        # Now verify that at least the date matches
        check_new_params = self.instrument_agent_client.get_resource([Parameter.TIME], timeout=300)

        instrument_time = time.mktime(time.strptime(check_new_params.get(Parameter.TIME).lower(), "%Y/%m/%d,%H:%M:%S %Z"))

        self.assertLessEqual(abs(instrument_time - time.mktime(time.gmtime())), 15)

    # this will probably need to move up to the leaf level.
    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.

        TODO: seems this should derive from _driver_capabilities in mixin
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.CLEAR_ERROR_STATUS_WORD,
                ProtocolEvent.CLEAR_FAULT_LOG,
                ProtocolEvent.GET_CALIBRATION,
                ProtocolEvent.GET_CONFIGURATION,
                ProtocolEvent.GET_ERROR_STATUS_WORD,
                ProtocolEvent.GET_FAULT_LOG,
                ProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX,
                ProtocolEvent.RUN_TEST_200,
                ProtocolEvent.SAVE_SETUP_TO_RAM,
                ProtocolEvent.SEND_LAST_SAMPLE
                ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            ProtocolEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.GET_CONFIGURATION,
            ProtocolEvent.GET_CALIBRATION,
            ]
        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)

    def test_startup_params_first_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SERIAL_FLOW_CONTROL, '11110') # Immutable
        self.assert_get_parameter(Parameter.BANNER, False)
        self.assert_get_parameter(Parameter.INSTRUMENT_ID, 0)
        self.assert_get_parameter(Parameter.SLEEP_ENABLE, 0)
        self.assert_get_parameter(Parameter.SAVE_NVRAM_TO_RECORDER, True) # Immutable
        self.assert_get_parameter(Parameter.POLLED_MODE, False)
        self.assert_get_parameter(Parameter.XMIT_POWER, 255)
        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1500)
        self.assert_get_parameter(Parameter.PITCH, 0)
        self.assert_get_parameter(Parameter.ROLL, 0)
        self.assert_get_parameter(Parameter.SALINITY, 35)
        self.assert_get_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_get_parameter(Parameter.TIME_PER_PING, '00:01.00')
        self.assert_get_parameter(Parameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_get_parameter(Parameter.BANDWIDTH_CONTROL, 0)
        self.assert_get_parameter(Parameter.CORRELATION_THRESHOLD, 64)
        self.assert_get_parameter(Parameter.SERIAL_OUT_FW_SWITCHES, '111100000') # Immutable
        self.assert_get_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_get_parameter(Parameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_get_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 0)
        self.assert_get_parameter(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_get_parameter(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_get_parameter(Parameter.WATER_PROFILING_MODE, 1) # Immutable
        self.assert_get_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_get_parameter(Parameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_get_parameter(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_get_parameter(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_get_parameter(Parameter.PING_WEIGHT, 0)
        self.assert_get_parameter(Parameter.AMBIGUITY_VELOCITY, 175)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(Parameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(Parameter.POLLED_MODE, True)
        self.assert_set_parameter(Parameter.XMIT_POWER, 250)
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(Parameter.PITCH, 1)
        self.assert_set_parameter(Parameter.ROLL, 1)
        self.assert_set_parameter(Parameter.SALINITY, 36)
        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(Parameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(Parameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(Parameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(Parameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(Parameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(Parameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(Parameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(Parameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(Parameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(Parameter.PING_WEIGHT, 1)
        self.assert_set_parameter(Parameter.AMBIGUITY_VELOCITY, 176)

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.SERIAL_FLOW_CONTROL, '11110') # Immutable
        self.assert_get_parameter(Parameter.BANNER, False)
        self.assert_get_parameter(Parameter.INSTRUMENT_ID, 0)
        self.assert_get_parameter(Parameter.SLEEP_ENABLE, 0)
        self.assert_get_parameter(Parameter.SAVE_NVRAM_TO_RECORDER, True) # Immutable
        self.assert_get_parameter(Parameter.POLLED_MODE, False)
        self.assert_get_parameter(Parameter.XMIT_POWER, 255)
        self.assert_get_parameter(Parameter.SPEED_OF_SOUND, 1500)
        self.assert_get_parameter(Parameter.PITCH, 0)
        self.assert_get_parameter(Parameter.ROLL, 0)
        self.assert_get_parameter(Parameter.SALINITY, 35)
        self.assert_get_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_get_parameter(Parameter.TIME_PER_PING, '00:01.00')
        self.assert_get_parameter(Parameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_get_parameter(Parameter.BANDWIDTH_CONTROL, 0)
        self.assert_get_parameter(Parameter.CORRELATION_THRESHOLD, 64)
        self.assert_get_parameter(Parameter.SERIAL_OUT_FW_SWITCHES, '111100000') # Immutable
        self.assert_get_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_get_parameter(Parameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_get_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 0)
        self.assert_get_parameter(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_get_parameter(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_get_parameter(Parameter.WATER_PROFILING_MODE, 1) # Immutable
        self.assert_get_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_get_parameter(Parameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_get_parameter(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_get_parameter(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_get_parameter(Parameter.PING_WEIGHT, 0)
        self.assert_get_parameter(Parameter.AMBIGUITY_VELOCITY, 175)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(Parameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(Parameter.POLLED_MODE, True)
        self.assert_set_parameter(Parameter.XMIT_POWER, 250)
        self.assert_set_parameter(Parameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(Parameter.PITCH, 1)
        self.assert_set_parameter(Parameter.ROLL, 1)
        self.assert_set_parameter(Parameter.SALINITY, 36)
        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(Parameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(Parameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(Parameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(Parameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(Parameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(Parameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(Parameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(Parameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(Parameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(Parameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(Parameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(Parameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(Parameter.PING_WEIGHT, 1)
        self.assert_set_parameter(Parameter.AMBIGUITY_VELOCITY, 176)


###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class WorkhorseDriverPublicationTest(TeledynePublicationTest):
    def setUp(self):
        TeledynePublicationTest.setUp(self)

    def test_granule_generation(self):
        self.assert_initialize_driver()

        # Currently these tests only verify that the data granule is generated, but the values
        # are not tested.  We will eventually need to replace log.debug with a better callback
        # function that actually tests the granule.
        self.assert_sample_async("raw data", log.debug, DataParticleType.RAW, timeout=10)
        self.assert_sample_async(SAMPLE_RAW_DATA, log.debug, DataParticleType.ADCP_PD0_PARSED_BEAM, timeout=10)
        self.assert_sample_async(PS0_RAW_DATA, log.debug, DataParticleType.ADCP_SYSTEM_CONFIGURATION, timeout=10)
        self.assert_sample_async(CALIBRATION_RAW_DATA, log.debug, DataParticleType.ADCP_COMPASS_CALIBRATION, timeout=10)
