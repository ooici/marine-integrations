"""
@package mi.instrument.sami.w.cgsn.test.test_driver
@file marine-integrations/mi/instrument/sami/w/cgsn/driver.py
@author Chris Center
@brief Test cases for InstrumentDriver

USAGE:
 Make tests verbose and provide stdout4
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]

   * From pyon
       $ bin/nosetests -s -v .../mi/instrument/seabird/sbe16plus_v2/ooicore
       $ bin/nosetests -s -v .../mi/instrument/seabird/sbe16plus_v2/ooicore -a UNIT
       $ bin/nosetests -s -v .../mi/instrument/seabird/sbe16plus_v2/ooicore -a INT
       $ bin/nosetests -s -v .../mi/instrument/seabird/sbe16plus_v2/ooicore -a QUAL
"""

__author__ = 'Chris Center'
__license__ = 'Apache 2.0'

import unittest
import json

from nose.plugins.attrib import attr
from mock import Mock

from gevent import monkey; monkey.patch_all()
import gevent
import time
import datetime
import calendar
import re

from mi.core.common import BaseEnum
from mi.core.log import get_logger ; log = get_logger()
from nose.plugins.attrib import attr

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.instrument.chunker import StringChunker

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.sami.pco2w.cgsn.driver import InstrumentDriver
from mi.instrument.sami.pco2w.cgsn.driver import DataParticleType
from mi.instrument.sami.pco2w.cgsn.driver import ProtocolState
from mi.instrument.sami.pco2w.cgsn.driver import ProtocolEvent
from mi.instrument.sami.pco2w.cgsn.driver import ScheduledJob
from mi.instrument.sami.pco2w.cgsn.driver import Capability
from mi.instrument.sami.pco2w.cgsn.driver import Parameter
from mi.instrument.sami.pco2w.cgsn.driver import Prompt
from mi.instrument.sami.pco2w.cgsn.driver import Protocol
from mi.instrument.sami.pco2w.cgsn.driver import NEWLINE
from mi.instrument.sami.pco2w.cgsn.driver import InstrumentCmds

# Support Tools.
from mi.instrument.sami.pco2w.cgsn.driver import get_timestamp_delayed_sec  # Modified 
from mi.instrument.sami.pco2w.cgsn.driver import get_timestamp_sec  # Modified 
from mi.instrument.sami.pco2w.cgsn.driver import convert_timestamp_to_sec
from mi.instrument.sami.pco2w.cgsn.driver import replace_string_chars
from mi.instrument.sami.pco2w.cgsn.driver import SamiConfiguration

# Data Particles
from mi.instrument.sami.pco2w.cgsn.driver import SamiImmediateStatusDataParticleKey
from mi.instrument.sami.pco2w.cgsn.driver import SamiControlRecordParticleKey
from mi.instrument.sami.pco2w.cgsn.driver import SamiDataRecordParticleKey
from mi.instrument.sami.pco2w.cgsn.driver import SamiRegularStatusDataParticleKey
from mi.instrument.sami.pco2w.cgsn.driver import SamiConfigDataParticleKey

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentDataException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentParameterException

from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue

###
#   Driver parameters for the tests
###
# Create some short names for the parameter test config
# CJC STARTUP = ParameterTestConfigKey.STARTUP

# SAMI Test Strings
SAMPLE_IMMEDIATE_STATUS_DATA = "10"
SAMPLE_ERROR_DATA = "?03" + NEWLINE
# This records is from the PCO2W_Record_Format.pdf file.
SAMPLE_CONTROL_RECORD = "*D21285CCB0F0A500410000460000000008B3EA"  # Provided by Mike at WHOI.
SAMPLE_DATA_RECORD_1  = "*5B2704C8EF9FC90FE606400FE8063C0FE30674640B1B1F0FE6065A0FE9067F0FE306A60CDE0FFF3B" # Also used in crc-test so please do not change.
SAMPLE_DATA_RECORD_2  = "*7E2705CBACEE7F007D007D0B2A00BF080500E00187034A008200790B2D00BE080600DE0C1406C98C"
SAMPLE_DATA_RECORD_3  = "*F72705CD73EB6B005500850A42067807FB06C226513416005300870A40067807FE06C00C88066961"
# Field Index Counter     01234567891123456789212345678931234567894123456789

# Regular Status.
SAMPLE_REGULAR_STATUS_DATA_1 = ":003F91BE00000000" # :003F91BE0000000000000000000000F7" + NEWLINE
SAMPLE_REGULAR_STATUS_DATA_2 = ":CD70C88B004100008F000000000C0EF7"  # From WHOI Manual Mode.
SAMPLE_REGULAR_STATUS_DATA_BAD = "000029ED40"  + NEWLINE

# SAMPLE_CONFIG_DATA = "CAB39E84000000F401E13380570007080401000258030A0002580017000258011A003840001C1020FFA8181C010038100101202564000433383335000200010200020000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000" + NEWLINE
# This sample configuration is from the PCO2W_Low_Level_SAMI_Use document.
SAMPLE_CONFIG_DATA_1 = "CAB39E84000000F401E13380570007080401000258030A0002580017000258011A003840001C071020FFA8181C010038100101202564000433383335000200010200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
SAMPLE_CONFIG_DATA_2 = "CD5D613E0966018001E13380060007080402000258010B000000000D000000000D000000000D071020FFA8181C010038140000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"

# Other actual data captures of Sami Status Data.
# :000EDCAE0000000000000000000000F70000F7
# :000EDCB30000000000000000000000F70000F7
# :000EDCB80000000000000000000000F70000F7
# :000EDCBD0000000000000000000000F70000F7
# :000EDCC20000000000000000000000F70000F7
# :000EDCC70000000000000000000000F70000F7
# :000EDCCC0000000000000000000000F70000F7
# :000EDCD10000000000000000000000F70000F7
# :000EDCD60000000000000000000000F70000F7

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.sami.pco2w.cgsn.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'E3SIRI',
    instrument_agent_name = 'sami_pco2w_cgsn',
    instrument_agent_packet_config = DataParticleType(),

    driver_startup_config = {}
)

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
class DataParticleMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constance and common data assertion methods.
    '''
    # Create some short names for the parameter test config
    TYPE      = ParameterTestConfigKey.TYPE
    READONLY  = ParameterTestConfigKey.READONLY
    STARTUP   = ParameterTestConfigKey.STARTUP
    DA        = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE     = ParameterTestConfigKey.VALUE
    REQUIRED  = ParameterTestConfigKey.REQUIRED
    DEFAULT   = ParameterTestConfigKey.DEFAULT
    ###
    #  Parameter and Type Definitions
    ##   
    _driver_parameters = {
        # parameters - contains all setsampling parameters
        Parameter.PUMP_PULSE :                  { TYPE: int, READONLY: True , DA: False, DEFAULT: 16,   VALUE: 16, REQUIRED: True },
        Parameter.PUMP_ON_TO_MEASURE :          { TYPE: int, READONLY: True , DA: False, DEFAULT: 32,   VALUE: 32, REQUIRED: True },
        Parameter.NUM_SAMPLES_PER_MEASURE :     { TYPE: int, READONLY: True , DA: False, DEFAULT: 255,  VALUE: 255,REQUIRED: True },
        Parameter.NUM_CYCLES_BETWEEN_BLANKS:    { TYPE: int, READONLY: False, DA: True,  DEFAULT: 168,  VALUE: 168,REQUIRED: True },
        Parameter.NUM_REAGENT_CYCLES :          { TYPE: int, READONLY: True , DA: False, DEFAULT: 24,   VALUE: 24, REQUIRED: True },
        Parameter.NUM_BLANK_CYCLES :            { TYPE: int, READONLY: True , DA: False, DEFAULT: 28,   VALUE: 28, REQUIRED: True },
        Parameter.FLUSH_PUMP_INTERVAL_SEC :     { TYPE: int, READONLY: True , DA: False, DEFAULT: 1,    VALUE: 1,  REQUIRED: True },
        Parameter.STARTUP_BLANK_FLUSH_ENABLE:   { TYPE: bool,READONLY: False, DA: True,  DEFAULT: False,VALUE: True, REQUIRED: True },
        Parameter.PUMP_PULSE_POST_MEASURE_ENABLE:{TYPE: bool,READONLY: True , DA: True,  DEFAULT: False,VALUE: False, REQUIRED: True },
        Parameter.NUM_EXTRA_PUMP_PULSE_CYCLES:  { TYPE: int, READONLY: True , DA: True,  DEFAULT: 56,   VALUE: 56, REQUIRED: True }
    }

    # Test results that get decoded from the string sent to the chunker.
    _data_record_parameters = {   
        SamiDataRecordParticleKey.UNIQUE_ID:        { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 91, REQUIRED: True},
        SamiDataRecordParticleKey.RECORD_LENGTH:    { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 39, REQUIRED: True},
        SamiDataRecordParticleKey.RECORD_TYPE:      { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 4,  REQUIRED: True},
        SamiDataRecordParticleKey.RECORD_TIME:      { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 0xC8EF9FC9, REQUIRED: True},
        SamiDataRecordParticleKey.VOLTAGE_BATTERY:  { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 205, REQUIRED: True },
        SamiDataRecordParticleKey.THERMISTER_RAW:   { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 255, REQUIRED: True },
        SamiDataRecordParticleKey.CHECKSUM:         { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 0x3B, REQUIRED: True},
        SamiDataRecordParticleKey.LIGHT_MEASUREMENT:{ TYPE: list,READONLY: False, DA: False }
    }
    
    _control_record_parameters = {   
        SamiControlRecordParticleKey.UNIQUE_ID:     { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 0xD2, REQUIRED: True},
        SamiControlRecordParticleKey.RECORD_LENGTH: { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 0x12, REQUIRED: True},
        SamiControlRecordParticleKey.RECORD_TYPE:   { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 0x85,  REQUIRED: True},
        SamiControlRecordParticleKey.RECORD_TIME:   { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 0xCCB0F0A5, REQUIRED: True},
        SamiControlRecordParticleKey.CHECKSUM:      { TYPE: int, READONLY: False, DA: False, DEFAULT: 0x0, VALUE: 0xEA, REQUIRED: True},
    }
   
    # Test results that get decoded from the string sent to the chunker.
    _regular_status_parameters = {
        SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG:  { TYPE: int,  VALUE: 0x3F91BE, REQUIRED: True},  # 48 5:14:38
        SamiRegularStatusDataParticleKey.CLOCK_ACTIVE:         { TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORDING_ACTIVE:     { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME:   { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL:   { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR:  { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK:     { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN:    { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.BATTERY_FATAL_ERROR:  { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT:{TYPE:bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK:     { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL: { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE_FAULT:{ TYPE: int,  VALUE: 0x0,   REQUIRED: True },
        SamiRegularStatusDataParticleKey.FLASH_ERASED:         { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiRegularStatusDataParticleKey.POWER_ON_INVALID:     { TYPE: bool, VALUE: False, REQUIRED: True }
    }
    
    # Test for Immediate Status.
    _immediate_status_parameters = {
        SamiImmediateStatusDataParticleKey.PUMP_ON:          { TYPE: bool, VALUE: True , REQUIRED: True },
        SamiImmediateStatusDataParticleKey.VALVE_ON:         { TYPE: bool, VALUE: False, REQUIRED: True },      
        SamiImmediateStatusDataParticleKey.EXTERNAL_POWER_ON:{ TYPE: bool, VALUE: False, REQUIRED: True },
        SamiImmediateStatusDataParticleKey.DEBUG_LED:        { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiImmediateStatusDataParticleKey.DEBUG_ECHO:       { TYPE: bool, VALUE: False, REQUIRED: True }
    } 
       
    # Not currently decoded
    _config_parameters = {
        SamiConfigDataParticleKey.LAUNCH_TIME:      { TYPE: int, VALUE: 0xCAB39E84, REQUIRED: True}, # 3400769156 = 0xCAB39E84
        SamiConfigDataParticleKey.START_TIME_OFFSET:{ TYPE: int, VALUE: 244, REQUIRED: True},
        SamiConfigDataParticleKey.RECORDING_TIME:   { TYPE: int, VALUE: 31536000, REQUIRED: True},
        
        SamiConfigDataParticleKey.PMI_SAMPLE_SCHEDULE         : { TYPE: bool, VALUE: True,  REQUIRED: True },
        SamiConfigDataParticleKey.SAMI_SAMPLE_SCHEDULE        : { TYPE: bool, VALUE: True,  REQUIRED: True },
        SamiConfigDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE : { TYPE: bool, VALUE: True,  REQUIRED: True },
        SamiConfigDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE  : { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiConfigDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE : { TYPE: bool, VALUE: True,  REQUIRED: True },
        SamiConfigDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE  : { TYPE: bool, VALUE: False, REQUIRED: True },
        SamiConfigDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE : { TYPE: bool, VALUE: True,  REQUIRED: True },
        SamiConfigDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE  : { TYPE: bool, VALUE: False, REQUIRED: True },

        SamiConfigDataParticleKey.TIMER_INTERVAL_SAMI:{ TYPE: int, VALUE: 1800, REQUIRED: True },
        SamiConfigDataParticleKey.DRIVER_ID_SAMI:     { TYPE: int, VALUE: 4,  REQUIRED: True },
        SamiConfigDataParticleKey.PARAM_PTR_SAMI:     { TYPE: int, VALUE: 1,  REQUIRED: True },
        SamiConfigDataParticleKey.TIMER_INTERVAL_1:   { TYPE: int, VALUE: 600,REQUIRED: True },
        SamiConfigDataParticleKey.DRIVER_ID_1:        { TYPE: int, VALUE: 3,  REQUIRED: True },
        SamiConfigDataParticleKey.PARAM_PTR_1:        { TYPE: int, VALUE: 10, REQUIRED: True },
        SamiConfigDataParticleKey.TIMER_INTERVAL_2:   { TYPE: int, VALUE: 600,REQUIRED: True },
        SamiConfigDataParticleKey.DRIVER_ID_2:        { TYPE: int, VALUE: 0,  REQUIRED: True },
        SamiConfigDataParticleKey.PARAM_PTR_2:        { TYPE: int, VALUE: 23, REQUIRED: True },    
        SamiConfigDataParticleKey.TIMER_INTERVAL_3:   { TYPE: int, VALUE: 600,REQUIRED: True },
        SamiConfigDataParticleKey.DRIVER_ID_3:        { TYPE: int, VALUE: 1,  REQUIRED: True },
        SamiConfigDataParticleKey.PARAM_PTR_3:        { TYPE: int, VALUE: 26, REQUIRED: True },
        SamiConfigDataParticleKey.TIMER_INTERVAL_PRESTART: { TYPE: int, VALUE: 14400, REQUIRED: True },
        SamiConfigDataParticleKey.DRIVER_ID_PRESTART: { TYPE: int, VALUE: 0, REQUIRED: True },
        SamiConfigDataParticleKey.PARAM_PTR_PRESTART: { TYPE: int, VALUE: 28, REQUIRED: True },
        
        SamiConfigDataParticleKey.USE_BAUD_RATE_9600:     { TYPE: bool, VALUE: False,REQUIRED: True },
        SamiConfigDataParticleKey.SEND_RECORD_TYPE_EARLY: { TYPE: bool, VALUE: True, REQUIRED: True },
        SamiConfigDataParticleKey.SEND_LIVE_RECORDS:      { TYPE: bool, VALUE: True, REQUIRED: True },
        
        SamiConfigDataParticleKey.PUMP_PULSE:             { TYPE: int, VALUE: 0x10, REQUIRED: True },
        SamiConfigDataParticleKey.PUMP_ON_TO_MEAURSURE:   { TYPE: int, VALUE: 0x20, REQUIRED: True },
        SamiConfigDataParticleKey.SAMPLES_PER_MEASURE:    { TYPE: int, VALUE: 0xFF, REQUIRED: True },
        SamiConfigDataParticleKey.CYCLES_BETWEEN_BLANKS:  { TYPE: int, VALUE: 0xA8, REQUIRED: True },
        SamiConfigDataParticleKey.NUM_REAGENT_CYCLES:     { TYPE: int, VALUE: 0x18, REQUIRED: True },
        SamiConfigDataParticleKey.NUM_BLANK_CYCLES:       { TYPE: int, VALUE: 0x1C, REQUIRED: True },
        SamiConfigDataParticleKey.FLUSH_PUMP_INTERVAL:    { TYPE: int, VALUE: 0x1,  REQUIRED: True },
        SamiConfigDataParticleKey.BLANK_FLUSH_ON_START_ENABLE:   { TYPE: bool, VALUE: True, REQUIRED: True },
        SamiConfigDataParticleKey.PUMP_PULSE_POST_MEASURE:{ TYPE: bool, VALUE: False, REQUIRED: True },
        SamiConfigDataParticleKey.NUM_EXTRA_PUMP_PULSE_CYCLES:   { TYPE: int,  VALUE: 56, REQUIRED: True },                         
    }
    
    ###
    #   Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    def assert_particle_configuration(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SamiConfigDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiConfigDataParticleKey, self._config_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.CONFIG_PARSED)
        self.assert_data_particle_parameters(data_particle, self._config_parameters, verify_values)
        
    def assert_particle_regular_status(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SamiRegularStatusDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiRegularStatusDataParticleKey, self._regular_status_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.REGULAR_STATUS_PARSED)
        self.assert_data_particle_parameters(data_particle, self._regular_status_parameters, verify_values)

    def assert_particle_immediate_status(self, data_particle, verify_values = False):
        '''
        Immediate Read Status SW & BUS response.
        '''
        self.assert_data_particle_keys(SamiImmediateStatusDataParticleKey, self._immediate_status_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.IMMEDIATE_STATUS_PARSED)
        self.assert_data_particle_parameters(data_particle, self._immediate_status_parameters, verify_values)
        
    def assert_particle_data_record(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SamiDataRecordParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiDataRecordParticleKey, self._data_record_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.DATA_RECORD_PARSED)
        self.assert_data_particle_parameters(data_particle, self._data_record_parameters, verify_values)

    def assert_particle_control_record(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SamiControlRecordParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiControlRecordParticleKey, self._control_record_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.CONTROL_RECORD_PARSED)
        self.assert_data_particle_parameters(data_particle, self._control_record_parameters, verify_values)
        
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
class SamiUnitTest(InstrumentDriverUnitTestCase, DataParticleMixin):
    """Unit Test Container"""
    
    ###
    #    This is the callback that would normally publish events 
    #    (streams, state transitions, etc.).
    #    Use this method to test for existence of events and to examine their
    #    attributes for correctness.
    ###
    
    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(ScheduledJob())
        self.assert_enum_has_no_duplicates(DataParticleType())

        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())

        self.assert_enum_has_no_duplicates(Parameter())

        self.assert_enum_has_no_duplicates(SamiControlRecordParticleKey)
        self.assert_enum_has_no_duplicates(SamiDataRecordParticleKey)
        self.assert_enum_has_no_duplicates(SamiConfigDataParticleKey)
        self.assert_enum_has_no_duplicates(SamiImmediateStatusDataParticleKey)
        self.assert_enum_has_no_duplicates(SamiRegularStatusDataParticleKey)
        
        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())
   
    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)
        
        test_data = SAMPLE_DATA_RECORD_1      
        self.assert_chunker_sample(chunker, test_data)
        self.assert_chunker_sample_with_noise(chunker, test_data)
        self.assert_chunker_fragmented_sample(chunker, test_data)
        self.assert_chunker_combined_sample(chunker, test_data)

        test_data = SAMPLE_CONTROL_RECORD
        self.assert_chunker_sample(chunker, test_data)
        self.assert_chunker_sample_with_noise(chunker, test_data)
        self.assert_chunker_fragmented_sample(chunker, test_data)
        self.assert_chunker_combined_sample(chunker, test_data)

        test_data = SAMPLE_CONFIG_DATA_1      
        self.assert_chunker_sample(chunker, test_data)
        self.assert_chunker_sample_with_noise(chunker, test_data)
        self.assert_chunker_fragmented_sample(chunker, test_data)
        self.assert_chunker_combined_sample(chunker, test_data)

        test_data = SAMPLE_REGULAR_STATUS_DATA_1
        self.assert_chunker_sample(chunker, test_data)
        self.assert_chunker_sample_with_noise(chunker, test_data)
        self.assert_chunker_fragmented_sample(chunker, test_data)
        self.assert_chunker_combined_sample(chunker, test_data)
        # Note: Immediate status data particle updated in parse_I_command().

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)
        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, SAMPLE_REGULAR_STATUS_DATA_1, self.assert_particle_regular_status, True)  # Regular Status
        self.assert_particle_published(driver, SAMPLE_DATA_RECORD_1, self.assert_particle_data_record, True)          # Data Record.
        self.assert_particle_published(driver, SAMPLE_CONTROL_RECORD, self.assert_particle_control_record, True)          # Data Record.
        self.assert_particle_published(driver, SAMPLE_CONFIG_DATA_1, self.assert_particle_configuration, True)
        
        # Note: The Immediate Status Particle is a command response!
#        self.assert_particle_published(driver, SAMPLE_IMMEDIATE_STATUS_DATA, self.assert_particle_immediate_status, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up "bogus" capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
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
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """    

        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                    'DRIVER_EVENT_ACQUIRE_STATUS',
                                    'DRIVER_EVENT_CLOCK_SYNC',
                                    'PROTOCOL_EVENT_ACQUIRE_CONFIGURATION',
                                    'PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_ACQUIRE_STATUS','DRIVER_EVENT_STOP_AUTOSAMPLE','PROTOCOL_EVENT_SCHEDULED_CLOCK_SYNC']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)
          
    def test_parse_config_response(self):
        """
        Test the parsing of ALL Data Dictionary parameters 
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)
        source = SAMPLE_CONFIG_DATA_1
		
        # First verify that parse sets all know parameters.
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        log.debug("Param Dict Values: %s" % pd)
        log.debug("Param Sample: %s" % source)
        self.assert_driver_parameters(pd, True)

        # Define the index of the SAMI-CO2 Driver 4/5 Parameters.
        param_index = SamiConfiguration._SAMI_DRIVER_PARAM_INDEX
        
        # Replace Pump Pulse (Driver-4 parameter first 2 characters).
        source = replace_string_chars(source, param_index, "1120FFA8181C010038")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.PUMP_PULSE), 0x11)

        source = replace_string_chars(source, param_index, "1040FFA8181C010038")  # 01 0000 0001
        log.debug("Param Sample: %s" % source[param_index:96])
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.PUMP_ON_TO_MEASURE), 0x40)

        source = replace_string_chars(source, param_index, "102001A8181C010038")
        log.debug("Param Sample: %s" % source[param_index:96])
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.NUM_SAMPLES_PER_MEASURE), 0x01)

        source = replace_string_chars(source, param_index, "1020FFA0181C010038")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.NUM_CYCLES_BETWEEN_BLANKS), 0xA0)

        source = replace_string_chars(source, param_index, "1020FFA8331C010038")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.NUM_REAGENT_CYCLES), 0x33)
                         
        source = replace_string_chars(source, param_index, "1020FFA818CC010038")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.NUM_BLANK_CYCLES), 0xCC)

        source = replace_string_chars(source, param_index, "1020FFA8181CFF0038")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.FLUSH_PUMP_INTERVAL_SEC), 0xFF)
        
        # Update the bit-switches (Bit-0 Don't start with BlankFlush, Bit-1 Meas after each pump pulse
        # Note that the startup_blank_flush_enable value is inverse of the bit-value.
        source = replace_string_chars(source, param_index, "1020FFA8181C010138")  # 01 0000 0001
        log.debug("Param Sample: %s" % source[param_index:96])
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.STARTUP_BLANK_FLUSH_ENABLE), False)
        self.assertEqual(pd.get(Parameter.PUMP_PULSE_POST_MEASURE_ENABLE), False)
               
        # Test the bit-field decoder (2-chars before 38 at the string end here).
        source = replace_string_chars(source, param_index, "1020FFA8181C010238")  # 02 0000 0010
        log.debug("Param Sample: %s" % source[param_index:96])
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.STARTUP_BLANK_FLUSH_ENABLE), True)
        self.assertEqual(pd.get(Parameter.PUMP_PULSE_POST_MEASURE_ENABLE), True)

        # Test the last entry
        source = replace_string_chars(source, param_index, "1120FFA8181C010030")
        log.debug("Param Sample: %s" % source)
        driver._protocol._parse_config_response(source, prompt=None)
        pd = driver._protocol._param_dict.get_config()
        self.assertEqual(pd.get(Parameter.NUM_EXTRA_PUMP_PULSE_CYCLES), 0x30)

    def test_parse_regular_response(self):
        """
        Test response from Regular Status Command
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)        
        source = SAMPLE_REGULAR_STATUS_DATA_2

        # Verify that parser sets all know parameters.
        driver._protocol._parse_S_response(source, prompt=None)
        
    def test_parse_immediate_response(self):
        """
        Test response from Immediate Status Command
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)
        source = SAMPLE_IMMEDIATE_STATUS_DATA
        
        # Verify that parser sets all know parameters.
        driver._protocol._parse_I_response(source, prompt=None)     

    def test_parse_take_response(self):
        """
        Test response from Take Sample commands.
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, ProtocolState.COMMAND)
        source = SAMPLE_REGULAR_STATUS_DATA_2
        
        # Verify that parser sets all know parameters.
        driver._protocol._parse_R_response(source, prompt=None)
        
    def test_utils(self):
        """
        Test the custom utility functions
        """       
        log.debug("Testing Error Handling")
        error_txt = SamiConfiguration.get_error_str( 0xA )
        self.assertEqual(error_txt, "Flash is Not Open")
        error_txt = SamiConfiguration.get_error_str(-1)
        self.assertEqual(error_txt, None)
        error_txt = SamiConfiguration.get_error_str(0x100)
        self.assertEqual(error_txt, None)
        
        log.debug("Testing vb_mid() Utility")
        s1 = "1234567890"
        s2 = SamiConfiguration.vb_mid(s1, 2, 2)
        self.assertEqual(s2, "23")
        
        # Test past the end of the string.
        s2 = SamiConfiguration.vb_mid(s1, 10, 2)
        self.assertEqual(s2, "0")
        
        log.debug("Testing replace_string_chars() utility")
        s1 = "0123456789"
        s2 = replace_string_chars(s1, 0, "23")
        self.assertEqual(s2, "2323456789")

        s1 = "0123456789"
        s2 = replace_string_chars(s1, 3, "FF")
        self.assertEqual(s2, "012FF56789")
        
        # Test the case beyond the string.
        s2 = replace_string_chars(s1, 10, "0123456789") # Cat
        self.assertEqual(s2, "01234567890123456789")
        
        s2 = replace_string_chars(s1, 20, "FFFFFFFFFF")
        self.assertEqual(s2, "0123456789")  # No change
        
        log.debug("Testing checksum utility")
        s1 = "0000"
        cs = SamiConfiguration.calc_crc(s1, 2)
        self.assertEqual(cs, 0x00)
        
        # This is a known CRC test
        record = SAMPLE_DATA_RECORD_1
        record_length = 39
        num_bytes = (record_length - 1)
        num_char = 2 * num_bytes
        # Sami says throw away the 1st 3 characters.
        cs_calc = SamiConfiguration.calc_crc( record[3:3+num_char], num_bytes)
        self.assertEqual(cs_calc, 0x3B)
        
        # Use our trusted replace-string function to corrupt a byte.
        record = replace_string_chars(record, 10, "FFF")
        cs_calc = SamiConfiguration.calc_crc( record[3:3+num_char], num_bytes)
        self.assertNotEqual(cs_calc, 0x3B)       

        log.debug("Testing time utilities")
        time_str = "abc"
        tsec = convert_timestamp_to_sec(time_str)
        self.assertEqual(tsec, 0)

        time_str = "01-01-1970 00:00:00"
        tsec = convert_timestamp_to_sec(time_str)
        self.assertEqual(tsec, 0)

        # these functions wrapper convert_timestamp_to_sec() so just call for test.
        tsec = get_timestamp_sec()
        log.debug("tsec = " + str(tsec))
        tsec = get_timestamp_delayed_sec()
        log.debug("tsec = " + str(tsec))
        
    def test_config_tool(self):
        """
        Test the custom configuration string management tool.
        """
        sami_config = SamiConfiguration()
        r = sami_config.set_config_str( SAMPLE_CONFIG_DATA_1 )
        if( not r ):
            log.debug("Invalid configuration setting")
            
        # This test is used to verify the comparision utility.
        r2 = SAMPLE_CONFIG_DATA_2   # different
        r = sami_config.compare(r2)
        self.assertEqual(r, False)
            
        r2 = SAMPLE_CONFIG_DATA_1   # equal
        r = sami_config.compare(r2)
        self.assertEqual(r, True)
        
        r = sami_config.compare("") # invalid
        self.assertEqual(r, None)
        
        # Set the time to the current time
        sami_config.set_config_str( SAMPLE_CONFIG_DATA_1 )
        tnow_sec_F = time.time()   # Currentonds since Epoch
        tnow_sec = int(tnow_sec_F)
        r = sami_config.set_config_time(tnow_sec)
        self.assertEqual(r, True)

        # Should be able to read-back the current time.
        test_txt = sami_config.get_config_time(unix_fmt=True)
        self.assertEqual(int(test_txt,16), tnow_sec)       

        # Test a time out-of-range problem.
        t = datetime.datetime(12, 1, 1, 0, 0)  # User setting to last year time.
        tsecF = calendar.timegm(t.timetuple())
        r = sami_config.set_config_time(int(tsecF))
        self.assertEqual(r, False)        

        # Set a corrupted configuration string by adding a second 1st character.
        source = "B" + SAMPLE_CONFIG_DATA_1[1:]
        r = sami_config.set_config_str(source)
        self.assertEqual(r, False)        

        source = SAMPLE_CONFIG_DATA_1[1:32]
        r = sami_config.set_config_str(source)
        self.assertEqual(r, False)

        # Store/Retrieve test
        r = sami_config.set_config_str( SAMPLE_CONFIG_DATA_1 )
        self.assertEqual(r, True)
        s = sami_config.get_config_str()
        # Only the first 232 characters of a configuration string are valid.
        self.assertEqual(s[0:232], SAMPLE_CONFIG_DATA_1[0:232])
        
###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SamiIntegrationTest(InstrumentDriverIntegrationTestCase, DataParticleMixin):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def check_state(self, expected_state):
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, expected_state)
        
    ###
    #    Add instrument specific integration tests
    ###

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
        
    def test_set(self):
        self.assert_initialize_driver()
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        # Verify we can set the clock
        # self.assert_set_clock(Parameter.DATE_TIME, tolerance=5)

        # Verify we can set all parameters in bulk
        new_values = {
            Parameter.PUMP_PULSE: 16,
            Parameter.PUMP_ON_TO_MEASURE: 10,
            Parameter.NUM_CYCLES_BETWEEN_BLANKS: 1
        }
        self.assert_set_bulk(new_values)

        self.assert_set_exception(Parameter.PUMP_PULSE, 'bad')
        
    def test_startup_configuration(self):
        '''
        Test that the startup configuration is applied correctly
        '''
        self.put_instrument_in_command_mode()

        result = self.driver_client.cmd_dvr('apply_startup_params')

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.PUMP_PULSE])

        self.assertEquals(reply, {Parameter.PUMP_PULSE: 16})

        params = {
            Parameter.PUMP_PULSE : 16
#            Parameter.TXWAVESTATS : False,
#            Parameter.USER_INFO : "KILROY WAZ HERE"
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, {Parameter.PUMP_PULSE: 16})
        
    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)
    
    def test_commands(self):
        self.put_instrument_in_command_mode()
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_driver_command(ProtocolEvent.GET_CONFIGURATION)
        # self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
                
    def test_set(self):       
        self.put_instrument_in_command_mode()
        
        new_params = {
           Parameter.PUMP_PULSE: 0xAA,
           Parameter.PUMP_ON_TO_MEASURE: 0xBB
        }
       
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        self.assertEquals(reply, new_params)
                 
        reply = self.driver_client.cmd_dvr('get_resource', new_params, timeout=20)
        self.assertEquals(reply, new_params)
        
        
    def test_set_broken(self):
        """
        Test all set commands. Verify all exception cases.
        """
#        self.assert_initialize_driver()   
        self.put_instrument_in_command_mode()
        self.assert_set(Parameter.PUMP_PULSE, 0xFF, no_get=True)
        self.assert_get(Parameter.PUMP_PULSE, 0xFF)

    def test_get(self):
        self.put_instrument_in_command_mode()

        #
        # Test the full list of parameters.        
        #
        params = {
                   Parameter.PUMP_PULSE: 16,
                   Parameter.PUMP_ON_TO_MEASURE: 32,
                   Parameter.NUM_SAMPLES_PER_MEASURE: 255,
                   Parameter.NUM_CYCLES_BETWEEN_BLANKS: 168,
                   Parameter.NUM_REAGENT_CYCLES: 24,
                   Parameter.NUM_BLANK_CYCLES: 28,
                   Parameter.FLUSH_PUMP_INTERVAL_SEC: 0x1,
                   Parameter.STARTUP_BLANK_FLUSH_ENABLE: True,
                   Parameter.PUMP_PULSE_POST_MEASURE_ENABLE: False,
                   Parameter.NUM_EXTRA_PUMP_PULSE_CYCLES: 56
        }

        reply = self.driver_client.cmd_dvr('get_resource',
                                           params.keys(),
                                           timeout=20)
        self.assertEquals(reply, params)

        #
        # Test a partial list of parameters.
        #
        params = {
                   Parameter.PUMP_PULSE: 16,
                   Parameter.PUMP_ON_TO_MEASURE: 32
        }

        reply = self.driver_client.cmd_dvr('get_resource',
                                           params.keys(),
                                           timeout=20)
        
        self.assertEquals(reply, params)

        #
        # Test a single set update.
        #
        self.assert_get(Parameter.PUMP_PULSE, 16)
        
    def test_get_cjc(self):
        
        self.put_instrument_in_command_mode()

        params = {
                   Parameter.PUMP_PULSE: 16,
                   Parameter.PUMP_ON_TO_MEASURE: 32
        }

        reply = self.driver_client.cmd_dvr('get_resource',
                                           params.keys(),
                                           timeout=20)
        
        self.assertEquals(reply, params)
        
    def test_apply_startup_params(self):
        """
        This test verifies that we can set the startup params
        from autosample mode.  It only verifies one parameter
        change because all parameters are tested above.
        """
        # Apply autosample happens for free when the driver fires up
        self.assert_initialize_driver()

        # Change something
        self.assert_set(Parameter.PUMP_PULSE, 15)

        # Now try to apply params in Streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE)
        self.driver_client.cmd_dvr('apply_startup_params')

        # All done.  Verify the startup parameter has been reset
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND)
        self.assert_get(Parameter.PUMP_PULSE, 15)
        
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
        
 #       self.assert_direct_access_start_telnet()
 #       self.assertTrue(self.tcp_client)

        ###
        #   Add instrument specific code here.
        ###

#       self.assert_direct_access_stop_telnet()
        
#    def test_poll(self):
#        '''
#        No polling for a single sample
#        '''
#       # Poll for a sample and confirm result.
#        sample1 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
#        log.debug("SAMPLE1 = " + str(sample1[1]))


    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        Pass
        
    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        '''
        Pass

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        
    def test_direct_access_telnet_mode(self):
        """
        Test that we can connect to the instrument via direct access.  Also
        verify that direct access parameters are reset on exit.
        """
        self.assert_enter_command_mode()
#       self.assert_set_parameter(Parameter.TXREALTIME, True)

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        # ask for device status from Sami.
        self.tcp_client.send_data("S0\r\n")
        self.tcp_client.expect(":")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()
        self.assert_get_parameter(Parameter.TXREALTIME, True)
    
    def test_execute_clock_sync(self):
        """
        Verify we can syncronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        # wait for a bit so the event can be triggered
        time.sleep(1)

        # Set the clock to something in the past
        time_str = "01-Jan-2001 01:01:01"
        time_sec = convert_timestamp_to_sec(time_str)
        self.assert_set_parameter(Parameter.PROGRAM_DATE_TIME, "01 Jan 2001 01:01:01", verify=False)

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)
        self.assert_execute_resource(ProtocolEvent.ACQUIRE_CONFIGURATION)   # Get Configuration.

        # Now verify that at least the date matches
        params = [Parameter.PROGRAM_DATE_TIME]
        check_new_params = self.instrument_agent_client.get_resource(params)
        lt = time.strftime("%d %b %Y  %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        log.debug("TIME: %s && %s" % (lt, check_new_params[Parameter.PROGRAM_DATE_TIME]))
        self.assertTrue(lt[:12].upper() in check_new_params[Parameter.PROGRAM_DATE_TIME].upper())

