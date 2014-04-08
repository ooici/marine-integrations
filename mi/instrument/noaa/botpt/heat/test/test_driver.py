"""
@package mi.instrument.noaa.heat.ooicore.test.test_driver
@file marine-integrations/mi/instrument/noaa/heat/ooicore/driver.py
@author David Everett
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""
from mi.core.exceptions import SampleException

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import time

import ntplib
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
from mi.idk.unit_test import AgentCapabilityType
from mi.core.common import BaseEnum
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.instrument.chunker import StringChunker
from mi.instrument.noaa.botpt.heat.driver import InstrumentDriver, HEATDataParticle
from mi.instrument.noaa.botpt.heat.driver import DataParticleType
from mi.instrument.noaa.botpt.heat.driver import HEATDataParticleKey
from mi.instrument.noaa.botpt.heat.driver import InstrumentCommand
from mi.instrument.noaa.botpt.heat.driver import ProtocolState
from mi.instrument.noaa.botpt.heat.driver import ProtocolEvent
from mi.instrument.noaa.botpt.heat.driver import Capability
from mi.instrument.noaa.botpt.heat.driver import Parameter
from mi.instrument.noaa.botpt.heat.driver import Protocol
from mi.instrument.noaa.botpt.heat.driver import NEWLINE
from pyon.agent.agent import ResourceAgentState

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.botpt.heat.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='1D644T',
    instrument_agent_name='noaa_heat_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={}
)

GO_ACTIVE_TIMEOUT = 180

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
TEST_HEAT_ON_DURATION_2 = 2  # Heat duration constant for tests
TEST_HEAT_ON_DURATION_3 = 3  # Heat duration constant for tests
TEST_HEAT_OFF = 0  # Heat off

INVALID_SAMPLE = "HEAT,2013/04/19 22:54:11,-001,0001,ERROR0025" + NEWLINE
VALID_SAMPLE_01 = "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE
VALID_SAMPLE_02 = "HEAT,2013/04/19 22:54:11,001,0001,0025" + NEWLINE
HEAT_ON_COMMAND_RESPONSE = "HEAT,2013/04/19 22:54:11,*" + str(TEST_HEAT_ON_DURATION_2) + NEWLINE
HEAT_OFF_COMMAND_RESPONSE = "HEAT,2013/04/19 22:54:11,*" + str(TEST_HEAT_OFF) + NEWLINE
BOTPT_FIREHOSE_01 = "IRIS,2013/05/16 17:03:23, -0.1963, -0.9139,28.23,N8642" + NEWLINE
BOTPT_FIREHOSE_01 += "NANO,P,2013/05/16 17:03:22.000,14.858126,25.243003840" + NEWLINE
BOTPT_FIREHOSE_01 += "LILY,2013/05/16 17:03:22,-202.490,-330.000,149.88, 25.72,11.88,N9656" + NEWLINE
BOTPT_FIREHOSE_01 += "HEAT,2013/04/19 22:54:11,-001,0001,0025" + NEWLINE


###############################################################################
#                           DRIVER TEST MIXIN                                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification                                                               #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.                                      #
###############################################################################
class HEATTestMixinSub(DriverTestMixin):
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.HEAT_DURATION: {TYPE: int, READONLY: False, DA: False, STARTUP: False},
    }

    _sample_parameters_01 = {
        HEATDataParticleKey.TIME: {TYPE: float, VALUE: 3575426051.0, REQUIRED: True},
        HEATDataParticleKey.X_TILT: {TYPE: int, VALUE: -1, REQUIRED: True},
        HEATDataParticleKey.Y_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEATDataParticleKey.TEMP: {TYPE: int, VALUE: 25, REQUIRED: True}
    }

    _sample_parameters_02 = {
        HEATDataParticleKey.TIME: {TYPE: float, VALUE: 3575426051.0, REQUIRED: True},
        HEATDataParticleKey.X_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEATDataParticleKey.Y_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEATDataParticleKey.TEMP: {TYPE: int, VALUE: 25, REQUIRED: True}
    }

    def assert_particle_sample_01(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  HEATDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(HEATDataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.HEAT_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)

    def assert_particle_sample_02(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  HEATDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(HEATDataParticleKey, self._sample_parameters_02)
        self.assert_data_particle_header(data_particle, DataParticleType.HEAT_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_02, verify_values)

    def assert_particle_sample_firehose(self, data_particle, verify_values=False):
        """
        Verify sample particle
        @param data_particle:  HEATDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        """
        self.assert_data_particle_keys(HEATDataParticleKey, self._sample_parameters_01)
        self.assert_data_particle_header(data_particle, DataParticleType.HEAT_PARSED, require_instrument_timestamp=True)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters_01, verify_values)


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
# noinspection PyProtectedMember
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, HEATTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def _send_port_agent_packet(self, driver, data):
        ts = ntplib.system_to_ntp_time(time.time())
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()

        # Push the response into the driver
        driver._protocol.got_data(port_agent_packet)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilities
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilities for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker
        """
        chunker = StringChunker(Protocol.sieve_function)
        self.assert_chunker_sample(chunker, VALID_SAMPLE_01)

    def test_connect(self, initial_protocol_state=ProtocolState.COMMAND):
        """
        Verify driver can transition to the COMMAND state
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state)
        return driver

    def test_data_build_parsed_values(self):
        """
        Verify that the BOTPT IRIS driver build_parsed_values method
        raises SampleException when an invalid sample is encountered
        and that it returns a result when a valid sample is encountered
        """
        items = [
            (INVALID_SAMPLE, False),
            (VALID_SAMPLE_01, True),
            (VALID_SAMPLE_02, True),
        ]

        for raw_data, is_valid in items:
            sample_exception = False
            result = None
            try:
                result = HEATDataParticle(raw_data)._build_parsed_values()
            except SampleException as e:
                log.debug('SampleException caught: %s.', e)
                sample_exception = True
            if is_valid:
                self.assertFalse(sample_exception)
                self.assertIsInstance(result, list)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = self.test_connect()

        self.assert_particle_published(driver, VALID_SAMPLE_01, self.assert_particle_sample_01, True)
        self.assert_particle_published(driver, VALID_SAMPLE_02, self.assert_particle_sample_02, True)
        self.assert_particle_published(driver, BOTPT_FIREHOSE_01, self.assert_particle_sample_01, True)

    def test_command_responses(self):
        """
        Verify that the driver correctly handles the various responses
        """
        driver = self.test_connect()

        items = [
            (HEAT_ON_COMMAND_RESPONSE, ',*2'),
            (HEAT_OFF_COMMAND_RESPONSE, ',*0'),
        ]

        for response, expected_prompt in items:
            log.debug('test_command_response: response: %r expected_prompt: %r', response, expected_prompt)
            self._send_port_agent_packet(driver, response)
            self.assertTrue(driver._protocol._get_response(expected_prompt=expected_prompt))

    def test_handlers(self):
        items = [
            ('_handler_command_heat_on',
             ProtocolState.COMMAND,
             None,
             HEAT_OFF_COMMAND_RESPONSE + NEWLINE + HEAT_ON_COMMAND_RESPONSE,
             ',*2'),
            ('_handler_command_heat_off',
             ProtocolState.COMMAND,
             None,
             HEAT_OFF_COMMAND_RESPONSE,
             ',*0'),
        ]

        for handler, initial_state, expected_state, response, prompt in items:
            def my_send(data):
                log.debug("my_send: data: %r, response: %r", data, response)
                driver._protocol._promptbuf += response
                return len(response)

            driver = self.test_connect(initial_protocol_state=initial_state)
            driver._connection.send.side_effect = my_send
            result = getattr(driver._protocol, handler)()
            log.debug('handler: %r - result: %r expected: %r', handler, result, prompt)
            next_state = result[0]
            if type(result[1]) == str:
                return_value = result[1]
            else:
                return_value = result[1][1]
            self.assertEqual(next_state, expected_state)
            self.assertTrue(return_value.endswith(prompt))

    def test_direct_access(self):
        driver = self.test_connect()
        driver._protocol._handler_direct_access_execute_direct(InstrumentCommand.HEAT_OFF)
        driver._protocol._handler_direct_access_execute_direct('LILY,BAD_COMMAND_HERE')
        self.assertEqual(driver._protocol._sent_cmds, [InstrumentCommand.HEAT_OFF])

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(BaseEnum, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities), sorted(protocol._filter_capabilities(test_capabilities)))


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
# noinspection PyProtectedMember
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, HEATTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_connect(self):
        self.assert_initialize_driver()

    def test_get(self):
        self.assert_initialize_driver()
        self.assert_get(Parameter.HEAT_DURATION)

    def test_set(self):
        """
        Test all set commands. Verify all exception cases.
        """
        self.assert_initialize_driver()

        self.assert_set(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_2)
        self.assert_set(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_3)

    def test_particle(self):
        self.assert_initialize_driver()
        self.assert_async_particle_generation(DataParticleType.HEAT_PARSED, self.assert_particle_sample_01,
                                              particle_count=3, timeout=15)

    def test_heat_on(self):
        """
        @brief Test for turning heater on
        """
        self.assert_initialize_driver()

        # Set the heat duration to a known value so that we can test for it later
        self.assert_set(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_2)

        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.HEAT_ON)
        log.debug("HEAT_ON returned: %r", response)
        self.assertTrue(response[1].endswith(',*2'))

        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.HEAT_OFF)
        log.debug("HEAT_OFF returned: %r", response)
        self.assertTrue(response[1].endswith(',*0'))

    def test_direct_access(self):
        """
        Verify we can enter the direct access state
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_DIRECT)
        self.assert_state_change(ProtocolState.DIRECT_ACCESS, 5)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase, HEATTestMixinSub):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_reset(self):
        """
        Verify the agent can be reset
        Overridden because HEAT has no autosample mode.
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet(inactivity_timeout=60, session_timeout=60)
        self.assert_state_change(ResourceAgentState.DIRECT_ACCESS, ProtocolState.DIRECT_ACCESS, 30)
        self.assert_reset()

    # N/A
    def test_discover(self):
        pass

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()
        self.assert_set_parameter(Parameter.HEAT_DURATION, 1)

    def test_sample_particles(self):
        self.assert_enter_command_mode()
        self.assert_particle_async(DataParticleType.HEAT_PARSED, self.assert_particle_sample_01,
                                   particle_count=3, timeout=15)

    def test_heat_on(self):
        self.assert_enter_command_mode()
        self.assert_execute_resource(Capability.HEAT_ON)
        self.assert_execute_resource(Capability.HEAT_OFF)

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
                ProtocolEvent.GET,
                ProtocolEvent.SET,
                ProtocolEvent.HEAT_ON,
                ProtocolEvent.HEAT_OFF,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports
        direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data(InstrumentCommand.HEAT_OFF + NEWLINE)
        self.tcp_client.expect(',*0')
        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)