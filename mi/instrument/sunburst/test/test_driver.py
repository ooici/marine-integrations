"""
@package mi.instrument.sunburst.test.test_driver
@file marine-integrations/mi/instrument/sunburst/driver.py
@author Stuart Pearce & Chris Wingard
@brief Common test case code for SAMI instrument drivers

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Stuart Pearce & Chris Wingard'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger
log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

# Might need these for later Integration tests and Qualification tests
#from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
#from ion.agents.instrument.instrument_agent import InstrumentAgentState
#from mi.core.instrument.instrument_driver import DriverAsyncEvent
#from mi.core.instrument.instrument_driver import DriverConnectionState
#from mi.core.instrument.instrument_driver import DriverProtocolState

from mi.instrument.sunburst.driver import Capability
from mi.instrument.sunburst.driver import NEWLINE
from mi.instrument.sunburst.driver import ProtocolEvent
from mi.instrument.sunburst.driver import ProtocolState
from mi.instrument.sunburst.driver import SamiControlRecordDataParticleKey
from mi.instrument.sunburst.driver import SamiDataParticleType
from mi.instrument.sunburst.driver import SamiRegularStatusDataParticleKey


###
#   Driver parameters for the tests
###


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

# Create some short names for the parameter test config
TYPE = ParameterTestConfigKey.TYPE
READONLY = ParameterTestConfigKey.READONLY
STARTUP = ParameterTestConfigKey.STARTUP
DA = ParameterTestConfigKey.DIRECT_ACCESS
VALUE = ParameterTestConfigKey.VALUE
REQUIRED = ParameterTestConfigKey.REQUIRED
DEFAULT = ParameterTestConfigKey.DEFAULT
STATES = ParameterTestConfigKey.STATES

###############################################################################
#                           DRIVER TEST MIXIN        		                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification 														      #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.									  #
###############################################################################


class SamiMixin(DriverTestMixin):
    '''
    Mixin class used for storing SAMI instrument data particle constants and common data
    assertion methods.

    Should be subclassed in the specific test driver
    '''

    ###
    #  Instrument output (driver input) Definitions
    ###

    # Control records
    VALID_CONTROL_RECORD = '*F81285CDDD74DD0041000003000000000224FC' + NEWLINE

    # Regular Status Message (response to S0 command)
    VALID_STATUS_MESSAGE = ':CDDD74E10041000003000000000236F8' + NEWLINE

    # Error records (valid error codes are between 0x00 and 0x11)
    VALID_ERROR_CODE = '?0B' + NEWLINE

    ###
    #  Parameter and Type Definitions
    ###

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.ACQUIRE_STATUS:      {STATES: [ProtocolState.COMMAND]},
        #Capability.ACQUIRE_SAMPLE:      {STATES: [ProtocolState.COMMAND]},
        Capability.START_AUTOSAMPLE:    {STATES: [ProtocolState.COMMAND,
                                                  ProtocolState.AUTOSAMPLE]},
        Capability.STOP_AUTOSAMPLE:     {STATES: [ProtocolState.AUTOSAMPLE,
                                                  ProtocolState.COMMAND]},
        Capability.START_DIRECT:        {STATES: [ProtocolState.COMMAND,
                                                  ProtocolState.UNKNOWN,
                                                  ProtocolState.DIRECT_ACCESS]},
        Capability.STOP_DIRECT:         {STATES: [ProtocolState.DIRECT_ACCESS,
                                                  ProtocolState.UNKNOWN]}
    }

    _regular_status_parameters = {
        # SAMI Regular Status Messages (S0)
        SamiRegularStatusDataParticleKey.ELAPSED_TIME_CONFIG:     {TYPE: int, VALUE: 0xCDDD74E1, REQUIRED: True},
        SamiRegularStatusDataParticleKey.CLOCK_ACTIVE:            {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORDING_ACTIVE:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_END_ON_TIME:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_MEMORY_FULL:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.RECORD_END_ON_ERROR:     {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.DATA_DOWNLOAD_OK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.FLASH_MEMORY_OPEN:       {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_PRESTART:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_MEASUREMENT: {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_BANK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.BATTERY_LOW_EXTERNAL:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE1_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE2_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.EXTERNAL_DEVICE3_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.FLASH_ERASED:            {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.POWER_ON_INVALID:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_DATA_RECORDS:        {TYPE: int, VALUE: 0x000003, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_ERROR_RECORDS:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiRegularStatusDataParticleKey.NUM_BYTES_STORED:        {TYPE: int, VALUE: 0x000236, REQUIRED: True},
        SamiRegularStatusDataParticleKey.UNIQUE_ID:               {TYPE: int, VALUE: 0xF8, REQUIRED: True}
    }

    _control_record_parameters = {
        SamiControlRecordDataParticleKey.UNIQUE_ID:               {TYPE: int, VALUE: 0xF8, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_LENGTH:           {TYPE: int, VALUE: 0x12, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_TYPE:             {TYPE: int, VALUE: 0x85,  REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_TIME:             {TYPE: int, VALUE: 0xCDDD74DD, REQUIRED: True},
        SamiControlRecordDataParticleKey.CLOCK_ACTIVE:            {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORDING_ACTIVE:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_END_ON_TIME:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_MEMORY_FULL:      {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.RECORD_END_ON_ERROR:     {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.DATA_DOWNLOAD_OK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.FLASH_MEMORY_OPEN:       {TYPE: bool, VALUE: True, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_PRESTART:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_MEASUREMENT: {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_BANK:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.BATTERY_LOW_EXTERNAL:    {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE1_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE2_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.EXTERNAL_DEVICE3_FAULT:  {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.FLASH_ERASED:            {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.POWER_ON_INVALID:        {TYPE: bool, VALUE: False, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_DATA_RECORDS:        {TYPE: int, VALUE: 0x000003, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_ERROR_RECORDS:       {TYPE: int, VALUE: 0x000000, REQUIRED: True},
        SamiControlRecordDataParticleKey.NUM_BYTES_STORED:        {TYPE: int, VALUE: 0x000224, REQUIRED: True},
        SamiControlRecordDataParticleKey.CHECKSUM:                {TYPE: int, VALUE: 0xFC, REQUIRED: True}
    }

    def assertSampleDataParticle(self, data_particle):
        '''
        Verify a particle is a known particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''
        if (isinstance(data_particle, RawDataParticle)):
            self.assert_particle_raw(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

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

    def assert_particle_regular_status(self, data_particle, verify_values=False):
        '''
        Verify regular_status particle
        @param data_particle: SamiRegularStatusDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiRegularStatusDataParticleKey,
                                       self._regular_status_parameters)
        self.assert_data_particle_header(data_particle,
                                         SamiDataParticleType.REGULAR_STATUS)
        self.assert_data_particle_parameters(data_particle,
                                             self._regular_status_parameters,
                                             verify_values)

    def assert_particle_control_record(self, data_particle, verify_values=False):
        '''
        Verify control_record particle
        @param data_particle: SamiControlRecordDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(SamiControlRecordDataParticleKey,
                                       self._control_record_parameters)
        self.assert_data_particle_header(data_particle,
                                         SamiDataParticleType.CONTROL_RECORD)
        self.assert_data_particle_parameters(data_particle,
                                             self._control_record_parameters,
                                             verify_values)


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
class SamiUnitTest(InstrumentDriverUnitTestCase, SamiMixin):

    def test_base_driver_enums(self):
        """
        Verify that all the SAMI Instrument driver enumerations have no
        duplicate values that might cause confusion. Also do a little
        extra validation for the Capabilites

        Extra enumeration tests are done in a specific subclass
        """
        # Test Enums defined in the base SAMI driver
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())

        # Test capabilites for duplicates, then verify that capabilities
        # is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    capabilities_test_dict = {
        ProtocolState.UNKNOWN:          ['DRIVER_EVENT_START_DIRECT',
                                         'DRIVER_EVENT_DISCOVER'],
        ProtocolState.WAITING:          ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND:          ['DRIVER_EVENT_GET',
                                         'DRIVER_EVENT_SET',
                                         'DRIVER_EVENT_START_DIRECT',
                                         #'DRIVER_EVENT_ACQUIRE_CONFIGURATION',
                                         'DRIVER_EVENT_ACQUIRE_STATUS',
                                         'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                         'DRIVER_EVENT_START_AUTOSAMPLE'],
        ProtocolState.AUTOSAMPLE:       ['DRIVER_EVENT_ACQUIRE_SAMPLE',
                                         'DRIVER_EVENT_STOP_AUTOSAMPLE'],
        ProtocolState.DIRECT_ACCESS:    ['EXECUTE_DIRECT',
                                         'DRIVER_EVENT_STOP_DIRECT'],
        ProtocolState.SCHEDULED_SAMPLE: ['PROTOCOL_EVENT_SUCCESS',
                                         'PROTOCOL_EVENT_TIMEOUT'],
        ProtocolState.POLLED_SAMPLE:    ['PROTOCOL_EVENT_SUCCESS',
                                         'PROTOCOL_EVENT_TIMEOUT']
    }


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SamiIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class SamiQualificationTest(InstrumentDriverQualificationTestCase):
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