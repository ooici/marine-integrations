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
from mi.core.instrument.port_agent_client import PortAgentPacket

from mi.core.instrument.chunker import StringChunker

from mi.instrument.noaa.heat.ooicore.driver import InstrumentDriver
from mi.instrument.noaa.heat.ooicore.driver import DataParticleType
from mi.instrument.noaa.heat.ooicore.driver import HEATDataParticleKey
from mi.instrument.noaa.heat.ooicore.driver import InstrumentCommand
from mi.instrument.noaa.heat.ooicore.driver import ProtocolState
from mi.instrument.noaa.heat.ooicore.driver import ProtocolEvent
from mi.instrument.noaa.heat.ooicore.driver import Capability
from mi.instrument.noaa.heat.ooicore.driver import Parameter
from mi.instrument.noaa.heat.ooicore.driver import Protocol
from mi.instrument.noaa.heat.ooicore.driver import Prompt
from mi.instrument.noaa.heat.ooicore.driver import NEWLINE

from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent
from pyon.core.exception import Conflict

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.heat.ooicore.driver',
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

    def assert_heat_on_response(self, response, verify_values=False):
        pass


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

    def _send_port_agent_packet(self, data, ts, driver):
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()

        # Push the response into the driver
        driver._protocol.got_data(port_agent_packet)

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

        # Test capabilities for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
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

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = self.test_connect()

        self.assert_particle_published(driver, VALID_SAMPLE_01, self.assert_particle_sample_01, True)
        self.assert_particle_published(driver, VALID_SAMPLE_02, self.assert_particle_sample_02, True)

    def test_firehose(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        Verify that the BOTPT HEAT driver publishes a particle correctly when the HEAT packet is
        embedded in the stream of other BOTPT sensor output.
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = self.test_connect()
        self.assert_particle_published(driver, BOTPT_FIREHOSE_01, self.assert_particle_sample_01, True)

    def test_heat_on_response(self):
        """
        Verify that the driver correctly parses the HEAT_ON response
        """
        driver = self.test_connect()
        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("HEAT ON command response: %s", HEAT_ON_COMMAND_RESPONSE)
        self._send_port_agent_packet(HEAT_ON_COMMAND_RESPONSE, ts, driver)
        self.assertTrue(driver._protocol._get_response(expected_prompt=TEST_HEAT_ON_DURATION_2))

    def test_heat_on_response_with_data(self):
        """
        Verify that the driver correctly parses the HEAT_ON response with a
        data sample right in front of it
        """
        driver = self.test_connect()
        ts = ntplib.system_to_ntp_time(time.time())

        log.debug("HEAT ON command response: %s", VALID_SAMPLE_01)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(VALID_SAMPLE_01, ts, driver)

        log.debug("HEAT ON command response: %s", HEAT_ON_COMMAND_RESPONSE)
        # Create and populate the port agent packet.
        self._send_port_agent_packet(HEAT_ON_COMMAND_RESPONSE, ts, driver)
        self.assertTrue(driver._protocol._get_response(expected_prompt=TEST_HEAT_ON_DURATION_2))

    def test_heat_on(self):
        driver = self.test_connect()

        def my_send(data):
            log.debug("my_send: %s", data)
            driver._protocol._promptbuf += HEAT_ON_COMMAND_RESPONSE
            return len(HEAT_ON_COMMAND_RESPONSE)

        driver._connection.send.side_effect = my_send

        driver._protocol._handler_command_heat_on()
        ts = ntplib.system_to_ntp_time(time.time())
        driver._protocol._got_chunk(HEAT_ON_COMMAND_RESPONSE, ts)

    def test_heat_off(self):
        driver = self.test_connect()

        def my_send(data):
            log.debug("my_send: %s", data)
            driver._protocol._promptbuf += HEAT_OFF_COMMAND_RESPONSE
            return 5

        driver._connection.send.side_effect = my_send

        driver._protocol._handler_command_heat_off()
        ts = ntplib.system_to_ntp_time(time.time())
        driver._protocol._got_chunk(HEAT_OFF_COMMAND_RESPONSE, ts)

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
        self.assertEquals(sorted(driver_capabilities), sorted(protocol._filter_capabilities(test_capabilities)))


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

    def test_connection(self):
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
        self.assert_get(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_2)

        self.assert_set(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_3)
        self.assert_get(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_3)

    def test_heat_on(self):
        """
        @brief Test for turning heater on
        """
        self.assert_initialize_driver()

        # Set the heat duration to a known value so that we can test for it later
        self.assert_set(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_2)
        self.assert_get(Parameter.HEAT_DURATION, TEST_HEAT_ON_DURATION_2)

        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.HEAT_ON)
        self.assertEqual(response, TEST_HEAT_ON_DURATION_2)

        log.debug("HEAT_ON returned: %r", response)

        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.HEAT_OFF)
        self.assertEqual(response, TEST_HEAT_OFF)

        log.debug("HEAT_OFF returned: %r", response)


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
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_start_autosample()
        self.assert_reset()

    # Overridden because does not apply for this driver
    def test_discover(self):
        pass

    def test_poll(self):
        """
        No polling for a single sample
        """

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()

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
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.HEAT_ON,
                ProtocolEvent.HEAT_OFF,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

    def test_instrument_agent_common_state_model_lifecycle(self, timeout=GO_ACTIVE_TIMEOUT):
        """
        @brief Test agent state transitions.
               This test verifies that the instrument agent can
               properly command the instrument through the following states.

                COMMANDS TESTED
                *ResourceAgentEvent.INITIALIZE
                *ResourceAgentEvent.RESET
                *ResourceAgentEvent.GO_ACTIVE
                *ResourceAgentEvent.RUN
                *ResourceAgentEvent.PAUSE
                *ResourceAgentEvent.RESUME
                *ResourceAgentEvent.GO_COMMAND
                *ResourceAgentEvent.GO_INACTIVE
                *ResourceAgentEvent.PING_RESOURCE
                *ResourceAgentEvent.CLEAR

                COMMANDS NOT TESTED
                * ResourceAgentEvent.GO_DIRECT_ACCESS
                * ResourceAgentEvent.GET_RESOURCE_STATE
                * ResourceAgentEvent.GET_RESOURCE
                * ResourceAgentEvent.SET_RESOURCE
                * ResourceAgentEvent.EXECUTE_RESOURCE

                STATES ACHIEVED:
                * ResourceAgentState.UNINITIALIZED
                * ResourceAgentState.INACTIVE
                * ResourceAgentState.IDLE'
                * ResourceAgentState.STOPPED
                * ResourceAgentState.COMMAND

                STATES NOT ACHIEVED:
                * ResourceAgentState.DIRECT_ACCESS
                * ResourceAgentState.STREAMING
                * ResourceAgentState.TEST
                * ResourceAgentState.CALIBRATE
                * ResourceAgentState.BUSY
                -- Not tested because they may not be implemented in the driver
        """
        ####
        # UNINITIALIZED
        ####
        self.assert_agent_state(ResourceAgentState.UNINITIALIZED)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.RUN, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_ACTIVE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_DIRECT_ACCESS, exception_class=Conflict)

        ####
        # INACTIVE
        ####
        self.assert_agent_command(ResourceAgentEvent.INITIALIZE)
        self.assert_agent_state(ResourceAgentState.INACTIVE)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.RUN, exception_class=Conflict)

        ####
        # IDLE
        ####
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE, timeout=600)

        # Try to run some commands that aren't available in this state
        self.assert_agent_command_exception(ResourceAgentEvent.INITIALIZE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.GO_ACTIVE, exception_class=Conflict)
        self.assert_agent_command_exception(ResourceAgentEvent.RESUME, exception_class=Conflict)

        # Verify we can go inactive
        self.assert_agent_command(ResourceAgentEvent.GO_INACTIVE)
        self.assert_agent_state(ResourceAgentState.INACTIVE)

        # Get back to idle
        self.assert_agent_command(ResourceAgentEvent.GO_ACTIVE, timeout=600)

        # Reset
        self.assert_agent_command(ResourceAgentEvent.RESET)
        self.assert_agent_state(ResourceAgentState.UNINITIALIZED)
