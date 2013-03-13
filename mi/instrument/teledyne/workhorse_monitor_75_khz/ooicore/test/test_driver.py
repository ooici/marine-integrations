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

import unittest
import time as time
import datetime as dt
from mi.core.time import get_timestamp_delayed

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.instrument.chunker import StringChunker
from mi.core.log import get_logger; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.instrument.teledyne.test.test_driver import TeledyneUnitTest
from mi.instrument.teledyne.test.test_driver import TeledyneIntegrationTest
from mi.instrument.teledyne.test.test_driver import TeledyneQualificationTest
from mi.instrument.teledyne.test.test_driver import TeledynePublicationTest

from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import InstrumentDriver
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import InstrumentCmds
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ProtocolState
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Capability
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Protocol

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ScheduledJob
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import NEWLINE

from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_PD0_PARSED_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_PD0_PARSED_DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_SYSTEM_CONFIGURATION_DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_KEY
from mi.instrument.teledyne.workhorse_monitor_75_khz.driver import ADCP_COMPASS_CALIBRATION_DataParticle



from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import SAMPLE_RAW_DATA 
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import CALIBRATION_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import PS0_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import PS3_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import FD_RAW_DATA
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.test.test_data import PT200_RAW_DATA

from random import randint


tolerance = 500

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
    Mixin class used for storing data particle constance
    and common data assertion methods.
    '''
    ###
    # Parameter and Type Definitions
    ###
    # Is DEFAULT the DEFAULT STARTUP VALUE?
    _driver_parameters = {
        Parameter.SERIAL_DATA_OUT: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: False},
        Parameter.SERIAL_FLOW_CONTROL: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 11110},
        Parameter.BANNER: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.INSTRUMENT_ID: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False},
        Parameter.SLEEP_ENABLE: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.SAVE_NVRAM_TO_RECORDER: {TYPE: bool, READONLY: True, DA: False, STARTUP: True, DEFAULT: True, VALUE: True},
        Parameter.POLLED_MODE: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: False},
        Parameter.XMIT_POWER: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 255, VALUE: 255},
        Parameter.SPEED_OF_SOUND: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 1485, VALUE: 1485},
        Parameter.PITCH: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.ROLL: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.SALINITY: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: 35, VALUE: 35},
        Parameter.SENSOR_SOURCE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False},
        Parameter.TIME_PER_ENSEMBLE: {TYPE: dt.datetime, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '00:00.00'},
        Parameter.TIME_OF_FIRST_PING: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False},
        Parameter.TIME_PER_PING: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '00:01.00'},
        Parameter.TIME: {TYPE: time, READONLY: False, DA: False, STARTUP: True, DEFAULT: False},
        Parameter.FALSE_TARGET_THRESHOLD: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '050,001'},
        Parameter.BANDWIDTH_CONTROL: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.CORRELATION_THRESHOLD: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 64},
        Parameter.SERIAL_OUT_FW_SWITCHES: {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: '111 100 000'},
        Parameter.ERROR_VELOCITY_THRESHOLD: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 2000},
        Parameter.BLANK_AFTER_TRANSMIT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0704},
        Parameter.CLIP_DATA_PAST_BOTTOM: {TYPE: bool, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.RECEIVER_GAIN_SELECT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},
        Parameter.WATER_REFERENCE_LAYER: {TYPE: str, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: '001,005'},
        Parameter.WATER_PROFILING_MODE: {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},
        Parameter.NUMBER_OF_DEPTH_CELLS: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 100},
        Parameter.PINGS_PER_ENSEMBLE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 1},
        Parameter.DEPTH_CELL_SIZE: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 800},
        Parameter.TRANSMIT_LENGTH: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.PING_WEIGHT: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 0},
        Parameter.AMBIGUITY_VELOCITY: {TYPE: int, READONLY: False, DA: False, STARTUP: True, DEFAULT: False, VALUE: 175}
    }

    #name, type done, value pending
    EF_CHAR = '\xef'
    _calibration_data_parameters = {
        ADCP_COMPASS_CALIBRATION_KEY.FLUXGATE_CALIBRATION_TIMESTAMP: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BX: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BY: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_BZ: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.S_INVERSE_ERR: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.COIL_OFFSET: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.ELECTRICAL_NULL: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_CALIBRATION_TIMESTAMP: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.ROLL_UP_DOWN: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.PITCH_UP_DOWN: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.OFFSET_UP_DOWN: {'type': float, 'value': 752 },
        ADCP_COMPASS_CALIBRATION_KEY.TILT_NULL: {'type': float, 'value': 752 }
    }

    #name, type done, value pending
    _ps0_parameters = {
        ADCP_SYSTEM_CONFIGURATION_KEY.SERIAL_NUMBER: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.TRANSDUCER_FREQUENCY: {'type': int, 'value': 752 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.CONFIGURATION: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.MATCH_LAYER: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_ANGLE: {'type': int, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.BEAM_PATTERN: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.ORIENTATION: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.SENSORS: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c3: {'type': float, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c2: {'type': float, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_c1: {'type': float, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.PRESSURE_COEFF_OFFSET: {'type': float, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.TEMPERATURE_SENSOR_OFFSET: {'type': float, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.CPU_FIRMWARE: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_REQUIRED: {'type': str, 'value': 752 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOOT_CODE_ACTUAL: {'type': str, 'value': 752 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_VERSION: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_1_TYPE: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_VERSION: {'type': str, 'value': 752 },
        ADCP_SYSTEM_CONFIGURATION_KEY.DEMOD_2_TYPE: {'type': str, 'value': 752 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_VERSION: {'type': str, 'value': 752 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.POWER_TIMING_TYPE: {'type': str, 'value': 752 }, 
        ADCP_SYSTEM_CONFIGURATION_KEY.BOARD_SERIAL_NUMBERS: {'type': str, 'value': 752 }
    }

    #name, type done, value pending
    _pd0_parameters = {
        ADCP_PD0_PARSED_KEY.PART_000_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_001_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_002_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_003_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_004_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_005_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_006_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_007_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_008_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_009_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_010_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_011_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_012_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_013_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_014_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_015_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_016_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_017_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_018_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_019_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_020_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_021_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_022_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_023_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_024_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_025_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_026_float32: {'type': float, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_027_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_028_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_029_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_030_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_031_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_032_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_033_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_034_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_035_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_036_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_037_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_038_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_039_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_040_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_041_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_042_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_043_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_044_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_045_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_046_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_047_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_048_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_049_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_050_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_051_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_052_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_053_uint64: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_054_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_055_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_056_uint32: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_057_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_058_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_059_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_060_float64: {'type': float, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_061_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_062_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_063_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_064_int8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_065_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_066_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_067_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_068_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_069_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_070_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_071_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_072_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_073_float32: {'type': float, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_074_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_075_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_076_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_077_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_078_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_079_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_080_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_081_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_082_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_083_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_084_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_085_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_086_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_087_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_088_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_089_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_090_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_091_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_092_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_093_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_094_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_095_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_096_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_097_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_098_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_099_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_100_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_101_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_102_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_103_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_104_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_105_uint32: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_106_uint32: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_107_float64: {'type': float, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_108_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_109_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_110_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_111_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_112_int16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_113_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_114_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_115_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_116_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_117_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_118_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_119_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_120_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_121_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_122_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_123_uint16: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_124_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_125_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_126_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_127_uint8: {'type': int, 'value': 752 },
        ADCP_PD0_PARSED_KEY.PART_128_uint16: {'type': int, 'value': 752 }
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

        if (isinstance(data_particle, DataParticleType.ADCP_PD0_PARSED)):
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
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_COMPASS_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_data_parameters, verify_values)

    def assert_particle_system_configuration(self, data_particle, verify_values = True):
        '''
        Verify an adcpt fd data particle
        @param data_particle: ADCPT_FDDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_SYSTEM_CONFIGURATION)
        self.assert_data_particle_parameters(data_particle, self._ps0_parameters, verify_values)

    def assert_particle_pd0_data(self, data_particle, verify_values = True):
        '''
        Verify an adcpt ps0 data particle
        @param data_particle: ADCPT_PS0DataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.ADCP_PD0_PARSED)
        self.assert_data_particle_parameters(data_particle, self._pd0_parameters, verify_values)


###############################################################################
#                                UNIT TESTS                                   #
###############################################################################
@attr('UNIT', group='mi')
class DriverUnitTest(TeledyneUnitTest, ADCPTMixin):
    def setUp(self):
        TeledyneUnitTest.setUp(self)

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
        """
        self.assert_chunker_sample(chunker, SAMPLE_TIDE_DATA_POLLED)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_TIDE_DATA_POLLED)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_TIDE_DATA_POLLED)
        self.assert_chunker_combined_sample(chunker, SAMPLE_TIDE_DATA_POLLED)

        self.assert_chunker_sample(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_combined_sample(chunker, SAMPLE_TIDE_DATA)

        self.assert_chunker_sample(chunker, SAMPLE_WAVE_BURST)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_WAVE_BURST)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_WAVE_BURST, 1024)
        self.assert_chunker_combined_sample(chunker, SAMPLE_WAVE_BURST)

        self.assert_chunker_sample(chunker, SAMPLE_STATISTICS)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_STATISTICS)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_STATISTICS, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_STATISTICS)

        self.assert_chunker_sample(chunker, SAMPLE_DEVICE_CALIBRATION)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_DEVICE_CALIBRATION)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_DEVICE_CALIBRATION, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_DEVICE_CALIBRATION)

        self.assert_chunker_sample(chunker, SAMPLE_DEVICE_STATUS) 
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_DEVICE_STATUS)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_DEVICE_STATUS, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_DEVICE_STATUS)
        """

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
        self.assert_particle_published(driver, SAMPLE_RAW_DATA, self.assert_particle_pd0_data, True)


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
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_ACQUIRE_SAMPLE',
                                    'DRIVER_EVENT_ACQUIRE_STATUS',
                                    'DRIVER_EVENT_CLOCK_SYNC',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'PROTOCOL_EVENT_ACQUIRE_CONFIGURATION',
                                    'PROTOCOL_EVENT_QUIT_SESSION',
                                    'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_GET',
                                       'DRIVER_EVENT_STOP_AUTOSAMPLE',
                                       'PROTOCOL_EVENT_SEND_LAST_SAMPLE',
                                       'PROTOCOL_EVENT_ACQUIRE_CONFIGURATION',
                                       'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC',
                                       'DRIVER_EVENT_ACQUIRE_STATUS'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(TeledyneIntegrationTest, ADCPTMixin):
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
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        # The clock in this instrument is a little odd.  It looks like if you wait until the edge of a second
        # to set it, it immediately ticks after the set, making it off by 1.  For now we will accept this
        # behavior, but we need to check this behavior on all SBE instruments.

        time_format = "%Y/%m/%d,%H:%M:%S"
        set_time = get_timestamp_delayed(time_format)

        self.assert_set(Parameter.TIME, set_time, no_get=True, startup=True)
        self.assertTrue(self._is_time_set(Parameter.TIME, set_time, time_format, tolerance))

        #
        # look at 16 for tolerance, within 5 minutes.
        # model after the 16

        ###
        #   Instrument Parameteres
        ###

        self.assert_set_readonly(Parameter.SERIAL_DATA_OUT)
        self.assert_set_readonly(Parameter.SERIAL_FLOW_CONTROL)
        self.assert_set_readonly(Parameter.SAVE_NVRAM_TO_RECORDER)
        self.assert_set_readonly(Parameter.WATER_PROFILING_MODE)
        self.assert_set_readonly(Parameter.SERIAL_OUT_FW_SWITCHES)

        self.assert_set(Parameter.BANNER, False)
        self.assert_set(Parameter.INSTRUMENT_ID, 0)
        self.assert_set(Parameter.SLEEP_ENABLE, 0)
        self.assert_set(Parameter.POLLED_MODE, True)
        self.assert_set(Parameter.XMIT_POWER, 255)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1485)
        self.assert_set(Parameter.PITCH, 0)
        self.assert_set(Parameter.ROLL, 0)
        self.assert_set(Parameter.SALINITY, 35)
        self.assert_set(Parameter.SENSOR_SOURCE, 1111101)
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, '01:00:00.00')
        self.assert_set(Parameter.TIME_OF_FIRST_PING, '****/**/**,**:**:**')
        self.assert_set(Parameter.TIME_PER_PING, '00:01.00')
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, '050,001')
        self.assert_set(Parameter.BANDWIDTH_CONTROL, False)
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 064)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 2000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 704)
        self.assert_set(Parameter.CLIP_DATA_PAST_BOTTOM, False)
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 100)
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 1)
        self.assert_set(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_set(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_set(Parameter.PING_WEIGHT, 0)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 175)

    def set_baseline(self):
        params = {
            Parameter.BANNER: False,
            Parameter.INSTRUMENT_ID: 0,
            Parameter.SLEEP_ENABLE: 0,
            Parameter.POLLED_MODE: True,
            Parameter.XMIT_POWER: 255,
            Parameter.SPEED_OF_SOUND: 1485,
            Parameter.PITCH: 0,
            Parameter.ROLL: 0,
            Parameter.SALINITY: 35,
            Parameter.SENSOR_SOURCE: 1111101,
            Parameter.TIME_PER_ENSEMBLE: '01:00:00.00',
            Parameter.TIME_OF_FIRST_PING: '****/**/**,**:**:**',
            Parameter.TIME_PER_PING: '00:01.00',
            Parameter.FALSE_TARGET_THRESHOLD: '050,001',
            Parameter.BANDWIDTH_CONTROL: False,
            Parameter.CORRELATION_THRESHOLD: 064,
            Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
            Parameter.BLANK_AFTER_TRANSMIT: 704,
            Parameter.CLIP_DATA_PAST_BOTTOM: False,
            Parameter.RECEIVER_GAIN_SELECT: 1,
            Parameter.WATER_REFERENCE_LAYER: '001,005',
            Parameter.NUMBER_OF_DEPTH_CELLS: 100,
            Parameter.PINGS_PER_ENSEMBLE: 1,
            Parameter.DEPTH_CELL_SIZE: 800,
            Parameter.TRANSMIT_LENGTH: 0,
            Parameter.PING_WEIGHT: 0,
            Parameter.AMBIGUITY_VELOCITY: 175,
        }
        # Set all parameters to a known ground state
        self.assert_set_bulk(params)
        return params

    def test_set_ranges(self):
        """
        @Brief test a variety of paramater ranges.
        """
        self.assert_initialize_driver()

        params = self.set_baseline()

        #Parameter.BANNER: False,
        params[Parameter.BANNER] = True
        self.assert_set_bulk(params)
        params[Parameter.BANNER] = "LEROY JENKINS!"
        self.assert_set_bulk_exception(params)
        #
        # Reset to good value.
        #
        params[Parameter.BANNER] = False
        self.assert_set_bulk(params)

        #Parameter.INSTRUMENT_ID: 0,
        params[Parameter.INSTRUMENT_ID] = "LEROY JENKINS!"
        self.assert_set_bulk_exception(params)
        params[Parameter.INSTRUMENT_ID] = -1
        self.assert_set_bulk_exception(params)
        #
        # Reset to good value.
        #
        params[Parameter.INSTRUMENT_ID] = 0
        self.assert_set_bulk(params)
        
        
        #Parameter.SLEEP_ENABLE: 0,
        #Parameter.POLLED_MODE: True,
        #Parameter.XMIT_POWER: 255,
        #Parameter.SPEED_OF_SOUND: 1485,
        #Parameter.PITCH: 0,
        #Parameter.ROLL: 0,
        #Parameter.SALINITY: 35,
        #Parameter.SENSOR_SOURCE: 1111101,
        #Parameter.TIME_PER_ENSEMBLE: '01:00:00.00',
        #Parameter.TIME_OF_FIRST_PING: '****/**/**,**:**:**',
        #Parameter.TIME_PER_PING: '00:01.00',
        #Parameter.FALSE_TARGET_THRESHOLD: '050,001',
        #Parameter.BANDWIDTH_CONTROL: False,
        #Parameter.CORRELATION_THRESHOLD: 064,
        #Parameter.ERROR_VELOCITY_THRESHOLD: 2000,
        #Parameter.BLANK_AFTER_TRANSMIT: 704,
        #Parameter.CLIP_DATA_PAST_BOTTOM: False,
        #Parameter.RECEIVER_GAIN_SELECT: 1,
        #Parameter.WATER_REFERENCE_LAYER: '001,005',
        #Parameter.NUMBER_OF_DEPTH_CELLS: 100,
        #Parameter.PINGS_PER_ENSEMBLE: 1,
        #Parameter.DEPTH_CELL_SIZE: 800,
        #Parameter.TRANSMIT_LENGTH: 0,
        #Parameter.PING_WEIGHT: 0,
        #Parameter.AMBIGUITY_VELOCITY: 175,

    def assert_set_sampling_no_txwavestats(self):
        log.debug("setsampling Test 1 - TXWAVESTATS = N.")

        # First tests to verify we can set all parameters properly
        sampling_params = self.set_baseline_no_txwavestats()

        # Tide interval parameter.  Check edges, out of range and invalid data
        #    * Tide interval (integer minutes)
        #        - Range 7 - 720
        sampling_params[Parameter.TIDE_INTERVAL] = 17
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 720
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 7
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 721
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 18
        
        # set to known good
        sampling_params = self.set_baseline_no_txwavestats()
        
        # Tide measurement duration.  Check edges, out of range and invalid data
        #    * Tide measurement duration (seconds)
        #        - Range: 10 - 1020 sec
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1020
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 9
        self.assert_set_bulk_exception(sampling_params)
        # apparently NOT and edge case...
        #sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1021
        #self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 60
        
        # set to known good
        sampling_params = self.set_baseline_no_txwavestats()

        # Tide samples between wave bursts.  Check edges, out of range and invalid data
        #   * Measure wave burst after every N tide samples
        #       - Range 1 - 10,000
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
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 6000
        
        # Wave samples per burst.  Check edges, out of range and invalid data
        #   * Number of wave samples per burst
        #       - Range 4 - 60,000 *MUST BE MULTIPLE OF 4*
        # Test a good value
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 1000
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 10
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 43200   # If we set this this high
        sampling_params[Parameter.TIDE_INTERVAL] = 181              # ... we need to set
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10860# ... we need to set
        self.assert_set_bulk(sampling_params)

        # set to known good
        sampling_params = self.set_baseline_no_txwavestats()

        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 9
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 43201
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 10
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = -1
        self.assert_set_bulk_exception(sampling_params)

        #    * wave scans per second
        #        - Range [4, 2, 1.33, 1]
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 4
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 2.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1.33
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1.0
        self.assert_set_bulk(sampling_params)

        # test bad values
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 3
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 5
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 4
        self.assert_set_bulk_exception(sampling_params)
           
    def set_baseline_txwavestats_dont_use_conductivity(self):
        sampling_params = {
            Parameter.TIDE_INTERVAL: 18,
            Parameter.TIDE_MEASUREMENT_DURATION: 60,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: 8,
            Parameter.WAVE_SAMPLES_PER_BURST: 512,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND: 4.0,
            Parameter.TXWAVESTATS: True,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC: False,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR: 15.0,
            Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR: 35.0,        
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS: 512,
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: 10.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND: 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION: 1.0000,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM: 0.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM: 1.0,
            Parameter.HANNING_WINDOW_CUTOFF: 1.0
        }
        # Set all parameters to a known ground state
        self.assert_set_bulk(sampling_params)
        return sampling_params
    
    def assert_set_sampling_txwavestats_dont_use_conductivity(self):
        log.debug("setsampling Test 2 - TXWAVESTATS = Y. CONDUCTIVITY = N")
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -274.0 # -1 Kelvin?
        self.assert_set_bulk(sampling_params)    
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -273.0 # 0 Kelvin?
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -100.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -30.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = -1.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 0.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 30.0 
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 100.0 # if it gets hotter than this, we are likely all dead...
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 500.0 # 500 C getting warmer
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = 32767.0 # 32767 C, it's a dry heat
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = True
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR] = int(1)
        self.assert_set_bulk_exception(sampling_params)
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = -1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = -100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = -10.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = 0.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = 35.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = 100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = True
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR] = int(1)
        self.assert_set_bulk_exception(sampling_params)
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # Tide interval parameter.  Check edges, out of range and invalid data
        #    * Tide interval (integer minutes)
        #        - Range 3 - 720
        sampling_params[Parameter.TIDE_INTERVAL] = 3
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 720
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 2
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = 721
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_INTERVAL] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # Tide measurement duration.  Check edges, out of range and invalid data
        #    * Tide measurement duration (seconds)
        #        - Range: 10 - 1020 sec
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10 # <--- was 60, should have been 10
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1020
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 9
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 1021
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # Tide samples between wave bursts.  Check edges, out of range and invalid data
        #   * Measure wave burst after every N tide samples
        #       - Range 1 - 10,000
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 1
        self.assert_set_bulk(sampling_params) # in wakeup.
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 10000
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 10001
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS] = 6000

        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # Test a good value
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 1000
        self.assert_set_bulk(sampling_params)

        # Wave samples per burst.  Check edges, out of range and invalid data
        #   * Number of wave samples per burst
        #       - Range 4 - 60,000 *MUST BE MULTIPLE OF 4*
        sampling_params[Parameter.TIDE_INTERVAL] = 720              # required for 60000
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 60000
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 10
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 36000   # If we set this this high
        sampling_params[Parameter.TIDE_INTERVAL] = 720              # ... we need to set <--- was 1001
        sampling_params[Parameter.TIDE_MEASUREMENT_DURATION] = 10860# ... we need to set
        self.assert_set_bulk(sampling_params)

        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

        # 512 - 60,000 in multiple of 4
        
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 3
        self.assert_set_bulk_exception(sampling_params)     
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 4      
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 508      
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 511     
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 43201
        self.assert_set_bulk_exception(sampling_params)
        
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = 60001
        self.assert_set_bulk_exception(sampling_params)           
        sampling_params[Parameter.WAVE_SAMPLES_PER_BURST] = "bar"
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

        
        # Wave samples per burst.  Check edges, out of range and invalid data
        #    * wave sample duration=
        #        - Range [0.25, 0.5, 0.75, 1.0]
        
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 2.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1.33
        self.assert_set_bulk(sampling_params)                           
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 1.0
        self.assert_set_bulk(sampling_params)
        
        # test bad values
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 3
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = 5
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.WAVE_SAMPLES_SCANS_PER_SECOND] = False
        self.assert_set_bulk_exception(sampling_params)
       
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = False
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = True
        self.assert_set_bulk(sampling_params)
        
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = 1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = float(1.0)
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC] = "bar"
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = 100000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = -1.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = "foo"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM] = True
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = 0
        self.assert_set_bulk(sampling_params)
        
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = 10
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = 100000
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = 10.0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = "car"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND] = True
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 0.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 0.0025
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 10.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 10000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 100000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = 100
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = "tar"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_ALLOWABLE_ATTENUATION] = True
        self.assert_set_bulk_exception(sampling_params)

        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 0.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM] = float(0.0001)
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 1.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 10.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = 10000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM] = 100000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = "far"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM] = True
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()
        
        # The manual only shows 0.10 as a value (assert float)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 1.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = -1
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 0
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 0.0
        self.assert_set_bulk(sampling_params)
        # Rounds to 0.00
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = float(0.0001) 
        self.assert_set_bulk_exception(sampling_params)
        # Rounds to 0.01
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = float(0.006) 
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 1.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 10.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 100.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 1000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 10000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = 100000.0
        self.assert_set_bulk(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = "far"
        self.assert_set_bulk_exception(sampling_params)
        sampling_params[Parameter.HANNING_WINDOW_CUTOFF] = False
        self.assert_set_bulk_exception(sampling_params)
        
        # set to known good
        sampling_params = self.set_baseline_txwavestats_dont_use_conductivity()

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
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE, regex=r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)')
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'SBE 26plus')
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_CONFIGURATION, regex=r'Pressure coefficients')
        self.assert_driver_command_exception(ProtocolEvent.SEND_LAST_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.QUIT_SESSION)

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_driver_command(ProtocolEvent.SCHEDULED_CLOCK_SYNC)
        self.assert_driver_command_exception(ProtocolEvent.START_AUTOSAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.ACQUIRE_SAMPLE, exception_class=InstrumentCommandException)
        self.assert_driver_command_exception(ProtocolEvent.CLOCK_SYNC, exception_class=InstrumentCommandException)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'SBE 26plus')
        self.assert_driver_command(ProtocolEvent.ACQUIRE_CONFIGURATION, regex=r'Pressure coefficients')
        self.assert_driver_command(ProtocolEvent.SEND_LAST_SAMPLE, regex=r'p = +([\-\d.]+), t = +([\-\d.]+)')
        self.assert_driver_command_exception(ProtocolEvent.QUIT_SESSION, exception_class=InstrumentCommandException)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_polled_particle_generation(self):
        """
        Test that we can generate particles with commands
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.ACQUIRE_SAMPLE, DataParticleType.TIDE_PARSED, self.assert_particle_tide_sample)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.DEVICE_STATUS, self.assert_particle_device_status)
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_CONFIGURATION, DataParticleType.DEVICE_CALIBRATION, self.assert_particle_device_calibration)

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample
        """
        self.assert_initialize_driver()

        params = {
            Parameter.TIDE_INTERVAL: 3,
            Parameter.TIDE_MEASUREMENT_DURATION: 60,
            Parameter.WAVE_SAMPLES_PER_BURST: 512,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: 2,
            Parameter.TXWAVEBURST: True,
            Parameter.TXWAVESTATS: True,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND: 4.0,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC: False,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR: 15.0,
            Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR: 35.0,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS: 512,
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: 10.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND: 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION: 0.0025,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM: 0.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM: 1.00e+06,
            Parameter.HANNING_WINDOW_CUTOFF: 0.1
        }
        self.assert_set_bulk(params)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        self.assert_async_particle_generation(DataParticleType.TIDE_PARSED, self.assert_particle_tide_sample, timeout=120)
        self.assert_async_particle_generation(DataParticleType.WAVE_BURST, self.assert_particle_wave_burst, timeout=300)
        self.assert_async_particle_generation(DataParticleType.STATISTICS, self.assert_particle_statistics, timeout=300)

    def test_startup_params_first_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run first.
        """
        self.assert_initialize_driver()

        self.assert_get(Parameter.TXWAVESTATS, False)
        self.assert_get(Parameter.TXREALTIME, True)
        self.assert_get(Parameter.TXWAVEBURST, False)

        # Now change them so they are caught and see if they are caught
        # on the second pass.
        self.assert_set(Parameter.TXWAVESTATS, True)
        self.assert_set(Parameter.TXREALTIME, False)
        self.assert_set(Parameter.TXWAVEBURST, True)

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_initialize_driver()

        self.assert_get(Parameter.TXWAVESTATS, False)
        self.assert_get(Parameter.TXREALTIME, True)
        self.assert_get(Parameter.TXWAVEBURST, False)

        # Change these values anyway just in case it ran first.
        self.assert_set(Parameter.TXWAVESTATS, True)
        self.assert_set(Parameter.TXREALTIME, False)
        self.assert_set(Parameter.TXWAVEBURST, True)

    def test_apply_startup_params(self):
        """
        This test verifies that we can set the startup params
        from autosample mode.  It only verifies one parameter
        change because all parameters are tested above.
        """
        # Apply autosample happens for free when the driver fires up
        self.assert_initialize_driver()

        # Change something
        self.assert_set(Parameter.TXWAVEBURST, True)

        # Now try to apply params in Streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE)
        self.driver_client.cmd_dvr('apply_startup_params')

        # All done.  Verify the startup parameter has been reset
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND)
        self.assert_get(Parameter.TXWAVEBURST, False)

    ###
    #   Test scheduled events
    ###
    def assert_calibration_coefficients(self):
        """
        Verify a calibration particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.DEVICE_CALIBRATION, self.assert_particle_device_calibration, timeout=30)

    def test_scheduled_device_configuration_command(self):
        """
        Verify the device configuration command can be triggered and run in command
        """
        self.assert_scheduled_event(ScheduledJob.CALIBRATION_COEFFICIENTS, self.assert_calibration_coefficients, delay=45)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_device_configuration_autosample(self):
        """
        Verify the device configuration command can be triggered and run in autosample
        """
        self.assert_scheduled_event(ScheduledJob.CALIBRATION_COEFFICIENTS, self.assert_calibration_coefficients,
            autosample_command=ProtocolEvent.START_AUTOSAMPLE, delay=60)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)

    def assert_acquire_status(self):
        """
        Verify a status particle was generated
        """
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.DEVICE_STATUS, self.assert_particle_device_status, timeout=30)

    def test_scheduled_device_status_command(self):
        """
        Verify the device status command can be triggered and run in command
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, self.assert_acquire_status, delay=45)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_device_status_autosample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, self.assert_acquire_status,
                                    autosample_command=ProtocolEvent.START_AUTOSAMPLE, delay=60)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)

    def assert_clock_sync(self):
        """
        Verify the clock is set to at least the current date
        """
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)
        dt = self.assert_get(Parameter.DS_DEVICE_DATE_TIME)
        lt = time.strftime("%d %b %Y  %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assertTrue(lt[:12].upper() in dt.upper())

    def test_scheduled_clock_sync_command(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, self.assert_clock_sync, delay=45)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_clock_sync_autosample(self):
        """
        Verify the scheduled clock sync is triggered and functions as expected
        """
        self.assert_scheduled_event(ScheduledJob.CLOCK_SYNC, self.assert_clock_sync,
                                    autosample_command=ProtocolEvent.START_AUTOSAMPLE, delay=60)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        TeledyneQualificationTest.setUp(self)

    def test_autosample(self):
        """
        Verify that we can enter streaming and that all particles are produced
        properly.

        Because we have to test for three different data particles we can't use
        the common assert_sample_autosample method
        """
        self.assert_enter_command_mode()

        params = {
            Parameter.TIDE_INTERVAL: 3,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS: 512,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: 2,
            Parameter.TXWAVEBURST: True,
            Parameter.TXWAVESTATS: True
        }
        self.instrument_agent_client.set_resource(params)

        self.assert_start_autosample()

        self.assert_sample_async(self.assert_particle_tide_sample, DataParticleType.TIDE_PARSED, timeout=120, sample_count=1)
        self.assert_sample_async(self.assert_particle_wave_burst, DataParticleType.WAVE_BURST, timeout=300, sample_count=1)
        self.assert_sample_async(self.assert_particle_statistics, DataParticleType.STATISTICS, timeout=300, sample_count=1)

        # Verify we can generate status and config particles while streaming
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_device_status, DataParticleType.DEVICE_STATUS)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_CONFIGURATION, self.assert_particle_device_calibration, DataParticleType.DEVICE_CALIBRATION)

        self.assert_stop_autosample()

    def test_poll(self):
        '''
        Verify that we can poll for a sample.  Take sample for this instrument
        Also poll for other engineering data streams.
        '''
        self.assert_enter_command_mode()

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_SAMPLE, self.assert_particle_tide_sample, DataParticleType.TIDE_PARSED)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_device_status, DataParticleType.DEVICE_STATUS, sample_count=1)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_CONFIGURATION, self.assert_particle_device_calibration, DataParticleType.DEVICE_CALIBRATION, sample_count=1)

    def test_direct_access_telnet_mode(self):
        """
        Test that we can connect to the instrument via direct access.  Also
        verify that direct access parameters are reset on exit.
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.TXREALTIME, True)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data("TxTide=N\r\n")
        self.tcp_client.expect("S>")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()
        self.assert_get_parameter(Parameter.TXREALTIME, True)

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
            AgentCapabilityType.AGENT_COMMAND: [
                ResourceAgentEvent.CLEAR,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_DIRECT_ACCESS,
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.PAUSE
            ],
            AgentCapabilityType.AGENT_PARAMETER: ['example'],
            AgentCapabilityType.RESOURCE_COMMAND: [
                DriverEvent.ACQUIRE_SAMPLE,
                DriverEvent.START_AUTOSAMPLE,
                ProtocolEvent.ACQUIRE_STATUS,
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.ACQUIRE_CONFIGURATION,
                ProtocolEvent.SETSAMPLING,
                ProtocolEvent.QUIT_SESSION
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
            }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ ResourceAgentEvent.RESET, ResourceAgentEvent.GO_INACTIVE ]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            DriverEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.ACQUIRE_STATUS,
            ProtocolEvent.SEND_LAST_SAMPLE,
            ProtocolEvent.ACQUIRE_CONFIGURATION
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ResourceAgentEvent.INITIALIZE]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        # wait for a bit so the event can be triggered
        time.sleep(1)

        # Set the clock to something in the past
        self.assert_set_parameter(Parameter.DS_DEVICE_DATE_TIME, "01 Jan 2001 01:01:01", verify=False)

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)
        self.assert_execute_resource(ProtocolEvent.ACQUIRE_STATUS)

        # Now verify that at least the date matches
        params = [Parameter.DS_DEVICE_DATE_TIME]
        check_new_params = self.instrument_agent_client.get_resource(params)
        lt = time.strftime("%d %b %Y  %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        log.debug("TIME: %s && %s" % (lt, check_new_params[Parameter.DS_DEVICE_DATE_TIME]))
        self.assertTrue(lt[:12].upper() in check_new_params[Parameter.DS_DEVICE_DATE_TIME].upper())

    def test_startup_params_first_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.TXWAVESTATS, False)
        self.assert_get_parameter(Parameter.TXREALTIME, True)
        self.assert_get_parameter(Parameter.TXWAVEBURST, False)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.TXWAVESTATS, True)
        self.assetert_set_parameter(Parameter.TXREALTIME, False)
        self.assetert_set_parameter(Parameter.TXWAVEBURST, True)

    def test_startup_params_second_pass(self):
        """
        Verify that startup parameters are applied correctly. Generally this
        happens in the driver discovery method.  We have two identical versions
        of this test so it is run twice.  First time to check and CHANGE, then
        the second time to check again.

        since nose orders the tests by ascii value this should run second.
        """
        self.assert_enter_command_mode()

        self.assert_get_parameter(Parameter.TXWAVESTATS, False)
        self.assert_get_parameter(Parameter.TXREALTIME, True)
        self.assert_get_parameter(Parameter.TXWAVEBURST, False)

        # Change these values anyway just in case it ran first.
        self.assert_set_parameter(Parameter.TXWAVESTATS, True)
        self.assetert_set_parameter(Parameter.TXREALTIME, False)
        self.assetert_set_parameter(Parameter.TXWAVEBURST, True)
        

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class DriverPublicationTest(TeledynePublicationTest):
    def setUp(self):
        TeledynePublicationTest.setUp(self)

    def test_granule_generation(self):
        self.assert_initialize_driver()

        # Currently these tests only verify that the data granule is generated, but the values
        # are not tested.  We will eventually need to replace log.debug with a better callback
        # function that actually tests the granule.
        self.assert_sample_async("raw data", log.debug, DataParticleType.RAW, timeout=10)
        self.assert_sample_async(SAMPLE_STATISTICS, log.debug, DataParticleType.STATISTICS, timeout=10)
        self.assert_sample_async(SAMPLE_TIDE_DATA, log.debug, DataParticleType.TIDE_PARSED, timeout=10)
        self.assert_sample_async(SAMPLE_DEVICE_CALIBRATION, log.debug, DataParticleType.DEVICE_CALIBRATION, timeout=10)
        self.assert_sample_async(SAMPLE_DEVICE_STATUS, log.debug, DataParticleType.DEVICE_STATUS, timeout=10)

        # Currently this fails
        self.assert_sample_async(SAMPLE_WAVE_BURST, log.debug, DataParticleType.WAVE_BURST, timeout=10)
