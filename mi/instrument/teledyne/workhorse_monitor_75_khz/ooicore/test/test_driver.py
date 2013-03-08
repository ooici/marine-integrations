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
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import DataParticleType
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import InstrumentCmds
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ProtocolState
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ProtocolEvent
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Capability
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Parameter
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Protocol
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ScheduledJob
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import Prompt
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PT200DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PT200DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PS3DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PS3DataParticle
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PS0DataParticleKey
from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_PS0DataParticle

#from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_EnsembleDataParticleKey
#from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_EnsembleDataParticle
#from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_CalibrationDataParticleKey
#from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_CalibrationDataParticle
#from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_FDDataParticleKey
#from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import ADCPT_FDDataParticle

from mi.instrument.teledyne.workhorse_monitor_75_khz.ooicore.driver import NEWLINE

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
    Mixin class used for storing data particle constance
    and common data assertion methods.
    '''
    ###
    # Parameter and Type Definitions
    ###

    _driver_parameters = {
        Parameter.INSTRUMENT_ID: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.POLLED_MODE: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: False},
        Parameter.XMIT_POWER: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 255},
        Parameter.TIME_PER_BURST: {
            TYPE: dt.datetime,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: dt.datetime.strptime('00:00:00.00', '%H:%M:%S.%f')},
        Parameter.ENSEMBLES_PER_BURST: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 2},
        Parameter.TIME_PER_ENSEMBLE: {
            TYPE: dt.datetime,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: dt.datetime.strptime('01:00:00.00', '%H:%M:%S.%f')},
        Parameter.TIME_OF_FIRST_PING: {
            TYPE: str,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '**/**/**,**:**:**'},
        Parameter.TIME_OF_FIRST_PING_Y2K: {
            TYPE: str,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '****/**/**,**:**:**'},
        Parameter.TIME_PER_PING: {
            TYPE: str,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '01:20.00'},
        #Parameter.TIME: {
        #    TYPE: time,
        #    READONLY: False,
        #    DA: False,
        #    STARTUP: False,
        #    DEFAULT: False,
        #    VALUE: time.strptime('13/03/01,08:20:29', "%y/%m/%d,%H:%M:%S")},
        Parameter.TIME: {
            TYPE: time,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: time.strptime('2013/03/01,08:20:29', "%Y/%m/%d,%H:%M:%S")},
        Parameter.BUFFERED_OUTPUT_PERIOD: {
            TYPE: time,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: time.strptime('00:00:00', "%H:%M:%S")},
        Parameter.FALSE_TARGET_THRESHOLD: {
            TYPE: str,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '255,001'},
        Parameter.CORRELATION_THRESHOLD: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 64},
        Parameter.SERIAL_OUT_FW_SWITCHES: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 111100000},
        Parameter.ERROR_VELOCITY_THRESHOLD: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 5000},
        Parameter.BLANK_AFTER_TRANSMIT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 88},
        Parameter.CLIP_DATA_PAST_BOTTOM: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: False},
        Parameter.RECEIVER_GAIN_SELECT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1},
        Parameter.WATER_REFERENCE_LAYER: {
            TYPE: str,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '001,005'},
        Parameter.WATER_PROFILING_MODE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1},
        Parameter.NUMBER_OF_DEPTH_CELLS: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 30},
        Parameter.PINGS_PER_ENSEMBLE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 45},
        Parameter.DEPTH_CELL_SIZE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 800},
        Parameter.TRANSMIT_LENGTH: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.PING_WEIGHT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.AMBIGUITY_VELOCITY: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 175},
        Parameter.CHOOSE_EXTERNAL_DEVICE: {
            TYPE: str,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '000 000 000'},
        Parameter.BANNER: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: False},
        Parameter.IMM_OUTPUT_ENABLE: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: False},
        Parameter.SLEEP_ENABLE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.SERIAL_SYNC_MASTER: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: False},
        Parameter.SAVE_NVRAM_TO_RECORDER: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: True},
        Parameter.TRIGGER_TIMEOUT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 250},
        Parameter.LOW_LATENCY_TRIGGER_ENABLE: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: True},
        Parameter.HEADING_ALIGNMENT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.HEADING_BIAS: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.SPEED_OF_SOUND: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1500},
        Parameter.TRANSDUCER_DEPTH: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.HEADING: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.PITCH: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.ROLL: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.SALINITY: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 35},
        Parameter.TEMPERATURE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 2500},
        Parameter.COORDINATE_TRANSFORMATION: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.SENSOR_SOURCE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1111101},
        Parameter.OUTPUT_BIN_SELECTION: {
            TYPE: str,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '001,000,1'},
        Parameter.DATA_STREAM_SELECT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.ENSEMBLE_SELECT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1},
        Parameter.VELOCITY_COMPONENT_SELECT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1111},
        Parameter.SYNCHRONIZE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1},
        Parameter.BREAK_INTERUPTS: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: True},
        Parameter.SYNC_INTERVAL: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.MODE_SELECT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1},
        Parameter.RDS3_SLEEP_MODE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.SLAVE_TIMEOUT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.SYNC_DELAY: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 100},
        Parameter.DEVICE_485_ID: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.DEPLOYMENT_AUTO_INCRIMENT: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: True},
        Parameter.DEPLOYMENT_NAME: {
            TYPE: str,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '_RDI_'},
        Parameter.BANDWIDTH_CONTROL: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 1},
        Parameter.WANTED_GOOD_PERCENT: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        Parameter.SAMPLE_AMBIENT_SOUND: {
            TYPE: bool,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: False},
        Parameter.PINGS_BEFORE_REAQUIRE: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 4},
        Parameter.MODE_5_AMBIGUITY_VELOCITY: {
            TYPE: int,
            READONLY: False,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 010},
        Parameter.ZERO_PRESSURE_READING: {
            TYPE: float,
            READONLY: True,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 13.386345},
        Parameter.SERIAL_PORT_CONTROL: {
            TYPE: int,
            READONLY: True,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 411},
        Parameter.SERIAL_DATA_OUT: {
            TYPE: str,
            READONLY: True,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: '000 000 000'},
        Parameter.SERIAL_FLOW_CONTROL: {
            TYPE: int,
            READONLY: True,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 11110},
        Parameter.SERIAL_485_BAUD: {
            TYPE: int,
            READONLY: True,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 411},
        Parameter.DEPLOYMENTS_RECORDED: {
            TYPE: int,
            READONLY: True,
            DA: False,
            STARTUP: False,
            DEFAULT: False,
            VALUE: 0},
        }


    """
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
    """

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
        """
        if (isinstance(data_particle, ADCPT_EnsembleDataParticle)):
            self.assert_particle_header_sample(data_particle)
        elif (isinstance(data_particle, ADCPT_CalibrationDataParticle)):
            self.assert_particle_calibration_data(data_particle)
        elif (isinstance(data_particle, ADCPT_FDDataParticle)):
            self.assert_particle_fd_data(data_particle)
        el
        """
        if (isinstance(data_particle, ADCPT_PS0DataParticle)):
            self.assert_particle_ps0_data(data_particle)
        elif (isinstance(data_particle, ADCPT_PS3DataParticle)):
            self.assert_particle_ps3_data(data_particle)
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

    def assert_particle_fd_data(self, data_particle, verify_values = False):
        '''
        Verify an adcpt fd data particle
        @param data_particle: ADCPT_FDDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.FD_PARSED)
        self.assert_data_particle_parameters(data_particle, self._fd_parameters, verify_values)



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
        self.assert_particle_published(driver, PT200_RAW_DATA, self.assert_particle_pt200_data, True)
        #self.assert_particle_published(driver, SAMPLE_TIDE_DATA, self.assert_particle_tide_sample, True)
        #self.assert_particle_published(driver, SAMPLE_TIDE_DATA_POLLED, self.assert_particle_tide_sample, True)
        #self.assert_particle_published(driver, SAMPLE_WAVE_BURST, self.assert_particle_wave_burst, True)
        #self.assert_particle_published(driver, SAMPLE_STATISTICS, self.assert_particle_statistics, True)
        #self.assert_particle_published(driver, SAMPLE_DEVICE_CALIBRATION, self.assert_particle_device_calibration, True)
        #self.assert_particle_published(driver, SAMPLE_DEVICE_STATUS, self.assert_particle_device_status, True)

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
        set_time = get_timestamp_delayed("%d %b %Y  %H:%M:%S")
        # One second later

        expected_time = get_timestamp_delayed("%d %b %Y  %H:%M:%S")

        self.assert_set(Parameter.TIME, set_time, no_get=True)
        #self.assert_get(Parameter.TIME, expected_time) # TODO: re-eneable this once its better understood.

        #
        # look at 16 for tolerance, within 5 minutes.
        # model after the 16

        ###
        #   Instrument Parameteres
        ###
        self.assert_set(Parameter.INSTRUMENT_ID, 0)
        self.assert_set(Parameter.POLLED_MODE, False)
        self.assert_set(Parameter.XMIT_POWER, 255)
        self.assert_set(Parameter.TIME_PER_BURST, '00:00:00.00')
        self.assert_set(Parameter.ENSEMBLES_PER_BURST, 2)
        self.assert_set(Parameter.TIME_PER_ENSEMBLE, '01:00:00.00')
        self.assert_set(Parameter.TIME_OF_FIRST_PING, '****/**/**,**:**:**')
        self.assert_set(Parameter.TIME_OF_FIRST_PING_Y2K, '****/**/**,**:**:**')
        self.assert_set(Parameter.TIME_PER_PING, '01:20.00')
        self.assert_set(Parameter.BUFFERED_OUTPUT_PERIOD, '00:00:00')
        self.assert_set(Parameter.FALSE_TARGET_THRESHOLD, '255,001')
        self.assert_set(Parameter.CORRELATION_THRESHOLD, 064)
        self.assert_set(Parameter.SERIAL_OUT_FW_SWITCHES, 111100000)
        self.assert_set(Parameter.ERROR_VELOCITY_THRESHOLD, 5000)
        self.assert_set(Parameter.BLANK_AFTER_TRANSMIT, 88)
        self.assert_set(Parameter.CLIP_DATA_PAST_BOTTOM, False)
        self.assert_set(Parameter.RECEIVER_GAIN_SELECT, 1)
        self.assert_set(Parameter.WATER_REFERENCE_LAYER, '001,005')
        self.assert_set(Parameter.WATER_PROFILING_MODE, 1)
        self.assert_set(Parameter.NUMBER_OF_DEPTH_CELLS, 030)
        self.assert_set(Parameter.PINGS_PER_ENSEMBLE, 45)
        self.assert_set(Parameter.DEPTH_CELL_SIZE, 800)
        self.assert_set(Parameter.TRANSMIT_LENGTH, 0)
        self.assert_set(Parameter.PING_WEIGHT, 0)
        self.assert_set(Parameter.AMBIGUITY_VELOCITY, 175)
        self.assert_set(Parameter.CHOOSE_EXTERNAL_DEVICE, '000 000 000')
        self.assert_set(Parameter.BANNER, False)
        self.assert_set(Parameter.IMM_OUTPUT_ENABLE, False)
        self.assert_set(Parameter.SLEEP_ENABLE, 0)
        self.assert_set(Parameter.SERIAL_SYNC_MASTER, False)
        self.assert_set(Parameter.SAVE_NVRAM_TO_RECORDER, False)
        self.assert_set(Parameter.TRIGGER_TIMEOUT, 250)
        self.assert_set(Parameter.LOW_LATENCY_TRIGGER_ENABLE, 1)
        self.assert_set(Parameter.HEADING_ALIGNMENT, 0)
        self.assert_set(Parameter.HEADING_BIAS, 0)
        self.assert_set(Parameter.SPEED_OF_SOUND, 1500)
        self.assert_set(Parameter.TRANSDUCER_DEPTH, 0)
        self.assert_set(Parameter.HEADING, 0)
        self.assert_set(Parameter.PITCH, 0)
        self.assert_set(Parameter.ROLL, 0)
        self.assert_set(Parameter.SALINITY, 35)
        self.assert_set(Parameter.TEMPERATURE, 2500)
        self.assert_set(Parameter.COORDINATE_TRANSFORMATION, 0)
        self.assert_set(Parameter.SENSOR_SOURCE, 1111101)
        self.assert_set(Parameter.OUTPUT_BIN_SELECTION, '001,000,1')
        self.assert_set(Parameter.DATA_STREAM_SELECT, 0)
        self.assert_set(Parameter.ENSEMBLE_SELECT, 1)
        self.assert_set(Parameter.VELOCITY_COMPONENT_SELECT, 1111)
        self.assert_set(Parameter.SYNCHRONIZE, 1)
        self.assert_set(Parameter.BREAK_INTERUPTS, True)
        self.assert_set(Parameter.SYNC_INTERVAL, 0)
        self.assert_set(Parameter.MODE_SELECT, 1)
        self.assert_set(Parameter.RDS3_SLEEP_MODE, 0)
        self.assert_set(Parameter.SLAVE_TIMEOUT, 0)
        self.assert_set(Parameter.SYNC_DELAY, 100)
        self.assert_set(Parameter.DEVICE_485_ID, 0)
        self.assert_set(Parameter.DEPLOYMENT_AUTO_INCRIMENT, True)
        self.assert_set(Parameter.DEPLOYMENT_NAME, '_RDI_')
        self.assert_set(Parameter.BANDWIDTH_CONTROL, 1)
        self.assert_set(Parameter.WANTED_GOOD_PERCENT, 0)
        self.assert_set(Parameter.SAMPLE_AMBIENT_SOUND, False)
        self.assert_set(Parameter.PINGS_BEFORE_REAQUIRE, 4)
        self.assert_set(Parameter.MODE_5_AMBIGUITY_VELOCITY, 10)


        ###
        #   Read only parameters
        ###
        self.assert_set_readonly(Parameter.ZERO_PRESSURE_READING)
        self.assert_set_readonly(Parameter.SERIAL_PORT_CONTROL)
        self.assert_set_readonly(Parameter.SERIAL_DATA_OUT)
        self.assert_set_readonly(Parameter.SERIAL_FLOW_CONTROL)
        self.assert_set_readonly(Parameter.SERIAL_485_BAUD)
        self.assert_set_readonly(Parameter.DEPLOYMENTS_RECORDED)

    def set_baseline(self):
        params = {
            Parameter.INSTRUMENT_ID: 'xxx',
            Parameter.POLLED_MODE: 'xxx',
            Parameter.XMIT_POWER: 'xxx',
            Parameter.TIME_PER_BURST: 'xxx',
            Parameter.ENSEMBLES_PER_BURST: 'xxx',
            Parameter.TIME_PER_ENSEMBLE: 'xxx',
            Parameter.TIME_OF_FIRST_PING: 'xxx',
            Parameter.TIME_OF_FIRST_PING_Y2K: 'xxx',
            Parameter.TIME_PER_PING: 'xxx',
            #Parameter.TIME: 'xxx',
            Parameter.BUFFERED_OUTPUT_PERIOD: 'xxx',
            Parameter.FALSE_TARGET_THRESHOLD: 'xxx',
            Parameter.CORRELATION_THRESHOLD: 'xxx',
            Parameter.SERIAL_OUT_FW_SWITCHES: 'xxx',
            Parameter.ERROR_VELOCITY_THRESHOLD: 'xxx',
            Parameter.BLANK_AFTER_TRANSMIT: 'xxx',
            Parameter.CLIP_DATA_PAST_BOTTOM: 'xxx',
            Parameter.RECEIVER_GAIN_SELECT: 'xxx',
            Parameter.WATER_REFERENCE_LAYER: 'xxx',
            Parameter.WATER_PROFILING_MODE: 'xxx',
            Parameter.NUMBER_OF_DEPTH_CELLS: 'xxx',
            Parameter.PINGS_PER_ENSEMBLE: 'xxx',
            Parameter.DEPTH_CELL_SIZE: 'xxx',
            Parameter.TRANSMIT_LENGTH: 'xxx',
            Parameter.PING_WEIGHT: 'xxx',
            Parameter.AMBIGUITY_VELOCITY: 'xxx',
            Parameter.CHOOSE_EXTERNAL_DEVICE: 'xxx',
            Parameter.BANNER: 'xxx',
            Parameter.IMM_OUTPUT_ENABLE: 'xxx',
            Parameter.SLEEP_ENABLE: 'xxx',
            Parameter.SERIAL_SYNC_MASTER: 'xxx',
            Parameter.SAVE_NVRAM_TO_RECORDER: 'xxx',
            Parameter.TRIGGER_TIMEOUT: 'xxx',
            Parameter.LOW_LATENCY_TRIGGER_ENABLE: 'xxx',
            Parameter.HEADING_ALIGNMENT: 'xxx',
            Parameter.HEADING_BIAS: 'xxx',
            Parameter.SPEED_OF_SOUND: 'xxx',
            Parameter.TRANSDUCER_DEPTH: 'xxx',
            Parameter.HEADING: 'xxx',
            Parameter.PITCH: 'xxx',
            Parameter.ROLL: 'xxx',
            Parameter.SALINITY: 'xxx',
            Parameter.TEMPERATURE: 'xxx',
            Parameter.COORDINATE_TRANSFORMATION: 'xxx',
            Parameter.SENSOR_SOURCE: 'xxx',
            Parameter.OUTPUT_BIN_SELECTION: 'xxx',
            Parameter.DATA_STREAM_SELECT: 'xxx',
            Parameter.ENSEMBLE_SELECT: 'xxx',
            Parameter.VELOCITY_COMPONENT_SELECT: 'xxx',
            Parameter.SYNCHRONIZE: 'xxx',
            Parameter.BREAK_INTERUPTS: 'xxx',
            Parameter.SYNC_INTERVAL: 'xxx',
            Parameter.MODE_SELECT: 'xxx',
            Parameter.RDS3_SLEEP_MODE: 'xxx',
            Parameter.SLAVE_TIMEOUT: 'xxx',
            Parameter.SYNC_DELAY: 'xxx',
            Parameter.DEVICE_485_ID: 'xxx',
            Parameter.DEPLOYMENT_AUTO_INCRIMENT: 'xxx',
            Parameter.DEPLOYMENT_NAME: 'xxx',
            Parameter.BANDWIDTH_CONTROL: 'xxx',
            Parameter.WANTED_GOOD_PERCENT: 'xxx',
            Parameter.SAMPLE_AMBIENT_SOUND: 'xxx',
            Parameter.PINGS_BEFORE_REAQUIRE: 'xxx',
            Parameter.MODE_5_AMBIGUITY_VELOCITY: 'xxx',
        }
        # Set all parameters to a known ground state
        self.assert_set_bulk(params)
        return params

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
