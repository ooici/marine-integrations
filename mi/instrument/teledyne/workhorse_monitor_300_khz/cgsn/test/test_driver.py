"""
@package mi.instrument.teledyne.workhorse_monitor_150_khz.cgsn.test.test_driver
@author Roger Unwin
@brief Test cases for InstrumentDriver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import unittest
from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.chunker import StringChunker

from mi.core.log import get_logger; log = get_logger()


from mi.idk.unit_test import InstrumentDriverTestCase


from mi.idk.unit_test import DriverTestMixin

from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import NEWLINE
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import ProtocolState
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import ScheduledJob
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import InstrumentCmds
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import Capability
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import InstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver import Protocol

from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_PD0_PARSED_KEY
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_PD0_PARSED_DataParticle
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_300_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import SAMPLE_RAW_DATA1
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import SAMPLE_RAW_DATA2
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import SAMPLE_RAW_DATA3
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import SAMPLE_RAW_DATA4
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import CALIBRATION_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_data import PS0_RAW_DATA

from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_driver import WorkhorseDriverUnitTest
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_driver import WorkhorseDriverIntegrationTest
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_driver import WorkhorseDriverQualificationTest
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_driver import WorkhorseDriverPublicationTest
from mi.instrument.teledyne.workhorse_monitor_300_khz.test.test_driver import DataParticleType
###
#   Driver parameters for tests
###

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.teledyne.workhorse_monitor_300_khz.cgsn.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'HTWZMW',
    instrument_agent_preload_id = 'IA7',
    instrument_agent_name = 'teledyne_workhorse_monitor_300_khz_cgsn',
    instrument_agent_packet_config = DataParticleType(),

    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 1,
            Parameter.SAVE_NVRAM_TO_RECORDER: True,
            Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.HEADING_ALIGNMENT: 0,
            Parameter.SPEED_OF_SOUND: 1500,
            Parameter.TRANSDUCER_DEPTH: 0,
            Parameter.SALINITY: 35,
            Parameter.COORDINATE_TRANSFORMATION: '00111',
            Parameter.SENSOR_SOURCE: "1111101",
            Parameter.TIME_PER_BURST: '00:00:00.00',
            Parameter.ENSEMBLES_PER_BURST: 0,
            Parameter.BUFFER_OUTPUT_PERIOD: '00:00:00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            Parameter.CLIP_DATA_PAST_BOTTOM: False,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
            Parameter.TIME_PER_ENSEMBLE: '01:00:00.00',
            Parameter.TIME_PER_PING: '01:20.00',
            Parameter.NUMBER_OF_DEPTH_CELLS: 30,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
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
    OFF_VALUE = 'off_value'
    
    ###
    # Parameter and Type Definitions
    ###
    # Verified with ADCPT-B IOS
    _driver_parameters = {
        Parameter.SERIAL_DATA_OUT:           {TYPE: str,  READONLY: True,  DA: False, STARTUP: True,  DEFAULT: "000 000 000",VALUE: "000 000 000",OFF_VALUE: "000 000 001"},
        Parameter.SERIAL_FLOW_CONTROL:       {TYPE: str,  READONLY: True,  DA: False, STARTUP: True,  DEFAULT: '11110', VALUE: '11110',      OFF_VALUE: '10110'},
        Parameter.BANNER:                    {TYPE: bool, READONLY: True,  DA: False, STARTUP: True,  DEFAULT: 0,       VALUE: False,        OFF_VALUE: True}, 
        Parameter.INSTRUMENT_ID:             {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 0,       VALUE: 0,            OFF_VALUE: 1},
        Parameter.SLEEP_ENABLE:              {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 1,       VALUE: 1,            OFF_VALUE: 0},
        Parameter.SAVE_NVRAM_TO_RECORDER:    {TYPE: bool, READONLY: False, DA: False, STARTUP: True,  DEFAULT: True,    VALUE: True,         OFF_VALUE: False},
        Parameter.POLLED_MODE:               {TYPE: bool, READONLY: False, DA: False, STARTUP: True,  DEFAULT: False,   VALUE: False,        OFF_VALUE: True},
        Parameter.XMIT_POWER:                {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 255,     VALUE: 255,          OFF_VALUE: 250},
        Parameter.HEADING_ALIGNMENT:         {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 0,       VALUE: 0,            OFF_VALUE: 1},
        Parameter.SPEED_OF_SOUND:            {TYPE: int,  READONLY: False, DA: True, STARTUP: True,  DEFAULT: 1500,    VALUE: 1500,         OFF_VALUE: 1480},
        Parameter.TRANSDUCER_DEPTH:          {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 0,       VALUE: 0,            OFF_VALUE: 32767},
        Parameter.SALINITY:                  {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 35,      VALUE: 35,           OFF_VALUE: 36},
        Parameter.COORDINATE_TRANSFORMATION: {TYPE: str,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: '00111', VALUE: '00111',      OFF_VALUE: '00000'},
        Parameter.SENSOR_SOURCE:             {TYPE: str,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: "1111101",VALUE: "1111101",   OFF_VALUE: '0000000'},
        Parameter.TIME_PER_BURST:            {TYPE: str,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: '00:00:00.00',VALUE: '00:00:00.00',OFF_VALUE: '00:55:00.00'},
        Parameter.ENSEMBLES_PER_BURST:       {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 0,       VALUE: 0,            OFF_VALUE: 999},
        Parameter.TIME_OF_FIRST_PING:        {TYPE: str,  READONLY: True,  DA: False, STARTUP: False},
        Parameter.TIME:                      {TYPE: str,  READONLY: True,  DA: False, STARTUP: False},
        Parameter.BUFFER_OUTPUT_PERIOD:      {TYPE: str,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: '00:00:00', VALUE: '00:00:00',   OFF_VALUE: '00:55:00'},
        Parameter.FALSE_TARGET_THRESHOLD:    {TYPE: str,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: '050,001', VALUE: '050,001',    OFF_VALUE: '049,002'},
        Parameter.CORRELATION_THRESHOLD:     {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 64,      VALUE: 64,           OFF_VALUE: 63},
        Parameter.SERIAL_OUT_FW_SWITCHES:    {TYPE: str,  READONLY: True,  DA: False, STARTUP: True,  DEFAULT: '111100000', VALUE: '111100000',  OFF_VALUE: '111100001'},
        Parameter.ERROR_VELOCITY_THRESHOLD:  {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 2000,    VALUE: 2000,         OFF_VALUE: 1999},
        Parameter.BLANK_AFTER_TRANSMIT:      {TYPE: int,  READONLY: True,  DA: False, STARTUP: True,  DEFAULT: 352,     VALUE: 352,          OFF_VALUE: 342},
        Parameter.CLIP_DATA_PAST_BOTTOM:     {TYPE: bool, READONLY: False, DA: False, STARTUP: True,  DEFAULT: False,   VALUE: False,        OFF_VALUE: True},
        Parameter.RECEIVER_GAIN_SELECT:      {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 1,       VALUE: 1,            OFF_VALUE: 0},
        Parameter.WATER_REFERENCE_LAYER:     {TYPE: str,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: '001,005', VALUE: '001,005',    OFF_VALUE: '002,006'},
        Parameter.WATER_PROFILING_MODE:      {TYPE: int,  READONLY: True,  DA: False, STARTUP: True,  DEFAULT: 1,       VALUE: 1,            OFF_VALUE: 0},
        Parameter.TRANSMIT_LENGTH:           {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 0,       VALUE: 0,            OFF_VALUE: 1},
        Parameter.PING_WEIGHT:               {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 0,       VALUE: 0,            OFF_VALUE: 1},
        Parameter.AMBIGUITY_VELOCITY:        {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 175,     VALUE: 175,          OFF_VALUE: 176},
        Parameter.TIME_PER_ENSEMBLE:         {TYPE: str,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: '01:00:00.00',VALUE: '01:00:00.00',OFF_VALUE: '00:00:01.00'},
        Parameter.TIME_PER_PING:             {TYPE: str,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: '01:20.00',VALUE: '01:20.00',   OFF_VALUE: '00:02.00'},
        Parameter.BANDWIDTH_CONTROL:         {TYPE: int,  READONLY: True,  DA: False, STARTUP: True,  DEFAULT: 1,       VALUE: 1,            OFF_VALUE: 0},
        Parameter.NUMBER_OF_DEPTH_CELLS:     {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 30,      VALUE: 30,           OFF_VALUE: 90},
        Parameter.PINGS_PER_ENSEMBLE:        {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 1,       VALUE: 1,            OFF_VALUE: 2},
        Parameter.DEPTH_CELL_SIZE:           {TYPE: int,  READONLY: False, DA: False, STARTUP: True,  DEFAULT: 800,     VALUE: 800,          OFF_VALUE: 790},
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
        Capability.POWER_DOWN: { STATES: [ProtocolState.COMMAND]},
    }

    #name, type done, value pending
    EF_CHAR = '\xef'
    _calibration_data_parameters = {
        ADCP_COMPASS_CALIBRATION_KEY.FLUXGATE_CALIBRATION_TIMESTAMP: {'type': float, 'value': -1785800539.0 },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BX: {'type': list, 'value': [3.8774e-01, 4.7391e-01, -2.5109e-02, -1.4835e-02] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BY: {'type': list, 'value': [-8.2932e-03, 1.8434e-02, -5.2666e-02, 5.8153e-01] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BZ: {'type': list, 'value': [2.2218e-01, -1.7820e-01, 2.9168e-01, 1.6125e-02] },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_ERR: {'type': list, 'value': [-5.3909e-01, 4.7951e-01, 7.0135e-01, 4.0629e-02] },
        ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET: {'type': list, 'value': [3.8310e+04, 3.4872e+04, 3.7008e+04, 3.4458e+04] },
        ADCP_COMPASS_CALIBRATION_KEY.ELECTRICAL_NULL: {'type': float, 'value': 34159 },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_CALIBRATION_TIMESTAMP: {'type': float, 'value': 1348176909.0 },
        ADCP_COMPASS_CALIBRATION_KEY.CALIBRATION_TEMP: {'type': float, 'value': 24.9 },
        ADCP_COMPASS_CALIBRATION_KEY.ROLL_UP_DOWN: {'type': list, 'value': [3.5167e-07, -1.4728e-05, -3.5240e-07,  1.5687e-05] },
        ADCP_COMPASS_CALIBRATION_KEY.PITCH_UP_DOWN: {'type': list, 'value': [-1.4773e-05, 2.9804e-23, -1.5654e-05, -1.2675e-07] },
        ADCP_COMPASS_CALIBRATION_KEY.OFFSET_UP_DOWN: {'type': list, 'value': [3.2170e+04, 3.3840e+04, 3.4094e+04, 3.3028e+04] },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_NULL: {'type': float, 'value': 33296 }
    }

    #name, type done, value pending
    _system_configuration_data_parameters = {
        ADCP_SYSTEM_CONFIGURATION_KEY.SERIAL_NUMBER: {'type': unicode, 'value': "18493" },
        ADCP_SYSTEM_CONFIGURATION_KEY.TRANSDUCER_FREQUENCY: {'type': int, 'value': 307200 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.CONFIGURATION: {'type': unicode, 'value': "4 BEAM, JANUS" },
        ADCP_SYSTEM_CONFIGURATION_KEY.MATCH_LAYER: {'type': unicode, 'value': "10" },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_ANGLE: {'type': int, 'value': 20 },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_PATTERN: {'type': unicode, 'value': "CONVEX" },
        ADCP_SYSTEM_CONFIGURATION_KEY.ORIENTATION: {'type': unicode, 'value': "UP" },
        ADCP_SYSTEM_CONFIGURATION_KEY.SENSORS: {'type': unicode, 'value': "HEADING  TILT 1  TILT 2  TEMPERATURE" },
        ADCP_SYSTEM_CONFIGURATION_KEY.TEMPERATURE_SENSOR_OFFSET: {'type': float, 'value': -0.02 },
        ADCP_SYSTEM_CONFIGURATION_KEY.CPU_FIRMWARE: {'type': unicode, 'value': "50.40 [0]" },
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_REQUIRED: {'type': unicode, 'value': "1.16" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_ACTUAL: {'type': unicode, 'value': "1.16" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_VERSION: {'type': unicode, 'value': "ad48" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_TYPE: {'type': unicode, 'value': "1f" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_VERSION: {'type': unicode, 'value': "ad48" },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_TYPE: {'type': unicode, 'value': "1f" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_VERSION: {'type': unicode, 'value': "85d3" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_TYPE: {'type': unicode, 'value': "7" }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS: {'type': unicode, 'value': u'2F  00 00 06 FF 25 D1  09 CPU727-2011-00E\n16  00 00 06 F5 E5 D1  09 DSP727-2001-04H\n27  00 00 06 FF 29 31  09 PIO727-3000-00G\n91  00 00 06 F6 17 A7  09 REC727-1000-04E\n'}
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
        ADCP_PD0_PARSED_KEY.SERIAL_NUMBER: {'type': long, 'value': 206045184 },
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

    def assert_particle_pd0_data(self, data_particle, verify_values=True):
        '''
        Verify an adcpt ps0 data particle
        @param data_particle: ADCPT_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        log.debug("IN assert_particle_pd0_data")
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_PD0_PARSED_BEAM)
        self.assert_data_particle_parameters(data_particle, self._pd0_parameters) # , verify_values

    def setUp(self):
        DriverTestMixin.setUp(self)

        self._driver_parameter_defaults = {}
        for label in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[label]:
                self._driver_parameter_defaults[label] = self._driver_parameters[label][self.VALUE]
            else:
                self._driver_parameter_defaults[label] = None

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(WorkhorseDriverUnitTest, ADCPTMixin):
    def setUp(self):
        WorkhorseDriverUnitTest.setUp(self)
        ADCPTMixin.setUp(self)

    def test_defaults(self):
        for label in sorted(self._driver_parameter_defaults.keys()):
            log.debug(str(label) + " = " + str(self._driver_parameter_defaults[label]))

    def test_sanity(self):
        my_event_callback = Mock(spec="fake evt_callback")
        driver = InstrumentDriver(self._got_data_event_callback)
        protocol = Protocol(Prompt, NEWLINE, my_event_callback)

    def test_send_break(self):
        my_event_callback = Mock(spec="fake evt_callback")
        self.protocol = Protocol(Prompt, NEWLINE, my_event_callback)
        def fake_send_break1_cmd(duration):
            log.debug("IN fake_send_break1_cmd")
            self.protocol._linebuf = "[BREAK Wakeup A]\n" + \
                                     "  Polled Mode is OFF -- Battery Saver is ONWorkHorse Broadband ADCP Version 50.40\n" + \
                                     "Teledyne RD Instruments (c) 1996-2010\n" + \
                                     "All Rights Reserved."

        def fake_send_break2_cmd(duration):
            log.debug("IN fake_send_break2_cmd")
            self.protocol._linebuf = "[BREAK Wakeup A]" + NEWLINE + \
                                    "WorkHorse Broadband ADCP Version 50.40" + NEWLINE + \
                                    "Teledyne RD Instruments (c) 1996-2010" + NEWLINE + \
                                    "All Rights Reserved."

        self.protocol._send_break_cmd = fake_send_break1_cmd

        self.assertTrue(self.protocol._send_break(500))

        self.protocol._send_break_cmd = fake_send_break2_cmd

        self.assertTrue(self.protocol._send_break(500))

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        self.maxDiff = None
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

        self.assert_particle_published(driver, CALIBRATION_RAW_DATA, self.assert_particle_compass_calibration, True)
        self.assert_particle_published(driver, PS0_RAW_DATA, self.assert_particle_system_configuration, True)

        self.assert_particle_published(driver, SAMPLE_RAW_DATA1, self.assert_particle_pd0_data, True)
        self.assert_particle_published(driver, SAMPLE_RAW_DATA2, self.assert_particle_pd0_data, True)
        self.assert_particle_published(driver, SAMPLE_RAW_DATA3, self.assert_particle_pd0_data, True)
        self.assert_particle_published(driver, SAMPLE_RAW_DATA4, self.assert_particle_pd0_data, True)

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
                                    'PROTOCOL_EVENT_CLEAR_ERROR_STATUS_WORD',
                                    'PROTOCOL_EVENT_CLEAR_FAULT_LOG',
                                    'PROTOCOL_EVENT_GET_CALIBRATION',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_GET_ERROR_STATUS_WORD',
                                    'PROTOCOL_EVENT_GET_FAULT_LOG',
                                    'PROTOCOL_EVENT_GET_INSTRUMENT_TRANSFORM_MATRIX',
                                    'PROTOCOL_EVENT_POWER_DOWN',
                                    'PROTOCOL_EVENT_RECOVER_AUTOSAMPLE',
                                    'PROTOCOL_EVENT_RUN_TEST_200',
                                    'PROTOCOL_EVENT_SAVE_SETUP_TO_RAM',
                                    'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC',
                                    'PROTOCOL_EVENT_SEND_LAST_SAMPLE'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_INIT_PARAMS',
                                    'DRIVER_EVENT_DISCOVER',
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

        self.assert_chunker_sample(chunker, SAMPLE_RAW_DATA1)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_RAW_DATA1)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_RAW_DATA1, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_RAW_DATA1)

        self.assert_chunker_sample(chunker, PS0_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, PS0_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, PS0_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, PS0_RAW_DATA)

        self.assert_chunker_sample(chunker, CALIBRATION_RAW_DATA)
        self.assert_chunker_sample_with_noise(chunker, CALIBRATION_RAW_DATA)
        self.assert_chunker_fragmented_sample(chunker, CALIBRATION_RAW_DATA, 32)
        self.assert_chunker_combined_sample(chunker, CALIBRATION_RAW_DATA)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        my_event_callback = Mock(spec="my_event_callback")
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
    # dict to store if a param has been range stress tested
    _tested = {}

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample
        """
        log.debug("IN test_autosample_particle_generation")
        self.assert_initialize_driver()

        # lets set things to do faster pinging so the test is runable in our time scales.
        self.assert_set_bulk({Parameter.PINGS_PER_ENSEMBLE: 5,
                              Parameter.TIME_PER_PING: "00:10.00",
                              Parameter.TIME_PER_ENSEMBLE: "00:01:00.00"})

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_async_particle_generation(DataParticleType.ADCP_PD0_PARSED_BEAM, self.assert_particle_pd0_data, timeout=200)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=50)

    def test_set_ranges(self):
        # Updated to match ADCPT-B
        log.debug("IN test_set_ranges")
        self.assert_initialize_driver()
        self._test_set_serial_data_out_readonly()
        self._test_set_serial_flow_control_readonly()
        self._test_set_banner_readonly()
        self._test_set_instrument_id()
        self._test_set_sleep_enable()
        self._test_set_save_nvram_to_recorder()
        self._test_set_polled_mode()
        self._test_set_xmit_power()
        self._test_set_heading_alignment()
        self._test_set_speed_of_sound()
        self._test_set_transducer_depth()
        self._test_set_salinity()
        self._test_set_coordinate_transformation()
        self._test_set_sensor_source()
        self._test_set_time_per_burst()
        self._test_set_ensembles_per_burst()
        self._test_set_time_of_first_ping_readonly()
        self._test_set_buffer_output_period()
        self._test_set_false_target_threshold()
        self._test_set_correlation_threshold()
        self._test_set_serial_out_fw_switches_readonly()
        self._test_set_error_velocity_threshold()
        self._test_set_blank_after_transmit_readonly()
        self._test_set_clip_data_past_bottom()
        self._test_set_receiver_gain_select()
        self._test_set_water_reference_layer()
        self._test_set_water_profiling_mode_readonly()
        self._test_set_transmit_length()
        self._test_set_ping_weight()
        self._test_set_ambiguity_velocity()
        self._test_set_time_per_ensemble()
        self._test_set_time_per_ping()
        self._test_set_bandwidth_control_readonly()
        self._test_set_number_of_depth_cells()
        self._test_set_pings_per_ensemble()
        self._test_set_depth_cell_size()

        fail = False
        log.error("self._tested = " + repr(self._tested))
        for k in self._tested.keys():
            if k not in self._driver_parameters.keys():
                log.error("*WARNING* " + k + " was tested but is not in _driver_parameters")
                #fail = True

        for k in self._driver_parameters.keys():
            if k not in [Parameter.TIME_OF_FIRST_PING, Parameter.TIME] + self._tested.keys():
                log.error("*ERROR* " + k + " is in _driver_parameters but was not tested.")
                fail = True

        self.assertFalse(fail, "See above for un-exercized parameters.")

    def test_set_bulk(self):
        """
        Test all set commands. Verify all exception cases.
        """
        log.error("IN test_set_bulk")
        self.assert_initialize_driver()

        params = {}
        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if self._driver_parameters[k][self.READONLY] == False:
                    params[k] = self._driver_parameters[k][self.VALUE]
        # Set all parameters to a known ground state
        self.assert_set_bulk(params)

        ###
        #   Instrument Parameteres
        ###

        # set to off_values so we get a config change
        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    self.assert_set(k, self._driver_parameters[k][self.OFF_VALUE])
                    log.debug("WANT PARAM CHANGE EVENT, SETTING " + k + " to " + str(self._driver_parameters[k][self.VALUE]))
                if True == self._driver_parameters[k][self.READONLY]:
                    self.assert_set_readonly(k)

        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    self.assert_set(k, self._driver_parameters[k][self.VALUE])
                    log.debug("WANT PARAM CHANGE EVENT, SETTING " + k + " to " + str(self._driver_parameters[k][self.VALUE]))
                if True == self._driver_parameters[k][self.READONLY]:
                    self.assert_set_exception(k, self._driver_parameters[k][self.VALUE])
                    log.debug("WANT EXCEPTION SETTING " + k + " to " + str(self._driver_parameters[k][self.VALUE]))

    def test_startup_params(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.

        since nose orders the tests by ascii value this should run first.
        """
        log.error("IN test_startup_params")
        self.assert_initialize_driver()

        # Updated to reflect T-F startup params.
        get_values = {
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 1,
            Parameter.SAVE_NVRAM_TO_RECORDER: True,
            Parameter.POLLED_MODE: False,
            Parameter.XMIT_POWER: 255,
            Parameter.HEADING_ALIGNMENT: 0,
            Parameter.SPEED_OF_SOUND: 1500,
            Parameter.TRANSDUCER_DEPTH: 0,
            Parameter.SALINITY: 35,
            Parameter.COORDINATE_TRANSFORMATION: '00111',
            Parameter.SENSOR_SOURCE: "1111101",
            Parameter.TIME_PER_BURST: '00:00:00.00',
            Parameter.ENSEMBLES_PER_BURST: 0,
            Parameter.BUFFER_OUTPUT_PERIOD: '00:00:00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            Parameter.CORRELATION_THRESHOLD: 64,
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            Parameter.CLIP_DATA_PAST_BOTTOM: False,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
            Parameter.TIME_PER_ENSEMBLE: '01:00:00.00',
            Parameter.TIME_PER_PING: '01:20.00',
            Parameter.NUMBER_OF_DEPTH_CELLS: 30,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
        }

        # Change the values of these parameters to something before the
        # driver is reinitalized.  They should be blown away on reinit.
        new_values = {}

        for k in self._driver_parameters.keys():
            if self.VALUE in self._driver_parameters[k]:
                if False == self._driver_parameters[k][self.READONLY]:
                    new_values[k] = self._driver_parameters[k][self.OFF_VALUE]

        self.assert_startup_parameters(self.assert_driver_parameters, new_values, get_values)

    def _test_set_heading_alignment(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for HEADING_ALIGNMENT ======")
        # HEADING_ALIGNMENT:  -- -17999 to 18000
        self.assert_set(Parameter.HEADING_ALIGNMENT, -17999)
        self.assert_set(Parameter.HEADING_ALIGNMENT, 0)
        self.assert_set(Parameter.HEADING_ALIGNMENT, 18000)

        self.assert_set_exception(Parameter.HEADING_ALIGNMENT, -18000)
        self.assert_set_exception(Parameter.HEADING_ALIGNMENT, 18001)

        self.assert_set(Parameter.HEADING_ALIGNMENT, self._driver_parameters[Parameter.HEADING_ALIGNMENT][self.VALUE])
        self._tested[Parameter.HEADING_ALIGNMENT] = True

    def _test_set_transducer_depth(self):
        ###
        #   test get set of a variety of parameter ranges
        ###
        log.debug("====== Testing ranges for TRANSDUCER_DEPTH ======")
        # HEADING_ALIGNMENT:  -- -17999 to 18000
        self.assert_set(Parameter.TRANSDUCER_DEPTH, 0)
        self.assert_set(Parameter.TRANSDUCER_DEPTH, 32767)
        self.assert_set(Parameter.TRANSDUCER_DEPTH, 65535)

        self.assert_set_exception(Parameter.TRANSDUCER_DEPTH, -1)
        self.assert_set_exception(Parameter.TRANSDUCER_DEPTH, 65536)
        self.assert_set_exception(Parameter.TIME_PER_BURST, "LEROY JENKINS")
        self.assert_set_exception(Parameter.TIME_PER_BURST, 3.1415926)

        self.assert_set(Parameter.TRANSDUCER_DEPTH, self._driver_parameters[Parameter.TRANSDUCER_DEPTH][self.VALUE])
        self._tested[Parameter.TRANSDUCER_DEPTH] = True

    def _test_set_depth_cell_size(self):
        ###
        #   test get set of a variety of parameter ranges
        #   * Override existing function, this instrument has a different range maxing out at 1600
        ###
        log.debug("====== Testing ranges for DEPTH_CELL_SIZE ======")

        # DEPTH_CELL_SIZE: int 80 - 3200
        self.assert_set(Parameter.DEPTH_CELL_SIZE, 20)
        self.assert_set(Parameter.DEPTH_CELL_SIZE, 1600)

        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, 1601)
        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, -1)
        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, 19)
        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, 3.1415926)
        self.assert_set_exception(Parameter.DEPTH_CELL_SIZE, "LEROY JENKINS")
        #
        # Reset to good value.
        #
        #self.assert_set(TeledyneParameter.DEPTH_CELL_SIZE, self._driver_parameter_defaults[TeledyneParameter.DEPTH_CELL_SIZE])
        self.assert_set(Parameter.DEPTH_CELL_SIZE, self._driver_parameters[Parameter.DEPTH_CELL_SIZE][self.VALUE])
        self._tested[Parameter.DEPTH_CELL_SIZE] = True

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(WorkhorseDriverQualificationTest, ADCPTMixin):
    # works
    def test_autosample(self):
        """
        Verify autosample works and data particles are created
        """
        self.assert_enter_command_mode()

        self.assert_set_parameter(Parameter.TIME_PER_ENSEMBLE, '00:01:00.00', True) 
        self.assert_set_parameter(Parameter.TIME_PER_PING, '00:30.00', True) 

        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED_BEAM, self.assert_particle_pd0_data, timeout=90) 
        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1, timeout=50)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1, timeout=50)

        # Stop autosample and do run a couple commands.
        self.assert_stop_autosample()

        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1)

        # Restart autosample and gather a couple samples
        self.assert_sample_autosample(self.assert_particle_pd0_data, DataParticleType.ADCP_PD0_PARSED_BEAM)

    def assert_cycle(self):
        self.assert_start_autosample()

        self.assert_particle_async(DataParticleType.ADCP_PD0_PARSED_BEAM, self.assert_particle_pd0_data, timeout=200)
        self.assert_particle_polled(ProtocolEvent.GET_CALIBRATION, self.assert_compass_calibration, DataParticleType.ADCP_COMPASS_CALIBRATION, sample_count=1, timeout=60)
        self.assert_particle_polled(ProtocolEvent.GET_CONFIGURATION, self.assert_configuration, DataParticleType.ADCP_SYSTEM_CONFIGURATION, sample_count=1, timeout=60)
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
