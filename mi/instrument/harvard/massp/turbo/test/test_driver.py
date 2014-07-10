"""
@package mi.instrument.harvard.massp.turbo.test.test_driver
@file marine-integrations/mi/instrument/harvard/massp/turbo/driver.py
@author Peter Cable
@brief Test cases for turbo driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

from nose.plugins.attrib import attr
from mock import Mock
import time
import ntplib

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentCommandException
from mi.core.instrument.data_particle import RawDataParticle
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.log import get_logger
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.core.instrument.chunker import StringChunker
from mi.instrument.harvard.massp.turbo.driver import InstrumentDriver, CURRENT_STABILIZE_RETRIES
from mi.instrument.harvard.massp.turbo.driver import TRUE
from mi.instrument.harvard.massp.turbo.driver import FALSE
from mi.instrument.harvard.massp.turbo.driver import TurboStatusParticleKey
from mi.instrument.harvard.massp.turbo.driver import QUERY
from mi.instrument.harvard.massp.turbo.driver import CommandType
from mi.instrument.harvard.massp.turbo.driver import ADDRESS
from mi.instrument.harvard.massp.turbo.driver import ParameterConstraints
from mi.instrument.harvard.massp.turbo.driver import DataParticleType
from mi.instrument.harvard.massp.turbo.driver import InstrumentCommand
from mi.instrument.harvard.massp.turbo.driver import ProtocolState
from mi.instrument.harvard.massp.turbo.driver import ProtocolEvent
from mi.instrument.harvard.massp.turbo.driver import Capability
from mi.instrument.harvard.massp.turbo.driver import Parameter
from mi.instrument.harvard.massp.turbo.driver import Protocol
from mi.instrument.harvard.massp.turbo.driver import Prompt
from mi.instrument.harvard.massp.turbo.driver import NEWLINE

__author__ = 'Peter Cable'
__license__ = 'Apache 2.0'

log = get_logger()

turbo_startup_config = {
    DriverConfigKey.PARAMETERS: {
        Parameter.UPDATE_INTERVAL: 5,
        Parameter.MAX_DRIVE_CURRENT: 140,
        Parameter.MAX_TEMP_BEARING: 65,
        Parameter.MAX_TEMP_MOTOR: 90,
        Parameter.MIN_SPEED: 80000,
        Parameter.TARGET_SPEED: 90000
    }
}

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.harvard.massp.turbo.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='OYYIN3',
    instrument_agent_name='harvard_massp_turbo',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config=turbo_startup_config
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
    # Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    def assert_sample_data_particle(self, data_particle):
        """
        Verify a particle is a know particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unknown type produced by the driver
        """
        if isinstance(data_particle, RawDataParticle):
            self.assert_particle_raw(data_particle)
        else:
            self.fail("Unknown Particle Detected: %s" % data_particle)

    query_error_code = '0010030302=?101'
    query_excess_temp_edu = '0010030402=?102'
    query_excess_temp_pump = '0010030502=?103'
    query_speed_attained = '0010030602=?104'
    query_pump_accelerates = '0010030702=?105'
    query_current = '0010031002=?099'
    query_voltage = '0010031302=?102'
    query_temp_electronic = '0010032602=?106'
    query_accel = '0010033602=?107'
    query_temp_bearing = '0010034202=?104'
    query_temp_motor = '0010034602=?108'
    query_speed_set = '0010039702=?114'
    query_speed_actual = '0010039802=?115'

    set_pump_on = '0011002306111111019'
    set_station_on = '0011001006111111015'
    set_pump_off = '0011002306000000013'
    set_station_off = '0011001006000000009'

    responses = {
        set_pump_on: set_pump_on,
        set_station_on: set_station_on,
        set_pump_off: set_pump_off,
        set_station_off: set_station_off,
        query_current: '0011031006000000012',
        query_voltage: '0011031306002339032',
        query_temp_bearing: '0011034206000021020',
        query_temp_motor: '0011034606000021024',
        query_speed_actual: '0011039806000000028',
    }

    # build new sets of responses to simulate various states
    responses_stopped = responses.copy()
    responses_at_speed = responses.copy()
    responses_underspeed = responses.copy()
    responses_at_speed[query_speed_actual] = '0011039806090000037'
    responses_underspeed[query_speed_actual] = '0011039806070000035'
    responses_overcurrent = responses_at_speed.copy()
    responses_overcurrent[query_current] = '0011031006000150018'
    responses_overtemp_b = responses_at_speed.copy()
    responses_overtemp_b[query_temp_bearing] = '0011034206000070024'
    responses_overtemp_m = responses_at_speed.copy()
    responses_overtemp_m[query_temp_motor] = '0011034606000091031'

    _sample_chunks = [
        '0011031006000234021' + NEWLINE +
        '0011031306002346030' + NEWLINE +
        '0011034206000028027' + NEWLINE +
        '0011034606000029032' + NEWLINE +
        '0011039806002326041' + NEWLINE,
    ]

    _status_parameters = {
        TurboStatusParticleKey.DRIVE_CURRENT: {TYPE: int, VALUE: 234, REQUIRED: True},
        TurboStatusParticleKey.DRIVE_VOLTAGE: {TYPE: int, VALUE: 2346, REQUIRED: True},
        TurboStatusParticleKey.ROTATION_SPEED: {TYPE: int, VALUE: 2326, REQUIRED: True},
        TurboStatusParticleKey.TEMP_BEARING: {TYPE: int, VALUE: 28, REQUIRED: True},
        TurboStatusParticleKey.TEMP_MOTOR: {TYPE: int, VALUE: 29, REQUIRED: True},
    }

    _driver_parameters = {
        # Parameters defined in the IOS
        Parameter.MAX_DRIVE_CURRENT: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.MAX_TEMP_BEARING: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.MAX_TEMP_MOTOR: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.MIN_SPEED: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.TARGET_SPEED: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.UPDATE_INTERVAL: {TYPE: int, READONLY: False, DA: False, STARTUP: True},
        Parameter.ERROR_REASON: {TYPE: str, READONLY: True, DA: False, STARTUP: False},
    }

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.START_TURBO: {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_TURBO: {STATES: [ProtocolState.SPINNING_UP, ProtocolState.AT_SPEED]},
        Capability.CLEAR: {STATES: [ProtocolState.ERROR]},
        Capability.ACQUIRE_STATUS: {STATES: [ProtocolState.SPINNING_UP, ProtocolState.AT_SPEED,
                                             ProtocolState.SPINNING_DOWN]},
    }

    _capabilities = {
        ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
        ProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                'DRIVER_EVENT_SET',
                                'DRIVER_EVENT_START_DIRECT',
                                'PROTOCOL_EVENT_START_TURBO'],
        ProtocolState.SPINNING_UP: ['DRIVER_EVENT_ACQUIRE_STATUS',
                                    'PROTOCOL_EVENT_STOP_TURBO',
                                    'PROTOCOL_EVENT_AT_SPEED',
                                    'PROTOCOL_EVENT_ERROR'],
        ProtocolState.AT_SPEED: ['DRIVER_EVENT_ACQUIRE_STATUS',
                                 'PROTOCOL_EVENT_STOP_TURBO',
                                 'PROTOCOL_EVENT_ERROR'],
        ProtocolState.SPINNING_DOWN: ['DRIVER_EVENT_ACQUIRE_STATUS',
                                      'PROTOCOL_EVENT_STOPPED'],
        ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT'],
        ProtocolState.ERROR: ['PROTOCOL_EVENT_CLEAR',
                              'PROTOCOL_EVENT_STOP_TURBO',
                              'DRIVER_EVENT_GET',
                              'DRIVER_EVENT_ACQUIRE_STATUS']
    }

    def _send_port_agent_packet(self, driver, data):
        """
        Send a port agent packet via got_data
        @param driver Instrument Driver instance
        @param data data to send
        """
        ts = ntplib.system_to_ntp_time(time.time())
        port_agent_packet = PortAgentPacket()
        port_agent_packet.attach_data(data)
        port_agent_packet.attach_timestamp(ts)
        port_agent_packet.pack_header()

        # Push the response into the driver
        driver._protocol.got_data(port_agent_packet)

    def my_send(self, driver):
        """
        Side effect function generator - will send responses based on input
        @param driver Instrument driver instance
        @returns side effect function
        """
        def inner(data):
            """
            Inner function for side effect generator
            @param data Data to send
            @returns length of response
            """
            data = data.replace(NEWLINE, '')
            log.debug('my_send data: %r', data)
            my_response = self.responses.get(data)
            if my_response is not None:
                log.debug("my_send: data: %r, my_response: %r", data, my_response)
                self._send_port_agent_packet(driver, my_response + NEWLINE)
                return len(my_response)

        return inner

    def assert_status_particle(self, particle, verify_values=False):
        self.assert_data_particle_keys(TurboStatusParticleKey, self._status_parameters)
        self.assert_data_particle_header(particle, DataParticleType.TURBO_STATUS)
        self.assert_data_particle_parameters(particle, self._status_parameters, verify_values)


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
class DriverUnitTest(InstrumentDriverUnitTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_connect(self, initial_protocol_state=ProtocolState.COMMAND):
        """
        Verify driver can transition to the COMMAND state
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state)
        driver._connection.send.side_effect = self.my_send(driver)
        driver._protocol.set_init_params(turbo_startup_config)
        driver._protocol._init_params()
        return driver

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

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, self._capabilities)

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)
        for sample in self._sample_chunks:
            self.assert_chunker_sample(chunker, sample)
            self.assert_chunker_fragmented_sample(chunker, sample)
            self.assert_chunker_combined_sample(chunker, sample)
            self.assert_chunker_sample_with_noise(chunker, sample)

            # create a malformed sample
            malformed = sample.replace('0', '4')
            chunker.add_chunk(malformed, self.get_ntp_timestamp())
            self.assert_chunker_sample(chunker, sample)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = self.test_connect()
        self.assert_particle_published(driver, self._sample_chunks[0], self.assert_status_particle, True)

    def test_build_commands(self):
        """
        Test the build command function for both queries and sets
        """
        driver = self.test_connect()

        def btq(command):
            return driver._protocol._build_turbo_command(ADDRESS, CommandType.QUERY, command, QUERY)

        def bts(command, value):
            return driver._protocol._build_turbo_command(ADDRESS, CommandType.SET, command, value)

        self.assertEqual(btq(InstrumentCommand.ERROR_CODE), self.query_error_code)
        self.assertEqual(btq(InstrumentCommand.EXCESS_TEMP_EDU), self.query_excess_temp_edu)
        self.assertEqual(btq(InstrumentCommand.EXCESS_TEMP_PUMP), self.query_excess_temp_pump)
        self.assertEqual(btq(InstrumentCommand.SPEED_ATTAINED), self.query_speed_attained)
        self.assertEqual(btq(InstrumentCommand.PUMP_ACCELERATES), self.query_pump_accelerates)
        self.assertEqual(btq(InstrumentCommand.DRIVE_CURRENT), self.query_current)
        self.assertEqual(btq(InstrumentCommand.DRIVE_VOLTAGE), self.query_voltage)
        self.assertEqual(btq(InstrumentCommand.TEMP_ELECTRONIC), self.query_temp_electronic)
        self.assertEqual(btq(InstrumentCommand.ACCEL), self.query_accel)
        self.assertEqual(btq(InstrumentCommand.TEMP_BEARING), self.query_temp_bearing)
        self.assertEqual(btq(InstrumentCommand.TEMP_MOTOR), self.query_temp_motor)
        self.assertEqual(btq(InstrumentCommand.ROTATION_SPEED_SET), self.query_speed_set)
        self.assertEqual(btq(InstrumentCommand.ROTATION_SPEED_ACTUAL), self.query_speed_actual)

        self.assertEqual(bts(InstrumentCommand.MOTOR_PUMP, TRUE), self.set_pump_on)
        self.assertEqual(bts(InstrumentCommand.PUMP_STATION, TRUE), self.set_station_on)
        self.assertEqual(bts(InstrumentCommand.MOTOR_PUMP, FALSE), self.set_pump_off)
        self.assertEqual(bts(InstrumentCommand.PUMP_STATION, FALSE), self.set_station_off)

    def test_start_turbo(self):
        """
        Test the start turbo handler
        """
        driver = self.test_connect()
        driver._protocol._handler_command_start_turbo()

    def test_acquire_status(self):
        """
        Test the acquire status handler
        """
        driver = self.test_connect()
        driver.test_force_state(state=ProtocolState.SPINNING_UP)
        driver._protocol._handler_acquire_status()

    def test_exception_handling(self):
        """
        sleeps are necessary to allow async events to fire...
        """
        for each in [self.responses_underspeed,
                     self.responses_overcurrent,
                     self.responses_overtemp_b,
                     self.responses_overtemp_m]:

            driver = self.test_connect()
            try:
                driver._protocol._protocol_fsm.on_event(Capability.START_TURBO)
                self.assertEqual(driver._protocol.get_current_state(), ProtocolState.SPINNING_UP)
                self.responses = self.responses_at_speed
                driver._protocol._protocol_fsm.on_event(Capability.ACQUIRE_STATUS)
                time.sleep(.1)
                self.assertEqual(driver._protocol.get_current_state(), ProtocolState.AT_SPEED)
                self.responses = each
                for x in xrange(CURRENT_STABILIZE_RETRIES+1):
                    driver._protocol._protocol_fsm.on_event(Capability.ACQUIRE_STATUS)
                    time.sleep(.1)
            except Exception as e:
                log.debug('Exception detected: %r', e)
            finally:
                self.responses = self.responses_stopped
                time.sleep(.1)
                self.assertEqual(driver._protocol.get_current_state(), ProtocolState.ERROR)
                driver._protocol._protocol_fsm.on_event(Capability.CLEAR)
                self.assertEqual(driver._protocol.get_current_state(), ProtocolState.COMMAND)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock()
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability.list()
        test_capabilities = Capability.list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)


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

    def test_start_stop_turbo(self):
        """
        Start the turbo, verify it transitions through the correct state
        sequence to AT_SPEED.  Stop the turbo and verify it transitions
        through the correct state sequence to COMMAND.
        """
        self.assert_initialize_driver()
        self.assert_driver_command(Capability.START_TURBO)
        self.assert_state_change(ProtocolState.SPINNING_UP, 10)
        self.assert_state_change(ProtocolState.AT_SPEED, 600)
        self.assert_driver_command(Capability.STOP_TURBO)
        self.assert_state_change(ProtocolState.SPINNING_DOWN, 10)
        self.assert_state_change(ProtocolState.COMMAND, 600)

    # while this is an integration test, it can be run without access to the instrument
    def test_get_parameters(self):
        """
        Verify we can get all the parameters
        """
        self.assert_initialize_driver()
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        for key, value in startup_params.items():
            self.assert_get(key, value)

    # while this is an integration test, it can be run without access to the instrument
    def test_set_parameters(self):
        """
        Verify we can set all parameters
        """
        self.assert_initialize_driver()
        constraints = ParameterConstraints.dict()
        parameters = Parameter.reverse_dict()
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        for key, value in startup_params.items():
            if key in parameters and parameters[key] in constraints:
                _, minimum, maximum = constraints[parameters[key]]
                self.assert_set(key, maximum-1)
            else:
                self.assert_set(key, value + 1)

        self.assert_set_bulk(startup_params)

    # while this is an integration test, it can be run without access to the instrument
    def test_out_of_range(self):
        self.assert_initialize_driver()
        constraints = ParameterConstraints.dict()
        parameters = Parameter.dict()
        log.debug(constraints)
        for each in constraints:
            parameter = parameters[each]
            _, minimum, maximum = constraints[each]
            self.assert_set_exception(parameter, minimum - 1)
            self.assert_set_exception(parameter, maximum + 1)
            self.assert_set_exception(parameter, "strings aren't valid here!")

    def test_set_bogus_parameter(self):
        """
        Verify setting a bad parameter raises an exception
        """
        self.assert_initialize_driver()
        self.assert_set_exception('BOGUS', 'CHEESE')

    def test_bad_command(self):
        """
        Verify sending a bad command raises an exception
        """
        self.assert_initialize_driver()
        self.assert_driver_command_exception('BAD_COMMAND', exception_class=InstrumentCommandException)

    def test_incomplete_config(self):
        """
        Break our startup config, then verify the driver raises an exception
        """
        # grab the old config
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        old_value = startup_params[Parameter.TARGET_SPEED]
        try:
            # delete a required parameter
            del (startup_params[Parameter.TARGET_SPEED])
            # re-init to take our broken config
            self.init_driver_process_client()
            self.assert_initialize_driver()
            self.assertTrue(False, msg='Failed to raise exception on missing parameter')
        except Exception as e:
            self.assertTrue(self._driver_exception_match(e, InstrumentProtocolException))
        finally:
            startup_params[Parameter.TARGET_SPEED] = old_value


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
        @brief This test manually tests that the Instrument Driver properly supports
        direct access to the physical instrument. (telnet mode)

        We just turn the turbo on, then off here
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        for command in [self.set_station_on,
                        self.set_pump_on,
                        self.set_pump_off,
                        self.set_station_off]:
            self.tcp_client.send_data(command + NEWLINE)
            self.assertTrue(self.tcp_client.expect(self.responses[command]))

        self.assert_direct_access_stop_telnet()
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 5)

    def test_particles(self):
        self.assert_enter_command_mode()
        self.assert_execute_resource(Capability.START_TURBO)
        self.assert_particle_async(DataParticleType.TURBO_STATUS,
                                   self.assert_status_particle,
                                   particle_count=2, timeout=20)
        self.assert_execute_resource(Capability.STOP_TURBO)
        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 30)

    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        self.assert_enter_command_mode()
        constraints = ParameterConstraints.dict()
        parameters = Parameter.reverse_dict()
        startup_params = self.test_config.driver_startup_config[DriverConfigKey.PARAMETERS]
        for key, value in startup_params.items():
            self.assert_get_parameter(key, value)
            if key in parameters and parameters[key] in constraints:
                _, minimum, maximum = constraints[parameters[key]]
                self.assert_set_parameter(key, maximum-1)
            else:
                self.assert_set_parameter(key, value+1)

    def test_reset(self):
        """
        Verify the agent can be reset
        Overridden, driver does not have autosample
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet()
        self.assert_state_change(ResourceAgentState.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS, 30)
        self.assert_reset()

    def test_discover(self):
        """
        Overridden, driver does not have autosample
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver which holds the current
        # instrument state.
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)

    def test_get_capabilities(self):
        """
        Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()

        ##################
        # Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [ProtocolEvent.START_TURBO],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        self.assert_execute_resource(Capability.START_TURBO)
        self.assert_state_change(ResourceAgentState.BUSY, ProtocolState.SPINNING_UP, 20)

        ##################
        # SPINNING_UP Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: [],
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [ProtocolEvent.STOP_TURBO, ProtocolEvent.ACQUIRE_STATUS],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        self.assert_state_change(ResourceAgentState.BUSY, ProtocolState.AT_SPEED, 300)

        ##################
        # AT_SPEED Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: [],
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [ProtocolEvent.STOP_TURBO, ProtocolEvent.ACQUIRE_STATUS],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        self.assert_execute_resource(Capability.STOP_TURBO)
        self.assert_state_change(ResourceAgentState.BUSY, ProtocolState.SPINNING_DOWN, 20)

        ##################
        # SPINNING_DOWN Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: []
            ,
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [ProtocolEvent.ACQUIRE_STATUS],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        self.assert_state_change(ResourceAgentState.COMMAND, ProtocolState.COMMAND, 200)

        ##################
        # DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        # Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)