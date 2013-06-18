"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver
@author Roger Unwin
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

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import WorkhorseInstrumentDriver

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import TeledyneProtocolState
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import TeledyneProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import TeledyneParameter

from mi.instrument.teledyne.driver import TeledyneScheduledJob
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import TeledynePrompt
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import NEWLINE

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle

#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import PS3_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import FD_RAW_DATA
#from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import PT200_RAW_DATA

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
###############################################################################

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
    def setUp(self):
        TeledyneIntegrationTest.setUp(self)

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
        reply = self.driver_client.cmd_dvr('get_resource', TeledyneParameter.ALL)
        self.assert_driver_parameters(reply, True)


    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        params = {
            TeledyneParameter.INSTRUMENT_ID: 0,
            TeledyneParameter.SLEEP_ENABLE: 0,
            TeledyneParameter.POLLED_MODE: False,
            TeledyneParameter.XMIT_POWER: 255,
            TeledyneParameter.SPEED_OF_SOUND: 1485,
            TeledyneParameter.PITCH: 0,
            TeledyneParameter.ROLL: 0,
            TeledyneParameter.SALINITY: 35,
            TeledyneParameter.SENSOR_SOURCE: "1111101",
            TeledyneParameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            TeledyneParameter.TIME_PER_PING: '00:01.00',
            TeledyneParameter.FALSE_TARGET_THRESHOLD: '050,001',
            TeledyneParameter.BANDWIDTH_CONTROL: 0,
            TeledyneParameter.CORRELATION_THRESHOLD: 64,
            TeledyneParameter.ERROR_VELOCITY_THRESHOLD: 2000,
            TeledyneParameter.BLANK_AFTER_TRANSMIT: 704,
            TeledyneParameter.CLIP_DATA_PAST_BOTTOM: False,
            TeledyneParameter.RECEIVER_GAIN_SELECT: 1,
            TeledyneParameter.WATER_REFERENCE_LAYER: '001,005',
            TeledyneParameter.NUMBER_OF_DEPTH_CELLS: 100,
            TeledyneParameter.PINGS_PER_ENSEMBLE: 1,
            TeledyneParameter.DEPTH_CELL_SIZE: 800,
            TeledyneParameter.TRANSMIT_LENGTH: 0,
            TeledyneParameter.PING_WEIGHT: 0,
            TeledyneParameter.AMBIGUITY_VELOCITY: 175,
        }

        # Set all parameters to a known ground state
        self.assert_set_bulk(params)

        ###
        #   Instrument Parameteres
        ###

        self.assert_set_readonly(TeledyneParameter.SERIAL_DATA_OUT)
        self.assert_set_readonly(TeledyneParameter.SERIAL_FLOW_CONTROL)
        self.assert_set_readonly(TeledyneParameter.SAVE_NVRAM_TO_RECORDER)
        self.assert_set_readonly(TeledyneParameter.WATER_PROFILING_MODE)
        self.assert_set_readonly(TeledyneParameter.SERIAL_OUT_FW_SWITCHES)
        self.assert_set_readonly(TeledyneParameter.BANNER)

        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, 64)
        self.assert_set(TeledyneParameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_set(TeledyneParameter.INSTRUMENT_ID, 0)
        self.assert_set(TeledyneParameter.SLEEP_ENABLE, 0)
        self.assert_set(TeledyneParameter.POLLED_MODE, False)
        self.assert_set(TeledyneParameter.XMIT_POWER, 255)
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, 1485)
        self.assert_set(TeledyneParameter.PITCH, 0)
        self.assert_set(TeledyneParameter.ROLL, 0) 
        self.assert_set(TeledyneParameter.SALINITY, 35)
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1111101")
        self.assert_set(TeledyneParameter.TIME_PER_PING, '00:01.00')
        self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_set(TeledyneParameter.BANDWIDTH_CONTROL, 0)
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 2000) 
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 704) 
        self.assert_set(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, False)
        self.assert_set(TeledyneParameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_set(TeledyneParameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_set(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_set(TeledyneParameter.DEPTH_CELL_SIZE, 800)
        self.assert_set(TeledyneParameter.TRANSMIT_LENGTH, 0)
        self.assert_set(TeledyneParameter.PING_WEIGHT, 0)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 175)

        """
        test a variety of paramater ranges.
        """

        # INSTRUMENT_ID -- Int 0-255
        self.assert_set_exception(TeledyneParameter.INSTRUMENT_ID, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.INSTRUMENT_ID, -1)

        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.INSTRUMENT_ID, 0)

        # SLEEP_ENABLE:  -- (0,1,2)
        self.assert_set(TeledyneParameter.SLEEP_ENABLE, 1)
        self.assert_set(TeledyneParameter.SLEEP_ENABLE, 2)

        self.assert_set_exception(TeledyneParameter.SLEEP_ENABLE, -1)
        self.assert_set_exception(TeledyneParameter.SLEEP_ENABLE, 3)
        self.assert_set_exception(TeledyneParameter.SLEEP_ENABLE, 3.1415926)
        self.assert_set_exception(TeledyneParameter.SLEEP_ENABLE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.SLEEP_ENABLE, 0)

        # POLLED_MODE:  -- (True/False)
        self.assert_set(TeledyneParameter.POLLED_MODE, True)
        self.assert_set_exception(TeledyneParameter.POLLED_MODE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.POLLED_MODE, False)

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
        self.assert_set(TeledyneParameter.XMIT_POWER, 255)

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
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, 1485)

        # PITCH:  -- Int -6000 to 6000
        self.assert_set(TeledyneParameter.PITCH, -6000)
        self.assert_set(TeledyneParameter.PITCH, -4000)
        self.assert_set(TeledyneParameter.PITCH, -2000)
        self.assert_set(TeledyneParameter.PITCH, -1)
        self.assert_set(TeledyneParameter.PITCH, 0)
        self.assert_set(TeledyneParameter.PITCH, 1)
        self.assert_set(TeledyneParameter.PITCH, 2000)
        self.assert_set(TeledyneParameter.PITCH, 4000)
        self.assert_set(TeledyneParameter.PITCH, 6000)

        self.assert_set_exception(TeledyneParameter.PITCH, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.PITCH, -6001)
        self.assert_set_exception(TeledyneParameter.PITCH, 6001)
        self.assert_set_exception(TeledyneParameter.PITCH, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.PITCH, 0)

        # ROLL:  -- Int -6000 to 6000
        self.assert_set(TeledyneParameter.ROLL, -6000)
        self.assert_set(TeledyneParameter.ROLL, -4000)
        self.assert_set(TeledyneParameter.ROLL, -2000)
        self.assert_set(TeledyneParameter.ROLL, -1)
        self.assert_set(TeledyneParameter.ROLL, 0)
        self.assert_set(TeledyneParameter.ROLL, 1)
        self.assert_set(TeledyneParameter.ROLL, 2000)
        self.assert_set(TeledyneParameter.ROLL, 4000)
        self.assert_set(TeledyneParameter.ROLL, 6000)

        self.assert_set_exception(TeledyneParameter.ROLL, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.ROLL, -6001)
        self.assert_set_exception(TeledyneParameter.ROLL, 6001)
        self.assert_set_exception(TeledyneParameter.ROLL, 3.1415926)
        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.ROLL, 0)

        # SALINITY:  -- Int (0 - 40)
        self.assert_set(TeledyneParameter.SALINITY, 0)
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
        self.assert_set(TeledyneParameter.SALINITY, 35)

        # SENSOR_SOURCE:  -- (0/1) for 7 positions.
        # note it lacks capability to have a 1 in the #6 position
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "0000000")
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1111101")
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1010101")
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "0101000")
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1100100")

        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, 2)
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, -1)
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, "1111112")
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, "11111112")
        self.assert_set_exception(TeledyneParameter.SENSOR_SOURCE, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1111101")

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

        self.assert_set(TeledyneParameter.TIME_PER_ENSEMBLE, "00:00:00.00")

        # TIME_OF_FIRST_PING:  -- str ****/**/**,**:**:** (CCYY/MM/DD,hh:mm:ss)
        # THIS IS AN EVIL COMMAND! NEVER USE.
        #now_1_hour = (dt.datetime.utcnow() + dt.timedelta(hours=1)).strftime("%Y/%m/%d,%H:%m:%S")
        #today_plus_10 = (dt.datetime.utcnow() + dt.timedelta(days=10)).strftime("%Y/%m/%d,%H:%m:%S")
        #today_plus_1month = (dt.datetime.utcnow() + dt.timedelta(days=31)).strftime("%Y/%m/%d,%H:%m:%S")
        #today_plus_6month = (dt.datetime.utcnow() + dt.timedelta(days=183)).strftime("%Y/%m/%d,%H:%m:%S")

        #self.assert_set(TeledyneParameter.TIME_OF_FIRST_PING, now_1_hour)
        #self.assert_set(TeledyneParameter.TIME_OF_FIRST_PING, today_plus_10)
        #self.assert_set(TeledyneParameter.TIME_OF_FIRST_PING, today_plus_1month)
        #self.assert_set(TeledyneParameter.TIME_OF_FIRST_PING, today_plus_6month)

        # AssertionError: Unexpected exception: TG no value match (2013/06/06,06:06:06 != LEROY JENKINS)
        #self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, "LEROY JENKINS")

        #self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, 2)
        #self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, -1)
        #self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, '99:99.99')
        #self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, '-1:-1.+1')
        #self.assert_set_exception(TeledyneParameter.TIME_OF_FIRST_PING, 3.1415926)

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
        self.assert_set(TeledyneParameter.TIME_PER_PING, '00:01.00')

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
        self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, "050,001")

        # BANDWIDTH_CONTROL: 0/1,
        self.assert_set(TeledyneParameter.BANDWIDTH_CONTROL, 1)

        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, -1)
        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, 2)
        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.BANDWIDTH_CONTROL, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.BANDWIDTH_CONTROL, 0)

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
        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, 64)

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
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 2000)

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
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 704)

        # CLIP_DATA_PAST_BOTTOM: True/False,
        self.assert_set(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, True)

        self.assert_set_exception(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, "LEROY JENKINS")

        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, False)

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
        self.assert_set(TeledyneParameter.RECEIVER_GAIN_SELECT, 1)

        # WATER_REFERENCE_LAYER:  -- int Begin Cell (0=OFF), End Cell  (0-100)
        self.assert_set(TeledyneParameter.WATER_REFERENCE_LAYER, "000,001")
        self.assert_set(TeledyneParameter.WATER_REFERENCE_LAYER, "000,100")
        self.assert_set(TeledyneParameter.WATER_REFERENCE_LAYER, "000,100")

        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, "255,000")
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, "000,000")
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, "001,000")
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, "100,000")
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, "000,101")
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, "100,101")
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, -1)
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, 2)
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, "LEROY JENKINS")
        self.assert_set_exception(TeledyneParameter.WATER_REFERENCE_LAYER, 3.1415926)

        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.WATER_REFERENCE_LAYER, "001,005")

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
        self.assert_set(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 100)

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
        self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, 1)

        # DEPTH_CELL_SIZE: int 80 - 3200
        self.assert_set(TeledyneParameter.DEPTH_CELL_SIZE, 80)
        self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, 3200)

        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, 3201)
        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, -1)
        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, 2)
        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, 3.1415926)
        self.assert_set_exception(TeledyneParameter.PING_WEIGHT, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, 0)

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
        self.assert_set(TeledyneParameter.TRANSMIT_LENGTH, 0)

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
        self.assert_set(TeledyneParameter.PING_WEIGHT, 0)

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
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 175)

        # Test read only raise exceptions on set.
        self.assert_set_exception(TeledyneParameter.SERIAL_DATA_OUT, '000 000 111')
        self.assert_set_exception(TeledyneParameter.SERIAL_FLOW_CONTROL, '10110')
        self.assert_set_exception(TeledyneParameter.SAVE_NVRAM_TO_RECORDER, False)
        self.assert_set_exception(TeledyneParameter.SERIAL_OUT_FW_SWITCHES, '110100100')
        self.assert_set_exception(TeledyneParameter.WATER_PROFILING_MODE, 0)
        self.assert_set_exception(TeledyneParameter.BANNER, True)

        # TODO: remove this its only here for testing to assert that it
        # isn't being caused by a leftover funky value..
        self.assert_set(TeledyneParameter.CORRELATION_THRESHOLD, 64)
        self.assert_set(TeledyneParameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_set(TeledyneParameter.INSTRUMENT_ID, 0)
        self.assert_set(TeledyneParameter.SLEEP_ENABLE, 0)
        self.assert_set(TeledyneParameter.POLLED_MODE, False)
        self.assert_set(TeledyneParameter.XMIT_POWER, 255)
        self.assert_set(TeledyneParameter.SPEED_OF_SOUND, 1485)
        self.assert_set(TeledyneParameter.PITCH, 0)
        self.assert_set(TeledyneParameter.ROLL, 0) 
        self.assert_set(TeledyneParameter.SALINITY, 35)
        self.assert_set(TeledyneParameter.SENSOR_SOURCE, "1111101")
        self.assert_set(TeledyneParameter.TIME_PER_PING, '00:01.00')
        self.assert_set(TeledyneParameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_set(TeledyneParameter.BANDWIDTH_CONTROL, 0)
        self.assert_set(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 2000) 
        self.assert_set(TeledyneParameter.BLANK_AFTER_TRANSMIT, 704) 
        self.assert_set(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, False)
        self.assert_set(TeledyneParameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_set(TeledyneParameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_set(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_set(TeledyneParameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_set(TeledyneParameter.DEPTH_CELL_SIZE, 800)
        self.assert_set(TeledyneParameter.TRANSMIT_LENGTH, 0)
        self.assert_set(TeledyneParameter.PING_WEIGHT, 0)
        self.assert_set(TeledyneParameter.AMBIGUITY_VELOCITY, 175)

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()
        ####
        # First test in command mode
        ####

        self.assert_driver_command(TeledyneProtocolEvent.START_AUTOSAMPLE, state=TeledyneProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE, state=TeledyneProtocolState.COMMAND, delay=1)

        self.assert_driver_command(TeledyneProtocolEvent.GET_CALIBRATION)
        self.assert_driver_command(TeledyneProtocolEvent.GET_CONFIGURATION)
        self.assert_driver_command(TeledyneProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command(TeledyneProtocolEvent.SEND_LAST_SAMPLE, regex='^\x7f\x7fh.*')
        self.assert_driver_command(TeledyneProtocolEvent.SAVE_SETUP_TO_RAM, expected="Parameters saved as USER defaults")
        self.assert_driver_command(TeledyneProtocolEvent.GET_ERROR_STATUS_WORD, regex='^........')
        self.assert_driver_command(TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD, regex='^Error Status Word Cleared')
        self.assert_driver_command(TeledyneProtocolEvent.GET_FAULT_LOG, regex='^Total Unique Faults   =.*')
        self.assert_driver_command(TeledyneProtocolEvent.CLEAR_FAULT_LOG, expected='FC ..........\r\n Fault Log Cleared.\r\nClearing buffer @0x00801000\r\nDone [i=2048].\r\n')
        self.assert_driver_command(TeledyneProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, regex='^Beam Width:')
        self.assert_driver_command(TeledyneProtocolEvent.RUN_TEST_200, regex='^  Ambient  Temperature =')

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(TeledyneProtocolEvent.START_AUTOSAMPLE, state=TeledyneProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command_exception(TeledyneProtocolEvent.SEND_LAST_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.SAVE_SETUP_TO_RAM, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.GET_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.GET_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.CLEAR_FAULT_LOG, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(TeledyneProtocolEvent.RUN_TEST_200, exception_class=InstrumentCommandException)
        self.assert_driver_command(TeledyneProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command_exception(TeledyneProtocolEvent.CLOCK_SYNC, exception_class=InstrumentCommandException)
        self.assert_driver_command(TeledyneProtocolEvent.GET_CALIBRATION, regex=r'Calibration date and time:')
        self.assert_driver_command(TeledyneProtocolEvent.GET_CONFIGURATION, regex=r' Instrument S/N')
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE, state=TeledyneProtocolState.COMMAND, delay=1)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_startup_params(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.

        since nose orders the tests by ascii value this should run first.
        """
        self.assert_initialize_driver()

        get_values = {
            TeledyneParameter.SERIAL_FLOW_CONTROL: '11110',
            TeledyneParameter.BANNER: False,
            TeledyneParameter.INSTRUMENT_ID: 0,
            TeledyneParameter.SLEEP_ENABLE: 0,
            TeledyneParameter.SAVE_NVRAM_TO_RECORDER: True,
            TeledyneParameter.POLLED_MODE: False,
            TeledyneParameter.XMIT_POWER: 255,
            TeledyneParameter.SPEED_OF_SOUND: 1485,
            TeledyneParameter.PITCH: 0,
            TeledyneParameter.ROLL: 0,
            TeledyneParameter.SALINITY: 35,
            TeledyneParameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            TeledyneParameter.TIME_PER_PING: '00:01.00',
            TeledyneParameter.FALSE_TARGET_THRESHOLD: '050,001',
            TeledyneParameter.BANDWIDTH_CONTROL: 0,
            TeledyneParameter.CORRELATION_THRESHOLD: 64,
            TeledyneParameter.SERIAL_OUT_FW_SWITCHES: '111100000',
            TeledyneParameter.ERROR_VELOCITY_THRESHOLD: 2000,
            TeledyneParameter.BLANK_AFTER_TRANSMIT: 704,
            TeledyneParameter.CLIP_DATA_PAST_BOTTOM: 0,
            TeledyneParameter.RECEIVER_GAIN_SELECT: 1,
            TeledyneParameter.WATER_REFERENCE_LAYER: '001,005',
            TeledyneParameter.WATER_PROFILING_MODE: 1,
            TeledyneParameter.NUMBER_OF_DEPTH_CELLS: 100,
            TeledyneParameter.PINGS_PER_ENSEMBLE: 1,
            TeledyneParameter.DEPTH_CELL_SIZE: 800,
            TeledyneParameter.TRANSMIT_LENGTH: 0,
            TeledyneParameter.PING_WEIGHT: 0,
            TeledyneParameter.AMBIGUITY_VELOCITY: 175,
        }

        # Change the values of these parameters to something before the
        # driver is reinitalized.  They should be blown away on reinit.
        new_values = {
            TeledyneParameter.INSTRUMENT_ID: 1,
            TeledyneParameter.SLEEP_ENABLE: 1,
            TeledyneParameter.POLLED_MODE: True,
            TeledyneParameter.XMIT_POWER: 250,
            TeledyneParameter.SPEED_OF_SOUND: 1400,
            TeledyneParameter.PITCH: 1,
            TeledyneParameter.ROLL: 1,
            TeledyneParameter.SALINITY: 37,
            TeledyneParameter.TIME_PER_ENSEMBLE: '00:01:00.00',
            TeledyneParameter.TIME_PER_PING: '00:02.00',
            TeledyneParameter.FALSE_TARGET_THRESHOLD: '051,001',
            TeledyneParameter.BANDWIDTH_CONTROL: 1,
            TeledyneParameter.CORRELATION_THRESHOLD: 60,
            TeledyneParameter.ERROR_VELOCITY_THRESHOLD: 1900,
            TeledyneParameter.BLANK_AFTER_TRANSMIT: 710,
            TeledyneParameter.CLIP_DATA_PAST_BOTTOM: 1,
            TeledyneParameter.RECEIVER_GAIN_SELECT: 0,
            TeledyneParameter.WATER_REFERENCE_LAYER: '002,006',
            TeledyneParameter.NUMBER_OF_DEPTH_CELLS: 80,
            TeledyneParameter.PINGS_PER_ENSEMBLE: 2,
            TeledyneParameter.DEPTH_CELL_SIZE: 600,
            TeledyneParameter.TRANSMIT_LENGTH: 1,
            TeledyneParameter.PING_WEIGHT: 1,
            TeledyneParameter.AMBIGUITY_VELOCITY: 100,
        }

        self.assert_startup_parameters(self.assert_driver_parameters, new_values, get_values)

    ###
    #   Test scheduled events
    ###
    def assert_compass_calibration(self):
        """
        Verify a calibration particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_COMPASS_CALIBRATION, self.assert_particle_compass_calibration, timeout=120)

    def test_scheduled_compass_calibration_command(self):
        """
        Verify the device configuration command can be triggered and run in command
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=100)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_compass_calibration_autosample(self):
        """
        Verify the device configuration command can be triggered and run in autosample
        """

        self.assert_scheduled_event(TeledyneScheduledJob.GET_CALIBRATION, self.assert_compass_calibration, delay=100,
            autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.ADCP_SYSTEM_CONFIGURATION, self.assert_particle_system_configuration, timeout=120)

    def test_scheduled_device_configuration_command(self):
        """
        Verify the device status command can be triggered and run in command
        """
        self.assert_scheduled_event(TeledyneScheduledJob.GET_CONFIGURATION, self.assert_acquire_status, delay=100)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_device_configuration_autosample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
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
        self.assert_scheduled_event(TeledyneScheduledJob.CLOCK_SYNC, self.assert_clock_sync, delay=90)
        self.assert_current_state(TeledyneProtocolState.COMMAND)

    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """

        self.assert_scheduled_event(TeledyneScheduledJob.CLOCK_SYNC, self.assert_clock_sync,
                                    autosample_command=TeledyneProtocolEvent.START_AUTOSAMPLE, delay=200)
        self.assert_current_state(TeledyneProtocolState.AUTOSAMPLE)
        self.assert_driver_command(TeledyneProtocolEvent.STOP_AUTOSAMPLE)

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
        self.assert_set_parameter(TeledyneParameter.SPEED_OF_SOUND, 1487)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)

        self.tcp_client.send_data("%sEC1488%s" % (NEWLINE, NEWLINE))

        self.tcp_client.expect(TeledynePrompt.COMMAND)

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()

        self.assert_get_parameter(TeledyneParameter.SPEED_OF_SOUND, 1488)

    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(TeledyneProtocolEvent.CLOCK_SYNC)

        # Now verify that at least the date matches
        check_new_params = self.instrument_agent_client.get_resource([TeledyneParameter.TIME], timeout=45)

        instrument_time = time.mktime(time.strptime(check_new_params.get(TeledyneParameter.TIME).lower(), "%Y/%m/%d,%H:%M:%S %Z"))

        self.assertLessEqual(abs(instrument_time - time.mktime(time.gmtime())), 45)

    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                TeledyneProtocolEvent.CLOCK_SYNC,
                TeledyneProtocolEvent.START_AUTOSAMPLE,
                TeledyneProtocolEvent.CLEAR_ERROR_STATUS_WORD,
                TeledyneProtocolEvent.CLEAR_FAULT_LOG,
                TeledyneProtocolEvent.GET_CALIBRATION,
                TeledyneProtocolEvent.GET_CONFIGURATION,
                TeledyneProtocolEvent.GET_ERROR_STATUS_WORD,
                TeledyneProtocolEvent.GET_FAULT_LOG,
                TeledyneProtocolEvent.GET_INSTRUMENT_TRANSFORM_MATRIX,
                TeledyneProtocolEvent.RUN_TEST_200,
                TeledyneProtocolEvent.SAVE_SETUP_TO_RAM,
                TeledyneProtocolEvent.SEND_LAST_SAMPLE
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
            TeledyneProtocolEvent.STOP_AUTOSAMPLE,
            TeledyneProtocolEvent.GET_CONFIGURATION,
            TeledyneProtocolEvent.GET_CALIBRATION,
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

        self.assert_get_parameter(TeledyneParameter.SERIAL_FLOW_CONTROL, '11110') # Immutable
        self.assert_get_parameter(TeledyneParameter.BANNER, False)
        self.assert_get_parameter(TeledyneParameter.INSTRUMENT_ID, 0)
        self.assert_get_parameter(TeledyneParameter.SLEEP_ENABLE, 0)
        self.assert_get_parameter(TeledyneParameter.SAVE_NVRAM_TO_RECORDER, True) # Immutable
        self.assert_get_parameter(TeledyneParameter.POLLED_MODE, False)
        self.assert_get_parameter(TeledyneParameter.XMIT_POWER, 255)
        self.assert_get_parameter(TeledyneParameter.SPEED_OF_SOUND, 1485)
        self.assert_get_parameter(TeledyneParameter.PITCH, 0)
        self.assert_get_parameter(TeledyneParameter.ROLL, 0)
        self.assert_get_parameter(TeledyneParameter.SALINITY, 35)
        self.assert_get_parameter(TeledyneParameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_get_parameter(TeledyneParameter.TIME_PER_PING, '00:01.00')
        self.assert_get_parameter(TeledyneParameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_get_parameter(TeledyneParameter.BANDWIDTH_CONTROL, 0)
        self.assert_get_parameter(TeledyneParameter.CORRELATION_THRESHOLD, 64)
        self.assert_get_parameter(TeledyneParameter.SERIAL_OUT_FW_SWITCHES, '111100000') # Immutable
        self.assert_get_parameter(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_get_parameter(TeledyneParameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_get_parameter(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, 0)
        self.assert_get_parameter(TeledyneParameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_get_parameter(TeledyneParameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_get_parameter(TeledyneParameter.WATER_PROFILING_MODE, 1) # Immutable
        self.assert_get_parameter(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_get_parameter(TeledyneParameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_get_parameter(TeledyneParameter.DEPTH_CELL_SIZE, 800)
        self.assert_get_parameter(TeledyneParameter.TRANSMIT_LENGTH, 0)
        self.assert_get_parameter(TeledyneParameter.PING_WEIGHT, 0)
        self.assert_get_parameter(TeledyneParameter.AMBIGUITY_VELOCITY, 175)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(TeledyneParameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(TeledyneParameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(TeledyneParameter.POLLED_MODE, True)
        self.assert_set_parameter(TeledyneParameter.XMIT_POWER, 250)
        self.assert_set_parameter(TeledyneParameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(TeledyneParameter.PITCH, 1)
        self.assert_set_parameter(TeledyneParameter.ROLL, 1)
        self.assert_set_parameter(TeledyneParameter.SALINITY, 36)
        self.assert_set_parameter(TeledyneParameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(TeledyneParameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(TeledyneParameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(TeledyneParameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(TeledyneParameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(TeledyneParameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(TeledyneParameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(TeledyneParameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(TeledyneParameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(TeledyneParameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(TeledyneParameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(TeledyneParameter.PING_WEIGHT, 1)
        self.assert_set_parameter(TeledyneParameter.AMBIGUITY_VELOCITY, 176)

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(TeledyneParameter.SERIAL_FLOW_CONTROL, '11110') # Immutable
        self.assert_get_parameter(TeledyneParameter.BANNER, False)
        self.assert_get_parameter(TeledyneParameter.INSTRUMENT_ID, 0)
        self.assert_get_parameter(TeledyneParameter.SLEEP_ENABLE, 0)
        self.assert_get_parameter(TeledyneParameter.SAVE_NVRAM_TO_RECORDER, True) # Immutable
        self.assert_get_parameter(TeledyneParameter.POLLED_MODE, False)
        self.assert_get_parameter(TeledyneParameter.XMIT_POWER, 255)
        self.assert_get_parameter(TeledyneParameter.SPEED_OF_SOUND, 1485)
        self.assert_get_parameter(TeledyneParameter.PITCH, 0)
        self.assert_get_parameter(TeledyneParameter.ROLL, 0)
        self.assert_get_parameter(TeledyneParameter.SALINITY, 35)
        self.assert_get_parameter(TeledyneParameter.TIME_PER_ENSEMBLE, '00:00:00.00')
        self.assert_get_parameter(TeledyneParameter.TIME_PER_PING, '00:01.00')
        self.assert_get_parameter(TeledyneParameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_get_parameter(TeledyneParameter.BANDWIDTH_CONTROL, 0)
        self.assert_get_parameter(TeledyneParameter.CORRELATION_THRESHOLD, 64)
        self.assert_get_parameter(TeledyneParameter.SERIAL_OUT_FW_SWITCHES, '111100000') # Immutable
        self.assert_get_parameter(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_get_parameter(TeledyneParameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_get_parameter(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, 0)
        self.assert_get_parameter(TeledyneParameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_get_parameter(TeledyneParameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_get_parameter(TeledyneParameter.WATER_PROFILING_MODE, 1) # Immutable
        self.assert_get_parameter(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_get_parameter(TeledyneParameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_get_parameter(TeledyneParameter.DEPTH_CELL_SIZE, 800)
        self.assert_get_parameter(TeledyneParameter.TRANSMIT_LENGTH, 0)
        self.assert_get_parameter(TeledyneParameter.PING_WEIGHT, 0)
        self.assert_get_parameter(TeledyneParameter.AMBIGUITY_VELOCITY, 175)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(TeledyneParameter.INSTRUMENT_ID, 1)
        self.assert_set_parameter(TeledyneParameter.SLEEP_ENABLE, 1)
        self.assert_set_parameter(TeledyneParameter.POLLED_MODE, True)
        self.assert_set_parameter(TeledyneParameter.XMIT_POWER, 250)
        self.assert_set_parameter(TeledyneParameter.SPEED_OF_SOUND, 1480)
        self.assert_set_parameter(TeledyneParameter.PITCH, 1)
        self.assert_set_parameter(TeledyneParameter.ROLL, 1)
        self.assert_set_parameter(TeledyneParameter.SALINITY, 36)
        self.assert_set_parameter(TeledyneParameter.TIME_PER_ENSEMBLE, '00:00:01.00')
        self.assert_set_parameter(TeledyneParameter.TIME_PER_PING, '00:02.00')
        self.assert_set_parameter(TeledyneParameter.FALSE_TARGET_THRESHOLD, '049,002')
        self.assert_set_parameter(TeledyneParameter.BANDWIDTH_CONTROL, 1)
        self.assert_set_parameter(TeledyneParameter.CORRELATION_THRESHOLD, 63)
        self.assert_set_parameter(TeledyneParameter.ERROR_VELOCITY_THRESHOLD, 1999)
        self.assert_set_parameter(TeledyneParameter.BLANK_AFTER_TRANSMIT, 714)
        self.assert_set_parameter(TeledyneParameter.CLIP_DATA_PAST_BOTTOM, 1)
        self.assert_set_parameter(TeledyneParameter.RECEIVER_GAIN_SELECT, 0)
        self.assert_set_parameter(TeledyneParameter.WATER_REFERENCE_LAYER, '002,006')
        self.assert_set_parameter(TeledyneParameter.NUMBER_OF_DEPTH_CELLS, 99)
        self.assert_set_parameter(TeledyneParameter.PINGS_PER_ENSEMBLE, 0)
        self.assert_set_parameter(TeledyneParameter.DEPTH_CELL_SIZE, 790)
        self.assert_set_parameter(TeledyneParameter.TRANSMIT_LENGTH, 1)
        self.assert_set_parameter(TeledyneParameter.PING_WEIGHT, 1)
        self.assert_set_parameter(TeledyneParameter.AMBIGUITY_VELOCITY, 176)


###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################

@attr('PUB', group='mi')
class WorkhorseDriverPublicationTest(TeledynePublicationTest):
    def setUp(self):
        TeledynePublicationTest.setUp(self)


