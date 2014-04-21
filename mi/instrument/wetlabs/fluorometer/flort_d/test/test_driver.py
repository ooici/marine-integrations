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

import gevent
import time
import copy

from nose.plugins.attrib import attr
from mock import Mock
from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentEvent
from pyon.agent.agent import ResourceAgentState

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from mi.core.time import get_timestamp_delayed

from mi.core.instrument.chunker import StringChunker

import unittest

from mi.instrument.wetlabs.fluorometer.flort_d.driver import InstrumentDriver
from mi.instrument.wetlabs.fluorometer.flort_d.driver import DataParticleType
from mi.instrument.wetlabs.fluorometer.flort_d.driver import InstrumentCommand
from mi.instrument.wetlabs.fluorometer.flort_d.driver import ProtocolState
from mi.instrument.wetlabs.fluorometer.flort_d.driver import ProtocolEvent
from mi.instrument.wetlabs.fluorometer.flort_d.driver import Capability
from mi.instrument.wetlabs.fluorometer.flort_d.driver import Parameter
from mi.instrument.wetlabs.fluorometer.flort_d.driver import Protocol
from mi.instrument.wetlabs.fluorometer.flort_d.driver import Prompt

from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDMET_ParticleKey
from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDMNU_ParticleKey
from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDRUN_ParticleKey
from mi.instrument.wetlabs.fluorometer.flort_d.driver import FlortDSample_ParticleKey
from mi.instrument.wetlabs.fluorometer.flort_d.driver import MNU_REGEX
from mi.instrument.wetlabs.fluorometer.flort_d.driver import MET_REGEX
from mi.instrument.wetlabs.fluorometer.flort_d.driver import RUN_REGEX
from mi.instrument.wetlabs.fluorometer.flort_d.driver import NEWLINE

from mi.core.instrument.instrument_driver import DriverProtocolState

# SAMPLE DATA FOR TESTING
from mi.instrument.wetlabs.fluorometer.flort_d.test.sample_data import SAMPLE_MNU_RESPONSE
from mi.instrument.wetlabs.fluorometer.flort_d.test.sample_data import SAMPLE_RUN_RESPONSE
from mi.instrument.wetlabs.fluorometer.flort_d.test.sample_data import SAMPLE_SAMPLE_RESPONSE
from mi.instrument.wetlabs.fluorometer.flort_d.test.sample_data import SAMPLE_MET_RESPONSE

from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import InstrumentProtocolException

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.wetlabs.fluorometer.flort_d.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='3DLE2A',
    instrument_agent_name='wetlabs_fluorometer_flort_d',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={}
)

#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific in the derived class                                    #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################

###############################################################################
#                           DRIVER TEST MIXIN        		                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification 														      #
#                                                                             #
#  In python, mixin classes are classes designed such that they wouldn't be   #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.									  #
###############################################################################


class DriverTestMixinSub(DriverTestMixin):
    """
    Mixin class used for storing data particle constance and common data assertion methods.
    """
    #Create some short names for the parameter test config
    TYPE        = ParameterTestConfigKey.TYPE
    READONLY    = ParameterTestConfigKey.READONLY
    STARTUP     = ParameterTestConfigKey.STARTUP
    DA          = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE       = ParameterTestConfigKey.VALUE
    REQUIRED    = ParameterTestConfigKey.REQUIRED
    DEFAULT     = ParameterTestConfigKey.DEFAULT
    STATES      = ParameterTestConfigKey.STATES

    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.Serial_number_value: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Firmware_version_value: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Measurements_per_reported_value: {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Measurement_1_dark_count_value: {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Measurement_1_slope_value: {TYPE: float, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Measurement_2_dark_count_value: {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Measurement_2_slope_value: {TYPE: float, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Measurement_3_dark_count_value: {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Measurement_3_slope_value: {TYPE: float, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Measurements_per_packet_value: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: None, VALUE: None},
        Parameter.Packets_per_set_value: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.Predefined_output_sequence_value: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.Baud_rate_value: {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1, VALUE: 1},
        Parameter.Recording_mode_value: {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 1, VALUE: 1},
        Parameter.Date_value: {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: None, VALUE: None},
        Parameter.Time_value: {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: None, VALUE: None},
        Parameter.Sampling_interval_value: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Manual_mode_value: {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0, VALUE: 0},
        Parameter.Manual_start_time_value: {TYPE: str, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Internal_memory_value: {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: None, VALUE: None},
        Parameter.Run_wiper_interval: {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: '00:01:00', VALUE: '00:01:00'},
        Parameter.Run_clock_sync_interval: {TYPE: str, READONLY: False, DA: True, STARTUP: True, DEFAULT: '12:00:00', VALUE: '12:00:00'}
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.RUN_WIPER: {STATES: [ProtocolState.AUTOSAMPLE]}
    }

    _flortD_mnu_parameters = {
        FlortDMNU_ParticleKey.Serial_number: {TYPE: unicode, VALUE: 'BBFL2W-993', REQUIRED: False},
        FlortDMNU_ParticleKey.Firmware_version: {TYPE: unicode, VALUE: 'Triplet5.20', REQUIRED: False},
        FlortDMNU_ParticleKey.Ave: {TYPE: int, VALUE: 1, REQUIRED: False},
        FlortDMNU_ParticleKey.Pkt: {TYPE: int, VALUE: 0, REQUIRED: False},
        FlortDMNU_ParticleKey.M1d: {TYPE: int, VALUE: 0, REQUIRED: False},
        FlortDMNU_ParticleKey.M2d: {TYPE: int, VALUE: 0, REQUIRED: False},
        FlortDMNU_ParticleKey.M3d: {TYPE: int, VALUE: 0, REQUIRED: False},
        FlortDMNU_ParticleKey.M1s: {TYPE: float, VALUE: 1.000E+00, REQUIRED: False},
        FlortDMNU_ParticleKey.M2s: {TYPE: float, VALUE: 1.000E+00, REQUIRED: False},
        FlortDMNU_ParticleKey.M3s: {TYPE: float, VALUE: 1.000E+00, REQUIRED: False},
        FlortDMNU_ParticleKey.Seq: {TYPE: int, VALUE: 0, REQUIRED: False},
        FlortDMNU_ParticleKey.Rat: {TYPE: int, VALUE: 19200, REQUIRED: False},
        FlortDMNU_ParticleKey.Set: {TYPE: int, VALUE: 0, REQUIRED: False},
        FlortDMNU_ParticleKey.Rec: {TYPE: int, VALUE: 1, REQUIRED: False},
        FlortDMNU_ParticleKey.Man: {TYPE: int, VALUE: 0, REQUIRED: False},
        FlortDMNU_ParticleKey.Int: {TYPE: unicode, VALUE: '00:00:10', REQUIRED: False},
        FlortDMNU_ParticleKey.Dat: {TYPE: unicode, VALUE: '07/11/13', REQUIRED: False},
        FlortDMNU_ParticleKey.Clk: {TYPE: unicode, VALUE: '12:48:34', REQUIRED: False},
        FlortDMNU_ParticleKey.Mst: {TYPE: unicode, VALUE: '12:48:31', REQUIRED: False},
        FlortDMNU_ParticleKey.Mem: {TYPE: int, VALUE: 4095, REQUIRED: False}
    }

    _flortD_run_parameters = {
        FlortDRUN_ParticleKey.MVS: {TYPE: int, VALUE: 1, REQUIRED: True}
    }

    _flortD_sample_parameters = {
        FlortDSample_ParticleKey.SAMPLE: {TYPE: unicode, VALUE: '07/16/13\t09:33:06\t700\t4130\t695\t1018\t460\t4130\t525\n', REQUIRED: False}
    }

    _flortD_met_parameters = {
        FlortDMET_ParticleKey.Column_delimiter: {TYPE: unicode, VALUE: '0,Delimiter,pf_tab,TAB', REQUIRED: False},
        FlortDMET_ParticleKey.Column_01_descriptor: {TYPE: unicode, VALUE: '1,DATE,MM/DD/YY,US_DATE', REQUIRED: False},
        FlortDMET_ParticleKey.Column_02_descriptor: {TYPE: unicode, VALUE: '2,TIME,HH:MM:SS,24H_TIME', REQUIRED: False},
        FlortDMET_ParticleKey.Column_03_descriptor: {TYPE: unicode, VALUE: '3,Ref_1,Emission_WL,', REQUIRED: False},
        FlortDMET_ParticleKey.Column_04_descriptor: {TYPE: unicode, VALUE: '4,Sig_1,counts,,SO,1.000E+00,0', REQUIRED: False},
        FlortDMET_ParticleKey.Column_05_descriptor: {TYPE: unicode, VALUE: '5,Ref_2,Emission_WL,', REQUIRED: False},
        FlortDMET_ParticleKey.Column_06_descriptor: {TYPE: unicode, VALUE: '6,Sig_2,counts,,SO,1.000E+00,0', REQUIRED: False},
        FlortDMET_ParticleKey.Column_07_descriptor: {TYPE: unicode, VALUE: '7,Ref_3,Emission_WL,', REQUIRED: False},
        FlortDMET_ParticleKey.Column_08_descriptor: {TYPE: unicode, VALUE: '8,Sig_3,counts,,SO,1.000E+00,0', REQUIRED: False},
        FlortDMET_ParticleKey.Column_09_descriptor: {TYPE: unicode, VALUE: '9,I-Temp,counts,C,EC,', REQUIRED: False},
        FlortDMET_ParticleKey.Column_10_descriptor: {TYPE: unicode, VALUE: '10,Termination,CRLF,Carriage_return-Line_feed', REQUIRED: False},
        FlortDMET_ParticleKey.IHM: {TYPE: int, VALUE: 0, REQUIRED: False},
        FlortDMET_ParticleKey.IOM: {TYPE: int, VALUE: 2, REQUIRED: False}
    }

    # #
    # Driver Parameter Methods
    # #
    def assert_particle_mnu(self, data_particle, verify_values=False):
        """
        Verify flortd_mnu particle
        @param data_particle:  FlortDMNU_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(FlortDMNU_ParticleKey, self._flortD_mnu_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_MNU)
        self.assert_data_particle_parameters(data_particle, self._flortD_mnu_parameters, verify_values)

    def assert_particle_run(self, data_particle, verify_values=False):
        """
        Verify flortd_run particle
        @param data_particle:  FlortDRUN_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(FlortDRUN_ParticleKey, self._flortD_run_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_RUN)
        self.assert_data_particle_parameters(data_particle, self._flortD_run_parameters, verify_values)

    def assert_particle_met(self, data_particle, verify_values=False):
        """
        Verify flortd_met particle
        @param data_particle:  FlortDMET_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(FlortDMET_ParticleKey, self._flortD_met_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_MET)
        self.assert_data_particle_parameters(data_particle, self._flortD_met_parameters, verify_values)

    def assert_particle_sample(self, data_particle, verify_values=False):
        """
        Verify flortd_sample particle
        @param data_particle:  FlortDSample_ParticleKey data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(FlortDSample_ParticleKey, self._flortD_sample_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.FlortD_SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._flortD_sample_parameters, verify_values)

    def assert_param_not_equal(self, param, value):
        """
        Verify the parameter is not equal to the value passed.  Used to determine if a READ ONLY param value
        has changed (it should not).
        """
        getParams = [ param ]
        result = self.instrument_agent_client.get_resource(getParams, timeout=10)
        log.debug("Asserting param: %s does not equal %s", param, value)
        self.assertNotEqual(result[param], value)


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
        do a little extra validation for the capabilities
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_driver_schema(self):
        """
        Get the driver schema and verify it is configured properly
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
        self.assert_particle_published(driver, SAMPLE_RUN_RESPONSE, self.assert_particle_run, True)
        self.assert_particle_published(driver, SAMPLE_SAMPLE_RESPONSE, self.assert_particle_sample, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock(spec="PortAgentClient")
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
            ProtocolState.UNKNOWN:      [ProtocolEvent.DISCOVER,
                                         ProtocolEvent.START_DIRECT],

            ProtocolState.COMMAND:      [ProtocolEvent.GET,
                                         ProtocolEvent.SET,
                                         ProtocolEvent.START_DIRECT,
                                         ProtocolEvent.START_AUTOSAMPLE,
                                         ProtocolEvent.GET_MENU,
                                         ProtocolEvent.GET_METADATA,
                                         ProtocolEvent.RUN_WIPER,
                                         ProtocolEvent.CLOCK_SYNC,
                                         ProtocolEvent.SET_CLOCK_SYNC_INTERVAL,
                                         ProtocolEvent.SET_RUN_WIPER_INTERVAL],

            ProtocolState.AUTOSAMPLE:   [ProtocolEvent.STOP_AUTOSAMPLE,
                                         ProtocolEvent.RUN_WIPER_SCHEDULED,
                                         ProtocolEvent.SCHEDULED_CLOCK_SYNC],

            ProtocolState.DIRECT_ACCESS: [ProtocolEvent.STOP_DIRECT,
                                          ProtocolEvent.EXECUTE_DIRECT]
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    def test_command_response(self):
        """
        Test response with no errors
        Test the general command response will raise an exception if the command is not recognized by
        the instrument
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)

        #test response with no errors
        protocol._parse_command_response(SAMPLE_MNU_RESPONSE, None)

        #test response with 'unrecognized command'
        response = False
        try:
            protocol._parse_command_response('unrecognized command', None)
        except InstrumentCommandException:
            response = True
        finally:
            self.assertTrue(response)

        #test correct response with error
        response = False
        try:
            protocol._parse_command_response(SAMPLE_MET_RESPONSE + NEWLINE + 'unrecognized command', None)
        except InstrumentCommandException:
            response = True
        finally:
            self.assertTrue(response)

    def test_run_wiper_response(self):
        """
        Test response with no errors
        Test the run wiper response will raise an exception:
        1. if the command is not recognized by
        2. the status of the wiper is bad
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)

        #test response with no errors
        protocol._parse_run_wiper_response(SAMPLE_RUN_RESPONSE, None)

        #test response with 'unrecognized command'
        response = False
        try:
            protocol._parse_run_wiper_response('unrecognized command', None)
        except InstrumentCommandException:
            response = True
        finally:
            self.assertTrue(response)

        #test response with error
        response = False
        try:
            protocol._parse_run_wiper_response("mvs 0" + NEWLINE, None)
        except InstrumentCommandException:
            response = True
        finally:
            self.assertTrue(response)

    def test_params(self):
        """
        Verify an exception is thrown when trying to set parameters when not in command mode
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)

        protocol._protocol_fsm.current_state = DriverProtocolState.AUTOSAMPLE
        exception_caught = False
        try:
            protocol._init_params()
        except InstrumentProtocolException as e:
            log.debug('InstrumentProtocolException: %s', e)
            exception_caught = True
        finally:
            self.assertTrue(exception_caught)

    def test_discover_state(self):
        """
        Test discovering the instrument in the COMMAND state and in the AUTOSAMPLE state
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)

        #COMMAND state
        protocol._linebuf = SAMPLE_MNU_RESPONSE
        protocol._promptbuf = SAMPLE_MNU_RESPONSE
        next_state, next_agent_state = protocol._handler_unknown_discover()
        self.assertEqual(next_state, DriverProtocolState.COMMAND)
        self.assertEqual(next_agent_state, ResourceAgentState.IDLE)

        #AUTOSAMPLE state
        protocol._linebuf = SAMPLE_SAMPLE_RESPONSE
        protocol._promptbuf = SAMPLE_SAMPLE_RESPONSE
        next_state, next_agent_state = protocol._handler_unknown_discover()
        self.assertEqual(next_state, DriverProtocolState.AUTOSAMPLE)
        self.assertEqual(next_agent_state, ResourceAgentState.STREAMING)

    def test_create_commands(self):
        """
        Test creating different types of commands
        1. command with no end of line
        2. simple command with no parameters
        3. command with parameter
        """
        #create the operator commands
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)

        #!!!!!
        cmd = protocol._build_no_eol_command('!!!!!')
        self.assertEqual(cmd, '!!!!!')
        #$met
        cmd = protocol._build_simple_command('$met')
        self.assertEqual(cmd, '$met' + NEWLINE)
        #$mnu
        cmd = protocol._build_simple_command('$mnu')
        self.assertEqual(cmd, '$mnu' + NEWLINE)
        #$run
        cmd = protocol._build_simple_command('$run')
        self.assertEqual(cmd, '$run' + NEWLINE)

        #parameters - do a subset
        cmd = protocol._build_single_parameter_command('$ave', Parameter.Measurements_per_reported_value, 14)
        self.assertEqual(cmd, '$ave 14' + NEWLINE)
        cmd = protocol._build_single_parameter_command('$m2d', Parameter.Measurement_2_dark_count_value, 34)
        self.assertEqual(cmd, '$m2d 34' + NEWLINE)
        cmd = protocol._build_single_parameter_command('$m1s', Parameter.Measurement_1_slope_value, 23.1341)
        self.assertEqual(cmd, '$m1s 23.1341' + NEWLINE)
        cmd = protocol._build_single_parameter_command('$int', Parameter.Sampling_interval_value, 3)
        self.assertEqual(cmd, '$int 3' + NEWLINE)
        cmd = protocol._build_single_parameter_command('$ser', Parameter.Serial_number_value, '1.232.1231F')
        self.assertEqual(cmd, '$ser 1.232.1231F' + NEWLINE)
        cmd = protocol._build_single_parameter_command('$dat', Parameter.Date_value, '041014')
        self.assertEqual(cmd, '$dat 041014' + NEWLINE)
        cmd = protocol._build_single_parameter_command('$clk', Parameter.Time_value, '010034')
        self.assertEqual(cmd, '$clk 010034' + NEWLINE)
        cmd = protocol._build_single_parameter_command('$int', Parameter.Sampling_interval_value, '110034')
        self.assertEqual(cmd, '$int 110034' + NEWLINE)
        cmd = protocol._build_single_parameter_command('$mst', Parameter.Manual_start_time_value, '012134')
        self.assertEqual(cmd, '$mst 012134' + NEWLINE)


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_commands(self):
        """
        Run instrument commands from command mode.
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        #test commands, now that we are in command mode
        #$mnu
        self.assert_driver_command(ProtocolEvent.GET_MENU, regex=MNU_REGEX)
        #$met
        self.assert_driver_command(ProtocolEvent.GET_METADATA, regex=MET_REGEX)

        #$run - testing putting instrument into autosample
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        #!!!!! - testing put instrument into command mode
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, regex=MNU_REGEX)
        #$mvs - test running wiper
        self.assert_driver_command(ProtocolEvent.RUN_WIPER, state=ProtocolState.COMMAND, regex=RUN_REGEX)
        #test syncing clock
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC, state=ProtocolState.COMMAND)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)

    def test_autosample(self):
        """
        Verify that we can enter streaming and that all particles are produced
        properly.

        Because we have to test for different data particles we can't use
        the common assert_sample_autosample method

        1. initialize the instrument to COMMAND state
        2. command the instrument to AUTOSAMPLE
        3. verify the particle coming in
        4. command the instrument to STOP AUTOSAMPLE state
        5. verify the particle coming in
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(DataParticleType.FlortD_SAMPLE, self.assert_particle_sample, timeout=10)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)
        self.assert_async_particle_generation(DataParticleType.FlortD_MNU, self.assert_particle_mnu, timeout=10)

    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        3. Can set read/write parameters w/direct access only
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        #test read/write parameter
        self.assert_set(Parameter.Measurements_per_reported_value, 14)

        #test read/write parameter w/direct access only
        self.assert_set(Parameter.Measurements_per_packet_value, 5)

        #test setting intervals for scheduled events
        self.assert_set(Parameter.Run_wiper_interval, '05:00:23')
        self.assert_set(Parameter.Run_clock_sync_interval, '12:12:12')

        #test setting date/time
        self.assert_set(Parameter.Date_value, get_timestamp_delayed("%m/%d/%y"))

        #test read only parameter - should not be set, value should not change
        self.assert_set(Parameter.Serial_number_value, '123.45.678', no_get=True)
        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.Serial_number_value])
        return_value = reply.get(Parameter.Serial_number_value)
        self.assertNotEqual(return_value, '123.45.678')


    def test_direct_access(self):
        """
        Verify we can enter the direct access state
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_DIRECT)
        self.assert_state_change(ProtocolState.DIRECT_ACCESS, 5)

    def test_run_wiper(self):
        """
        Test setting the wiper interval to 10 seconds and 0 seconds
        At 10 seconds, should see the instrument pulled from autosample to command mode, then back to autosample mode
        performing $mvs during command mode
        At 0 seconds, the instrument should stay in autosample mode
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        #set the wiper interval to 10 seconds
        #put the instrument back into autosample, log will contain scheduled run wiper commands
        self.assert_set(Parameter.Run_wiper_interval, '00:00:10')
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=30)

        #set the wiper interval to 0 seconds
        #put the instrument back into autosample, log should not contain scheduled run wiper commands
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)
        self.assert_set(Parameter.Run_wiper_interval, '00:00:00')
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=10)

    def test_sync_clock(self):
        """
        Test setting the clock sync to 10 seconds and 0 seconds
        At 10 seconds, should see the instrument pulled from autosample to command mode, then back to autosample mode
        performing $clk and $dat during command mode
        At 0 seconds, the instrument should stay in autosample mode
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        self.assert_set(Parameter.Run_clock_sync_interval, '00:00:10')
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=30)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)
        self.assert_set(Parameter.Run_clock_sync_interval, '00:00:00')
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=10)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_mode(self):
        """
        Verify while in Direct Access, we can manually set DA parameters.  After stopping DA, the instrument
        will enter Command State and any parameters set during DA are reset to previous values.  Also verifying
        timeouts with inactivity, with activity, and without activity.
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        log.debug("DA Server Started.  Adjust DA Parameter.")
        self.tcp_client.send_data("$pkt 128" + NEWLINE)
        self.tcp_client.expect("Pkt 128")
        log.debug("DA Parameter Measurements_per_packet_value Updated")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)
        self.assert_get_parameter(Parameter.Measurements_per_packet_value, 0)

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
        Verify Direct Access can start autosampling for the instrument, and if stopping DA, the
        driver will resort to Autosample State. Also, testing disconnect
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        log.debug("DA Server Started.  Adjust DA Parameter.")
        self.tcp_client.send_data("$run" + NEWLINE)
        self.tcp_client.expect("mvs 1")
        log.debug("DA autosample started")

        #Assert if stopping DA while autosampling, discover will put driver into Autosample state
        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.STREAMING, ProtocolState.AUTOSAMPLE, timeout=10)

        ###
        # Test direct access disconnect
        ###
        self.assert_direct_access_start_telnet()
        self.tcp_client.disconnect()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 30)

    def test_autosample(self):
        """
        start and stop autosample
        """

        self.assert_enter_command_mode()

        time.sleep(30)

        self.assert_start_autosample()
        self.assert_stop_autosample()

    def test_get_set_parameters(self):
        """
        Verify that all parameters can be get/set properly.  This includes ensuring that
        read only parameters cannot be set.
        """

        self.assert_enter_command_mode()

        log.debug("Start watching the sniffer")
        time.sleep(30)
        # NOTE:  assert_set_parameter also verifies that on 'get' the value returned is equal to the 'set' value

        self.assert_set_parameter(Parameter.Serial_number_value, '123.45.678', verify=False)
        self.assert_param_not_equal(Parameter.Serial_number_value, '123.45.678')

        self.assert_set_parameter(Parameter.Firmware_version_value, 'FW123', verify=False)
        self.assert_param_not_equal(Parameter.Firmware_version_value, 'FW123')

        self.assert_set_parameter(Parameter.Measurements_per_reported_value, 128)

        self.assert_set_parameter(Parameter.Measurements_per_packet_value, 16)

        self.assert_set_parameter(Parameter.Measurement_1_dark_count_value, 10, verify=False)
        self.assert_param_not_equal(Parameter.Measurement_1_dark_count_value, 10)

        self.assert_set_parameter(Parameter.Measurement_2_dark_count_value, 20, verify=False)
        self.assert_param_not_equal(Parameter.Measurement_2_dark_count_value, 20)

        self.assert_set_parameter(Parameter.Measurement_3_dark_count_value, 30, verify=False)
        self.assert_param_not_equal(Parameter.Measurement_3_dark_count_value, 30)

        self.assert_set_parameter(Parameter.Measurement_1_slope_value, 12.00, verify=False)
        self.assert_param_not_equal(Parameter.Measurement_1_slope_value, 12.00)

        self.assert_set_parameter(Parameter.Measurement_2_slope_value, 13.00, verify=False)
        self.assert_param_not_equal(Parameter.Measurement_2_slope_value, 13.00)

        self.assert_set_parameter(Parameter.Measurement_3_slope_value, 14.00, verify=False)
        self.assert_param_not_equal(Parameter.Measurement_3_slope_value, 14.00)

        self.assert_set_parameter(Parameter.Predefined_output_sequence_value, 3)

        self.assert_set_parameter(Parameter.Baud_rate_value, 2422, verify=False)
        self.assert_param_not_equal(Parameter.Baud_rate_value, 2422)

        self.assert_set_parameter(Parameter.Packets_per_set_value, 10)

        self.assert_set_parameter(Parameter.Recording_mode_value, 0)

        self.assert_set_parameter(Parameter.Manual_mode_value, 1)

        self.assert_set_parameter(Parameter.Sampling_interval_value, "003000", verify=False)
        self.assert_param_not_equal(Parameter.Sampling_interval_value, "003000")

        self.assert_set_parameter(Parameter.Date_value, get_timestamp_delayed("%m/%d/%y"))

        self.assert_set_parameter(Parameter.Manual_start_time_value, "15:10:45", verify=False)
        self.assert_param_not_equal(Parameter.Manual_start_time_value, "15:10:45")

        self.assert_set_parameter(Parameter.Internal_memory_value, 512, verify=False)
        self.assert_param_not_equal(Parameter.Internal_memory_value, 512)

        self.assert_set_parameter(Parameter.Run_wiper_interval, "12:23:00")

        self.assert_set_parameter(Parameter.Run_clock_sync_interval, "23:00:02")

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """

        # ##################
        # #  Command Mode
        # ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [ProtocolEvent.CLOCK_SYNC,
                                                   ProtocolEvent.RUN_WIPER,
                                                   ProtocolEvent.SET_CLOCK_SYNC_INTERVAL,
                                                   ProtocolEvent.SET_RUN_WIPER_INTERVAL],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_enter_command_mode()
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################
        capabilities = {}
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = ['ave', 'clk', 'clk_interval', 'dat', 'int', 'm1d',
                                                                'm1s', 'm2d', 'm2s', 'm3d', 'm3s', 'man', 'mem', 'mst',
                                                                'mvs_interval', 'pkt', 'rat', 'rec', 'seq', 'ser',
                                                                'set', 'ver']

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)
