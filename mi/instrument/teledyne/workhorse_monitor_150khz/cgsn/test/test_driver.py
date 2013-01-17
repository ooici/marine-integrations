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

from random import randint

# Globals
raw_stream_received = False
parsed_stream_received = False

SAMPLE_RAW_DATA = "7F7FF002000612004D008E008001FA01740200003228C941000D041E2D002003600101400900D0070\
114001F000000007D3DD104610301053200620028000006FED0FC090100FF00A148000014800001000C0C0D0D323862000000\
FF050800E014C5EE93EE2300040A000000000000454A4F4B4A4E829F80810088BDB09DFFFFFF9208000000140C0C0D0D323862\
000120FF570089000FFF0080008000800080008000800080008000800080008000800080008000800080008000800080008000\
800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080\
00800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800\
0800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080008000800080\
008000800080008000800080008000800080008000800080008000800080008000800080008000025D585068650D0D2C0C0D0\
C0E0C0E0C0D0C0E0D0C0C0E0E0B0D0E0D0D0D0C0C0C0C0E0F0E0C0D0F0C0D0E0F0D0C0C0D0D0D00000E0D00000D0B00000D0\
C00000C0C00000C0B00000E0C00000D0C00000D0C00000D0C00000C0C00000D0C00000C00000000000000000000000000000\
000000000000000000000035A52675150434B454341484142414841424148414241484142414841424148414241484142414\
8414241484142414741424148414241474142414841434148414241484142414841424148414241484142414841424148414\
24148414241484142414741424148414241484142414741424148414241484100040400005F00006400000064000000640000\
006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400\
00006400000064000000640000006400000064000000640000006400000064000000640000006400000064000000640000006400\
FA604091"

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
        Parameter.TRANSMIT_POWER : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 255},
        Parameter.SPEED_OF_SOUND : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1500},
        Parameter.SALINITY : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 35},
        Parameter.TIME_PER_BURST : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00:00:00:00'},
        Parameter.ENSEMBLES_PER_BURST : {TYPE:int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.TIME_PER_ENSEMBLE : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '01:00:00:00'},
        Parameter.TIME_OF_FIRST_PING : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00/00/00, 00:00:00'},
        Parameter.TIME_OF_FIRST_PING_Y2K : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '0000/00/00, 00:00:00'},
        Parameter.TIME_BETWEEN_PINGS : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '01:20:00'},
        Parameter.REAL_TIME_CLOCK : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00/00/00, 00:00:00'},
        Parameter.REAL_TIME_CLOCK_Y2K : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '0000/00/00, 00:00:00'},
        Parameter.BUFFERED_OUTPUT_PERIOD : {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '00:00:00'},
        Parameter.FALSE_TARGET_THRESHOLD_MAXIMUM : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 50},
        Parameter.LOW_CORRELATION_THRESHOLD : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 64},
        Parameter.ERROR_VELOCITY_THRESHOLD : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 2000},
        Parameter.CLIP_DATA_PAST_BOTTOM : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0},
        Parameter.RECEIVER_GAIN_SELECT : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 1},
        Parameter.WATER_REFERENCE_LAYER : {TYPE: list, READONLY: False, DA: False, STARTUP: False, DEFAULT: [1,5]},
        Parameter.NUMBER_OF_DEPTH_CELLS : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 30},
        Parameter.PINGS_PER_ENSEMBLE : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 45},
        Parameter.DEPTH_CELL_SIZE : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 800 },
        Parameter.TRANSMIT_LENGTH : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.PING_WEIGHT : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.AMBIGUITY_VELOCITY : {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 175},

        Parameter.MODE_1_BANDWIDTH_CONTROL : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1},
        Parameter.BLANK_AFTER_TRANSMIT : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 352},
        Parameter.DATA_OUT : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 111100000},
        Parameter.INSTRUMENT_ID : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 0},
        Parameter.WATER_PROFILING_MODE : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 1}
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
        ADCPT_EnsembleDataParticleKey.CALC_SPD_SND_FROM_DATA : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_DEPTH_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_HEADING_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_PITCH_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_ROLL_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.USE_SALINITY_FROM_SENSOR : {TYPE: bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.USE_TEMPERATURE_FROM_SENSOR : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.DEPTH_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.HEADING_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.PITCH_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.ROLL_SENSOR_AVAIL : {TYPE: bool, 'value': True},
        ADCPT_EnsembleDataParticleKey.SALINITY_SENSOR_AVAIL : {TYPE: bool, 'value': False},
        ADCPT_EnsembleDataParticleKey.TEMPERATURE_SENSOR_AVAIL : {TYPE: bool, 'value': True},
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


###############################################################################
#                                UNIT TESTS                                   #
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
        my_parameters = sorted(driver.get_resource(Parameter.ALL))
        
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
            ProtocolState.UNKNOWN: ['BREAK_ALARM', 'BREAK_SUCCESS','DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['POWERING_DOWN',
                                    'START_AUTOSAMPLE',
                                    'SELF_DEPLOY',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'PROTOCOL_EVENT_QUIT_SESSION'],
            ProtocolState.AUTOSAMPLE: ['BREAK_SUCCESS',
                                       'DRIVER_EVENT_GET'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    def test_build_param_dict(self):
        mock_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        saved_dict = {}
        result_dict = {}
        #save current values in adcpt_cache_dict
        saved_dict.update(adcpt_cache_dict)
        #load adcpt_cache_dict with new values
        for key in adcpt_cache_dict.keys():
            adcpt_cache_dict[key] = randint(0,100)
        #sync _param_dict to adcpt_cache_dict
        protocol._build_param_dict()
        #check if the same dict results
        for key in adcpt_cache_dict.keys():
            result_dict[key] = protocol._param_dict.get(key)
        log.debug("cached values: %s" % adcpt_cache_dict)
        log.debug("param_dict: %s" % result_dict)

        self.assertEqual(adcpt_cache_dict, result_dict)
        #restore original values in adcpt_cache_dict
        adcpt_cache_dict.update(saved_dict)
        
###############################################################################
#                            INTEGRATION TESTS                                #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, ADCPTMixin):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_parameters(self):
        """
        Test driver parameters and verify their type. Startup parameters also verify the parameter
        value. This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        set_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
        # One second later
        expected_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
        print "timestamp: ",expected_time
#        self.assert_set(Parameter.DS_DEVICE_DATE_TIME, set_time, no_get=True)
#        self.assert_get(Parameter.DS_DEVICE_DATE_TIME, expected_time.upper())

        ###
        # Instrument Parameteres
        ###
        self.assert_set(Parameter.SALINITY, 'iontest'.upper())

        ###
        # Set Sample Parameters
        ###
        # Tested in another method

        ###
        # Read only parameters
        ###
        self.assert_set_readonly(Parameter.BLANK_AFTER_TRANSMIT)
        self.assert_set_readonly(Parameter.MODE1_BANDWIDTH_CONTROL)

#  these are cut and paste from sbe26plus. Not used but keep for reference.

    def test_set_sampling(self):
        """
        @brief Test device setsampling.
        
        setsampling functionality now handled via set. Below test converted to use set.
        This tests assumes Conductivity is set to false as described in the IOS, we verify
        this, but don't set it because this is a startup parameter.
        """
        self.assert_initialize_driver()
        self.assert_get(Parameter.CONDUCTIVITY, False)

        self.assert_set_sampling_no_txwavestats()

    def check_state(self, expected_state):
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, expected_state)

    def put_instrument_in_command_mode(self):
        """Wrap the steps and asserts for going into command mode.
           May be used in multiple test cases.
        """
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('connect')

        # Test that the driver protocol is in state unknown.
        self.check_state(ProtocolState.UNKNOWN)

        # Discover what state the instrument is in and set the protocol state accordingly.
        self.driver_client.cmd_dvr('discover_state')

        # Test that the driver protocol is in state command.
        self.check_state(ProtocolState.COMMAND)

    def assert_set_sampling_no_txwavestats(self):
        """
        Test setting parameters, including bad parameter tests, for all parameters in the set
        sampling when txwavestats is set to false.
        
        Parameter set:
        * Tide interval (integer minutes)
        - Range 17 - 720
        * Tide measurement duration (seconds)
        - Range: 10 - 1020 sec
        * Measure wave burst after every N tide samples
        - Range 1 - 10,000
        * Number of wave samples per burst
        - Range 4 - 60,000
        * wave sample duration
        - Range [0.25, 0.5, 0.75, 1.0]
        * use start time - Not set, driver hard codes to false
        - Range [y, n]
        * use stop time - Not set, driver hard codes to false
        - Range [y, n]
        * TXWAVESTATS (real-time wave statistics)
        - Set to False for this test
        """
        log.debug("setsampling Test 1 - TXWAVESTATS = N, small subset of possible parameters.")
        sampling_params = {
            Parameter.TIDE_INTERVAL: 18,
            Parameter.TIDE_MEASUREMENT_DURATION: 60,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: 6000,
            Parameter.WAVE_SAMPLES_PER_BURST: 1000,
            
            # todo: The get command doesn't work for this paramter since it is
            # set to a derived parameter.
            # Parameter.WAVE_SAMPLES_SCANS_PER_SECOND: 4,
            Parameter.TXWAVESTATS: False,
        }

        # First tests to verify we can set all parameters properly
        self.assert_set_bulk(sampling_params)

        # Tide interval parameter. Check edges, out of range and invalid data
        # * Tide interval (integer minutes)
        # - Range 17 - 720
        #sampling_params[Parameter.TIDE_INTERVAL] = 17
        #self.assert_set_bulk(sampling_params)
        #sampling_params[Parameter.TIDE_INTERVAL] = 720
        #self.assert_set_bulk(sampling_params)
        #sampling_params[Parameter.TIDE_INTERVAL] = 16
        #self.assert_set_bulk_exception(sampling_params)
        #sampling_params[Parameter.TIDE_INTERVAL] = 721
        #self.assert_set_bulk_exception(sampling_params)
        #sampling_params[Parameter.TIDE_INTERVAL] = "foo"
        #self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 17

        # Tide measurement duration. Check edges, out of range and invalid data
        # * Tide measurement duration (seconds)
        # - Range: 10 - 1020 sec
        #sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10
        #self.assert_set_bulk(sampling_params)
        #sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1020
        #self.assert_set_bulk(sampling_params)
        #sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 9
        #self.assert_set_bulk_exception(sampling_params)
        #sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1021
        #self.assert_set_bulk_exception(sampling_params)
        #sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = "foo"
        #self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 60

        # Tide samples between wave bursts. Check edges, out of range and invalid data
        # * Measure wave burst after every N tide samples
        # - Range 1 - 10,000
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 1
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 10000
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 10001
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 1

        # Wave samples per burst. Check edges, out of range and invalid data
        # * Number of wave samples per burst
        # - Range 4 - 60,000
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 10
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 43200
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 9
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 43201
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 10

        # Wave samples per burst. Check edges, out of range and invalid data
        # * wave sample duration
        # - Range [0.25, 0.5, 0.75, 1.0]
        # TODO: Enable these tests once the set/get is fixed for this param
        # sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 4
        # self.assert_set_bulk(sampling_params)
        # sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 3
        # self.assert_set_bulk(sampling_params)
        # sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 2
        # self.assert_set_bulk(sampling_params)
        # sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1
        # self.assert_set_bulk(sampling_params)
        # sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 0
        # self.assert_set_bulk_exception(sampling_params)
        # sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = -1
        # self.assert_set_bulk_exception(sampling_params)
        # sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 5
        # self.assert_set_bulk_exception(sampling_params)
        # sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = "foo"
        # self.assert_set_bulk_exception(sampling_params)
        
    def placeholder(self):
        log.debug("TEST 2 - TXWAVESTATS = N, full set of possible parameters")
        ###
        # Test 2: TXWAVESTATS = Y
        # Set:
        # * Tide interval (integer minutes)
        # - Range 1 - 720
        # * Tide measurement duration (seconds)
        # - Range: 10 - 43200 sec
        # * Measure wave burst after every N tide samples
        # - Range 1 - 10,000
        # * Number of wave samples per burst
        # - Range 4 - 60,000
        # * wave sample duration
        # - Range [0.25, 0.5, 0.75, 1.0]
        # - USE WAVE_SAMPLES_SCANS_PER_SECOND instead
        # where WAVE_SAMPLES_SCANS_PER_SECOND = 1 / wave_sample_duration
        # * use start time
        # - Range [y, n]
        # * use stop time
        # - Range [y, n]
        # * TXWAVESTATS (real-time wave statistics)
        # - Range [y, n]
        # OPTIONAL DEPENDING ON TXWAVESTATS
        # * Show progress messages
        # - Range [y, n]
        # * Number of wave samples per burst to use for wave
        # statistics
        # - Range > 512, power of 2...
        # * Use measured temperature and conductivity for
        # density calculation
        # - Range [y,n]
        # * Average water temperature above the pressure sensor
        # - Degrees C
        # * Height of pressure sensor from bottom
        # - Distance Meters
        # * Number of spectral estimates for each frequency
        # band
        # - You may have used Plan Deployment to determine
        # desired value
        # * Minimum allowable attenuation
        # * Minimum period (seconds) to use in auto-spectrum
        # Minimum of the two following
        # - frequency where (measured pressure / pressure at
        # surface) < (minimum allowable attenuation / wave
        # sample duration).
        # - (1 / minimum period). Frequencies > fmax are not
        # processed.
        # * Maximum period (seconds) to use in auto-spectrum
        # - ( 1 / maximum period). Frequencies < fmin are
        # not processed.
        # * Hanning window cutoff
        # - Hanning window suppresses spectral leakage that
        # occurs when time series to be Fourier transformed
        # contains periodic signal that does not correspond
        # to one of exact frequencies of FFT.
        ###
        sampling_params = {
            Parameter.TIDE_INTERVAL : 9,
            Parameter.TIDE_MEASUREMENT_DURATION : 540,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(4.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False,
        }
        #self.assert_set_bulk(sampling_params)

        sampling_params = {
            Parameter.TIDE_INTERVAL : 18, #1,
            Parameter.TIDE_MEASUREMENT_DURATION : 1080,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : True,
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: 10.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION : 1.0,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.HANNING_WINDOW_CUTOFF : 1.0
        }
        #self.assert_set_bulk(sampling_params)

        """
Test 3: These 2 prompts appears only if you enter N for using measured T and C for density calculation
Average water temperature above the pressure sensor (Deg C) = 15.0, new value =
Average salinity above the pressure sensor (PSU) = 35.0, new value =

"""
        sampling_params = {
            Parameter.TIDE_INTERVAL : 18, #4,
            Parameter.TIDE_MEASUREMENT_DURATION : 1080, #40,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : False,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR : float(15.0),
            Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR : float(37.6),
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: 10.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION : 1.0,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.HANNING_WINDOW_CUTOFF : 1.0
        }
        #self.assert_set_bulk(sampling_params)

        """

Test 1B: TXWAVESTATS = N, NEGATIVE TESTING
Set:
* Tide interval (integer minutes)
- Range 1 - 720 (SEND OUT OF RANGE HIGH)
* Tide measurement duration (seconds)
- Range: 10 - 43200 sec (SEND OUT OF RANGE LOW)
* Measure wave burst after every N tide samples
- Range 1 - 10,000 (SEND OUT OF RANGE HIGH)
* Number of wave samples per burst
- Range 4 - 60,000 (SEND OUT OF RANGE LOW)
* wave sample duration
- Range [0.25, 0.5, 0.75, 1.0] (SEND OUT OF RANGE HIGH)
- USE WAVE_SAMPLES_SCANS_PER_SECOND instead
where WAVE_SAMPLES_SCANS_PER_SECOND = 1 / wave_sample_duration
* use start time
- Range [y, n]
* use stop time
- Range [y, n]
* TXWAVESTATS (real-time wave statistics)
"""
        sampling_params = {
            Parameter.TIDE_INTERVAL : 800,
            Parameter.TIDE_MEASUREMENT_DURATION : 1,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 20000,
            Parameter.WAVE_SAMPLES_PER_BURST : 1,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(2.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False,
        }

        #try:
        # #reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.SETSAMPLING, sampling_params)
        # reply = self.driver_client.cmd_dvr('set_resource', sampling_params)
        #except InstrumentParameterException:
        # exception = True
        #self.assertTrue(exception)

    def test_take_sample(self):
        """
@brief execute the take_sample (ts) command and verify that a line with at
least 3 floats is returned, indicating a acceptable sample.
"""
        self.assert_initialize_driver()

        # take a sample.
        sample = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
        log.debug("sample = " + repr(sample[1]))
        TS_REGEX = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)'
        TS_REGEX_MATCHER = re.compile(TS_REGEX)
        matches = TS_REGEX_MATCHER.match(sample[1])

        log.debug("COUNT = " + str(len(matches.groups())))
        self.assertEqual(3, len(matches.groups()))

    def test_init_logging(self):
        """
@brief Test initialize logging command.
"""
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.INIT_LOGGING)
        self.assertTrue(reply)

        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_STATUS)
        self.assert_get(Parameter.LOGGING, True)

    def test_quit_session(self):
        """
@brief Test quit session command.
quit session causes the instrument to enter a timedout state where it uses less power.

this test wakes it up after placing it in the timedout (quit session) state, then
verifies it can obtain paramaters to assert the instrument is working.
"""
        self.assert_initialize_driver()

        # Note quit session just sleeps the device, so its safe to remain in COMMAND mode.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.QUIT_SESSION)

        self.assertEqual(reply, None)

        # Must stay in COMMAND state (but sleeping)
        self.assert_current_state(ProtocolState.COMMAND)
        # now can we return to command state?

        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_STATUS)
        self.assert_get(Parameter.LOGGING, False)

    def test_get_resource_capabilities(self):
        """
        Test get resource capabilities.
        """
        # Test the driver is in state unconfigured.
        self.assert_initialize_driver()

        # COMMAND
        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS', 'DRIVER_EVENT_ACQUIRE_SAMPLE',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 4)

        # Verify all paramaters are present in res_params

        # DS
        self.assertTrue(Parameter.DEVICE_VERSION in res_params)
        self.assertTrue(Parameter.SERIAL_NUMBER in res_params)
        self.assertTrue(Parameter.DS_DEVICE_DATE_TIME in res_params)
        self.assertTrue(Parameter.USER_INFO in res_params)
        self.assertTrue(Parameter.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER in res_params)
        self.assertTrue(Parameter.QUARTZ_PRESSURE_SENSOR_RANGE in res_params)
        self.assertTrue(Parameter.EXTERNAL_TEMPERATURE_SENSOR in res_params)
        self.assertTrue(Parameter.CONDUCTIVITY in res_params)
        self.assertTrue(Parameter.IOP_MA in res_params)
        self.assertTrue(Parameter.VMAIN_V in res_params)
        self.assertTrue(Parameter.VLITH_V in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_P in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_T in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_S in res_params)

        # DS/SETSAMPLING
        self.assertTrue(Parameter.TIDE_INTERVAL in res_params)
        self.assertTrue(Parameter.TIDE_MEASUREMENT_DURATION in res_params)
        self.assertTrue(Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS in res_params)
        self.assertTrue(Parameter.WAVE_SAMPLES_PER_BURST in res_params)
        self.assertTrue(Parameter.WAVE_SAMPLES_SCANS_PER_SECOND in res_params)
        self.assertTrue(Parameter.USE_START_TIME in res_params)
        #Parameter.START_TIME,
        self.assertTrue(Parameter.USE_STOP_TIME in res_params)
        #Parameter.STOP_TIME,
        self.assertTrue(Parameter.TXWAVESTATS in res_params)
        self.assertTrue(Parameter.TIDE_SAMPLES_PER_DAY in res_params)
        self.assertTrue(Parameter.WAVE_BURSTS_PER_DAY in res_params)
        self.assertTrue(Parameter.MEMORY_ENDURANCE in res_params)
        self.assertTrue(Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE in res_params)
        self.assertTrue(Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS in res_params)
        self.assertTrue(Parameter.TOTAL_RECORDED_WAVE_BURSTS in res_params)
        self.assertTrue(Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START in res_params)
        self.assertTrue(Parameter.WAVE_BURSTS_SINCE_LAST_START in res_params)
        self.assertTrue(Parameter.TXREALTIME in res_params)
        self.assertTrue(Parameter.TXWAVEBURST in res_params)
        self.assertTrue(Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS in res_params)
        self.assertTrue(Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC in res_params)
        self.assertTrue(Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC in res_params)
        self.assertTrue(Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR in res_params)
        self.assertTrue(Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR in res_params)
        self.assertTrue(Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM in res_params)
        self.assertTrue(Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND in res_params)
        self.assertTrue(Parameter.MIN_ALLOWABLE_ATTENUATION in res_params)
        self.assertTrue(Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM in res_params)
        self.assertTrue(Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM in res_params)
        self.assertTrue(Parameter.HANNING_WINDOW_CUTOFF in res_params)
        self.assertTrue(Parameter.SHOW_PROGRESS_MESSAGES in res_params)
        self.assertTrue(Parameter.STATUS in res_params)
        self.assertTrue(Parameter.LOGGING in res_params)

        reply = self.driver_client.cmd_dvr('execute_resource', Capability.START_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)


        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_STOP_AUTOSAMPLE']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 1)
        reply = self.driver_client.cmd_dvr('execute_resource', Capability.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)


        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS', 'DRIVER_EVENT_ACQUIRE_SAMPLE',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 4)

    def test_connect_configure_disconnect(self):
        """
        @brief connect and then disconnect, verify state
        """
        self.assert_initialize_driver()

        reply = self.driver_client.cmd_dvr('disconnect')
        self.assertEqual(reply, None)

        self.assert_current_state(DriverConnectionState.DISCONNECTED)

    def test_bad_commands(self):
        """
        @brief test that bad commands are handled with grace and style.
        """
        print ">>>>>>>>>>>>>>>>>>>>>>>>> got to test_bad_commands"
        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Test bad commands in UNCONFIGURED state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr('conquer_the_world')
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("1 - conquer_the_world - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

        # Test the driver is configured for comms.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        self.check_state(DriverConnectionState.DISCONNECTED)

        # Test bad commands in DISCONNECTED state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr('test_the_waters')
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("2 - test_the_waters - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)


        # Test the driver is in unknown state.
        reply = self.driver_client.cmd_dvr('connect')
        self.check_state(ProtocolState.UNKNOWN)

        # Test bad commands in UNKNOWN state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr("skip_to_the_loo")
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("3 - skip_to_the_loo - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)



        # Test the driver is in command mode.
        reply = self.driver_client.cmd_dvr('discover_state')

        self.check_state(ProtocolState.COMMAND)


        # Test bad commands in COMMAND state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr("... --- ..., ... --- ...")
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("4 - ... --- ..., ... --- ... - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

    def test_poll(self):
        """
@brief Test sample polling commands and events.
also tests execute_resource
"""
        # Test the driver is in state unconfigured.
        self.put_instrument_in_command_mode()


        # Poll for a sample and confirm result.
        sample1 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE1 = " + str(sample1[1]))

        # Poll for a sample and confirm result.
        sample2 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE2 = " + str(sample2[1]))

        # Poll for a sample and confirm result.
        sample3 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE3 = " + str(sample3[1]))

        TS_REGEX = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)'
        TS_REGEX_MATCHER = re.compile(TS_REGEX)

        matches1 = TS_REGEX_MATCHER.match(sample1[1])
        self.assertEqual(3, len(matches1.groups()))

        matches2 = TS_REGEX_MATCHER.match(sample2[1])
        self.assertEqual(3, len(matches2.groups()))

        matches3 = TS_REGEX_MATCHER.match(sample3[1])
        self.assertEqual(3, len(matches3.groups()))




        # Confirm that 3 samples arrived as published events.
        gevent.sleep(1)
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]

        self.assertEqual(len(sample_events), 12)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

    def test_connect(self):
        """
        Test configuring and connecting to the device through the port
        agent. Discover device state.
        """
        log.info("test_connect test started")
        self.put_instrument_in_command_mode()

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

    def test_clock_sync(self):
        self.put_instrument_in_command_mode()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)
        self.check_state(ProtocolState.COMMAND)


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
