"""
@package mi.instrument.um.thsph.thsph.test.test_driver
@file marine-integrations/mi/instrument/um/thsph/thsph/driver.py
@author Richard Han
@brief Test cases for thsph driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""
from mi.core.instrument.data_particle import RawDataParticle

__author__ = 'Richard Han'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase, ParameterTestConfigKey
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin


from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from mi.instrument.um.thsph.thsph.driver import InstrumentDriver, THSPHDataParticleKey
from mi.instrument.um.thsph.thsph.driver import DataParticleType
from mi.instrument.um.thsph.thsph.driver import Command
from mi.instrument.um.thsph.thsph.driver import ProtocolState
from mi.instrument.um.thsph.thsph.driver import ProtocolEvent
from mi.instrument.um.thsph.thsph.driver import Capability
from mi.instrument.um.thsph.thsph.driver import Parameter
from mi.instrument.um.thsph.thsph.driver import THSPHProtocol
from mi.instrument.um.thsph.thsph.driver import Prompt
from mi.instrument.um.thsph.thsph.driver import NEWLINE

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.um.thsph.thsph.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'WHSSRV',
    instrument_agent_name = 'um_thsph_thsph',
    instrument_agent_packet_config = DataParticleType(),

    driver_startup_config = {}
)

GO_ACTIVE_TIMEOUT=180
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
class THSPHMixinSub(DriverTestMixin):

    InstrumentDriver = InstrumentDriver

    '''
    Mixin class used for storing data particle constants and common data assertion methods.
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

    INVALID_SAMPLE  = "This is an invalid sample; it had better cause an exception." + NEWLINE
    VALID_SAMPLE_01 = "aH200A200720DE20AA10883FFF2211225E#"
    VALID_SAMPLE_02 = "aH200A200720E120AB108A3FFF21FF2420#"
    #VALID_SAMPLE_02 = "aH200A200720E120AB108A3FFF21FF2420#" + NEWLINE

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.INTERVAL : {TYPE: int, READONLY: False, DA: False, STARTUP: False},
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.ACQUIRE_SAMPLE : {STATES: [ProtocolState.COMMAND]},
        Capability.START_AUTOSAMPLE : {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_AUTOSAMPLE : {STATES: [ProtocolState.AUTOSAMPLE]},
        Capability.GET : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.SET : {STATES: [ProtocolState.COMMAND]},
    }

    _sample_parameters = {
        THSPHDataParticleKey.HIGH_IMPEDANCE_ELECTRODE_1: {TYPE: int, VALUE: 8202, REQUIRED: True },
        THSPHDataParticleKey.HIGH_IMPEDANCE_ELECTRODE_2: {TYPE: int, VALUE: 8199, REQUIRED: True },
        THSPHDataParticleKey.H2_ELECTRODE: {TYPE: int, VALUE: 8414, REQUIRED: True },
        THSPHDataParticleKey.S2_ELECTRODE: {TYPE: int, VALUE: 8362, REQUIRED: True },
        THSPHDataParticleKey.THERMOCOUPLE1: {TYPE: int, VALUE: 4232, REQUIRED: True },
        THSPHDataParticleKey.THERMOCOUPLE2: {TYPE: int, VALUE: 16383, REQUIRED: True },
        THSPHDataParticleKey.REFERENCE_THERMISTOR: {TYPE: int, VALUE: 8721, REQUIRED: True },
        THSPHDataParticleKey.BOARD_THERMISTOR: {TYPE: int, VALUE: 8798, REQUIRED: True },

    }

    _sample_parameters_2 = {
        THSPHDataParticleKey.HIGH_IMPEDANCE_ELECTRODE_1: {TYPE: int, VALUE: 8202, REQUIRED: True },
        THSPHDataParticleKey.HIGH_IMPEDANCE_ELECTRODE_2: {TYPE: int, VALUE: 8199, REQUIRED: True },
        THSPHDataParticleKey.H2_ELECTRODE: {TYPE: int, VALUE: 8417, REQUIRED: True },
        THSPHDataParticleKey.S2_ELECTRODE: {TYPE: int, VALUE: 8363, REQUIRED: True },
        THSPHDataParticleKey.THERMOCOUPLE1: {TYPE: int, VALUE: 4234, REQUIRED: True },
        THSPHDataParticleKey.THERMOCOUPLE2: {TYPE: int, VALUE: 16383, REQUIRED: True },
        THSPHDataParticleKey.REFERENCE_THERMISTOR: {TYPE: int, VALUE: 8703, REQUIRED: True },
        THSPHDataParticleKey.BOARD_THERMISTOR: {TYPE: int, VALUE: 9248, REQUIRED: True },

    }

    _status_parameters = {
        #SBE16StatusParticleKey.FIRMWARE_VERSION: {TYPE: unicode, VALUE: '2.5', REQUIRED: True },

    }

    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify sample particle
        @param data_particle:  THSPHDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(THSPHDataParticleKey, self._sample_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.THSPH_PARSED, require_instrument_timestamp=False)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)


    def assert_particle_sample2(self, data_particle, verify_values = False):
        '''
        Verify sample particle
        @param data_particle:  THSPHDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(THSPHDataParticleKey, self._sample_parameters_2)
        self.assert_data_particle_header(data_particle, DataParticleType.THSPH_PARSED, require_instrument_timestamp=False)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_2, verify_values)



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
class DriverUnitTest(InstrumentDriverUnitTestCase, THSPHMixinSub):
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
        self.assert_enum_has_no_duplicates(Command())

        # Test capabilites for duplicates, then verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = self.InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(THSPHProtocol.sieve_function)
        self.assert_chunker_sample(chunker, self.VALID_SAMPLE_01)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_SAMPLE_01)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_SAMPLE_01)
        self.assert_chunker_combined_sample(chunker, self.VALID_SAMPLE_01)

        self.assert_chunker_sample(chunker, self.VALID_SAMPLE_02)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_SAMPLE_02)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_SAMPLE_02)
        self.assert_chunker_combined_sample(chunker, self.VALID_SAMPLE_02)


    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, self.VALID_SAMPLE_01, self.assert_particle_sample, True)
        self.assert_particle_published(driver, self.VALID_SAMPLE_02, self.assert_particle_sample2, True)


    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = THSPHProtocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.COMMAND: ['DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_GET',
                                       'DRIVER_EVENT_START_AUTOSAMPLE',
                                       'DRIVER_EVENT_STOP_AUTOSAMPLE'],
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER']
        }
        driver = self.InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, THSPHMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)


    def test_connection(self):

         self.assert_initialize_driver()


    def test_data_on(self):
        """
        @brief Test for turning data on
        """
        self.assert_initialize_driver()
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_SAMPLE,
                                        DataParticleType.THSPH_PARSED,
                                        self.assert_particle_sample,
                                        delay=2)


    def test_autosample_on(self):
        """
        @brief Test for turning data on
        """
        self.assert_initialize_driver()
        self.assert_particle_generation(ProtocolEvent.START_AUTOSAMPLE,
                                        DataParticleType.THSPH_PARSED,
                                        self.assert_particle_sample,
                                        delay=2)
        self.assert_async_particle_generation(DataParticleType.THSPH_PARSED,
                                                self.assert_particle_sample,
                                                particle_count=10,
                                                timeout=12)
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)






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
