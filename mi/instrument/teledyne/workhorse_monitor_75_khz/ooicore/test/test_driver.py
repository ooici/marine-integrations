"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_driver
@file marine-integrations/mi/instrument/teledyne/workhorse_monitor_75_khz/ooicore/driver.py
@author Lytle Johnson
@brief Test cases for ooicore driver

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


from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.chunker import StringChunker
from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey


from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import InstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import InstrumentCmds
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ProtocolState
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Capability
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Protocol
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_EnsembleDataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_EnsembleDataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_CalibrationDataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_CalibrationDataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PS0DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PS0DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PS3DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PS3DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_FDDataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_FDDataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PT200DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PT200DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import NEWLINE
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import adcpt_cache_dict

from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import SAMPLE_RAW_DATA 
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import CALIBRATION_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import PS0_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import PS3_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import FD_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import PT200_RAW_DATA

from random import randint

# Globals
raw_stream_received = False
parsed_stream_received = False

###
#   Driver parameters for tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver ',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'HTWZMW',
    instrument_agent_name = 'teledyne_workhorse_monitor_75_khz_ooicore',
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
    EF_CHAR = '?'
    _calibration_data_parameters = {
        ADCPT_CalibrationDataParticleKey.CALIBRATION_DATA: {'type': unicode, 'value': \
            "ACTIVE FLUXGATE CALIBRATION MATRICES in NVRAM" + NEWLINE + \
            "               Calibration date and time: 9/14/2012  09:25:32" + NEWLINE + \
            "                             S inverse" + NEWLINE + \
            "          " + EF_CHAR + "                                                  " + EF_CHAR + "" + NEWLINE + \
            "     Bx   " + EF_CHAR + "   3.9218e-01  3.9660e-01 -3.1681e-02  6.4332e-03 " + EF_CHAR + "" + NEWLINE + \
            "     By   " + EF_CHAR + "  -2.4320e-02 -1.0376e-02 -2.2428e-03 -6.0628e-01 " + EF_CHAR + "" + NEWLINE + \
            "     Bz   " + EF_CHAR + "   2.2453e-01 -2.1972e-01 -2.7990e-01 -2.4339e-03 " + EF_CHAR + "" + NEWLINE + \
            "     Err  " + EF_CHAR + "   4.6514e-01 -4.0455e-01  6.9083e-01 -1.4291e-02 " + EF_CHAR + "" + NEWLINE + \
            "          " + EF_CHAR + "                                                  " + EF_CHAR + "" + NEWLINE + \
            "                             Coil Offset" + NEWLINE + \
            "                         " + EF_CHAR + "                " + EF_CHAR + "" + NEWLINE + \
            "                         " + EF_CHAR + "   3.4233e+04   " + EF_CHAR + "" + NEWLINE + \
            "                         " + EF_CHAR + "   3.4449e+04   " + EF_CHAR + "" + NEWLINE + \
            "                         " + EF_CHAR + "   3.4389e+04   " + EF_CHAR + "" + NEWLINE + \
            "                         " + EF_CHAR + "   3.4698e+04   " + EF_CHAR + "" + NEWLINE + \
            "                         " + EF_CHAR + "                " + EF_CHAR + "" + NEWLINE + \
            "                             Electrical Null" + NEWLINE + \
            "                              " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
            "                              " + EF_CHAR + " 34285 " + EF_CHAR + "" + NEWLINE + \
            "                              " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
            "                    TILT CALIBRATION MATRICES in NVRAM" + NEWLINE + \
            "                Calibration date and time: 9/14/2012  09:14:45" + NEWLINE + \
            "              Average Temperature During Calibration was   24.4 " + EF_CHAR + "C" + NEWLINE + \
            NEWLINE + \
            "                   Up                              Down" + NEWLINE + \
            NEWLINE + \
            "        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
            " Roll   " + EF_CHAR + "   7.4612e-07  -3.1727e-05 " + EF_CHAR + "     " + EF_CHAR + "  -3.0054e-07   3.2190e-05 " + EF_CHAR + "" + NEWLINE + \
            " Pitch  " + EF_CHAR + "  -3.1639e-05  -6.3505e-07 " + EF_CHAR + "     " + EF_CHAR + "  -3.1965e-05  -1.4881e-07 " + EF_CHAR + "" + NEWLINE + \
            "        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
            NEWLINE + \
            "        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
            " Offset " + EF_CHAR + "   3.2808e+04   3.2568e+04 " + EF_CHAR + "     " + EF_CHAR + "   3.2279e+04   3.3047e+04 " + EF_CHAR + "" + NEWLINE + \
            "        " + EF_CHAR + "                           " + EF_CHAR + "     " + EF_CHAR + "                           " + EF_CHAR + "" + NEWLINE + \
            NEWLINE + \
            "                             " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
            "                      Null   " + EF_CHAR + " 33500 " + EF_CHAR + "" + NEWLINE + \
            "                             " + EF_CHAR + "       " + EF_CHAR + "" + NEWLINE + \
            NEWLINE + \
            NEWLINE + \
            NEWLINE + \
            NEWLINE + \
            NEWLINE}
        }


    _ps0_parameters = {
        ADCPT_PS0DataParticleKey.PS0_DATA: {'type': unicode, 'value': 
            "Instrument S/N:  18444" + NEWLINE +\
            "       Frequency:  76800 HZ" + NEWLINE +\
            "   Configuration:  4 BEAM, JANUS" + NEWLINE +\
            "     Match Layer:  10" + NEWLINE +\
            "      Beam Angle:  20 DEGREES" + NEWLINE +\
            "    Beam Pattern:  CONVEX" + NEWLINE +\
            "     Orientation:  UP" + NEWLINE +\
            "       Sensor(s):  HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" + NEWLINE +\
            "Pressure Sens Coefficients:" + NEWLINE +\
            "              c3 = -1.927850E-11" + NEWLINE +\
            "              c2 = +1.281892E-06" + NEWLINE +\
            "              c1 = +1.375793E+00" + NEWLINE +\
            "          Offset = +2.813725E+00" + NEWLINE +\
            NEWLINE +\
            "Temp Sens Offset:  -0.01 degrees C" + NEWLINE +\
            NEWLINE +\
            "    CPU Firmware:  50.40 [0]" + NEWLINE +\
            "   Boot Code Ver:  Required:  1.16   Actual:  1.16" + NEWLINE +\
            "    DEMOD #1 Ver:  ad48, Type:  1f" + NEWLINE +\
            "    DEMOD #2 Ver:  ad48, Type:  1f" + NEWLINE +\
            "    PWRTIMG  Ver:  85d3, Type:   7" + NEWLINE +\
            NEWLINE +\
            "Board Serial Number Data:" + NEWLINE +\
            "   72  00 00 06 FE BC D8  09 HPA727-3009-00B" + NEWLINE +\
            "   81  00 00 06 F5 CD 9E  09 REC727-1004-06A" + NEWLINE +\
            "   A5  00 00 06 FF 1C 79  09 HPI727-3007-00A" + NEWLINE +\
            "   82  00 00 06 FF 23 E5  09 CPU727-2011-00E" + NEWLINE +\
            "   07  00 00 06 F6 05 15  09 TUN727-1005-06A" + NEWLINE +\
            "   DB  00 00 06 F5 CB 5D  09 DSP727-2001-06H" + NEWLINE }
        }

    _ps3_parameters = {
        ADCPT_PS3DataParticleKey.PS3_DATA: {'type': unicode, 'value': 
            "Beam Width:   3.7 degrees" + NEWLINE +\
            NEWLINE +\
            "Beam     Elevation     Azimuth" + NEWLINE +\
            "  1         -70.00      270.00" + NEWLINE +\
            "  2         -70.00       90.00" + NEWLINE +\
            "  3         -70.00        0.01" + NEWLINE +\
            "  4         -70.00      180.00" + NEWLINE +\
            NEWLINE +\
            "Beam Directional Matrix (Down):" + NEWLINE +\
            "  0.3420    0.0000    0.9397    0.2419" + NEWLINE +\
            " -0.3420    0.0000    0.9397    0.2419" + NEWLINE +\
            "  0.0000   -0.3420    0.9397   -0.2419" + NEWLINE +\
            "  0.0000    0.3420    0.9397   -0.2419" + NEWLINE +\
            NEWLINE +\
            "Instrument Transformation Matrix (Down):    Q14:" + NEWLINE +\
            "  1.4619   -1.4619    0.0000    0.0000       23952  -23952       0       0" + NEWLINE +\
            "  0.0000    0.0000   -1.4619    1.4619           0       0  -23952   23952" + NEWLINE +\
            "  0.2661    0.2661    0.2661    0.2661        4359    4359    4359    4359" + NEWLINE +\
            "  1.0337    1.0337   -1.0337   -1.0337       16936   16936  -16936  -16936" + NEWLINE +\
            "Beam Angle Corrections Are Loaded." + NEWLINE  }
    }       
        
    _fd_parameters = {
        ADCPT_FDDataParticleKey.FD_DATA: {'type': unicode, 'value': 
            "Total Unique Faults   =     2" + NEWLINE +\
            "Overflow Count        =     0" + NEWLINE +\
            "Time of first fault:    13/02/11,10:05:43.29" + NEWLINE +\
            "Time of last fault:     13/02/22,12:59:26.80" + NEWLINE +\
            NEWLINE +\
            "Fault Log:" + NEWLINE +\
            "Entry #  0 Code=0a08h  Count=    5  Delta=7679898 Time=13/02/22,12:59:26.66" + NEWLINE +\
            " Parameter = 00000000h" + NEWLINE +\
            "  Tilt axis X over range." + NEWLINE +\
            "Entry #  1 Code=0a09h  Count=    5  Delta=7679899 Time=13/02/22,12:59:26.80" + NEWLINE +\
            " Parameter = 00000000h" + NEWLINE +\
            "  Tilt axis Y over range." + NEWLINE +\
            "End of fault log." + NEWLINE + NEWLINE}
        }

    _pt200_parameters = {
        ADCPT_PT200DataParticleKey.PT200_DATA: {'type': unicode, 'value': 
            "Ambient  Temperature =    18.44 Degrees C" + NEWLINE +\
            "  Attitude Temperature =    21.55 Degrees C" + NEWLINE +\
            "  Internal Moisture    = 8F26h" + NEWLINE +\
            "" + NEWLINE +\
            "Correlation Magnitude: Narrow Bandwidth" + NEWLINE +\
            "" + NEWLINE +\
            "               Lag  Bm1  Bm2  Bm3  Bm4" + NEWLINE +\
            "                 0  255  255  255  255" + NEWLINE +\
            "                 1  153  136  134  164" + NEWLINE +\
            "                 2   66   39   77   48" + NEWLINE +\
            "                 3   54    3   43   43" + NEWLINE +\
            "                 4   43   15   21   62" + NEWLINE +\
            "                 5   29   17    8   38" + NEWLINE +\
            "                 6   24    7    3   63" + NEWLINE +\
            "                 7   15    7   12   83" + NEWLINE +\
            "" + NEWLINE +\
            "  High Gain RSSI:    63   58   74   73" + NEWLINE +\
            "   Low Gain RSSI:     6    7   10    8" + NEWLINE +\
            "" + NEWLINE +\
            "  SIN Duty Cycle:    49   49   50   49" + NEWLINE +\
            "  COS Duty Cycle:    50   48   50   49" + NEWLINE +\
            "" + NEWLINE +\
            "Receive Test Results = $00020000 ... FAIL" + NEWLINE +\
            "" + NEWLINE +\
            "IXMT    =      5.4 Amps rms  [Data=7bh]" + NEWLINE +\
            "VXMT    =    387.2 Volts rms [Data=b9h]" + NEWLINE +\
            "   Z    =     71.8 Ohms" + NEWLINE +\
            "Transmit Test Results = $0 ... PASS" + NEWLINE +\
            "" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "   12   12   12   12" + NEWLINE +\
            "  255  255  255  255" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "   12   12   12   12" + NEWLINE +\
            "  255  255  255  255" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "    0    0    0    0" + NEWLINE +\
            "   12   12   12   12" + NEWLINE +\
            "  255  255  255  255" + NEWLINE +\
            "Electronics Test Results = $00000000" + NEWLINE +\
            "Receive Bandwidth:" + NEWLINE +\
            "    Sample      bw    bw    bw    bw    bw" + NEWLINE +\
            "      rate  expect   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
            "        19       7     4     6     5     3 Khz" + NEWLINE +\
            "   results          PASS  PASS  PASS  FAIL" + NEWLINE +\
            "RSSI Time Constant:" + NEWLINE +\
            "" + NEWLINE +\
            "RSSI Filter Strobe 1 =   38400 Hz" + NEWLINE +\
            "  time   Bm1   Bm2   Bm3   Bm4" + NEWLINE +\
            "  msec  cnts  cnts  cnts  cnts" + NEWLINE +\
            "     1     7     8     8     8" + NEWLINE +\
            "     2    12    15    14    15" + NEWLINE +\
            "     3    16    20    20    22" + NEWLINE +\
            "     4    21    25    25    27" + NEWLINE +\
            "     5    24    29    29    31" + NEWLINE +\
            "     6    27    32    33    35" + NEWLINE +\
            "     7    30    35    36    38" + NEWLINE +\
            "     8    32    37    39    41" + NEWLINE +\
            "     9    34    39    41    43" + NEWLINE +\
            "    10    35    41    43    45" + NEWLINE +\
            "   nom    45    49    54    55" + NEWLINE +\
            "result    PASS  PASS  PASS  PASS" + NEWLINE}
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
        elif (isinstance(data_particle, ADCPT_CalibrationDataParticle)):
            self.assert_particle_calibration_data(data_particle)
        elif (isinstance(data_particle, ADCPT_PS0DataParticle)):
            self.assert_particle_ps0_data(data_particle)
        elif (isinstance(data_particle, ADCPT_PS3DataParticle)):
            self.assert_particle_ps3_data(data_particle)
        elif (isinstance(data_particle, ADCPT_FDDataParticle)):
            self.assert_particle_fd_data(data_particle)
        elif (isinstance(data_particle, ADCPT_PT200DataParticle)):
            self.assert_particle_py200_data(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_particle_header_sample(self, data_particle, verify_values = False):
        '''
        Verify an adcpt ensemble data particle
        @param data_particle: ADCPT_EnsembleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.ENSEMBLE_PARSED)
        self.assert_data_particle_parameters(data_particle, self._header_sample_parameters, verify_values)

    def assert_particle_calibration_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt calibration data particle
        @param data_particle: ADCPT_CalibrationDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.CALIBRATION_PARSED)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    def assert_particle_ps0_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt ps0 data particle
        @param data_particle: ADCPT_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.PS0_PARSED)
        self.assert_data_particle_parameters(data_particle, self._ps0_parameters, verify_values)

    def assert_particle_ps3_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt ps3 data particle
        @param data_particle: ADCPT_PS3DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.PS3_PARSED)
        self.assert_data_particle_parameters(data_particle, self._ps3_parameters, verify_values)

    def assert_particle_fd_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt fd data particle
        @param data_particle: ADCPT_FDDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.FD_PARSED)
        self.assert_data_particle_parameters(data_particle, self._fd_parameters, verify_values)

    def assert_particle_pt200_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt pt200 data particle
        @param data_particle: ADCPT_PT200DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.PT200_PARSED)
        self.assert_data_particle_parameters(data_particle, self._pt200_parameters, verify_values)


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

        # TODO: need to work out where to tweek data from instrument to remove the evil character thats borks it
        #self.assert_chunker_sample(chunker, CALIBRATION_RAW_DATA)
        #self.assert_chunker_sample_with_noise(chunker, CALIBRATION_RAW_DATA)
        #self.assert_chunker_fragmented_sample(chunker, CALIBRATION_RAW_DATA)
        #self.assert_chunker_combined_sample(chunker, CALIBRATION_RAW_DATA)
 
        self.assert_chunker_sample(chunker, PS0_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, PS0_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, PS0_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, PS0_RAW_DATA)

        self.assert_chunker_sample(chunker, PS3_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, PS3_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, PS3_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, PS3_RAW_DATA)

        self.assert_chunker_sample(chunker, FD_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, FD_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, FD_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, FD_RAW_DATA)

        self.assert_chunker_sample(chunker, PT200_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, PT200_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, PT200_RAW_DATA)
        self.assert_chunker_combined_sample(chunker, PT200_RAW_DATA)

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
        self.assert_particle_published(driver, CALIBRATION_RAW_DATA, self.assert_particle_calibration_data, True)
        self.assert_particle_published(driver, PS0_RAW_DATA, self.assert_particle_ps0_data, True)
        self.assert_particle_published(driver, PS3_RAW_DATA, self.assert_particle_ps3_data, True)
        self.assert_particle_published(driver, FD_RAW_DATA, self.assert_particle_fd_data, True)
        self.assert_particle_published(driver, PT200_RAW_DATA, self.assert_particle_pt200_data, True)

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

        """
        ### This section of code left in but commented out;
        ### might be of use in expanding tests.
        set_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
        # One second later
        expected_time = get_timestamp_delayed("%d %b %Y %H:%M:%S")
        print "timestamp: ",expected_time
        self.assert_set(Parameter.DS_DEVICE_DATE_TIME, set_time, no_get=True)
        self.assert_get(Parameter.DS_DEVICE_DATE_TIME, expected_time.upper())
        """

        ###
        # Instrument Parameteres
        ###
        self.assert_set(Parameter.SALINITY, 35)  # 'iontest'.upper()

        ###
        # Set Sample Parameters
        ###
        # Tested in another method

        ###
        # Read only parameters
        ###
        # TODO: re-enable below and expand.
        #self.assert_set_readonly(Parameter.MODE_1_BANDWIDTH_CONTROL)
        #self.assert_set_readonly(Parameter.BLANK_AFTER_TRANSMIT)
        #self.assert_set_readonly(Parameter.DATA_OUT)
        #self.assert_set_readonly(Parameter.INSTRUMENT_ID)
        #self.assert_set_readonly(Parameter.WATER_PROFILING_MODE)

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
        log.debug("test_direct_access_telnet_mode 1")
        self.assert_direct_access_start_telnet()
        log.debug("test_direct_access_telnet_mode 2")
        self.assertTrue(self.tcp_client)
        log.debug("test_direct_access_telnet_mode 3")

        ###
        #   Add instrument specific code here.
        ###

        self.assert_direct_access_stop_telnet()
        log.debug("test_direct_access_telnet_mode 4")

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
