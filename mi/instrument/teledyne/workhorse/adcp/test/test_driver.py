"""
@package mi.instrument.teledyne.workhorse.adcp.driver
@file marine-integrations/mi/instrument/teledyne/workhorse/ADCP/test/test_driver.py
@author Sung Ahn
@brief Test Driver for the ADCP
Release notes:

GGeneric test Driver for ADCPS-K, ADCPS-I, ADCPT-B and ADCPT-DE
"""

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

import unittest
import datetime as dt
from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.chunker import StringChunker

from mi.core.log import get_logger; log = get_logger()

from mi.instrument.teledyne.workhorse.test.test_driver import WorkhorseDriverUnitTest
from mi.instrument.teledyne.workhorse.test.test_driver import WorkhorseDriverIntegrationTest
from mi.instrument.teledyne.workhorse.test.test_driver import WorkhorseDriverQualificationTest
from mi.instrument.teledyne.workhorse.test.test_driver import WorkhorseDriverPublicationTest
from mi.instrument.teledyne.workhorse.test.test_driver import DataParticleType
from mi.idk.unit_test import InstrumentDriverTestCase

from mi.instrument.teledyne.workhorse.test.test_data import RSN_SAMPLE_RAW_DATA
from mi.instrument.teledyne.workhorse.test.test_data import RSN_CALIBRATION_RAW_DATA
from mi.instrument.teledyne.workhorse.test.test_data import RSN_PS0_RAW_DATA

from mi.idk.unit_test import DriverTestMixin

from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey
from mi.instrument.teledyne.workhorse.adcp.driver import Parameter
from mi.instrument.teledyne.workhorse.adcp.driver import Prompt
from mi.instrument.teledyne.workhorse.adcp.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse.driver import NEWLINE
from mi.instrument.teledyne.workhorse.adcp.driver import ScheduledJob
from mi.instrument.teledyne.workhorse.adcp.driver import Capability
from mi.instrument.teledyne.workhorse.adcp.driver import InstrumentCmds

from mi.instrument.teledyne.workhorse.driver import ADCP_PD0_PARSED_KEY
from mi.instrument.teledyne.workhorse.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse.driver import ADCP_COMPASS_CALIBRATION_KEY

from mi.instrument.teledyne.workhorse.adcp.driver import InstrumentDriver
from mi.instrument.teledyne.workhorse.adcp.driver import Protocol

from mi.instrument.teledyne.workhorse.adcp.driver import ProtocolState
###
#   Driver parameters for tests
###

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.teledyne.workhorse.adcp.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'HTWZMW',
    instrument_agent_preload_id = 'IA7',
    instrument_agent_name = 'teledyne_workhorse_monitor ADCP',
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
            Parameter.COORDINATE_TRANSFORMATION: '00111',
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
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
            Parameter.LATENCY_TRIGGER: 0,
            Parameter.HEADING_ALIGNMENT: '+00000',
            Parameter.HEADING_BIAS: '+00000',
            Parameter.TRANSDUCER_DEPTH: 8000,
            Parameter.DATA_STREAM_SELECTION: 0,
            Parameter.ENSEMBLE_PER_BURST: 0,
            Parameter.SAMPLE_AMBIENT_SOUND: 0,
            Parameter.BUFFERED_OUTPUT_PERIOD: '00:00:00',
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
    _driver_parameters = {
        Parameter.SERIAL_DATA_OUT: {TYPE: str, READONLY: True, DA: True, STARTUP: True, DEFAULT: '000 000 000', VALUE:'000 000 000'},
        Parameter.SERIAL_FLOW_CONTROL: {TYPE: str, READONLY: True, DA: True, STARTUP: True, DEFAULT: '11110', VALUE: '11110'},
        Parameter.SAVE_NVRAM_TO_RECORDER: {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.TIME: {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: False},
        Parameter.SERIAL_OUT_FW_SWITCHES: {TYPE: str, READONLY: True, DA: True, STARTUP: True, DEFAULT: '111100000', VALUE: '111100000'},
        Parameter.BANNER: {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.INSTRUMENT_ID: {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.SLEEP_ENABLE: {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.POLLED_MODE: {TYPE: bool, READONLY: True, DA: True, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.XMIT_POWER: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 255, VALUE: 255},
        Parameter.SPEED_OF_SOUND: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 1485, VALUE: 1485},
        Parameter.PITCH: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.ROLL: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.SALINITY: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 35, VALUE: 35},
        Parameter.COORDINATE_TRANSFORMATION: {TYPE: str, READONLY: True, DA: True, STARTUP: True, DEFAULT: '00111', VALUE: '00111'},
        Parameter.SENSOR_SOURCE: {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: "1111101", VALUE: "1111101"},
        Parameter.TIME_PER_ENSEMBLE: {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: False, VALUE: '00:00:00.00'},
        Parameter.TIME_OF_FIRST_PING: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: False}, # STARTUP: True, VALUE: '****/**/**,**:**:**'
        Parameter.TIME_PER_PING: {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: '00:01.00', VALUE: '00:01.00'},
        Parameter.FALSE_TARGET_THRESHOLD: {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: '050,001', VALUE: '050,001'},
        Parameter.BANDWIDTH_CONTROL: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.CORRELATION_THRESHOLD: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 64, VALUE: 64},
        Parameter.ERROR_VELOCITY_THRESHOLD: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 2000, VALUE: 2000},
        Parameter.BLANK_AFTER_TRANSMIT: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 704, VALUE: 704},
        Parameter.CLIP_DATA_PAST_BOTTOM: {TYPE: bool, READONLY: False, DA: True, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.RECEIVER_GAIN_SELECT: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.NUMBER_OF_DEPTH_CELLS: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 100, VALUE: 100},
        Parameter.PINGS_PER_ENSEMBLE: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.DEPTH_CELL_SIZE: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 800, VALUE: 800},
        Parameter.TRANSMIT_LENGTH: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.PING_WEIGHT: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.AMBIGUITY_VELOCITY: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 175, VALUE: 175},

        Parameter.LATENCY_TRIGGER: {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.HEADING_ALIGNMENT: {TYPE: str, READONLY: True, DA: True, STARTUP: True, DEFAULT: '+00000', VALUE:'+00000'},
        Parameter.HEADING_BIAS: {TYPE: str, READONLY: True, DA: True, STARTUP: True, DEFAULT: '+00000', VALUE:'+00000'},
        Parameter.TRANSDUCER_DEPTH: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 8000, VALUE:8000},
        Parameter.DATA_STREAM_SELECTION: {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.ENSEMBLE_PER_BURST: {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.BUFFERED_OUTPUT_PERIOD: {TYPE: str, READONLY: True, DA: True, STARTUP: True, DEFAULT: '00:00:00', VALUE:'00:00:00'},
        Parameter.SAMPLE_AMBIENT_SOUND: {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE:0}
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
        Capability.RUN_TEST_200: { STATES: [ProtocolState.COMMAND]},
        Capability.FACTORY_SETS: { STATES: [ProtocolState.COMMAND]},
        Capability.USER_SETS: { STATES: [ProtocolState.COMMAND]},

        Capability.ACQUIRE_STATUS: { STATES: [ProtocolState.COMMAND]},
        Capability.START_DIRECT: { STATES: [ProtocolState.COMMAND]},
        Capability.STOP_DIRECT: { STATES: [ProtocolState.COMMAND]},


    }

    EF_CHAR = '\xef'
    _calibration_data_parameters = {
        ADCP_COMPASS_CALIBRATION_KEY.FLUXGATE_CALIBRATION_TIMESTAMP: {'type': float, 'value': 1347639932.0 },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BX: {'type': list, 'value': [0.39218, 0.3966, -0.031681, 0.0064332] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BY: {'type': list, 'value': [-0.02432, -0.010376, -0.0022428, -0.60628] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BZ: {'type': list, 'value': [0.22453, -0.21972, -0.2799, -0.0024339] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_ERR: {'type': list, 'value': [0.46514, -0.40455, 0.69083, -0.014291] },
        ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET: {'type': list, 'value': [34233.0, 34449.0, 34389.0, 34698.0] },
        ADCP_COMPASS_CALIBRATION_KEY.ELECTRICAL_NULL: {'type': float, 'value': 34285.0 },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_CALIBRATION_TIMESTAMP: {'type': float, 'value': 1347639285.0 },
        ADCP_COMPASS_CALIBRATION_KEY.CALIBRATION_TEMP: {'type': float, 'value': 24.4 },
        ADCP_COMPASS_CALIBRATION_KEY.ROLL_UP_DOWN: {'type': list, 'value': [7.4612e-07, -3.1727e-05, -3.0054e-07, 3.219e-05] },
        ADCP_COMPASS_CALIBRATION_KEY.PITCH_UP_DOWN: {'type': list, 'value': [-3.1639e-05, -6.3505e-07, -3.1965e-05, -1.4881e-07] },
        ADCP_COMPASS_CALIBRATION_KEY.OFFSET_UP_DOWN: {'type': list, 'value': [32808.0, 32568.0, 32279.0, 33047.0] },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_NULL: {'type': float, 'value': 33500.0 }
    }

    _system_configuration_data_parameters = {
        ADCP_SYSTEM_CONFIGURATION_KEY.SERIAL_NUMBER: {'type': unicode, 'value': "18444" },
        ADCP_SYSTEM_CONFIGURATION_KEY.TRANSDUCER_FREQUENCY: {'type': int, 'value': 76800 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.CONFIGURATION: {'type': unicode, 'value': "4 BEAM, JANUS" },
        ADCP_SYSTEM_CONFIGURATION_KEY.MATCH_LAYER: {'type': unicode, 'value': "10" },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_ANGLE: {'type': int, 'value': 20 },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_PATTERN: {'type': unicode, 'value': "CONVEX" },
        ADCP_SYSTEM_CONFIGURATION_KEY.ORIENTATION: {'type': unicode, 'value': "UP" },
        ADCP_SYSTEM_CONFIGURATION_KEY.SENSORS: {'type': unicode, 'value': "HEADING  TILT 1  TILT 2  DEPTH  TEMPERATURE  PRESSURE" },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c3: {'type': float, 'value': -1.927850E-11 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c2: {'type': float, 'value': +1.281892E-06 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c1: {'type': float, 'value': +1.375793E+00 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_OFFSET: {'type': float, 'value': 13.38634 },
        ADCP_SYSTEM_CONFIGURATION_KEY.TEMPERATURE_SENSOR_OFFSET: {'type': float, 'value': -0.01 },
        ADCP_SYSTEM_CONFIGURATION_KEY.CPU_FIRMWARE: {'type': unicode, 'value': "50.40 [0]" },
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_REQUIRED: {'type': unicode, 'value': "1.16" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_ACTUAL: {'type': unicode, 'value': "1.16" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_VERSION: {'type': unicode, 'value': "ad48" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_TYPE: {'type': unicode, 'value': "1f" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_VERSION: {'type': unicode, 'value': "ad48" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_TYPE: {'type': unicode, 'value': "1f" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_VERSION: {'type': unicode, 'value': "85d3" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_TYPE: {'type': unicode, 'value': "7" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS: {'type': unicode, 'value': u"72  00 00 06 FE BC D8  09 HPA727-3009-00B \n" + \
                                                                                    "81  00 00 06 F5 CD 9E  09 REC727-1004-06A\n" + \
                                                                                    "A5  00 00 06 FF 1C 79  09 HPI727-3007-00A\n" + \
                                                                                    "82  00 00 06 FF 23 E5  09 CPU727-2011-00E\n" + \
                                                                                    "07  00 00 06 F6 05 15  09 TUN727-1005-06A\n" + \
                                                                                    "DB  00 00 06 F5 CB 5D  09 DSP727-2001-06H" }
    }

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
                           _coordinate_transformation_beam_parameters.items())
    _pd0_parameters_earth = dict(_pd0_parameters_base.items() +
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

        if (isinstance(data_particle, DataParticleType.ADCP_PD0_PARSED_BEAM)):
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
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_PD0_PARSED_BEAM)
        self.assert_data_particle_parameters(data_particle, self._pd0_parameters) # , verify_values

    def assert_particle_pd0_data_earth(self, data_particle, verify_values = True):
        '''
        Verify an adcpt ps0 data particle
        @param data_particle: ADCPT_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        log.debug("IN assert_particle_pd0_data")
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_PD0_PARSED_EARTH)
        self.assert_data_particle_parameters(data_particle, self._pd0_parameters_earth) # , verify_values

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(WorkhorseDriverUnitTest, ADCPTMixin):
    def setUp(self):
        WorkhorseDriverUnitTest.setUp(self)

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

        self.assert_particle_published(driver, RSN_CALIBRATION_RAW_DATA, self.assert_particle_compass_calibration, True)
        self.assert_particle_published(driver, RSN_PS0_RAW_DATA, self.assert_particle_system_configuration, True)
        self.assert_particle_published(driver, RSN_SAMPLE_RAW_DATA, self.assert_particle_pd0_data, True)

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
                                    'DRIVER_EVENT_INIT_PARAMS',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'DRIVER_EVENT_ACQUIRE_STATUS',
                                    'PROTOCOL_EVENT_CLEAR_ERROR_STATUS_WORD',
                                    'PROTOCOL_EVENT_CLEAR_FAULT_LOG',
                                    'PROTOCOL_EVENT_GET_CALIBRATION',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_GET_ERROR_STATUS_WORD',
                                    'PROTOCOL_EVENT_GET_FAULT_LOG',
                                    'PROTOCOL_EVENT_RECOVER_AUTOSAMPLE',
                                    'FACTORY_DEFAULT_SETTINGS',
                                    'USER_DEFAULT_SETTINGS',
                                    'PROTOCOL_EVENT_RUN_TEST_200',
                                    'PROTOCOL_EVENT_SAVE_SETUP_TO_RAM',
                                    'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_DISCOVER',
                                       'DRIVER_EVENT_STOP_AUTOSAMPLE',
                                       'DRIVER_EVENT_GET',
                                       'DRIVER_EVENT_INIT_PARAMS',
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

        self.assert_chunker_sample(chunker, RSN_SAMPLE_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, RSN_SAMPLE_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, RSN_SAMPLE_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, RSN_SAMPLE_RAW_DATA)

        self.assert_chunker_sample(chunker, RSN_PS0_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, RSN_PS0_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, RSN_PS0_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, RSN_PS0_RAW_DATA)

        self.assert_chunker_sample(chunker, RSN_CALIBRATION_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, RSN_CALIBRATION_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, RSN_CALIBRATION_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, RSN_CALIBRATION_RAW_DATA)

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
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
            Parameter.SERIAL_DATA_OUT: '000 000 000',
            Parameter.LATENCY_TRIGGER: 0,
            Parameter.HEADING_ALIGNMENT: '+00000',
            Parameter.HEADING_BIAS: '+00000',
            Parameter.TRANSDUCER_DEPTH:8000,
            Parameter.DATA_STREAM_SELECTION:0,
            Parameter.ENSEMBLE_PER_BURST:0,
            Parameter.BUFFERED_OUTPUT_PERIOD:'00:00:00',
            Parameter.SAMPLE_AMBIENT_SOUND:0,

        }

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(DataParticleType.ADCP_PD0_PARSED_BEAM, self.assert_particle_pd0_data, timeout=40)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=10)

    def _test_test_set_instrument_id(self):
        self.assert_initialize_driver()
        self._test_set_instrument_id()

    def _test_test_set_sleep_enable(self):
        self.assert_initialize_driver()
        self._test_set_sleep_enable()

    def _test_test_set_polled_mode(self):
        self.assert_initialize_driver()
        self._test_set_polled_mode()

    def _test_test_set_xmit_power(self):
        self.assert_initialize_driver()
        self._test_set_xmit_power()

    def _test_test_set_pitch(self):
        self.assert_initialize_driver()
        self._test_set_pitch()

    def _test_test_set_roll(self):
        self.assert_initialize_driver()
        self._test_set_roll()

    def _test_test_set_salinity(self):
        self.assert_initialize_driver()
        self._test_set_salinity()

    def _test_test_set_coordinate_transformation(self):
        self.assert_initialize_driver()
        self._test_set_coordinate_transformation()

    def _test_test_set_sensor_source(self):
        self.assert_initialize_driver()
        self._test_set_sensor_source()

    def _test_test_set_time_per_ensemble(self):
        self.assert_initialize_driver()
        self._test_set_time_per_ensemble()

    def _test_test_set_time_per_ping(self):
        self.assert_initialize_driver()
        self._test_set_time_per_ping()

    def _test_test_set_false_target_threshold(self):
        self.assert_initialize_driver()
        self._test_set_false_target_threshold()

    def _test_test_set_bandwidth_control(self):
        self.assert_initialize_driver()
        self._test_set_bandwidth_control()

    def _test_test_set_correlation_threshold(self):
        self.assert_initialize_driver()
        self._test_set_correlation_threshold()

    def _test_test_set_error_velocity_threshold(self):
        self.assert_initialize_driver()
        self._test_set_error_velocity_threshold()

    def _test_test_set_blank_after_transmit(self):
        self.assert_initialize_driver()
        self._test_set_blank_after_transmit()

    def _test_test_set_clip_data_past_bottom(self):
        self.assert_initialize_driver()
        self._test_set_clip_data_past_bottom()

    def _test_test_set_receiver_gain_select(self):
        self.assert_initialize_driver()
        self._test_set_receiver_gain_select()

    def _test_test_set_number_of_depth_cells(self):
        self.assert_initialize_driver()
        self._test_set_number_of_depth_cells()

    def _test_test_set_pings_per_ensemble(self):
        self.assert_initialize_driver()
        self._test_set_pings_per_ensemble()

    def _test_test_set_depth_cell_size(self):
        self.assert_initialize_driver()
        self._test_set_depth_cell_size()

    def _test_test_set_transmit_length(self):
        self.assert_initialize_driver()
        self._test_set_transmit_length()

    def _test_test_set_ping_weight(self):
        self.assert_initialize_driver()
        self._test_set_ping_weight()

    def _test_test_set_ambiguity_velocity(self):
        self.assert_initialize_driver()
        self._test_set_ambiguity_velocity()

    def _test_test_set_serial_data_out_readonly(self):
        self.assert_initialize_driver()
        self._test_set_serial_data_out_readonly()

    def _test_test_set_serial_flow_control_readonly(self):
        self.assert_initialize_driver()
        self._test_set_serial_flow_control_readonly()

    def _test_test_set_banner_readonly(self):
        self.assert_initialize_driver()
        self._test_set_banner_readonly()

    def _test_test_set_save_nvram_to_recorder_readonly(self):
        self.assert_initialize_driver()
        self._test_set_save_nvram_to_recorder_readonly()

    def _test_test_set_serial_out_fw_switches_readonly(self):
        self.assert_initialize_driver()
        self._test_set_serial_out_fw_switches_readonly()

    def _test_test_set_water_profiling_mode_readonly(self):
        self.assert_initialize_driver()
        self._test_set_water_profiling_mode_readonly()


    def _test_parameter_test_set(self):
        self.assert_initialize_driver()
        self._test_set_parameter_test()

    def _test_set_time_first_ping(self):
        self.assert_initialize_driver()
        self._test_set_time_of_first_ping_readonly()

    def _test_test_set_ranges(self):
        self.assert_initialize_driver()
        fail = False

        for k in self._tested.keys():
            if k not in self._driver_parameters.keys():
                log.error("*WARNING* " + k + " was tested but is not in _driver_parameters")
                #fail = True

        for k in self._driver_parameters.keys():
            if k not in [Parameter.TIME_OF_FIRST_PING, Parameter.TIME] + self._tested.keys():
                log.error("*ERROR* " + k + " is in _driver_parameters but was not tested.")
                fail = True

        self.assertFalse(fail, "See above for un-exercized parameters.")

    def test_set_ranges(self):
        self.assert_initialize_driver()


        self._test_set_xmit_power()
        self._test_set_speed_of_sound()
        self._test_set_pitch()
        self._test_set_roll()
        self._test_set_salinity()
        self._test_set_sensor_source()
        self._test_set_time_per_ensemble()
        self._test_set_false_target_threshold()
        self._test_set_bandwidth_control()
        self._test_set_correlation_threshold()
        self._test_set_error_velocity_threshold()
        self._test_set_blank_after_transmit()
        self._test_set_clip_data_past_bottom()
        self._test_set_receiver_gain_select()
        self._test_set_number_of_depth_cells()
        self._test_set_pings_per_ensemble()
        self._test_set_depth_cell_size()
        self._test_set_transmit_length()
        self._test_set_ping_weight()
        self._test_set_ambiguity_velocity()

        fail = False

        self.assertFalse(fail, "See above for un-exercized parameters.")



###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(WorkhorseDriverQualificationTest, ADCPTMixin):

    def test_recover_from_TG(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """

        self.assert_enter_command_mode()

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        today_plus_1month = (dt.datetime.utcnow() + dt.timedelta(days=31)).strftime("%Y/%m/%d,%H:%m:%S")

        self.tcp_client.send_data("%sTG%s%s" % (NEWLINE, today_plus_1month, NEWLINE))

        self.tcp_client.expect(Prompt.COMMAND)

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.TIME_OF_FIRST_PING, '****/**/**,**:**:**')

    # Note: Parameter.COORDINATE_TRANSFORMATION is ReadOnly
    # Before testing it, remove the readOnly
    def _test_autosample_earth(self):

        #Verify autosample works and data particles are created
        #NOTE: If TG is set autosample behaves odd...

        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.COORDINATE_TRANSFORMATION, '11111')
        self.assert_start_autosample()
        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED_EARTH, self.assert_particle_pd0_data_earth, timeout=140)

        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1)
        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1)

        # Restart autosample and gather a couple samples
        self.assert_sample_autosample(self.assert_particle_pd0_data_earth, DataParticleType.ADCP_PD0_PARSED_EARTH)


    # Note: Parameter.COORDINATE_TRANSFORMATION is ReadOnly
    # Before testin it, remove the readOnly
    def _test_autosample_beam(self):

        """
        Verify autosample works and data particles are created
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.COORDINATE_TRANSFORMATION, '00111')
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED_BEAM, self.assert_particle_pd0_data, timeout=50) # ADCP_PD0_PARSED_BEAM
        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1, timeout=20)

        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1, timeout=20)

        # Stop autosample and do run a couple commands.
        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1)

        # Restart autosample and gather a couple samples
        self.assert_sample_autosample(self.assert_particle_pd0_data, DataParticleType.ADCP_PD0_PARSED_BEAM)

    def assert_cycle(self):
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED_BEAM, self.assert_particle_pd0_data, timeout=200)
        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1, timeout=20)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1, timeout=20)

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
    pass
