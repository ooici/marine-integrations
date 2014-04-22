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

from nose.plugins.attrib import attr

from mi.core.log import get_logger

log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType
from mi.core.instrument.instrument_driver import DriverParameter, DriverConfigKey
from mi.instrument.noaa.botpt.heat.driver import InstrumentDriver
from mi.instrument.noaa.botpt.heat.driver import HEATDataParticle
from mi.instrument.noaa.botpt.heat.driver import DataParticleType
from mi.instrument.noaa.botpt.heat.driver import HEATDataParticleKey
from mi.instrument.noaa.botpt.heat.driver import InstrumentCommand
from mi.instrument.noaa.botpt.heat.driver import ProtocolState
from mi.instrument.noaa.botpt.heat.driver import ProtocolEvent
from mi.instrument.noaa.botpt.heat.driver import Capability
from mi.instrument.noaa.botpt.heat.driver import Parameter
from mi.instrument.noaa.botpt.heat.driver import Protocol
from mi.instrument.noaa.botpt.heat.driver import NEWLINE
from mi.instrument.noaa.botpt.test.test_driver import BotptDriverUnitTest
from pyon.agent.agent import ResourceAgentState


###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.botpt.heat.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id='1D644T',
    instrument_agent_name='noaa_botpt_heat',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={DriverConfigKey.PARAMETERS: {Parameter.HEAT_DURATION: 2}}
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

HEAT_ON = ',*2'
HEAT_OFF = ',*0'


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
    _Driver = InstrumentDriver
    _DataParticleType = DataParticleType
    _ProtocolState = ProtocolState
    _ProtocolEvent = ProtocolEvent
    _DriverParameter = DriverParameter
    _InstrumentCommand = InstrumentCommand
    _Capability = Capability
    _Protocol = Protocol

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

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.HEAT_ON: {STATES: [ProtocolState.COMMAND]},
        Capability.HEAT_OFF: {STATES: [ProtocolState.COMMAND]},
    }

    _capabilities = {
        ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                'DRIVER_EVENT_SET',
                                'DRIVER_EVENT_INIT_PARAMS',
                                'EXPORTED_INSTRUMENT_CMD_HEAT_OFF',
                                'EXPORTED_INSTRUMENT_CMD_HEAT_ON',
                                'DRIVER_EVENT_START_DIRECT'],
        ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT',
                                      'EXECUTE_DIRECT']
    }

    _sample_parameters_01 = {
        HEATDataParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'HEAT', REQUIRED: True},
        HEATDataParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/04/19 22:54:11', REQUIRED: True},
        HEATDataParticleKey.X_TILT: {TYPE: int, VALUE: -1, REQUIRED: True},
        HEATDataParticleKey.Y_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEATDataParticleKey.TEMP: {TYPE: int, VALUE: 25, REQUIRED: True}
    }

    _sample_parameters_02 = {
        HEATDataParticleKey.SENSOR_ID: {TYPE: unicode, VALUE: u'HEAT', REQUIRED: True},
        HEATDataParticleKey.TIME: {TYPE: unicode, VALUE: u'2013/04/19 22:54:11', REQUIRED: True},
        HEATDataParticleKey.X_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEATDataParticleKey.Y_TILT: {TYPE: int, VALUE: 1, REQUIRED: True},
        HEATDataParticleKey.TEMP: {TYPE: int, VALUE: 25, REQUIRED: True}
    }

    _sample_chunks = [VALID_SAMPLE_01]

    _build_parsed_values_items = [
        (INVALID_SAMPLE, HEATDataParticle, False),
        (VALID_SAMPLE_01, HEATDataParticle, False),
        (VALID_SAMPLE_02, HEATDataParticle, False),
    ]

    _command_response_items = [
        (HEAT_ON_COMMAND_RESPONSE, HEAT_ON),
        (HEAT_OFF_COMMAND_RESPONSE, HEAT_OFF),
    ]

    _test_handlers_items = [
        ('_handler_command_heat_on', ProtocolState.COMMAND, None, HEAT_ON),
        ('_handler_command_heat_off', ProtocolState.COMMAND, None, HEAT_OFF),
    ]

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
class DriverUnitTest(BotptDriverUnitTest, HEATTestMixinSub):
    @staticmethod
    def my_send(driver):
        responses = {
            InstrumentCommand.HEAT_ON: HEAT_ON_COMMAND_RESPONSE,
            InstrumentCommand.HEAT_OFF: HEAT_OFF_COMMAND_RESPONSE,
        }

        def inner(data):
            my_response = None
            for key in responses:
                if data.startswith(key):
                    my_response = responses[key]
            if my_response is not None:
                log.debug("my_send: data: %s, my_response: %s", data, my_response)
                driver._protocol._promptbuf += my_response
                return len(my_response)

        return inner

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = self.test_connect()

        self.assert_particle_published(driver, VALID_SAMPLE_01, self.assert_particle_sample_01, True)
        self.assert_particle_published(driver, VALID_SAMPLE_02, self.assert_particle_sample_02, True)
        self.assert_particle_published(driver, BOTPT_FIREHOSE_01, self.assert_particle_sample_01, True)


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
        self.assert_get(Parameter.HEAT_DURATION,
                        self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS][Parameter.HEAT_DURATION])

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

    # N/A, this instrument always samples automatically
    # so it has no autosample state.
    def test_discover(self):
        pass

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()
        self.assert_get_parameter(Parameter.HEAT_DURATION,
                                  self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
                                  [Parameter.HEAT_DURATION])
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

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports
        direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data(InstrumentCommand.HEAT_OFF + NEWLINE)
        result = self.tcp_client.expect(',*0')
        self.assertTrue(result, msg='Failed to receive expected response in direct access mode.')
        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 10)