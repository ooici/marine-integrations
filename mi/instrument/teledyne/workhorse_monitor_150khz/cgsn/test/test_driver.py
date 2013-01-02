"""
@package mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.test.test_driver
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_150khz/cgsn/driver.py
@author Lytle Johnson
@brief Test cases for cgsn driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Lytle Johnson'
__license__ = 'Apache 2.0'

import unittest
import re

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.common import BaseEnum
from nose.plugins.attrib import attr
from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import InstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import InstrumentCmds
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ProtocolState
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import Capability
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import Protocol
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_EnsembleDataParticleKey
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import ADCPT_EnsembleDataParticle
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import NEWLINE
from mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver import adcpt_cache_dict

from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException, InstrumentCommandException
from pyon.core.exception import Conflict
from interface.objects import AgentCommand
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent


# Globals
raw_stream_received = False
parsed_stream_received = False

SAMPLE_RAW_DATA = "7F7FF002000612004D008E008001FA01740200003228C941000D041E2D002003600101400900D0070114001F000000007D3DD104610301053200620028000006FED0FC090100FF00A148000014800001000C0C0D0D323862000000FF050800E014C5EE93EE2300040A000000000000454A4F4B4A4E829F80810088BDB09DFFFFFF9208000000140C0C0D0D323862000120FF570089000FFF0080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000025D585068650D0D2C0C0D0C0E0C0E0C0D0C0E0D0C0C0E0E0B0D0E0D0D0D0C0C0C0C0E0F0E0C0D0F0C0D0E0F0D0C0C0D0D0D00000E0D00000D0B00000D0C00000C0C00000C0B00000E0C00000D0C00000D0C00000D0C00000C0C00000D0C00000C00000000000000000000000000000000000000000000000000035A52675150434B454341484142414841424148414241484142414841424148414241484142414841424148414241474142414841424147414241484143414841424148414241484142414841424148414241484142414841424148414241484142414741424148414241484142414741424148414241484100040400005F0000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400FA604091"

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.teledyne.workhorse_monitor_150khz.cgsn.driver ',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'HTWZMW',
    instrument_agent_name = 'teledyne_workhorse_monitor_150khz_cgsn',
    instrument_agent_packet_config = DataParticleType(),
    driver_startup_config = {}
)

# Create some short names for the parameter test config
TYPE = ParameterTestConfigKey.TYPE
READONLY = ParameterTestConfigKey.READONLY
STARTUP = ParameterTestConfigKey.STARTUP
DA = ParameterTestConfigKey.DIRECT_ACCESS
VALUE = ParameterTestConfigKey.VALUE
REQUIRED = ParameterTestConfigKey.REQUIRED
DEFAULT = ParameterTestConfigKey.DEFAULT

class ADCPTMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constance and common data assertion methods.
    '''
    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.TRANSMIT_POWER : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 255},
        Parameter.SPEED_OF_SOUND : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 1500},
        Parameter.SALINITY : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 35},
        Parameter.TIME_PER_BURST : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00:00:00:00'},
        Parameter.ENSEMBLE_PER_BURST : {TYPE:int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.TIME_PER_ENSEMBLE : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '01:00:00:00'},
        Parameter.TIME_BETWEEN_PINGS : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '01:20:00'},
        Parameter.BUFFERED_OUTPUT_PERIOD : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00:00:00'},
        Parameter.FALSE_TARGET_THRESHOLD_MAXIMUM : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 50},
        Parameter.MODE_1_BANDWIDTH_CONTROL : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1},
        Parameter.LOW_CORRELATION_THRESHOLD : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 64},
        Parameter.ERROR_VELOCITY_THRESHOLD : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 2000},
        Parameter.BLANK_AFTER_TRANSMIT : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 352},
        Parameter.CLIP_DATA_PAST_BOTTOM : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0},
        Parameter.RECEIVER_GAIN_SELECT : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 1},
        Parameter.WATER_REFERENCE_LAYER : {TYPE: list, READONLY: False, DA: False, STARTUP: False, DEFAULT: [1,5]},
        Parameter.NUMBER_OF_DEPTH_CELLS : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 30},
        Parameter.PINGS_PER_ENSEMBLE : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 45},
        Parameter.DEPTH_CELL_SIZE : {TYPE: list, READONLY: False, DA: False, STARTUP: True, DEFAULT: [800,40,3200]},
        Parameter.TRANSMIT_LENGTH : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.PING_WEIGHT : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.AMBIGUITY_VELOCITY : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 175},
        }

 
    _header_sample_parameters = {
        ADCPT_EnsembleDataParticleKey.NUM_BYTES_IN_ENSEMBLE: {'type': int, 'value': 752 },
        ADCPT_EnsembleDataParticleKey.NUM_DATA_TYPES: {'type': int, 'value': 6 },
        ADCPT_EnsembleDataParticleKey.CPU_FW_VER: {'type': int, 'value': 50 },
        ADCPT_EnsembleDataParticleKey.CPU_FW_REV: {'type': int, 'value': 40 },
        ADCPT_EnsembleDataParticleKey.SYS_CONFIG: {'type': int, 'value': 16841 },
        ADCPT_EnsembleDataParticleKey.LAG_LEN: {'type': int, 'value': 13 },
        ADCPT_EnsembleDataParticleKey.NUM_BEAMS: {'type': int, 'value': 4 },
        ADCPT_EnsembleDataParticleKey.NUM_CELLS: {'type': int, 'value': 30 },
        ADCPT_EnsembleDataParticleKey.PINGS_PER_ENSEMBLE: {'type': int, 'value': 45 },
        ADCPT_EnsembleDataParticleKey.DEPTH_CELL_LEN: {'type': int, 'value': 800},
        ADCPT_EnsembleDataParticleKey.BLANK_AFTER_TX: {'type': int, 'value': 352},
        ADCPT_EnsembleDataParticleKey.PROFILING_MODE: {'type': int, 'value': 1},
        ADCPT_EnsembleDataParticleKey.LOW_CORR_THRESH: {'type': int, 'value': 64},
        ADCPT_EnsembleDataParticleKey.NUM_CODE_REPS: {'type': int, 'value': 9},
        ADCPT_EnsembleDataParticleKey.PERCENT_GD_MIN: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.ERR_VEL_MAX: {'type': int, 'value': 2000},
        ADCPT_EnsembleDataParticleKey.TIME_BETWEEN_PINGS: {'type': list, 'value': [1,20,0]},
        ADCPT_EnsembleDataParticleKey.COORD_XFRM: {'type': int, 'value': 31},
        ADCPT_EnsembleDataParticleKey.HEAD_ALIGN: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.HEAD_BIAS: {'type': int, 'value': 0},
        #  This needs to be expanded
        ADCPT_EnsembleDataParticleKey.SENSOR_SRC: {'type': int, 'value': 125},
        #   This needs to be expanded
        ADCPT_EnsembleDataParticleKey.SENSOR_AVAIL: {'type': int, 'value': 61},
        ADCPT_EnsembleDataParticleKey.BIN1_DIST: {'type': int, 'value': 1233},
        ADCPT_EnsembleDataParticleKey.XMIT_PULSE_LEN: {'type': int, 'value': 865},
        ADCPT_EnsembleDataParticleKey.WP_REF_LAYER_AVG: {'type': int, 'value': 1281},
        ADCPT_EnsembleDataParticleKey.FALSE_TARGET_THRESH: {'type': int, 'value': 50},
        ADCPT_EnsembleDataParticleKey.XMIT_LAG_DIST: {'type': int, 'value': 98},
        ADCPT_EnsembleDataParticleKey.CPU_SN: {'type': unicode, 'value': '28000006FED0FC09'},
        ADCPT_EnsembleDataParticleKey.SYS_BW: {'type': int, 'value': 1},
        ADCPT_EnsembleDataParticleKey.SYS_PWR: {'type': int, 'value': 255},
        ADCPT_EnsembleDataParticleKey.INST_SN: {'type': unicode, 'value': 'A1480000'},
        ADCPT_EnsembleDataParticleKey.BEAM_ANGLE: {'type': int, 'value': 20},
###---------now for the var leader data
        ADCPT_EnsembleDataParticleKey.ENSEMBLE_NUMBER: {'type': int, 'value': 1},
        ADCPT_EnsembleDataParticleKey.RTC_DATE_TIME: {'type': list, 'value': [12,12,13,13,50,56,98]},
        ADCPT_EnsembleDataParticleKey.ENSEMBLE_NUM_MSB: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.TIMESTAMP: {'type': float, 'value': 3564424256.98},
        ADCPT_EnsembleDataParticleKey.BIT_RESULT: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.SPEED_OF_SOUND: {'type': int, 'value': 1535},
        ADCPT_EnsembleDataParticleKey.DEPTH_OF_XDUCER: {'type': int, 'value': 8},
        ADCPT_EnsembleDataParticleKey.HEADING: {'type': int, 'value': 224},
        ADCPT_EnsembleDataParticleKey.PITCH: {'type': int, 'value': 61125},
        ADCPT_EnsembleDataParticleKey.ROLL: {'type': int, 'value': 61075},
        ADCPT_EnsembleDataParticleKey.SALINITY: {'type': int, 'value': 35},
        ADCPT_EnsembleDataParticleKey.TEMPERATURE: {'type': int, 'value': 2564},
        ADCPT_EnsembleDataParticleKey.MIN_PRE_PING_WAIT_TIME: {'type': list, 'value': [0,0,0]},
        ADCPT_EnsembleDataParticleKey.HDG_DEV: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.PITCH_DEV: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.ROLL_DEV: {'type': int, 'value': 0},
        ADCPT_EnsembleDataParticleKey.XMIT_CURRENT: {'type': int, 'value': 69},
        ADCPT_EnsembleDataParticleKey.XMIT_VOLTAGE: {'type': int, 'value': 74},
        ADCPT_EnsembleDataParticleKey.AMBIENT_TEMP: {'type': int, 'value': 79},
        ADCPT_EnsembleDataParticleKey.PRESSURE_POS: {'type': int, 'value': 75},
        ADCPT_EnsembleDataParticleKey.PRESSURE_NEG: {'type': int, 'value': 74},
        ADCPT_EnsembleDataParticleKey.ATTITUDE_TEMP: {'type': int, 'value': 78},
        ADCPT_EnsembleDataParticleKey.ATTITUDE: {'type': int, 'value': 130},
        ADCPT_EnsembleDataParticleKey.CONTAMINATION_SENSOR: {'type': int, 'value': 159},
        ADCPT_EnsembleDataParticleKey.BUS_ERR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.ADDR_ERR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.ILLEGAL_INSTR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.ZERO_DIV: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.EMUL_EXCEP: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.UNASS_EXCEP: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.WATCHDOG: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.BATT_SAVE_PWR: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.PINGING: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.COLD_WAKEUP: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.UNKNOWN_WAKEUP: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.CLOCK_RD_ERR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.UNEXP_ALARM: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.CLOCK_JMP_FWD: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.CLOCK_JMP_BKWRD: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.PWR_FAIL: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.SPUR_4_INTR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.SPUR_5_INTR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.SPUR_6_INTR: {'type': bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.LEV_7_INTR: {'type': bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.PRESSURE: {'type': int, 'value': 4294967197},
        ADCPT_EnsembleDataParticleKey.PRESSURE_VAR: {'type': int, 'value': 2194},
        ADCPT_EnsembleDataParticleKey.RTCY2K_DATE_TIME: {'type': list, 'value': [20,12,12,13,13,50,56,98]},
###------------Velocity data
        ADCPT_EnsembleDataParticleKey.VELOCITY_DATA: {'type': list, 'value': 
            [[-224, 87, 137, -241],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768],[-32768, -32768, -32768, -32768]]},
###------------Correlation magnitude data
        ADCPT_EnsembleDataParticleKey.CORR_MAG_DATA: {'type': list, 'value': 
            [[93, 88, 80, 104],[101, 13, 13, 44],[12, 13, 12, 14],[12, 14, 12, 13], [12, 14, 13, 12],
            [12, 14, 14, 11], [13, 14, 13, 13], [13, 12, 12, 12], [12, 14, 15, 14],
            [12, 13, 15, 12], [13, 14, 15, 13], [12, 12, 13, 13], [13, 0, 0, 14], [13, 0, 0, 13], [11, 0, 0, 13],
            [12, 0, 0, 12], [12, 0, 0, 12], [11, 0, 0, 14], [12, 0, 0, 13],[12, 0, 0, 13], [12, 0, 0, 13],
            [12, 0, 0, 12], [12, 0, 0, 13],
            [12, 0, 0, 12], [0 ,0 , 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0],[0, 0, 0, 0]]},
###------------Echo intensity data
        ADCPT_EnsembleDataParticleKey.ECHO_INTENSITY_DATA: {'type': list, 'value': 
            [[90, 82, 103, 81], [80, 67, 75, 69], [67, 65, 72, 65],[66, 65, 72, 65], [66, 65, 72, 65], 
            [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], 
            [66, 65, 72, 65], [66, 65, 71, 65], [66, 65, 72, 65], [66, 65, 71, 65], [66, 65, 72, 65], 
            [67, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], 
            [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 71, 65], 
            [66, 65, 72, 65], [66, 65, 72, 65], [66, 65, 71, 65], [66, 65, 72, 65], [66, 65, 72, 65]]},
###------------Percent good data
        ADCPT_EnsembleDataParticleKey.PERCENT_GOOD_DATA: {'type': list, 'value': 
            [[4, 0, 0, 95], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], 
            [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], 
            [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], 
            [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], 
            [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0], [0, 0, 100, 0]]}
        }

# Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    ###
    # Data Particle Parameters Methods
    ###
    def assert_sample_data_particle(self, data_particle):
        '''
        Verify a particle is a know particle to this driver and verify the particle is  correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''
        if (isinstance(data_particle, ADCPT_EnsembleDataParticle)):
            self.assert_particle_header_sample(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_particle_header_sample(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle: SBE26plusTideSampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.ENSEMBLE_PARSED)
        self.assert_data_particle_parameters(data_particle, self._header_sample_parameters, verify_values)

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

###
#   Driver constant definitions
###

###############################################################################
#                           DATA PARTICLE TEST MIXIN                          #
#     Defines a set of assert methods used for data particle verification     #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.
###############################################################################


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
#                                                                             #
#   These tests are especially useful for testing parsers and other data      #
#   handling.  The tests generally focus on small segments of code, like a    #
#   single function call, but more complex code using Mock objects.  However  #
#   if you find yourself mocking too much maybe it is better as an            #
#   integration test.                                                         #
#                                                                             #
#   Unit tests do not start up external processes like the port agent or      #
#   driver process.                                                           #
###############################################################################
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase,ADCPTMixin):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCmds())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, SAMPLE_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, SAMPLE_RAW_DATA)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, SAMPLE_RAW_DATA, self.assert_particle_header_sample, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_driver_parameters(self):
        """
        Verify the set of parameters known by the driver
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        expected_parameters = sorted(self._driver_parameters.keys())
        reported_parameters = sorted(driver.get_resource(Parameter.ALL))

        log.debug("Reported Parameters: %s" % reported_parameters)
        log.debug("Expected Parameters: %s" % expected_parameters)

        self.assertEqual(reported_parameters, expected_parameters)

        # Verify the parameter definitions
        self.assert_driver_parameter_definition(driver, self._driver_parameters)


    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected. All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['BREAK_ALARM', 'BREAK_SUCCESS'],
            ProtocolState.COMMAND: ['POWERING_DOWN',
                                    'CS',
                                    'SELF_DEPLOY',
                                    'DRIVER_EVENT_GET'],
            ProtocolState.AUTOSAMPLE: ['BREAK_SUCCESS',
                                       'DRIVER_EVENT_GET'],
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    def test_sync_param_dict(self):
        mock_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        saved_values = []
        cached_list = []
        param_dict_list = []
        #save current values in adcpt_cache_dict
        #load adcpt_cache_dict with new values
        #call sync_param_dict
        #get list of adcpt_cache_dict values
        #get list of param_dict values
        #restore original values in adcpt_cache_dict
        
        log.debug("cached values: %s" % cached_list)
        log.debug("param_dict values: %s" % param_dict_list)

        self.assertEqual(cached_list, param_dict_list)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        ###
        #   Add instrument specific code here.
        ###

        self.assert_direct_access_stop_telnet()

    def test_poll(self):
        '''
        No polling for a single sample
        '''

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''

    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        '''
        self.assert_enter_command_mode()

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()
