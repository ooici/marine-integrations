"""
@package mi.instrument.teledyne.workhorse_monitor_75_khz.bep.test.test_driver
@author Roger Unwin
@brief Test cases for InstrumentDriver
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import unittest
from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.chunker import StringChunker

from mi.core.log import get_logger; log = get_logger()

from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import WorkhorseDriverUnitTest
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import WorkhorseDriverIntegrationTest
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import WorkhorseDriverQualificationTest
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import WorkhorseDriverPublicationTest
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_driver import DataParticleType
from mi.idk.unit_test import InstrumentDriverTestCase

from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import CG_SAMPLE_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import CG_SAMPLE_RAW_DATA2
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import CG_CALIBRATION_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.test.test_data import CG_PS0_RAW_DATA

from mi.idk.unit_test import DriverTestMixin

from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import NEWLINE
from mi.instrument.teledyne.driver import ScheduledJob
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Capability
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import InstrumentCmds

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_PD0_PARSED_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_PD0_PARSED_DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle

from mi.instrument.teledyne.workhorse_monitor_75_khz.bep.driver import InstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_75_khz.bep.driver import Protocol

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ProtocolState
###
#   Driver parameters for tests
###

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.teledyne.workhorse_monitor_75_khz.bep.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'HTWZMW',
    instrument_agent_preload_id = 'IA7',
    instrument_agent_name = 'teledyne_workhorse_monitor_75_khz_cgsn',
    instrument_agent_packet_config = DataParticleType(),

    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            Parameter.SERIAL_FLOW_CONTROL: '11110',
            Parameter.BANNER: False,
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 0,
            Parameter.SAVE_NVRAM_TO_RECORDER: True,
            Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1485,
            Parameter.PITCH: 0,
            Parameter.ROLL: 0,
            Parameter.SALINITY: 35,

            # first 2 bits represent beam vs earth
            Parameter.COORDINATE_TRANSFORMATION: '11111',
            Parameter.TIME_PER_ENSEMBLE: '00:00:00.00',
            Parameter.TIME_PER_PING: '00:01.00',
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
        },
        DriverStartupConfigKey.SCHEDULER: {
            ScheduledJob.GET_CALIBRATION: {},
            ScheduledJob.GET_CONFIGURATION: {},
            ScheduledJob.CLOCK_SYNC: {}
        }
    }
)
###################################################################

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
    Mixin class used for storing data particle constance
    and common data assertion methods.
    '''
    # Create some short names for the parameter test config
    TYPE      = ParameterTestConfigKey.TYPE
    READONLY  = ParameterTestConfigKey.READONLY
    STARTUP   = ParameterTestConfigKey.STARTUP
    DA        = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE     = ParameterTestConfigKey.VALUE
    REQUIRED  = ParameterTestConfigKey.REQUIRED
    DEFAULT   = ParameterTestConfigKey.DEFAULT
    STATES    = ParameterTestConfigKey.STATES 

    ###
    # Parameter and Type Definitions
    ###
    # Is DEFAULT the DEFAULT STARTUP VALUE?
    _driver_parameters = {
        Parameter.SERIAL_DATA_OUT: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: False},
        Parameter.SERIAL_FLOW_CONTROL: {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: '11110'},
        Parameter.SAVE_NVRAM_TO_RECORDER: {TYPE: bool, READONLY: True, DA: False, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.TIME: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: False},
        Parameter.SERIAL_OUT_FW_SWITCHES: {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: '111100000'},
        Parameter.WATER_PROFILING_MODE: {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},

        Parameter.BANNER: {TYPE: bool, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.INSTRUMENT_ID: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.SLEEP_ENABLE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.POLLED_MODE: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.XMIT_POWER: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 255, VALUE: 255},
        Parameter.SPEED_OF_SOUND: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1485, VALUE: 1485},
        Parameter.PITCH: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.ROLL: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.SALINITY: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 35, VALUE: 35},
        Parameter.COORDINATE_TRANSFORMATION: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: '11111', VALUE: '11111'},
        Parameter.SENSOR_SOURCE: {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: False, VALUE: "1111101"}, 
        Parameter.TIME_PER_ENSEMBLE: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '00:00:00.00'},
        Parameter.TIME_OF_FIRST_PING: {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: False}, # STARTUP: True, VALUE: '****/**/**,**:**:**'
        Parameter.TIME_PER_PING: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '00:01.00'},
        Parameter.FALSE_TARGET_THRESHOLD: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '050,001'},
        Parameter.BANDWIDTH_CONTROL: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.CORRELATION_THRESHOLD: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 64},
        Parameter.ERROR_VELOCITY_THRESHOLD: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 2000},
        Parameter.BLANK_AFTER_TRANSMIT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 704},
        Parameter.CLIP_DATA_PAST_BOTTOM: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.RECEIVER_GAIN_SELECT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},
        Parameter.WATER_REFERENCE_LAYER: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '001,005'},
        Parameter.NUMBER_OF_DEPTH_CELLS: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 100},
        Parameter.PINGS_PER_ENSEMBLE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},
        Parameter.DEPTH_CELL_SIZE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 800},
        Parameter.TRANSMIT_LENGTH: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.PING_WEIGHT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.AMBIGUITY_VELOCITY: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 175}
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.START_AUTOSAMPLE: { STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.STOP_AUTOSAMPLE: { STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.CLOCK_SYNC: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_CALIBRATION: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_CONFIGURATION: { STATES: [ProtocolState.COMMAND]},
        Capability.SAVE_SETUP_TO_RAM: { STATES: [ProtocolState.COMMAND]},
        Capability.SEND_LAST_SAMPLE: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_ERROR_STATUS_WORD: { STATES: [ProtocolState.COMMAND]},
        Capability.CLEAR_ERROR_STATUS_WORD: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_FAULT_LOG: { STATES: [ProtocolState.COMMAND]},
        Capability.CLEAR_FAULT_LOG: { STATES: [ProtocolState.COMMAND]},
        Capability.GET_INSTRUMENT_TRANSFORM_MATRIX: { STATES: [ProtocolState.COMMAND]},
        Capability.RUN_TEST_200: { STATES: [ProtocolState.COMMAND]},
    }

    #name, type done, value pending
    EF_CHAR = '\xef'
    _calibration_data_parameters = {
        ADCP_COMPASS_CALIBRATION_KEY.FLUXGATE_CALIBRATION_TIMESTAMP: {'type': float, 'value': 1355526119.0 },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BX: {'type': list, 'value': [0.45971, -0.43188, 0.025594, -0.0064585] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BY: {'type': list, 'value': [-0.030328, 0.030124, -0.040265, 0.60791] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BZ: {'type': list, 'value': [0.23864, 0.22808, 0.32896, 0.024285]     },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_ERR: {'type': list, 'value': [0.50144, 0.49284, -0.70207, -0.045907] },
        ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET: {'type': list, 'value': [34143.0, 33943.0, 34059.0, 33528.0] },
        ADCP_COMPASS_CALIBRATION_KEY.ELECTRICAL_NULL: {'type': float, 'value': 34441.0 },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_CALIBRATION_TIMESTAMP: {'type': float, 'value': 1355525719.0 },
        ADCP_COMPASS_CALIBRATION_KEY.CALIBRATION_TEMP: {'type': float, 'value': 23.3 },
        ADCP_COMPASS_CALIBRATION_KEY.ROLL_UP_DOWN: {'type': list, 'value': [-3.7232e-08, -2.8741e-05, -1.0957e-08, 3.0921e-05] },
        ADCP_COMPASS_CALIBRATION_KEY.PITCH_UP_DOWN: {'type': list, 'value': [-2.8553e-05, 1.2566e-07, -3.1241e-05, -4.9307e-08] },
        ADCP_COMPASS_CALIBRATION_KEY.OFFSET_UP_DOWN: {'type': list, 'value': [33216.0, 33314.0, 33685.0, 32469.0] },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_NULL: {'type': float, 'value': 33459.0 }
    }

    #name, type done, value pending
    _system_configuration_data_parameters = {
        ADCP_SYSTEM_CONFIGURATION_KEY.SERIAL_NUMBER: {'type': unicode, 'value': "18919" },
        ADCP_SYSTEM_CONFIGURATION_KEY.TRANSDUCER_FREQUENCY: {'type': int, 'value': 76800 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.CONFIGURATION: {'type': unicode, 'value': "4 BEAM, JANUS" },
        ADCP_SYSTEM_CONFIGURATION_KEY.MATCH_LAYER: {'type': unicode, 'value': "10" },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_ANGLE: {'type': int, 'value': 20 },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_PATTERN: {'type': unicode, 'value': "CONVEX" },
        ADCP_SYSTEM_CONFIGURATION_KEY.ORIENTATION: {'type': unicode, 'value': "UP" },
        ADCP_SYSTEM_CONFIGURATION_KEY.SENSORS: {'type': unicode, 'value': "HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c3: {'type': float, 'value': +4.074753E-12 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c2: {'type': float, 'value': +8.083932E-07 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c1: {'type': float, 'value': +1.241627E+00 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_OFFSET: {'type': float, 'value': +3.805579E+00 },
        ADCP_SYSTEM_CONFIGURATION_KEY.TEMPERATURE_SENSOR_OFFSET: {'type': float, 'value': -0.08 },
        ADCP_SYSTEM_CONFIGURATION_KEY.CPU_FIRMWARE: {'type': unicode, 'value': "50.40 [0]" },
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_REQUIRED: {'type': unicode, 'value': "1.16" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_ACTUAL: {'type': unicode, 'value': "1.16" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_VERSION: {'type': unicode, 'value': "ad48" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_TYPE: {'type': unicode, 'value': "1f" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_VERSION: {'type': unicode, 'value': "ad48" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_TYPE: {'type': unicode, 'value': "1f" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_VERSION: {'type': unicode, 'value': "85d3" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_TYPE: {'type': unicode, 'value': "7" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS: {'type': unicode, 'value': u'B3  00 00 06 FF 2A 00  09 DSP727-2001-06H\n' + \
                                                                                        '2D  00 00 06 F6 17 D8  09 TUN727-1005-06X\n' + \
                                                                                        '2E  00 00 06 FF 25 54  09 CPU727-2011-00E\n' + \
                                                                                        '3C  00 00 06 FF 2E 3C  09 HPA727-3009-00B \n' + \
                                                                                        'C2  00 00 06 FF 09 46  09 HPI727-3007-00A\n' + \
                                                                                        'D5  00 00 06 FF 06 E9  09 REC727-1004-06A'}
        }

    #name, type done, value pending
    _pd0_parameters_base = {
        ADCP_PD0_PARSED_KEY.HEADER_ID: {'type': int, 'value': 127 },
        ADCP_PD0_PARSED_KEY.DATA_SOURCE_ID: {'type': int, 'value': 127 },
        ADCP_PD0_PARSED_KEY.NUM_BYTES: {'type': int, 'value': 26632 },
        ADCP_PD0_PARSED_KEY.NUM_DATA_TYPES: {'type': int, 'value': 6 },
        ADCP_PD0_PARSED_KEY.OFFSET_DATA_TYPES: {'type': list, 'value': [18, 77, 142, 944, 1346, 1748, 2150] },
        ADCP_PD0_PARSED_KEY.FIXED_LEADER_ID: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.FIRMWARE_VERSION: {'type': int, 'value': 50 },
        ADCP_PD0_PARSED_KEY.FIRMWARE_REVISION: {'type': int, 'value': 40 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_FREQUENCY: {'type': int, 'value': 150 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_BEAM_PATTERN: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_SENSOR_CONFIG: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_HEAD_ATTACHED: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SYSCONFIG_VERTICAL_ORIENTATION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.DATA_FLAG: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.LAG_LENGTH: {'type': int, 'value': 53 },
        ADCP_PD0_PARSED_KEY.NUM_BEAMS: {'type': int, 'value': 4 },
        ADCP_PD0_PARSED_KEY.NUM_CELLS: {'type': int, 'value': 100 },
        ADCP_PD0_PARSED_KEY.PINGS_PER_ENSEMBLE: {'type': int, 'value': 256 },
        ADCP_PD0_PARSED_KEY.DEPTH_CELL_LENGTH: {'type': int, 'value': 32780 },
        ADCP_PD0_PARSED_KEY.BLANK_AFTER_TRANSMIT: {'type': int, 'value': 49154 },
        ADCP_PD0_PARSED_KEY.SIGNAL_PROCESSING_MODE: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.LOW_CORR_THRESHOLD: {'type': int, 'value': 64 },
        ADCP_PD0_PARSED_KEY.NUM_CODE_REPETITIONS: {'type': int, 'value': 17 },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_MIN: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ERROR_VEL_THRESHOLD: {'type': int, 'value': 53255 },
        ADCP_PD0_PARSED_KEY.TIME_PER_PING_MINUTES: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.TIME_PER_PING_SECONDS: {'type': float, 'value': 1.0 },
        ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_TYPE: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_TILTS: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_BEAMS: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.COORD_TRANSFORM_MAPPING: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.HEADING_ALIGNMENT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.HEADING_BIAS: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_SPEED: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_DEPTH: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_HEADING: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_PITCH: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_ROLL: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_CONDUCTIVITY: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SENSOR_SOURCE_TEMPERATURE: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_DEPTH: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_HEADING: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_PITCH: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_ROLL: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_CONDUCTIVITY: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SENSOR_AVAILABLE_TEMPERATURE: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.BIN_1_DISTANCE: {'type': int, 'value': 60175 },
        ADCP_PD0_PARSED_KEY.TRANSMIT_PULSE_LENGTH: {'type': int, 'value': 4109 },
        ADCP_PD0_PARSED_KEY.REFERENCE_LAYER_START: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.REFERENCE_LAYER_STOP: {'type': int, 'value': 5 },
        ADCP_PD0_PARSED_KEY.FALSE_TARGET_THRESHOLD: {'type': int, 'value': 50 },
        ADCP_PD0_PARSED_KEY.LOW_LATENCY_TRIGGER: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.TRANSMIT_LAG_DISTANCE: {'type': int, 'value': 50688 },
        ADCP_PD0_PARSED_KEY.CPU_BOARD_SERIAL_NUMBER: {'type': long, 'value': 9367487254980977929L },
        ADCP_PD0_PARSED_KEY.SYSTEM_BANDWIDTH: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SYSTEM_POWER: {'type': int, 'value': 255 },
        ADCP_PD0_PARSED_KEY.SERIAL_NUMBER: {'type': int, 'value': 206045184 },
        ADCP_PD0_PARSED_KEY.BEAM_ANGLE: {'type': int, 'value': 20 },
        ADCP_PD0_PARSED_KEY.VARIABLE_LEADER_ID: {'type': int, 'value': 128 },
        ADCP_PD0_PARSED_KEY.ENSEMBLE_NUMBER: {'type': int, 'value': 5 },
        ADCP_PD0_PARSED_KEY.INTERNAL_TIMESTAMP: {'type': float, 'value': 752 },
        ADCP_PD0_PARSED_KEY.ENSEMBLE_NUMBER_INCREMENT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BIT_RESULT_DEMOD_1: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BIT_RESULT_DEMOD_2: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BIT_RESULT_TIMING: {'type': int, 'value': 0  },
        ADCP_PD0_PARSED_KEY.SPEED_OF_SOUND: {'type': int, 'value': 1523 },
        ADCP_PD0_PARSED_KEY.TRANSDUCER_DEPTH: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.HEADING: {'type': int, 'value': 5221 },
        ADCP_PD0_PARSED_KEY.PITCH: {'type': int, 'value': -4657 },
        ADCP_PD0_PARSED_KEY.ROLL: {'type': int, 'value': -4561 },
        ADCP_PD0_PARSED_KEY.SALINITY: {'type': int, 'value': 35 },
        ADCP_PD0_PARSED_KEY.TEMPERATURE: {'type': int, 'value': 2050     },
        ADCP_PD0_PARSED_KEY.MPT_MINUTES: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.MPT_SECONDS: {'type': float, 'value': 0.0 },
        ADCP_PD0_PARSED_KEY.HEADING_STDEV: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.PITCH_STDEV: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ROLL_STDEV: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ADC_TRANSMIT_CURRENT: {'type': int, 'value': 116 },
        ADCP_PD0_PARSED_KEY.ADC_TRANSMIT_VOLTAGE: {'type': int, 'value': 169 },
        ADCP_PD0_PARSED_KEY.ADC_AMBIENT_TEMP: {'type': int, 'value': 88 },
        ADCP_PD0_PARSED_KEY.ADC_PRESSURE_PLUS: {'type': int, 'value': 79 },
        ADCP_PD0_PARSED_KEY.ADC_PRESSURE_MINUS: {'type': int, 'value': 79 },
        ADCP_PD0_PARSED_KEY.ADC_ATTITUDE_TEMP: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ADC_ATTITUDE: {'type': int, 'value': 0   },
        ADCP_PD0_PARSED_KEY.ADC_CONTAMINATION_SENSOR: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BUS_ERROR_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ADDRESS_ERROR_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ILLEGAL_INSTRUCTION_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ZERO_DIVIDE_INSTRUCTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.EMULATOR_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.UNASSIGNED_EXCEPTION: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.WATCHDOG_RESTART_OCCURED: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.BATTERY_SAVER_POWER: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.PINGING: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.COLD_WAKEUP_OCCURED: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.UNKNOWN_WAKEUP_OCCURED: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.CLOCK_READ_ERROR: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.UNEXPECTED_ALARM: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.CLOCK_JUMP_FORWARD: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.CLOCK_JUMP_BACKWARD: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.POWER_FAIL: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SPURIOUS_DSP_INTERRUPT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SPURIOUS_UART_INTERRUPT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.SPURIOUS_CLOCK_INTERRUPT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.LEVEL_7_INTERRUPT: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.ABSOLUTE_PRESSURE: {'type': int, 'value': 4294963793 },
        ADCP_PD0_PARSED_KEY.PRESSURE_VARIANCE: {'type': int, 'value': 0 },
        ADCP_PD0_PARSED_KEY.INTERNAL_TIMESTAMP: {'type': float, 'value': 1363408382.02 },
        ADCP_PD0_PARSED_KEY.VELOCITY_DATA_ID: {'type': int, 'value': 1 },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_ID: {'type': int, 'value': 2 },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM1: {'type': list, 'value': [19801, 1796, 1800, 1797, 1288, 1539, 1290, 1543, 1028, 1797, 1538, 775, 1034, 1283, 1029, 1799, 1801, 1545, 519, 772, 519, 1033, 1028, 1286, 521, 519, 1545, 1801, 522, 1286, 1030, 1032, 1542, 1035, 1283, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM2: {'type': list, 'value': [22365, 2057, 2825, 2825, 1801, 2058, 1545, 1286, 3079, 522, 1547, 519, 2052, 2820, 519, 1806, 1026, 1547, 1795, 1801, 2311, 1030, 781, 1796, 1037, 1802, 1035, 1798, 770, 2313, 1292, 1031, 1030, 2830, 523, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM3: {'type': list, 'value': [3853, 1796, 1289, 1803, 2317, 2571, 1028, 1282, 1799, 2825, 2574, 1026, 1028, 518, 1290, 1286, 1032, 1797, 1028, 2312, 1031, 775, 1549, 772, 1028, 772, 2570, 1288, 1796, 1542, 1538, 777, 1282, 773, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.CORRELATION_MAGNITUDE_BEAM4: {'type': list, 'value': [5386, 4100, 2822, 1286, 774, 1799, 518, 778, 3340, 1031, 1546, 1545, 1547, 2566, 3077, 3334, 1801, 1809, 2058, 1539, 1798, 1546, 3593, 1032, 2307, 1025, 1545, 2316, 2055, 1546, 1292, 2312, 1035, 2316, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_ID: {'type': int, 'value': 3 },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM1: {'type': list, 'value': [24925, 10538, 10281, 10537, 10282, 10281, 10281, 10282, 10282, 10281, 10281, 10281, 10538, 10282, 10281, 10282, 10281, 10537, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10281, 10282, 10281, 10282, 10537, 10281, 10281, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM2: {'type': list, 'value': [29027, 12334, 12334, 12078, 12078, 11821, 12334, 12334, 12078, 12078, 12078, 12078, 12078, 12078, 12078, 12079, 12334, 12078, 12334, 12333, 12078, 12333, 12078, 12077, 12078, 12078, 12078, 12334, 12077, 12078, 12078, 12078, 12078, 12078, 12078, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM3: {'type': list, 'value': [12079, 10282, 10281, 10281, 10282, 10281, 10282, 10282, 10281, 10025, 10282, 10282, 10282, 10282, 10025, 10282, 10281, 10025, 10281, 10281, 10282, 10281, 10282, 10281, 10281, 10281, 10537, 10282, 10281, 10281, 10281, 10281, 10281, 10282, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.ECHO_INTENSITY_BEAM4: {'type': list, 'value': [14387, 12334, 12078, 12078, 12078, 12334, 12078, 12334, 12078, 12078, 12077, 12077, 12334, 12078, 12334, 12078, 12334, 12077, 12078, 11821, 12335, 12077, 12078, 12077, 12334, 11822, 12334, 12334, 12077, 12077, 12078, 11821, 11821, 12078, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_ID: {'type': int, 'value': 4 },
        ADCP_PD0_PARSED_KEY.CHECKSUM: {'type': int, 'value': 8239 }
    }

    #CG?
    """
    SAMPLEDICT: {'quality_flag': 'ok', 'preferred_timestamp': 'port_timestamp', 'stream_name': 'adcp_pd0_earth_parsed', 'port_timestamp': 3577202162.3577204, 'pkt_format_id': 'JSON_Data', 'pkt_version': 1, 'values': [{'value_id': 'checksum', 'value': 16167}, {'value_id': 'header_id', 'value': 127}, {'value_id': 'data_source_id', 'value': 127}, {'value_id': 'num_bytes', 'value': 26632}, {'value_id': 'num_data_types', 'value': 6}, {'value_id': 'offset_data_types', 'value': [18, 77, 142, 944, 1346, 1748, 2150]}, {'value_id': 'fixed_leader_id', 'value': 0}, {'value_id': 'firmware_version', 'value': 50}, {'value_id': 'firmware_revision', 'value': 40}, {'value_id': 'sysconfig_frequency', 'value': 150}, {'value_id': 'sysconfig_beam_pattern', 'value': 0}, {'value_id': 'sysconfig_sensor_config', 'value': 1}, {'value_id': 'sysconfig_head_attached', 'value': 1}, {'value_id': 'sysconfig_vertical_orientation', 'value': 0}, {'value_id': 'data_flag', 'value': 0}, {'value_id': 'lag_length', 'value': 53}, {'value_id': 'num_beams', 'value': 4}, {'value_id': 'num_cells', 'value': 100}, {'value_id': 'pings_per_ensemble', 'value': 256}, {'value_id': 'depth_cell_length', 'value': 8195}, {'value_id': 'blank_after_transmit', 'value': 49154}, {'value_id': 'signal_processing_mode', 'value': 1}, {'value_id': 'low_corr_threshold', 'value': 64}, {'value_id': 'num_code_repetitions', 'value': 5}, {'value_id': 'percent_good_min', 'value': 0}, {'value_id': 'error_vel_threshold', 'value': 53255}, {'value_id': 'time_per_ping_minutes', 'value': 0}, {'value_id': 'time_per_ping_seconds', 'value': 1.0}, {'value_id': 'coord_transform_type', 'value': 3}, {'value_id': 'coord_transform_tilts', 'value': 1}, {'value_id': 'coord_transform_beams', 'value': 0}, {'value_id': 'coord_transform_mapping', 'value': 1}, {'value_id': 'heading_alignment', 'value': 0}, {'value_id': 'heading_bias', 'value': 0}, {'value_id': 'sensor_source_speed', 'value': 1}, {'value_id': 'sensor_source_depth', 'value': 1}, {'value_id': 'sensor_source_heading', 'value': 1}, {'value_id': 'sensor_source_pitch', 'value': 1}, {'value_id': 'sensor_source_roll', 'value': 1}, {'value_id': 'sensor_source_conductivity', 'value': 0}, {'value_id': 'sensor_source_temperature', 'value': 1}, {'value_id': 'sensor_available_depth', 'value': 1}, {'value_id': 'sensor_available_heading', 'value': 1}, {'value_id': 'sensor_available_pitch', 'value': 1}, {'value_id': 'sensor_available_roll', 'value': 1}, {'value_id': 'sensor_available_conductivity', 'value': 0}, {'value_id': 'sensor_available_temperature', 'value': 1}, {'value_id': 'bin_1_distance', 'value': 39942}, {'value_id': 'transmit_pulse_length', 'value': 53763}, {'value_id': 'reference_layer_start', 'value': 1}, {'value_id': 'reference_layer_stop', 'value': 5}, {'value_id': 'false_target_threshold', 'value': 50}, {'value_id': 'low_latency_trigger', 'value': 0}, {'value_id': 'transmit_lag_distance', 'value': 50944}, {'value_id': 'cpu_board_serial_number', 'value': 3314649355795125257L}, {'value_id': 'system_bandwidth', 'value': 0}, {'value_id': 'system_power', 'value': 255}, {'value_id': 'serial_number', 'value': 3880321024}, {'value_id': 'beam_angle', 'value': 20}, {'value_id': 'variable_leader_id', 'value': 128}, {'value_id': 'ensemble_number', 'value': 1}, {'value_id': 'ensemble_number_increment', 'value': 0}, {'value_id': 'bit_result_demod_1', 'value': 0}, {'value_id': 'bit_result_demod_2', 'value': 0}, {'value_id': 'bit_result_timing', 'value': 0}, {'value_id': 'speed_of_sound', 'value': 1529}, {'value_id': 'transducer_depth', 'value': 0}, {'value_id': 'heading', 'value': 29160}, {'value_id': 'pitch', 'value': -4282}, {'value_id': 'roll', 'value': 4361}, {'value_id': 'salinity', 'value': 35}, {'value_id': 'temperature', 'value': 2272}, {'value_id': 'mpt_minutes', 'value': 0}, {'value_id': 'mpt_seconds', 'value': 0.0}, {'value_id': 'heading_stdev', 'value': 0}, {'value_id': 'pitch_stdev', 'value': 0}, {'value_id': 'roll_stdev', 'value': 0}, {'value_id': 'adc_transmit_current', 'value': 255}, {'value_id': 'adc_transmit_voltage', 'value': 0}, {'value_id': 'adc_ambient_temp', 'value': 0}, {'value_id': 'adc_pressure_plus', 'value': 0}, {'value_id': 'adc_pressure_minus', 'value': 0}, {'value_id': 'adc_attitude_temp', 'value': 0}, {'value_id': 'adc_attitiude', 'value': 0}, {'value_id': 'adc_contamination_sensor', 'value': 0}, {'value_id': 'bus_error_exception', 'value': 0}, {'value_id': 'address_error_exception', 'value': 0}, {'value_id': 'illegal_instruction_exception', 'value': 0}, {'value_id': 'zero_divide_instruction', 'value': 0}, {'value_id': 'emulator_exception', 'value': 0}, {'value_id': 'unassigned_exception', 'value': 0}, {'value_id': 'watchdog_restart_occurred', 'value': 0}, {'value_id': 'battery_saver_power', 'value': 0}, {'value_id': 'pinging', 'value': 0}, {'value_id': 'cold_wakeup_occurred', 'value': 0}, {'value_id': 'unknown_wakeup_occurred', 'value': 0}, {'value_id': 'clock_read_error', 'value': 0}, {'value_id': 'unexpected_alarm', 'value': 0}, {'value_id': 'clock_jump_forward', 'value': 0}, {'value_id': 'clock_jump_backward', 'value': 0}, {'value_id': 'power_fail', 'value': 0}, {'value_id': 'spurious_dsp_interrupt', 'value': 0}, {'value_id': 'spurious_uart_interrupt', 'value': 0}, {'value_id': 'spurious_clock_interrupt', 'value': 0}, {'value_id': 'level_7_interrupt', 'value': 0}, {'value_id': 'pressure', 'value': 4294966733}, {'value_id': 'pressure_variance', 'value': 0}, {'value_id': 'internal_timestamp', 'value': 1368238559.59}, {'value_id': 'velocity_data_id', 'value': 1}, {'value_id': 'water_velocity_east', 'value': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128]}, {'value_id': 'water_velocity_north', 'value': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128]}, {'value_id': 'water_velocity_up', 'value': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128]}, {'value_id': 'error_velocity', 'value': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128]}, {'value_id': 'beam_1_velocity', 'value': []}, {'value_id': 'beam_2_velocity', 'value': []}, {'value_id': 'beam_3_velocity', 'value': []}, {'value_id': 'beam_4_velocity', 'value': []}, {'value_id': 'correlation_magnitude_id', 'value': 2}, {'value_id': 'correlation_magnitude_beam1', 'value': [33819, 2836, 2830, 3340, 4108, 1546, 3596, 5895, 3589, 1549, 3085, 3590, 5389, 1308, 5392, 2838, 4099, 4868, 2053, 6933, 11, 12, 15, 7, 9, 4, 6, 19, 3, 12, 9, 26, 10, 17, 14, 6, 8, 13, 16, 14, 7, 0, 0, 0, 0, 0, 0, 0, 0]}, {'value_id': 'correlation_magnitude_beam2', 'value': [9267, 775, 4104, 2825, 3598, 4114, 2315, 5390, 4369, 4363, 2819, 3342, 2835, 1543, 4107, 2059, 5904, 3336, 1547, 2827, 17, 11, 11, 16, 13, 11, 16, 9, 9, 10, 10, 22, 4, 11, 15, 9, 1, 15, 9, 11, 12, 0, 0, 0, 0, 0, 0, 0, 0]}, {'value_id': 'correlation_magnitude_beam3', 'value': [2821, 2312, 3364, 3336, 2318, 2827, 2057, 519, 2060, 3083, 1288, 2062, 4105, 3599, 6665, 2061, 2056, 2823, 1810, 3348, 9, 11, 18, 14, 8, 9, 16, 11, 4, 3, 12, 20, 5, 9, 12, 13, 12, 13, 17, 14, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, {'value_id': 'correlation_magnitude_beam4', 'value': [2066, 3347, 1284, 3080, 3089, 4880, 2057, 3095, 3595, 2315, 2314, 2057, 3847, 4626, 3088, 4117, 4621, 3076, 3594, 4381, 8, 14, 17, 10, 18, 13, 11, 14, 6, 24, 10, 5, 14, 26, 8, 11, 14, 6, 8, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, {'value_id': 'echo_intensity_id', 'value': 3}, {'value_id': 'echo_intesity_beam1', 'value': [6944, 5404, 5148, 5404, 5148, 5404, 5404, 5404, 5404, 5147, 5404, 5147, 5147, 5404, 5404, 5404, 5404, 5404, 5404, 5404, 5404, 5404, 5404, 5403, 5661, 5404, 5404, 5403, 5149, 5403, 5404, 5660, 5404, 5404, 5405, 5148, 5404, 5148, 5404, 5403, 5147, 5148, 5148, 5148, 5147, 5148, 5403, 5404, 5148]}, {'value_id': 'echo_intesity_beam2', 'value': [6431, 5915, 5915, 6170, 6171, 6427, 6170, 5914, 6683, 5914, 6171, 6171, 5659, 6427, 6170, 6426, 5659, 5914, 6171, 5915, 6171, 6171, 6171, 6171, 6171, 6171, 5915, 5915, 6427, 5914, 5914, 5660, 6170, 6171, 5914, 6171, 6170, 6426, 6170, 6171, 6427, 6170, 6170, 6426, 5916, 6170, 6170, 6171, 5915]}, {'value_id': 'echo_intesity_beam3', 'value': [5661, 5403, 5404, 5403, 5659, 5148, 5404, 5403, 5660, 5404, 5404, 5403, 5148, 5404, 5403, 5148, 5404, 5404, 5404, 5147, 5404, 5147, 5404, 5404, 5403, 5148, 5148, 5659, 5403, 5148, 5660, 5403, 5148, 5403, 5404, 5404, 5148, 5404, 5405, 5147, 5404, 5147, 5404, 5148, 5404, 5660, 5404, 5404, 5147]}, {'value_id': 'echo_intesity_beam4', 'value': [6172, 5915, 6171, 5659, 6171, 5916, 5915, 5915, 5915, 5659, 6171, 5914, 6171, 5915, 6427, 5915, 5914, 6170, 5915, 6170, 6171, 5915, 6171, 6427, 6171, 6171, 5914, 5915, 6426, 6171, 6170, 6171, 6427, 6171, 6171, 6426, 6426, 6171, 5915, 6426, 5914, 6171, 5915, 5914, 6170, 5915, 6171, 5658, 5914]}, {'value_id': 'percent_good_id', 'value': 4}, {'value_id': 'percent_good_3beam', 'value': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, {'value_id': 'percent_transforms_reject', 'value': [25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600]}, {'value_id': 'percent_bad_beams', 'value': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}, {'value_id': 'percent_good_4beam', 'value': [25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600]}, {'value_id': 'percent_good_beam1', 'value': []}, {'value_id': 'percent_good_beam2', 'value': []}, {'value_id': 'percent_good_beam3', 'value': []}, {'value_id': 'percent_good_beam4', 'value': []}], 'driver_timestamp': 3577202164.788333}
    2013-05-10 12:16:05,749 INFO     mi.idk.unit_test Sample Keys: ['ensemble_number', 'num_beams', 'adc_pressure_plus', 'percent_bad_beams', 'sysconfig_head_attached', 'sensor_available_heading', 'pitch', 'header_id', 'time_per_ping_seconds', 'correlation_magnitude_beam1', 'watchdog_restart_occurred', 'percent_good_beam1', 'percent_good_beam3', 'percent_good_beam2', 'percent_good_beam4', 'coord_transform_beams', 'reference_layer_stop', 'clock_jump_backward', 'sensor_available_pitch', 'cpu_board_serial_number', 'depth_cell_length', 'adc_attitude_temp', 'unexpected_alarm', 'percent_transforms_reject', 'sensor_source_speed', 'echo_intesity_beam1', 'spurious_uart_interrupt', 'battery_saver_power', 'sensor_source_roll', 'reference_layer_start', 'bit_result_demod_2', 'echo_intesity_beam3', 'bit_result_demod_1', 'sensor_available_roll', 'echo_intesity_beam4', 'num_bytes', 'coord_transform_type', 'correlation_magnitude_beam4', 'correlation_magnitude_beam2', 'correlation_magnitude_beam3', 'spurious_dsp_interrupt', 'sensor_available_conductivity', 'mpt_minutes', 'heading', 'adc_ambient_temp', 'time_per_ping_minutes', 'transducer_depth', 'beam_2_velocity', 'power_fail', 'address_error_exception', 'error_vel_threshold', 'beam_3_velocity', 'data_flag', 'bus_error_exception', 'sensor_source_heading', 'bit_result_timing', 'pressure_variance', 'lag_length', 'sensor_source_pitch', 'sensor_source_depth', 'illegal_instruction_exception', 'adc_transmit_voltage', 'adc_attitiude', 'emulator_exception', 'transmit_pulse_length', 'heading_alignment', 'adc_pressure_minus', 'pings_per_ensemble', 'adc_transmit_current', 'pressure', 'checksum', 'low_corr_threshold', 'zero_divide_instruction', 'blank_after_transmit', 'system_bandwidth', 'sysconfig_beam_pattern', 'transmit_lag_distance', 'water_velocity_east', 'system_power', 'percent_good_min', 'beam_angle', 'water_velocity_north', 'beam_1_velocity', 'false_target_threshold', 'spurious_clock_interrupt', 'roll_stdev', 'temperature', 'unassigned_exception', 'percent_good_id', 'water_velocity_up', 'internal_timestamp', 'adc_contamination_sensor', 'serial_number', 'echo_intensity_id', 'sysconfig_vertical_orientation', 'correlation_magnitude_id', 'mpt_seconds', 'heading_bias', 'num_cells', 'low_latency_trigger', 'error_velocity', 'clock_read_error', 'sensor_available_temperature', 'echo_intesity_beam2', 'sysconfig_sensor_config', 'firmware_revision', 'percent_good_4beam', 'firmware_version', 'coord_transform_mapping', 'velocity_data_id', 'speed_of_sound', 'percent_good_3beam', 'pitch_stdev', 'offset_data_types', 'level_7_interrupt', 'coord_transform_tilts', 'ensemble_number_increment', 'roll', 'data_source_id', 'sensor_source_temperature', 'beam_4_velocity', 'variable_leader_id', 'sensor_source_conductivity', 'num_code_repetitions', 'num_data_types', 'unknown_wakeup_occurred', 'pinging', 'cold_wakeup_occurred', 'sysconfig_frequency', 'sensor_available_depth', 'salinity', 'clock_jump_forward', 'signal_processing_mode', 'fixed_leader_id', 'heading_stdev', 'bin_1_distance']
    2013-05-10 12:16:05,749 INFO     mi.idk.unit_test Required Keys: ['ensemble_number', 'num_beams', 'adc_pressure_plus', 'percent_bad_beams', 'percent_transforms_reject', 'sensor_available_heading', 'ensemble_number_increment', 'pitch', 'header_id', 'time_per_ping_seconds', 'correlation_magnitude_beam1', 'watchdog_restart_occurred', 'percent_good_beam1', 'percent_good_beam3', 'percent_good_beam2', 'percent_good_beam4', 'coord_transform_beams', 'reference_layer_stop', 'clock_jump_backward', 'low_latency_trigger', 'cpu_board_serial_number', 'depth_cell_length', 'adc_attitude_temp', 'beam_angle', 'sensor_source_speed', 'echo_intesity_beam1', 'spurious_uart_interrupt', 'battery_saver_power', 'sensor_source_roll', 'sensor_available_roll', 'bit_result_demod_2', 'echo_intesity_beam3', 'bit_result_demod_1', 'reference_layer_start', 'echo_intesity_beam4', 'num_bytes', 'coord_transform_type', 'correlation_magnitude_beam4', 'correlation_magnitude_beam2', 'correlation_magnitude_beam3', 'spurious_dsp_interrupt', 'sensor_available_conductivity', 'mpt_minutes', 'heading', 'adc_ambient_temp', 'time_per_ping_minutes', 'transducer_depth', 'power_fail', 'address_error_exception', 'error_vel_threshold', 'sensor_source_temperature', 'beam_3_velocity', 'data_flag', 'bus_error_exception', 'sensor_source_heading', 'bit_result_timing', 'pressure_variance', 'lag_length', 'sensor_source_pitch', 'sensor_source_depth', 'beam_2_velocity', 'adc_transmit_voltage', 'adc_attitiude', 'emulator_exception', 'transmit_pulse_length', 'heading_alignment', 'adc_pressure_minus', 'pings_per_ensemble', 'adc_transmit_current', 'pressure', 'checksum', 'low_corr_threshold', 'zero_divide_instruction', 'blank_after_transmit', 'sysconfig_beam_pattern', 'sysconfig_sensor_config', 'water_velocity_east', 'system_power', 'percent_good_min', 'unexpected_alarm', 'water_velocity_north', 'beam_1_velocity', 'false_target_threshold', 'spurious_clock_interrupt', 'roll_stdev', 'temperature', 'unassigned_exception', 'percent_good_id', 'water_velocity_up', 'internal_timestamp', 'adc_contamination_sensor', 'serial_number', 'echo_intensity_id', 'sysconfig_vertical_orientation', 'correlation_magnitude_id', 'mpt_seconds', 'heading_bias', 'num_cells', 'sensor_available_pitch', 'error_velocity', 'clock_read_error', 'sensor_available_temperature', 'echo_intesity_beam2', 'transmit_lag_distance', 'firmware_revision', 'sysconfig_frequency', 'percent_good_4beam', 'firmware_version', 'coord_transform_mapping', 'velocity_data_id', 'speed_of_sound', 'percent_good_3beam', 'pitch_stdev', 'offset_data_types', 'level_7_interrupt', 'coord_transform_tilts', 'illegal_instruction_exception', 'roll', 'data_source_id', 'system_bandwidth', 'beam_4_velocity', 'variable_leader_id', 'sensor_source_conductivity', 'num_code_repetitions', 'num_data_types', 'unknown_wakeup_occurred', 'pinging', 'cold_wakeup_occurred', 'sysconfig_head_attached', 'sensor_available_depth', 'salinity', 'clock_jump_forward', 'signal_processing_mode', 'fixed_leader_id', 'heading_stdev', 'bin_1_distance']
    
    
    """



    # red
    _coordinate_transformation_earth_parameters = {
        # Earth Coordinates
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_EAST: {'type': list, 'value': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_NORTH: {'type': list, 'value': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.WATER_VELOCITY_UP: {'type': list, 'value': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.ERROR_VELOCITY: {'type': list, 'value': [128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_3BEAM: {'type': list, 'value': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_TRANSFORMS_REJECT: {'type': list, 'value': [25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600] },
        ADCP_PD0_PARSED_KEY.PERCENT_BAD_BEAMS: {'type': list, 'value': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_4BEAM: {'type': list, 'value': [25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600, 25600] },
    }

    # blue
    _coordinate_transformation_beam_parameters = {
        # Beam Coordinates
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM1: {'type': list, 'value': [25700, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM2: {'type': list, 'value': [25700, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM3: {'type': list, 'value': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.PERCENT_GOOD_BEAM4: {'type': list, 'value': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] },
        ADCP_PD0_PARSED_KEY.BEAM_1_VELOCITY: {'type': list, 'value': [4864, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.BEAM_2_VELOCITY: {'type': list, 'value': [62719, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.BEAM_3_VELOCITY: {'type': list, 'value': [45824, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        ADCP_PD0_PARSED_KEY.BEAM_4_VELOCITY  : {'type': list, 'value': [19712, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128] },
        
    }

    _pd0_parameters = dict(_pd0_parameters_base.items() +
                           _coordinate_transformation_earth_parameters.items())
    # Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        log.debug("assert_driver_parameters current_parameters = " + str(current_parameters))
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    ###
    # Data Particle Parameters Methods
    ###
    def assert_sample_data_particle(self, data_particle):
        '''
        Verify a particle is a know particle to this driver and verify the particle is  correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''

        if (isinstance(data_particle, DataParticleType.ADCP_PD0_PARSED_EARTH)):
            self.assert_particle_pd0_data(data_particle)
        elif (isinstance(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)):
            self.assert_particle_system_configuration(data_particle)
        elif (isinstance(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)):
            self.assert_particle_compass_calibration(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_particle_compass_calibration(self, data_particle, verify_values = True):
        '''
        Verify an adcpt calibration data particle
        @param data_particle: ADCPT_CalibrationDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        log.debug("in assert_particle_compass_calibration")
        log.debug("data_particle = " + repr(data_particle))
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    def assert_particle_system_configuration(self, data_particle, verify_values = True):
        '''
        Verify an adcpt fd data particle
        @param data_particle: ADCPT_FDDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)
        self.assert_data_particle_parameters(data_particle, self._system_configuration_data_parameters, verify_values)

    def assert_particle_pd0_data(self, data_particle, verify_values = True):
        '''
        Verify an adcpt ps0 data particle
        @param data_particle: ADCPT_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        log.debug("IN assert_particle_pd0_data")
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_PD0_PARSED_EARTH)
        self.assert_data_particle_parameters(data_particle, self._pd0_parameters) # , verify_values


###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(WorkhorseDriverUnitTest, ADCPTMixin):
    def setUp(self):
        WorkhorseDriverUnitTest.setUp(self)

    def test_send_break(self):
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        self.protocol = Protocol(Prompt, NEWLINE, my_event_callback)
        def fake_send_break1_cmd():
            log.debug("IN fake_send_break1_cmd")
            self.protocol._linebuf =  "[BREAK Wakeup A]\n" + \
                                     "  Polled Mode is OFF -- Battery Saver is ONWorkHorse Broadband ADCP Version 50.40\n" + \
                                     "Teledyne RD Instruments (c) 1996-2010\n" + \
                                     "All Rights Reserved."

        def fake_send_break2_cmd():
            log.debug("IN fake_send_break2_cmd")
            self.protocol._linebuf = "[BREAK Wakeup A]" + NEWLINE + \
                                    "WorkHorse Broadband ADCP Version 50.40" + NEWLINE + \
                                    "Teledyne RD Instruments (c) 1996-2010" + NEWLINE + \
                                    "All Rights Reserved."

        self.protocol._send_break_cmd = fake_send_break1_cmd

        self.assertTrue(self.protocol._send_break())

        self.protocol._send_break_cmd = fake_send_break2_cmd

        self.assertTrue(self.protocol._send_break())

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles

        self.assert_particle_published(driver, CG_CALIBRATION_RAW_DATA, self.assert_particle_compass_calibration, True)
        self.assert_particle_published(driver, CG_PS0_RAW_DATA, self.assert_particle_system_configuration, True)
        self.assert_particle_published(driver, CG_SAMPLE_RAW_DATA, self.assert_particle_pd0_data, True)
        
    def test_driver_parameters(self):
        """
        Verify the set of parameters known by the driver
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)

        expected_parameters = sorted(self._driver_parameters.keys())
        reported_parameters = sorted(driver.get_resource(Parameter.ALL))

        log.debug("*** Expected Parameters: %s" % expected_parameters)
        log.debug("*** Reported Parameters: %s" % reported_parameters)

        self.assertEqual(reported_parameters, expected_parameters)

        # Verify the parameter definitions
        self.assert_driver_parameter_definition(driver, self._driver_parameters)

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_CLOCK_SYNC',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'PROTOCOL_EVENT_CLEAR_ERROR_STATUS_WORD',
                                    'PROTOCOL_EVENT_CLEAR_FAULT_LOG',
                                    'PROTOCOL_EVENT_GET_CALIBRATION',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_GET_ERROR_STATUS_WORD',
                                    'PROTOCOL_EVENT_GET_FAULT_LOG',
                                    'PROTOCOL_EVENT_GET_INSTRUMENT_TRANSFORM_MATRIX',
                                    'PROTOCOL_EVENT_RUN_TEST_200',
                                    'PROTOCOL_EVENT_SAVE_SETUP_TO_RAM',
                                    'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC',
                                    'PROTOCOL_EVENT_SEND_LAST_SAMPLE'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE',
                                    'DRIVER_EVENT_GET',
                                    'PROTOCOL_EVENT_GET_CALIBRATION',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """

        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ScheduledJob())
        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, CG_SAMPLE_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, CG_SAMPLE_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, CG_SAMPLE_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, CG_SAMPLE_RAW_DATA)

        self.assert_chunker_sample(chunker, CG_PS0_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, CG_PS0_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, CG_PS0_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, CG_PS0_RAW_DATA)

        self.assert_chunker_sample(chunker, CG_CALIBRATION_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, CG_CALIBRATION_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, CG_CALIBRATION_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, CG_CALIBRATION_RAW_DATA)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, my_event_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(driver_capabilities, protocol._filter_capabilities(test_capabilities))


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(WorkhorseDriverIntegrationTest, ADCPTMixin):
    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample
        """
        self.assert_initialize_driver()

        params = {
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 0,
            Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1485,
            Parameter.PITCH: 0,
            Parameter.ROLL: 0,
            Parameter.SALINITY: 35,
            Parameter.TIME_PER_ENSEMBLE: '00:00:20.00',
            Parameter.TIME_PER_PING: '00:01.00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            Parameter.BANDWIDTH_CONTROL: 0,
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            Parameter.BLANK_AFTER_TRANSMIT: 704,
            Parameter.CLIP_DATA_PAST_BOTTOM: 0,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
        }
        self.assert_set_bulk(params)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_async_particle_generation(DataParticleType.ADCP_PD0_PARSED_EARTH, self.assert_particle_pd0_data, timeout=40)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=10)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(WorkhorseDriverQualificationTest, ADCPTMixin):
    def test_autosample(self):
        """
        Verify autosample works and data particles are created
        """
        self.assert_enter_command_mode()
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED_EARTH, self.assert_particle_pd0_data, timeout=50) # ADCP_PD0_PARSED_BEAM
        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1, timeout=50)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1, timeout=50)

        # Stop autosample and do run a couple commands.
        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1)

        # Restart autosample and gather a couple samples
        self.assert_sample_autosample(self.assert_particle_pd0_data, DataParticleType.ADCP_PD0_PARSED_EARTH)

    def assert_cycle(self):
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED_EARTH, self.assert_particle_pd0_data, timeout=200)
        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1, timeout=50)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1, timeout=50)

        # Stop autosample and do run a couple commands.
        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1)

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific publication tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class PubFromIDK(WorkhorseDriverPublicationTest):
    def setUp(self):
        WorkhorseDriverPublicationTest.setUp(self)

    def test_granule_generation(self):
        self.assert_initialize_driver()

        # Currently these tests only verify that the data granule is generated, but the values
        # are not tested.  We will eventually need to replace log.debug with a better callback
        # function that actually tests the granule.
        self.assert_sample_async("raw data", log.debug, DataParticleType.RAW, timeout=10)
        self.assert_sample_async(CG_SAMPLE_RAW_DATA, log.debug, DataParticleType.ADCP_PD0_PARSED_BEAM, timeout=10)
        self.assert_sample_async(CG_PS0_RAW_DATA, log.debug, DataParticleType.ADCP_SYSTEM_CONFIGURATION, timeout=10)
        self.assert_sample_async(CG_CALIBRATION_RAW_DATA, log.debug, DataParticleType.ADCP_COMPASS_CALIBRATION, timeout=10)


