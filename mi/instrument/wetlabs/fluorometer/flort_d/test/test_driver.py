"""
@package mi.instrument.wetlabs.fluorometer.flort_d.test.test_driver
@file marine-integrations/mi/instrument/wetlabs/fluorometer/flort_d/driver.py
@author Art Teranishi
@brief Test cases for flort_d driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Art Teranishi'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin

from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.wetlabs.fluorometer.flort_d.driver import InstrumentDriver
from mi.instrument.wetlabs.fluorometer.flort_d.driver import DataParticleType
from mi.instrument.wetlabs.fluorometer.flort_d.driver import InstrumentCommand
from mi.instrument.wetlabs.fluorometer.flort_d.driver import ProtocolState
from mi.instrument.wetlabs.fluorometer.flort_d.driver import ProtocolEvent
from mi.instrument.wetlabs.fluorometer.flort_d.driver import Capability
from mi.instrument.wetlabs.fluorometer.flort_d.driver import Parameter
from mi.instrument.wetlabs.fluorometer.flort_d.driver import Protocol
from mi.instrument.wetlabs.fluorometer.flort_d.driver import Prompt
from mi.instrument.wetlabs.fluorometer.flort_d.driver import NEWLINE

from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDMET_ParticleKey
from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDMNU_ParticleKey
from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDRUN_ParticleKey
from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDSample_ParticleKey
from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDDUMP_MEMORY_ParticleKey

# SAMPLE DATA FOR TESTING
from mi.instrument.wetlabs.fluorometer.flort_d.test.sample_data import *

from pyon.agent.agent import ResourceAgentEvent
from pyon.agent.agent import ResourceAgentState

from mi.core.exceptions import InstrumentCommandException

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.wetlabs.fluorometer.flort_d.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = '3DLE2A',
    instrument_agent_name = 'wetlabs_fluorometer_flort_d',
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
class DriverTestMixinSub(DriverTestMixin):
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
    STATES    = ParameterTestConfigKey.STATES

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.Serial_number_value : {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1, VALUE: 1},
        Parameter.Firmware_version_value : {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: 0, VALUE: 0},
        Parameter.Measurements_per_reported_value : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.Measurement_1_dark_count_value : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.Measurement_1_slope_value : {TYPE: float, READONLY: True, DA: False, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.Measurement_2_dark_count_value : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.Measurement_2_slope_value : {TYPE: float, READONLY: True, DA: False, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.Measurement_3_dark_count_value : {TYPE: int, READONLY: True, DA: False, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.Measurement_3_slope_value : {TYPE: float, READONLY: True, DA: False, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.Measurements_per_packet_value : {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.Packets_per_set_value : {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.Predefined_output_sequence_value : {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.Baud_rate_value : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1, VALUE: 1},
        Parameter.Recording_mode_value : {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.Date_value : {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: None, VALUE: None},
        Parameter.Time_value : {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: None, VALUE: None},
        Parameter.Sampling_interval_value : {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Manual_mode_value : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 0, VALUE: 0},
        Parameter.Manual_start_time_value : {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Internal_memory_value : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        }

    _driver_capabilities = {
        # capabilities defined in the IOS
        #Capability.INTERRUPT_INSTRUMENT: {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.START_AUTOSAMPLE: {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_AUTOSAMPLE: {STATES: [ProtocolState.AUTOSAMPLE]},
        Capability.GET_METADATA: {STATES: [ProtocolState.COMMAND]},
        Capability.GET_MENU: {STATES: [ProtocolState.COMMAND]},
    }

    _flortD_mnu_parameters = {
        FlortDMNU_ParticleKey.Serial_number: {TYPE: unicode, VALUE: 'BBFL2W-993', REQUIRED: True },
        FlortDMNU_ParticleKey.Firmware_version: {TYPE: unicode, VALUE: 'Triplet5.20', REQUIRED: True },
        FlortDMNU_ParticleKey.Ave: {TYPE: int, VALUE: 1, REQUIRED: True },
        FlortDMNU_ParticleKey.Pkt: {TYPE: int, VALUE: 0, REQUIRED: True },
        FlortDMNU_ParticleKey.M1d: {TYPE: int, VALUE: 0, REQUIRED: True },
        FlortDMNU_ParticleKey.M2d: {TYPE: int, VALUE: 0, REQUIRED: True },
        FlortDMNU_ParticleKey.M3d: {TYPE: int, VALUE: 0, REQUIRED: True },
        FlortDMNU_ParticleKey.M1s: {TYPE: float, VALUE: 1.000E+00, REQUIRED: True },
        FlortDMNU_ParticleKey.M2s: {TYPE: float, VALUE: 1.000E+00, REQUIRED: True },
        FlortDMNU_ParticleKey.M3s: {TYPE: float, VALUE: 1.000E+00, REQUIRED: True },
        FlortDMNU_ParticleKey.Seq: {TYPE: int, VALUE: 0, REQUIRED: True },
        FlortDMNU_ParticleKey.Rat: {TYPE: int, VALUE: 19200, REQUIRED: True },
        FlortDMNU_ParticleKey.Set: {TYPE: int, VALUE: 0, REQUIRED: True },
        FlortDMNU_ParticleKey.Rec: {TYPE: int, VALUE: 1, REQUIRED: True },
        FlortDMNU_ParticleKey.Man: {TYPE: int, VALUE: 0, REQUIRED: True },
        FlortDMNU_ParticleKey.Int: {TYPE: unicode, VALUE: '00:00:10', REQUIRED: True },
        FlortDMNU_ParticleKey.Dat: {TYPE: unicode, VALUE: '07/11/13', REQUIRED: True },
        FlortDMNU_ParticleKey.Clk: {TYPE: unicode, VALUE: '12:48:34', REQUIRED: True },
        FlortDMNU_ParticleKey.Mst: {TYPE: unicode, VALUE: '12:48:31', REQUIRED: True },
        FlortDMNU_ParticleKey.Mem: {TYPE: int, VALUE: 4095, REQUIRED: True }
    }

    _flortD_run_parameters = {
        FlortDRUN_ParticleKey.MVS: {TYPE: int, VALUE: 1, REQUIRED: True }
    }

    _flortD_sample_parameters = {
        FlortDSample_ParticleKey.SAMPLE: {TYPE: unicode, VALUE: '07/16/13\t09:33:06\t700\t4130\t695\t1018\t460\t4130\t525', REQUIRED: True }
    }

    _flortD_dump_memory_parameters = {
        FlortDDUMP_MEMORY_ParticleKey.Get_response: {TYPE: int, VALUE: 77222, REQUIRED: True }
    }

    _flortD_met_parameters = {
        FlortDMET_ParticleKey.Column_delimiter: {TYPE: unicode, VALUE: '0,Delimiter,pf_tab,TAB', REQUIRED: True },
        FlortDMET_ParticleKey.Column_01_descriptor: {TYPE: unicode, VALUE: '1,DATE,MM/DD/YY,US_DATE', REQUIRED: True },
        FlortDMET_ParticleKey.Column_02_descriptor: {TYPE: unicode, VALUE: '2,TIME,HH:MM:SS,24H_TIME', REQUIRED: True },
        FlortDMET_ParticleKey.Column_03_descriptor: {TYPE: unicode, VALUE: '3,Ref_1,Emission_WL,', REQUIRED: True },
        FlortDMET_ParticleKey.Column_04_descriptor: {TYPE: unicode, VALUE: '4,Sig_1,counts,,SO,1.000E+00,0', REQUIRED: True },
        FlortDMET_ParticleKey.Column_05_descriptor: {TYPE: unicode, VALUE: '5,Ref_2,Emission_WL,', REQUIRED: True },
        FlortDMET_ParticleKey.Column_06_descriptor: {TYPE: unicode, VALUE: '6,Sig_2,counts,,SO,1.000E+00,0', REQUIRED: True },
        FlortDMET_ParticleKey.Column_07_descriptor: {TYPE: unicode, VALUE: '7,Ref_3,Emission_WL,', REQUIRED: True },
        FlortDMET_ParticleKey.Column_08_descriptor: {TYPE: unicode, VALUE: '8,Sig_3,counts,,SO,1.000E+00,0', REQUIRED: True },
        FlortDMET_ParticleKey.Column_09_descriptor: {TYPE: unicode, VALUE: '9,I-Temp,counts,C,EC,', REQUIRED: True },
        FlortDMET_ParticleKey.Column_10_descriptor: {TYPE: unicode, VALUE: '10,Termination,CRLF,Carriage_return-Line_feed', REQUIRED: True },
        FlortDMET_ParticleKey.IHM: {TYPE: int, VALUE: 0, REQUIRED: True },
        FlortDMET_ParticleKey.IOM: {TYPE: int, VALUE: 2, REQUIRED: True }
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

    def assert_particle_mnu(self, data_particle, verify_values = False):
        '''
        Verify flortd_mnu particle
        @param data_particle:  FlortDMNU_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(FlortDMNU_ParticleKey, self._flortD_mnu_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_MNU)
        self.assert_data_particle_parameters(data_particle, self._flortD_mnu_parameters, verify_values)

    def assert_particle_run(self, data_particle, verify_values = False):
        '''
        Verify flortd_run particle
        @param data_particle:  FlortDRUN_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(FlortDRUN_ParticleKey, self._flortD_run_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_RUN)
        self.assert_data_particle_parameters(data_particle, self._flortD_run_parameters, verify_values)

    def assert_particle_met(self, data_particle, verify_values = False):
        '''
        Verify flortd_met particle
        @param data_particle:  FlortDMET_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(FlortDMET_ParticleKey, self._flortD_met_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_MET)
        self.assert_data_particle_parameters(data_particle, self._flortD_met_parameters, verify_values)

    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify flortd_sample particle
        @param data_particle:  FlortDSample_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(FlortDSample_ParticleKey, self._flortD_sample_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._flortD_sample_parameters, verify_values)

    def assert_particle_dump_memory(self, data_particle, verify_values = False):
        '''
        Verify flortd_sample particle
        @param data_particle:  FlortDDUMP_MEMORY_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(FlortDDUMP_MEMORY_ParticleKey, self._flortD_dump_memory_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_DUMP_MEMORY)
        self.assert_data_particle_parameters(data_particle, self._flortD_dump_memory_parameters, verify_values)

    def assertSampleDataParticle(self, data_particle):
        '''
        Verify a particle is a know particle to this driver and verify the particle is
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
class DriverUnitTest(InstrumentDriverUnitTestCase, DriverTestMixinSub):
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
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, SAMPLE_MNU_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_MNU_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_MNU_RESPONSE, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_MNU_RESPONSE)

        self.assert_chunker_sample(chunker, SAMPLE_RUN_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_RUN_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_RUN_RESPONSE, 1)
        self.assert_chunker_combined_sample(chunker, SAMPLE_RUN_RESPONSE)

        self.assert_chunker_sample(chunker, SAMPLE_MET_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_MET_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_MET_RESPONSE, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_MET_RESPONSE)

        self.assert_chunker_sample(chunker, SAMPLE_SAMPLE_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_SAMPLE_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_SAMPLE_RESPONSE, 32)
        self.assert_chunker_combined_sample(chunker, SAMPLE_SAMPLE_RESPONSE)

        self.assert_chunker_sample(chunker, SAMPLE_DUMP_MEMORY_RESPONSE)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_DUMP_MEMORY_RESPONSE)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_DUMP_MEMORY_RESPONSE, 2)
        self.assert_chunker_combined_sample(chunker, SAMPLE_DUMP_MEMORY_RESPONSE)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, SAMPLE_MNU_RESPONSE, self.assert_particle_mnu, True)
        self.assert_particle_published(driver, SAMPLE_MET_RESPONSE, self.assert_particle_met, True)
        self.assert_particle_published(driver, SAMPLE_DUMP_MEMORY_RESPONSE, self.assert_particle_dump_memory, True)
        self.assert_particle_published(driver, SAMPLE_RUN_RESPONSE, self.assert_particle_run, True)
        self.assert_particle_published(driver, SAMPLE_SAMPLE_RESPONSE, self.assert_particle_sample, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
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
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER', 'DRIVER_EVENT_START_DIRECT'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'PROTOCOL_EVENT_GET_MENU',
                                    'PROTOCOL_EVENT_GET_METADATA',
                                    'PROTOCOL_EVENT_INTERRUPT_INSTRUMENT'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE',
                                       'PROTOCOL_EVENT_INTERRUPT_INSTRUMENT'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_commands(self):
        """
        Run instrument commands from command mode.
        """
        self.assert_initialize_driver()

        ####
        # First test in command mode
        ####
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_driver_command(ProtocolEvent.GET_MENU, regex=r'Ser')
        self.assert_driver_command(ProtocolEvent.GET_METADATA, regex=r'0,')

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_autosample(self):
        """
        Verify that we can enter streaming and that all particles are produced
        properly.

        Because we have to test for three different data particles we can't use
        the common assert_sample_autosample method
        """
        self.assert_initialize_driver()

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(DataParticleType.FlortD_RUN, self.assert_particle_run, timeout=120)
        self.assert_async_particle_generation(DataParticleType.FlortD_SAMPLE, self.assert_particle_sample, timeout=120)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    def test_discover(self):
        """
        Verify we can discover from both command and auto sample modes
        """
        self.assert_initialize_driver()
        self.assert_cycle()
        self.assert_cycle()


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

        log.debug("DA Server Started.  Adjust DA Parameter.")
        self.tcp_client.send_data("$pkt 128\n")
        self.tcp_client.expect("Pkt 128")
        log.debug("DA Parameter Measurements_per_packet_value Updated")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)
        self.assert_get_parameter(Parameter.Measurements_per_packet_value, 10)

        ###
        # Test direct access inactivity timeout
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=90)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        ###
        # Test session timeout without activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=120, session_timeout=30)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        ###
        # Test direct access session timeout with activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=60)
        # Send some activity every 30 seconds to keep DA alive.
        for i in range(1, 2, 3):
            self.tcp_client.send_data(NEWLINE)
            log.debug("Sending a little keep alive communication, sleeping for 15 seconds")
            gevent.sleep(15)

        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 45)

        ###
        # Test direct access disconnect
        ###
        self.assert_direct_access_start_telnet()
        self.tcp_client.disconnect()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 30)

    def test_direct_access_telnet_mode_autosample(self):
        """
        @brief This test manually tests that the Instrument Driver properly
        supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        ###
        #   Add instrument specific code here.
        ###

        log.debug("DA Server Started.  Adjust DA Parameter.")
        self.tcp_client.send_data("$run\n")
        #self.tcp_client.expect("Pkt 128")
        log.debug("DA autosample started")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)
        #self.assert_get_parameter(Parameter.Measurements_per_packet_value, 10)

        ###
        # Test direct access inactivity timeout
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=90)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        ###
        # Test session timeout without activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=120, session_timeout=30)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)

        ###
        # Test direct access session timeout with activity
        ###
        self.assert_direct_access_start_telnet(inactivity_timeout=30, session_timeout=60)
        # Send some activity every 30 seconds to keep DA alive.
        for i in range(1, 2, 3):
            self.tcp_client.send_data(NEWLINE)
            log.debug("Sending a little keep alive communication, sleeping for 15 seconds")
            gevent.sleep(15)

        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 45)

        ###
        # Test direct access disconnect
        ###
        self.assert_direct_access_start_telnet()
        self.tcp_client.disconnect()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 30)

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        self.assert_enter_command_mode()

        log.debug("Start watching the sniffer")
        time.sleep(30)

        self.assert_start_autosample()
        self.assert_stop_autosample()


    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        '''
        self.assert_enter_command_mode()

        log.debug("getting ready to set some parameters!  Start watching the sniffer")
        time.sleep(30)

        self.assert_set_parameter(Parameter.Measurements_per_reported_value, 128)
        self.assert_get_parameter(Parameter.Measurements_per_reported_value, 128)

        self.assert_set_parameter(Parameter.Measurements_per_packet_value, 16)
        self.assert_get_parameter(Parameter.Measurements_per_packet_value, 16)

        self.assert_set_parameter(Parameter.Measurement_1_dark_count_value, 1)
        self.assert_get_parameter(Parameter.Measurement_1_dark_count_value, 1)

        self.assert_set_parameter(Parameter.Measurement_2_dark_count_value, 2)
        self.assert_get_parameter(Parameter.Measurement_2_dark_count_value, 2)

        self.assert_set_parameter(Parameter.Measurement_3_dark_count_value, 3)
        self.assert_get_parameter(Parameter.Measurement_3_dark_count_value, 3)

        self.assert_set_parameter(Parameter.Measurement_1_slope_value, 1.000E+01)
        self.assert_get_parameter(Parameter.Measurement_1_slope_value, 1.000E+01)

        self.assert_set_parameter(Parameter.Measurement_2_slope_value, 1.000E+02)
        self.assert_get_parameter(Parameter.Measurement_2_slope_value, 1.000E+02)

        self.assert_set_parameter(Parameter.Measurement_3_slope_value, 1.000E+03)
        self.assert_get_parameter(Parameter.Measurement_3_slope_value, 1.000E+03)

        self.assert_set_parameter(Parameter.Predefined_output_sequence_value, 3)
        self.assert_get_parameter(Parameter.Predefined_output_sequence_value, 3)

        self.assert_set_parameter(Parameter.Baud_rate_value, 3)
        self.assert_get_parameter(Parameter.Baud_rate_value, 3)

        self.assert_set_parameter(Parameter.Packets_per_set_value, 10)
        self.assert_get_parameter(Parameter.Packets_per_set_value, 10)

        self.assert_set_parameter(Parameter.Recording_mode_value, 0)
        self.assert_get_parameter(Parameter.Recording_mode_value, 0)

        self.assert_set_parameter(Parameter.Manual_mode_value, 1)
        self.assert_get_parameter(Parameter.Manual_mode_value, 1)

        self.assert_set_parameter(Parameter.Sampling_interval_value, "00:01:00")
        self.assert_get_parameter(Parameter.Sampling_interval_value, "00:01:00")

        self.assert_set_parameter(Parameter.Date_value, "01/01/10")
        self.assert_get_parameter(Parameter.Date_value, "01/01/10")

        self.assert_set_parameter(Parameter.Time_value, "10:10:30")
        self.assert_get_parameter(Parameter.Time_value, "10:10:30")

        self.assert_set_parameter(Parameter.Manual_start_time_value, "15:10:45")
        self.assert_get_parameter(Parameter.Manual_start_time_value, "15:10:45")

        self.assert_set_parameter(Parameter.Internal_memory_value, 512)
        self.assert_get_parameter(Parameter.Internal_memory_value, 512)

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
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
                ProtocolEvent.GET_MENU,
                ProtocolEvent.GET_METADATA,
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
        ]

        self.assert_start_autosample()
        self.assert_capabilities(st_capabilities)
        self.assert_stop_autosample()

        ##################
        #  Command Mode
        ##################

        # We should be back in command mode from DA.
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 60)
        self.assert_capabilities(capabilities)

        #######################
        #  Streaming Recovery
        #######################

        # Command mode times out after 120 seconds.  This test will verify the agent states are correct
        self.assert_set_parameter(Parameter.SAMPLE_PERIOD, 1)
        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, 200)
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
