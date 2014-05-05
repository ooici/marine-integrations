"""
@package mi.instrument.sunburst.sami2_pco2.pco2a.test.test_driver
@file marine-integrations/mi/instrument/sunburst/sami2_pco2/pco2a/driver.py
@author Christopher Wingard
@brief Test cases for pco2a driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Christopher Wingard & Kevin Stiemke'
__license__ = 'Apache 2.0'

import unittest
import time
import copy

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger
log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey
from mi.idk.unit_test import AgentCapabilityType

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from pyon.agent.agent import ResourceAgentEvent
from pyon.agent.agent import ResourceAgentState

from mi.instrument.sunburst.sami2_pco2.pco2a.driver import InstrumentDriver
from mi.instrument.sunburst.driver import SamiInstrumentCommand
from mi.instrument.sunburst.driver import ScheduledJob
from mi.instrument.sunburst.sami2_pco2.pco2a.driver import ProtocolState
from mi.instrument.sunburst.sami2_pco2.pco2a.driver import ProtocolEvent
from mi.instrument.sunburst.driver import Capability
from mi.instrument.sunburst.sami2_pco2.pco2a.driver import Parameter
from mi.instrument.sunburst.sami2_pco2.pco2a.driver import Protocol
from mi.instrument.sunburst.driver import Prompt
from mi.instrument.sunburst.driver import NEWLINE
from mi.instrument.sunburst.sami2_pco2.pco2a.driver import Pco2wSamiSampleDataParticleKey
from mi.instrument.sunburst.sami2_pco2.pco2a.driver import Pco2wConfigurationDataParticleKey
from mi.instrument.sunburst.sami2_pco2.pco2a.driver import DataParticleType

# Added Imports (Note, these pick up some of the base classes not directly imported above)
from mi.instrument.sunburst.sami2_pco2.test.test_driver import Pco2DriverTestMixinSub
from mi.instrument.sunburst.sami2_pco2.test.test_driver import Pco2DriverUnitTest
from mi.instrument.sunburst.sami2_pco2.test.test_driver import Pco2DriverIntegrationTest
from mi.instrument.sunburst.sami2_pco2.test.test_driver import Pco2DriverQualificationTest

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(

    driver_module='mi.instrument.sunburst.sami2_pco2.pco2a.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='V7HE4T',
    instrument_agent_name='sunburst_sami2_pco2_pco2a',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={}
#    driver_startup_config={
#            DriverStartupConfigKey.PARAMETERS: {
#            Parameter.STOP_TIME_FROM_START: 7,
#        },
#    }
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
# Driver constant definitions
###

###############################################################################
#                           DRIVER TEST MIXIN                                 #
#     Defines a set of constants and assert methods used for data particle    #
#     verification                                                            #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.                                      #
###############################################################################
class DriverTestMixinSub(Pco2DriverTestMixinSub):

    '''
    Mixin class used for storing data particle constants and common data
    assertion methods.
    '''
    # Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    ###
    #  Instrument output (driver input) Definitions
    ###
    # Configuration string received from the instrument via the L command
    # (clock set to 2014-01-01 00:00:00) with sampling set to start 540 days
    # (~18 months) later and stop 365 days after that. SAMI and Device1
    # (external SBE pump) are set to run every 60 minutes, but will be polled
    # on a regular schedule rather than autosampled. Device1 is not configured
    # to run after the SAMI and will run for 10 seconds. To configure the
    # instrument using this string, add a null byte (00) to the end of the
    # string.
    VALID_CONFIG_STRING = 'CEE90B0002C7EA0001E133800A000E100402000E10010B' + \
                          '000000000D000000000D000000000D07' + \
                          '1020FF54181C010038' + \
                          '000000000000000000000000000000000000000000000000000' + \
                          '000000000000000000000000000000000000000000000000000' + \
                          '000000000000000000000000000000' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                          'FFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + NEWLINE

    # Data records -- SAMI and Device1 (external pump) (responses to R0 and R1
    # commands, respectively)
    VALID_R0_BLANK_SAMPLE = '*542705CEE91CC800400019096206800730074C2CE042' + \
                            '74003B0018096106800732074E0D82066124' + NEWLINE
    VALID_R0_DATA_SAMPLE = '*542704CEE91CC8003B001909620155073003E908A1232' + \
                           'D0043001A09620154072F03EA0D92065F3B' + NEWLINE

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.LAUNCH_TIME:              {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x00000000, VALUE: 0xCEE90B00, REQUIRED: True},
        Parameter.START_TIME_FROM_LAUNCH:   {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x02C7EA00, VALUE: 0x02C7EA00, REQUIRED: True},
        Parameter.STOP_TIME_FROM_START:     {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x01E13380, VALUE: 0x01E13380, REQUIRED: True},
        Parameter.MODE_BITS:                {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x0A, VALUE: 0x0A, REQUIRED: True},
        Parameter.SAMI_SAMPLE_INTERVAL:     {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x000E10, VALUE: 0x000E10, REQUIRED: True},
        Parameter.SAMI_DRIVER_VERSION:      {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x04, VALUE: 0x04, REQUIRED: True},
        Parameter.SAMI_PARAMS_POINTER:      {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x02, VALUE: 0x02, REQUIRED: True},
        Parameter.DEVICE1_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x000E10, VALUE: 0x000E10, REQUIRED: True},
        Parameter.DEVICE1_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x01, VALUE: 0x01, REQUIRED: True},
        Parameter.DEVICE1_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x0B, VALUE: 0x0B, REQUIRED: True},
        Parameter.DEVICE2_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x000000, VALUE: 0x000000, REQUIRED: True},
        Parameter.DEVICE2_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x00, VALUE: 0x00, REQUIRED: True},
        Parameter.DEVICE2_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x0D, VALUE: 0x0D, REQUIRED: True},
        Parameter.DEVICE3_SAMPLE_INTERVAL:  {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x000000, VALUE: 0x000000, REQUIRED: True},
        Parameter.DEVICE3_DRIVER_VERSION:   {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x00, VALUE: 0x00, REQUIRED: True},
        Parameter.DEVICE3_PARAMS_POINTER:   {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x0D, VALUE: 0x0D, REQUIRED: True},
        Parameter.PRESTART_SAMPLE_INTERVAL: {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x000000, VALUE: 0x000000, REQUIRED: True},
        Parameter.PRESTART_DRIVER_VERSION:  {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x00, VALUE: 0x00, REQUIRED: True},
        Parameter.PRESTART_PARAMS_POINTER:  {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x0D, VALUE: 0x00, REQUIRED: True},
        Parameter.GLOBAL_CONFIGURATION:     {TYPE: int, READONLY: True, DA: True, STARTUP: False,
                                             DEFAULT: 0x07, VALUE: 0x07, REQUIRED: True},
        Parameter.PUMP_PULSE:               {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0x10, VALUE: 0x10, REQUIRED: True},
        Parameter.PUMP_DURATION:            {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0x20, VALUE: 0x20, REQUIRED: True},
        Parameter.SAMPLES_PER_MEASUREMENT:  {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0xFF, VALUE: 0xFF, REQUIRED: True},
        Parameter.CYCLES_BETWEEN_BLANKS:    {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0x54, VALUE: 0x54, REQUIRED: True},
        Parameter.NUMBER_REAGENT_CYCLES:    {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0x18, VALUE: 0x18, REQUIRED: True},
        Parameter.NUMBER_BLANK_CYCLES:      {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0x1C, VALUE: 0x1C, REQUIRED: True},
        Parameter.FLUSH_PUMP_INTERVAL:      {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0x01, VALUE: 0x01, REQUIRED: True},
        Parameter.BIT_SWITCHES:             {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0x00, VALUE: 0x00, REQUIRED: True},
        Parameter.NUMBER_EXTRA_PUMP_CYCLES: {TYPE: int, READONLY: False, DA: True, STARTUP: False,
                                             DEFAULT: 0x38, VALUE: 0x38, REQUIRED: True},
        Parameter.AUTO_SAMPLE_INTERVAL:     {TYPE: int, READONLY: False, DA: False, STARTUP: False,
                                             DEFAULT: 0x38, VALUE: 3600, REQUIRED: True},
    }

    _sami_data_sample_parameters = {
        # SAMI Type 4/5 sample (in this case it is a Type 4)
        Pco2wSamiSampleDataParticleKey.UNIQUE_ID:           {TYPE: int, VALUE: 0x54, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_LENGTH:       {TYPE: int, VALUE: 0x27, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_TYPE:         {TYPE: int, VALUE: 0x04, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_TIME:         {TYPE: int, VALUE: 0xCEE91CC8, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS:  {TYPE: list, VALUE: [0x003B, 0x0019, 0x0962, 0x0155,
                                                                                 0x0730, 0x03E9, 0x08A1, 0x232D,
                                                                                 0x0043, 0x001A, 0x0962, 0x0154,
                                                                                 0x072F, 0x03EA], REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.VOLTAGE_BATTERY:     {TYPE: int, VALUE: 0x0D92, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.THERMISTER_RAW:      {TYPE: int, VALUE: 0x065F, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.CHECKSUM:            {TYPE: int, VALUE: 0x3B, REQUIRED: True}
    }

    _sami_blank_sample_parameters = {
        # SAMI Type 4/5 sample (in this case it is a Type 5)
        Pco2wSamiSampleDataParticleKey.UNIQUE_ID:           {TYPE: int, VALUE: 0x54, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_LENGTH:       {TYPE: int, VALUE: 0x27, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_TYPE:         {TYPE: int, VALUE: 0x05, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.RECORD_TIME:         {TYPE: int, VALUE: 0xCEE91CC8, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.LIGHT_MEASUREMENTS:  {TYPE: list, VALUE: [0x0040, 0x0019, 0x0962, 0x0680, 0x0730,
                                                                                 0x074C, 0x2CE0, 0x4274, 0x003B, 0x0018,
                                                                                 0x0961, 0x0680, 0x0732, 0x074E],
                                                             REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.VOLTAGE_BATTERY:     {TYPE: int, VALUE: 0x0D82, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.THERMISTER_RAW:      {TYPE: int, VALUE: 0x0661, REQUIRED: True},
        Pco2wSamiSampleDataParticleKey.CHECKSUM:            {TYPE: int, VALUE: 0x24, REQUIRED: True}
    }

    _configuration_parameters = {
        # Configuration settings
        Pco2wConfigurationDataParticleKey.LAUNCH_TIME:                  {TYPE: int, VALUE: 0xCEE90B00, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.START_TIME_OFFSET:            {TYPE: int, VALUE: 0x02C7EA00, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.RECORDING_TIME:               {TYPE: int, VALUE: 0x01E13380, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PMI_SAMPLE_SCHEDULE:          {TYPE: bool, VALUE: False,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SAMI_SAMPLE_SCHEDULE:         {TYPE: bool, VALUE: True,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT1_FOLLOWS_SAMI_SCHEDULE:  {TYPE: bool, VALUE: False,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT1_INDEPENDENT_SCHEDULE:   {TYPE: bool, VALUE: True, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT2_FOLLOWS_SAMI_SCHEDULE:  {TYPE: bool, VALUE: False,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT2_INDEPENDENT_SCHEDULE:   {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT3_FOLLOWS_SAMI_SCHEDULE:  {TYPE: bool, VALUE: False,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SLOT3_INDEPENDENT_SCHEDULE:   {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_SAMI:          {TYPE: int, VALUE: 0x000E10, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_SAMI:               {TYPE: int, VALUE: 0x04,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_SAMI:       {TYPE: int, VALUE: 0x02,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE1:       {TYPE: int, VALUE: 0x000E10, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE1:            {TYPE: int, VALUE: 0x01,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE1:    {TYPE: int, VALUE: 0x0B, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE2:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE2:            {TYPE: int, VALUE: 0x00,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE2:    {TYPE: int, VALUE: 0x0D, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_DEVICE3:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_DEVICE3:            {TYPE: int, VALUE: 0x00,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_DEVICE3:    {TYPE: int, VALUE: 0x0D, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.TIMER_INTERVAL_PRESTART:      {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DRIVER_ID_PRESTART:           {TYPE: int, VALUE: 0x00, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PARAMETER_POINTER_PRESTART:   {TYPE: int, VALUE: 0x0D, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.USE_BAUD_RATE_57600:          {TYPE: bool, VALUE: True, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SEND_RECORD_TYPE:             {TYPE: bool, VALUE: True, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SEND_LIVE_RECORDS:            {TYPE: bool, VALUE: True, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.EXTEND_GLOBAL_CONFIG:         {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PUMP_PULSE:                   {TYPE: int, VALUE: 0x10, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.PUMP_DURATION:                {TYPE: int, VALUE: 0x20, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.SAMPLES_PER_MEASUREMENT:      {TYPE: int, VALUE: 0xFF, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.CYCLES_BETWEEN_BLANKS:        {TYPE: int, VALUE: 0x54, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.NUMBER_REAGENT_CYCLES:        {TYPE: int, VALUE: 0x18, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.NUMBER_BLANK_CYCLES:          {TYPE: int, VALUE: 0x1C, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.FLUSH_PUMP_INTERVAL:          {TYPE: int, VALUE: 0x01,  REQUIRED: True},
        Pco2wConfigurationDataParticleKey.DISABLE_START_BLANK_FLUSH:    {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.MEASURE_AFTER_PUMP_PULSE:     {TYPE: bool, VALUE: False, REQUIRED: True},
        Pco2wConfigurationDataParticleKey.NUMBER_EXTRA_PUMP_CYCLES:     {TYPE: int,  VALUE: 0x38, REQUIRED: True},
    }

    ###
    #   Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values=False):
        """
        Verify that all driver parameters are correct and potentially verify
        values.
        @param current_parameters: driver parameters read from the driver
        instance
        @param verify_values: should we verify values against definition?
        """

        self.assert_parameters(current_parameters, self._driver_parameters,
                               verify_values)
        #self.assert_parameters(current_parameters, self._driver_parameters,
        #                       False)

    def assert_particle_sami_sample(self, data_particle, verify_values=False):
        '''
        Verify sami_data_sample particles (Type 4 and 5).  Used in INT test where type doesn't matter.
        @param data_particle: Pco2wSamiSampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(Pco2wSamiSampleDataParticleKey,
                                       self._sami_data_sample_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.SAMI_SAMPLE)
        self.assert_data_particle_parameters(data_particle,
                                             self._sami_data_sample_parameters,
                                             verify_values)

    def assert_particle_sami_data_sample(self, data_particle, verify_values=False):
        '''
        Verify sami_data_sample particle (Type 4)
        @param data_particle: Pco2wSamiSampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''

        sample_dict = self.get_data_particle_values_as_dict(data_particle)
        record_type = sample_dict.get(Pco2wSamiSampleDataParticleKey.RECORD_TYPE)
        self.assertEqual(record_type, 4, msg="Not a regular sample, record_type = %d" % record_type)

        self.assert_data_particle_keys(Pco2wSamiSampleDataParticleKey,
                                       self._sami_data_sample_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.SAMI_SAMPLE)
        self.assert_data_particle_parameters(data_particle,
                                             self._sami_data_sample_parameters,
                                             verify_values)

        sample_dict = self.get_data_particle_values_as_dict(data_particle)
        record_type = sample_dict.get(Pco2wSamiSampleDataParticleKey.RECORD_TYPE)
        required_record_type = 4
        log.debug('herb: ' + 'assert_particle_sami_data_sample(): record_type:required_record_type = ' +
                  str(record_type) + ":" +
                  str(required_record_type))
        self.assertEquals(record_type, required_record_type)


    def assert_particle_sami_blank_sample(self, data_particle, verify_values=False):
        '''
        Verify sami_blank_sample particle (Type 5)
        @param data_particle: Pco2wSamiSampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''

        sample_dict = self.get_data_particle_values_as_dict(data_particle)
        record_type = sample_dict.get(Pco2wSamiSampleDataParticleKey.RECORD_TYPE)
        self.assertEqual(record_type, 5, msg="Not a blank sample, record_type = %d" % record_type)

        self.assert_data_particle_keys(Pco2wSamiSampleDataParticleKey,
                                       self._sami_blank_sample_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.SAMI_SAMPLE)
        self.assert_data_particle_parameters(data_particle,
                                             self._sami_blank_sample_parameters,
                                             verify_values)

        sample_dict = self.get_data_particle_values_as_dict(data_particle)
        record_type = sample_dict.get(Pco2wSamiSampleDataParticleKey.RECORD_TYPE)
        required_record_type = 5
        log.debug('herb: ' + 'assert_particle_sami_blank_sample(): record_type:required_record_type = ' +
                  str(record_type) + ":" +
                  str(required_record_type))
        self.assertEquals(record_type, required_record_type)

    def assert_particle_configuration(self, data_particle, verify_values=False):
        '''
        Verify configuration particle
        @param data_particle: Pco2wConfigurationDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(Pco2wConfigurationDataParticleKey,
                                       self._configuration_parameters)
        self.assert_data_particle_header(data_particle,
                                         DataParticleType.CONFIGURATION)
        self.assert_data_particle_parameters(data_particle,
                                             self._configuration_parameters,
                                             verify_values)

###############################################################################
#                                UNIT TESTS                                   #
#         Unit Tests: test the method calls and parameters using Mock.        #
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
class DriverUnitTest(Pco2DriverUnitTest, DriverTestMixinSub):

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might
        cause confusion. Also do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(SamiInstrumentCommand())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, self.VALID_STATUS_MESSAGE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_STATUS_MESSAGE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_STATUS_MESSAGE)
        self.assert_chunker_combined_sample(chunker, self.VALID_STATUS_MESSAGE)

        self.assert_chunker_sample(chunker, self.VALID_CONTROL_RECORD)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_CONTROL_RECORD)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_CONTROL_RECORD)
        self.assert_chunker_combined_sample(chunker, self.VALID_CONTROL_RECORD)

        self.assert_chunker_sample(chunker, self.VALID_R0_BLANK_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_R0_BLANK_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_R0_BLANK_SAMPLE)
        self.assert_chunker_combined_sample(chunker, self.VALID_R0_BLANK_SAMPLE)

        self.assert_chunker_sample(chunker, self.VALID_R0_DATA_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_R0_DATA_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_R0_DATA_SAMPLE)
        self.assert_chunker_combined_sample(chunker, self.VALID_R0_DATA_SAMPLE)

        self.assert_chunker_sample(chunker, self.VALID_CONFIG_STRING)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_CONFIG_STRING)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_CONFIG_STRING)
        self.assert_chunker_combined_sample(chunker, self.VALID_CONFIG_STRING)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the
        correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, self.VALID_STATUS_MESSAGE,
                                       self.assert_particle_regular_status, True)
        self.assert_particle_published(driver, self.VALID_CONTROL_RECORD,
                                       self.assert_particle_control_record, True)
        self.assert_particle_published(driver, self.VALID_R0_BLANK_SAMPLE,
                                       self.assert_particle_sami_blank_sample, True)
        self.assert_particle_published(driver, self.VALID_R0_DATA_SAMPLE,
                                       self.assert_particle_sami_data_sample, True)
        self.assert_particle_published(driver, self.VALID_CONFIG_STRING,
                                       self.assert_particle_configuration, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities. Iterate through available
        capabilities, and verify that they can pass successfully through the
        filter. Test silly made up capabilities to verify they are blocked by
        filter.
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

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected. All states defined in
        this dict must also be defined in the protocol FSM. Note, the EXIT and
        ENTER DRIVER_EVENTS don't need to be listed here.
        """
        # capabilities defined in base class test_driver.

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, self.capabilities_test_dict)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################



@attr('INT', group='mi')
class DriverIntegrationTest(Pco2DriverIntegrationTest, DriverTestMixinSub):
    """
    Integration Tests:

    test_set:  In command state, test configuration particle generation.
        Parameter.PUMP_PULSE
        Parameter.PUMP_DURATION
        Parameter.SAMPLES_PER_MEASUREMENT
        Parameter.CYCLES_BETWEEN_BLANKS
        Parameter.NUMBER_REAGENT_CYCLES
        Parameter.NUMBER_BLANK_CYCLES
        Parameter.FLUSH_PUMP_INTERVAL
        Parameter.BIT_SWITCHES
        Parameter.NUMBER_EXTRA_PUMP_CYCLES
        Parameter.AUTO_SAMPLE_INTERVAL
        Negative Set Tests:
            START_TIME_FROM_LAUNCH
            STOP_TIME_FROM_START
            MODE_BITS
            SAMI_SAMPLE_INTERVAL

    test_commands:  In autosample and command states, test particle generation.
        ACQUIRE_STATUS = ProtocolEvent.ACQUIRE_STATUS
        ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
        ACQUIRE_BLANK_SAMPLE = ProtocolEvent.ACQUIRE_BLANK_SAMPLE

    test_autosample:  Test autosample particle generation.
        START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
        STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE

    test_scheduled_data:  In command and autosample states
        ACQUIRE_STATUS
        ACQUIRE_BLANK_SAMPLE
    """

    def test_set(self):
        self.assert_initialize_driver()
        self.assert_set(Parameter.AUTO_SAMPLE_INTERVAL, 77)
        self.assert_set(Parameter.CYCLES_BETWEEN_BLANKS, 7)
        self.assert_set(Parameter.PUMP_PULSE, 20)
        self.assert_set(Parameter.SAMPLES_PER_MEASUREMENT, 239)
        self.assert_set(Parameter.NUMBER_REAGENT_CYCLES, 26)
        self.assert_set(Parameter.NUMBER_BLANK_CYCLES, 30)
        self.assert_set(Parameter.FLUSH_PUMP_INTERVAL, 2)
        self.assert_set(Parameter.BIT_SWITCHES, 1)
        self.assert_set(Parameter.NUMBER_EXTRA_PUMP_CYCLES, 88)

        self.assert_set_readonly(Parameter.START_TIME_FROM_LAUNCH, 84600)
        self.assert_set_readonly(Parameter.STOP_TIME_FROM_START, 84600)
        self.assert_set_readonly(Parameter.MODE_BITS, 10)
        self.assert_set_readonly(Parameter.SAMI_SAMPLE_INTERVAL, 1800)

    def test_bulk_set(self):
        self.assert_initialize_driver()

        new_values = {
            Parameter.AUTO_SAMPLE_INTERVAL: 77,
            Parameter.CYCLES_BETWEEN_BLANKS: 7,
            Parameter.PUMP_PULSE: 20,
            Parameter.SAMPLES_PER_MEASUREMENT: 239,
            Parameter.NUMBER_REAGENT_CYCLES: 26,
            Parameter.NUMBER_BLANK_CYCLES: 30,
            Parameter.FLUSH_PUMP_INTERVAL: 2,
            Parameter.BIT_SWITCHES: 1,
            Parameter.NUMBER_EXTRA_PUMP_CYCLES: 88,
        }
        self.assert_set_bulk(new_values)

    def test_acquire_sample(self):
        self.assert_initialize_driver()
        # Will always take a blank sample first after initialization.
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)
        self.clear_events()
        # Take a regular sample
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_data_sample, timeout=160)

    def test_acquire_blank_sample(self):
        self.assert_initialize_driver()
        # Will always take a blank sample first after initialization.
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)
        self.clear_events()
        # Take a blank sample
        self.assert_driver_command(ProtocolEvent.ACQUIRE_BLANK_SAMPLE)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)

    def test_auto_sample(self):
        self.assert_initialize_driver()
        self.assert_set(Parameter.AUTO_SAMPLE_INTERVAL, 160)
        ## A blank sample is taken immediately upon entering autosample state
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.SCHEDULED_SAMPLE, delay=5)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_data_sample, particle_count=4, timeout=840)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=5)

    def test_polled_sample_state(self):
        self.assert_initialize_driver()
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE, state=ProtocolState.POLLED_SAMPLE, delay=5)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)

    def test_polled_blank_sample_state(self):
        self.assert_initialize_driver()
        self.assert_driver_command(ProtocolEvent.ACQUIRE_BLANK_SAMPLE, state=ProtocolState.POLLED_BLANK_SAMPLE, delay=5)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)

    def test_scheduled_sample_state(self):
        self.assert_initialize_driver()
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.SCHEDULED_SAMPLE, delay=5)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=5)

    def test_scheduled_blank_sample_state(self):
        self.assert_initialize_driver()
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.SCHEDULED_SAMPLE, delay=5)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)
        self.clear_events()
        self.assert_driver_command(ProtocolEvent.ACQUIRE_BLANK_SAMPLE, state=ProtocolState.SCHEDULED_BLANK_SAMPLE, delay=5)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=160)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=5)

    def test_scheduled_blank_sample_command(self):
        """
        Verify the blank sample command can be triggered and run in command
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_BLANK_SAMPLE, delay=120)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=300)
        self.assert_current_state(ProtocolState.COMMAND)

    def test_scheduled_device_status_auto_sample(self):
        """
        Verify the device status command can be triggered and run in autosample
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_STATUS, delay=160)
        self.clear_events()
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.SCHEDULED_SAMPLE, delay=5)
        self.assert_async_particle_generation(DataParticleType.CONFIGURATION, self.assert_particle_configuration, timeout=280)
        self.assert_async_particle_generation(DataParticleType.BATTERY_VOLTAGE, self.assert_particle_battery_voltage)
        self.assert_async_particle_generation(DataParticleType.THERMISTOR_VOLTAGE, self.assert_particle_thermistor_voltage)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)

    def test_scheduled_blank_sample_auto_sample(self):
        """
        Verify the blank sample command can be triggered and run in autosample
        """
        self.assert_scheduled_event(ScheduledJob.ACQUIRE_BLANK_SAMPLE, delay=180)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.SCHEDULED_SAMPLE, delay=5)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, particle_count=2, timeout=460)
        self.assert_current_state(ProtocolState.AUTOSAMPLE)

    def test_queued_command(self):
        """
        Verify commands are queued while samples are being taken
        """
        self.assert_initialize_driver()

        ## Queue sample and status
        self.clear_events()
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=180)
        self.assert_async_particle_generation(DataParticleType.REGULAR_STATUS, self.assert_particle_regular_status, timeout=180)
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_data_sample, timeout=180)

        ## Queue blank sample and status
        self.clear_events()
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_BLANK_SAMPLE)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_data_sample, timeout=180)
        self.assert_async_particle_generation(DataParticleType.REGULAR_STATUS, self.assert_particle_regular_status, timeout=180)
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=180)

        self.assert_current_state(ProtocolState.COMMAND)

    def test_queued_autosample(self):
        """
        Verify commands are queued while samples are being taken
        """
        self.assert_initialize_driver()
        self.clear_events()
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.SCHEDULED_SAMPLE, delay=5)

        ## Queue sample and status
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=180)
        self.assert_async_particle_generation(DataParticleType.REGULAR_STATUS, self.assert_particle_regular_status, timeout=180)
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_data_sample, timeout=180)

        ## Queue blank sample and status
        self.clear_events()
        self.assert_driver_command(ProtocolEvent.ACQUIRE_SAMPLE)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_BLANK_SAMPLE)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS)
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_data_sample, timeout=180)
        self.assert_async_particle_generation(DataParticleType.REGULAR_STATUS, self.assert_particle_regular_status, timeout=180)
        self.clear_events()
        self.assert_async_particle_generation(DataParticleType.SAMI_SAMPLE, self.assert_particle_sami_blank_sample, timeout=180)

        self.assert_current_state(ProtocolState.AUTOSAMPLE)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(Pco2DriverQualificationTest, DriverTestMixinSub):

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly
        supports direct access to the physical instrument. (telnet mode)
        """

        self.assert_enter_command_mode()

        self.assert_set_parameter(Parameter.CYCLES_BETWEEN_BLANKS, 7)

        configuration_string =  'CF889C9C02C7EA0001E1338002000E10040200000000000000000000000000000000000000000' + \
                                '71020FFA8181C0100380000000000000000000000000000000000000000000000000000000000' + \
                                '00000000000000000000000000000000000000000000000000000000000000000000000000000' + \
                                '0FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                                'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                                'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF' + \
                                'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'

        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        # Erase memory
        self.tcp_client.send_data("E5A%s" % NEWLINE)

        time.sleep(1)

        # Load a new configuration string changing X to X
        self.tcp_client.send_data("L5A%s" % NEWLINE)

        time.sleep(1)

        self.tcp_client.send_data("%s00%s" % (configuration_string, NEWLINE))

        time.sleep(1)

        # Check that configuration was changed
        self.tcp_client.send_data("L%s" % NEWLINE)
        return_value = self.tcp_client.expect(configuration_string)
        self.assertTrue(return_value)

        ###
        #   Add instrument specific code here.
        ###

        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        self.assert_get_parameter(Parameter.CYCLES_BETWEEN_BLANKS, 7)

    def test_command_poll(self):

        self.assert_enter_command_mode()

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_SAMPLE, self.assert_particle_sami_blank_sample, DataParticleType.SAMI_SAMPLE, sample_count=1, timeout=200)

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_SAMPLE, self.assert_particle_sami_data_sample, DataParticleType.SAMI_SAMPLE, sample_count=1, timeout=200)

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_BLANK_SAMPLE, self.assert_particle_sami_blank_sample, DataParticleType.SAMI_SAMPLE, sample_count=1, timeout=200)

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_regular_status, DataParticleType.REGULAR_STATUS, sample_count=1, timeout=10)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_configuration, DataParticleType.CONFIGURATION, sample_count=1, timeout=10)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_battery_voltage, DataParticleType.BATTERY_VOLTAGE, sample_count=1, timeout=10)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_thermistor_voltage, DataParticleType.THERMISTOR_VOLTAGE, sample_count=1, timeout=10)

    def test_autosample_poll(self):

        self.assert_enter_command_mode()

        self.assert_start_autosample(timeout=200)

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_SAMPLE, self.assert_particle_sami_data_sample, DataParticleType.SAMI_SAMPLE, sample_count=1, timeout=200)

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_BLANK_SAMPLE, self.assert_particle_sami_blank_sample, DataParticleType.SAMI_SAMPLE, sample_count=1, timeout=200)

        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_regular_status, DataParticleType.REGULAR_STATUS, sample_count=1, timeout=10)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_configuration, DataParticleType.CONFIGURATION, sample_count=1, timeout=10)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_battery_voltage, DataParticleType.BATTERY_VOLTAGE, sample_count=1, timeout=10)
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_STATUS, self.assert_particle_thermistor_voltage, DataParticleType.THERMISTOR_VOLTAGE, sample_count=1, timeout=10)

        self.assert_stop_autosample()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

    def test_autosample(self):
        """
        Verify autosample works and data particles are created
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.AUTO_SAMPLE_INTERVAL, 160)

        ## Get the blank sample out of the way
        self.assert_particle_polled(ProtocolEvent.ACQUIRE_SAMPLE, self.assert_particle_sami_blank_sample, DataParticleType.SAMI_SAMPLE, sample_count=1, timeout=200)

        self.assert_sample_autosample(self.assert_particle_sami_data_sample, DataParticleType.SAMI_SAMPLE)

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
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.ACQUIRE_STATUS,
                ProtocolEvent.ACQUIRE_SAMPLE,
                ProtocolEvent.ACQUIRE_BLANK_SAMPLE
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  DA Mode
        ##################

        da_capabilities = copy.deepcopy(capabilities)
        da_capabilities[AgentCapabilityType.AGENT_COMMAND] = [ResourceAgentEvent.GO_COMMAND]
        da_capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []

        # Test direct access disconnect
        self.assert_direct_access_start_telnet(timeout=10)
        self.assertTrue(self.tcp_client)

        self.assert_capabilities(da_capabilities)
        self.tcp_client.disconnect()

        # Now do it again, but use the event to stop DA
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)
        self.assert_direct_access_start_telnet(timeout=10)
        self.assert_capabilities(da_capabilities)
        self.assert_direct_access_stop_telnet()


        ##################
        #  Command Mode
        ##################

        # We should be back in command mode from DA.
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        st_capabilities = copy.deepcopy(capabilities)
        st_capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        st_capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            ProtocolEvent.STOP_AUTOSAMPLE,
            ProtocolEvent.ACQUIRE_STATUS,
            ProtocolEvent.ACQUIRE_SAMPLE,
            ProtocolEvent.ACQUIRE_BLANK_SAMPLE
        ]

        self.assert_start_autosample(timeout=200)
        self.assert_capabilities(st_capabilities)
        self.assert_stop_autosample()

        ##################
        #  Command Mode
        ##################

        # We should be back in command mode from DA.
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)
        self.assert_capabilities(capabilities)

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)