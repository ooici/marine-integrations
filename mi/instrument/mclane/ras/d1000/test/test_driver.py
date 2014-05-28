"""
@package mi.instrument.mclane.ras.ooicore.test.test_driver
@file marine-integrations/mi/instrument/mclane/ras/ooicore/test/test_driver.py
@author Dan Mergens
@brief Test cases for D1000 driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Dan Mergens'
__license__ = 'Apache 2.0'

import time

from mock import Mock
from nose.plugins.attrib import attr
from mi.core.log import get_logger


log = get_logger()

from mi.idk.unit_test import \
    InstrumentDriverTestCase, \
    InstrumentDriverUnitTestCase, \
    InstrumentDriverIntegrationTestCase, \
    InstrumentDriverQualificationTestCase, \
    DriverTestMixin, \
    ParameterTestConfigKey, \
    AgentCapabilityType

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverProtocolState, DriverConfigKey

from mi.instrument.mclane.ras.d1000.driver import \
    InstrumentDriver, \
    DataParticleType, \
    Command, \
    ProtocolState, \
    ProtocolEvent, \
    Capability, \
    Parameter, \
    Protocol, \
    Prompt, \
    NEWLINE, \
    D1000TemperatureDataParticleKey, \
    D1000TemperatureDataParticle

from mi.core.exceptions import SampleException

from pyon.agent.agent import ResourceAgentState

# Globals
raw_stream_received = False
parsed_stream_received = False

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.mclane.ras.d1000.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id='DQPJJX',
    instrument_agent_name='mclane_ras_d1000',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={DriverConfigKey.PARAMETERS: {Parameter.SAMPLE_INTERVAL: 6}},
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
class UtilMixin(DriverTestMixin):
    """
    Mixin class used for storing data particle constants and common data assertion methods.
    """
    # Create some short names for the parameter test config
    TYPE = ParameterTestConfigKey.TYPE
    READONLY = ParameterTestConfigKey.READONLY
    STARTUP = ParameterTestConfigKey.STARTUP
    DA = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE = ParameterTestConfigKey.VALUE
    REQUIRED = ParameterTestConfigKey.REQUIRED
    DEFAULT = ParameterTestConfigKey.DEFAULT
    STATES = ParameterTestConfigKey.STATES

    SAMPLE_DATA1 = \
        "*1RD+00019.16AB" + NEWLINE + \
        "#2RD" + NEWLINE + \
        "*2RD+00019.17AD" + NEWLINE + \
        "#3RD" + NEWLINE + \
        "*3RD+00019.18AF" + NEWLINE
    SAMPLE_DATA_MISSING_CHECKSUM = \
        "*1RD+00019.16AB" + NEWLINE + \
        "#2RD" + NEWLINE + \
        "*2RD+00019.17" + NEWLINE + \
        "#3RD" + NEWLINE + \
        "*3RD+00019.18AF" + NEWLINE
    SAMPLE_DATA_WRONG_CHECKSUM = \
        "*1RD+00019.16AA" + NEWLINE + \
        "#2RD" + NEWLINE + \
        "*2RD+00019.17AD" + NEWLINE + \
        "#3RD" + NEWLINE + \
        "*3RD+00019.18AF" + NEWLINE
    SAMPLE_DATA2 = \
        "*1RD+00019.29AF" + NEWLINE + \
        "#2RD" + NEWLINE + \
        "*2RD+00019.17AD" + NEWLINE + \
        "#3RD" + NEWLINE + \
        "*3RD+00019.18AF" + NEWLINE

    _driver_capabilities = {
        # capabilities defined in the IOS
        # Capability.START_AUTOSAMPLE: {STATES: [ProtocolState.COMMAND]},
    }

    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {
        Parameter.SAMPLE_INTERVAL:
            {TYPE: int, READONLY: False, DA: False, STARTUP: True, VALUE: 15, REQUIRED: False},
        Parameter.CHANNEL_ADDRESS:
            {TYPE: int, READONLY: True, DA: True, STARTUP: False, VALUE: 0x31, REQUIRED: False},
        Parameter.LINEFEED:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: False, REQUIRED: False},
        Parameter.PARITY_TYPE:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: False, REQUIRED: False},
        Parameter.PARITY_ENABLE:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: False, REQUIRED: False},
        Parameter.EXTENDED_ADDRESSING:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: False, REQUIRED: False},
        Parameter.BAUD_RATE:
            {TYPE: int, READONLY: True, DA: True, STARTUP: False, VALUE: 9600, REQUIRED: False},
        Parameter.ALARM_ENABLE:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: False, REQUIRED: False},
        Parameter.LOW_ALARM_LATCH:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: False, REQUIRED: False},
        Parameter.HIGH_ALARM_LATCH:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: False, REQUIRED: False},
        Parameter.RTD_4_WIRE:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: True, REQUIRED: False},
        Parameter.TEMP_UNITS:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: False, REQUIRED: False},
        Parameter.ECHO:
            {TYPE: bool, READONLY: True, DA: True, STARTUP: False, VALUE: True, REQUIRED: False},
        Parameter.COMMUNICATION_DELAY:
            {TYPE: int, READONLY: True, DA: True, STARTUP: False, VALUE: 0, REQUIRED: False},
        Parameter.PRECISION:
            {TYPE: int, READONLY: True, DA: True, STARTUP: False, VALUE: 6, REQUIRED: False},
        Parameter.LARGE_SIGNAL_FILTER_C:
            {TYPE: float, READONLY: True, DA: True, STARTUP: False, VALUE: 0.0, REQUIRED: False},
        Parameter.SMALL_SIGNAL_FILTER_C:
            {TYPE: float, READONLY: True, DA: True, STARTUP: False, VALUE: 0.50, REQUIRED: False},
    }

    ###
    # Data Particle Parameters
    ### 
    _sample_parameters = {
        D1000TemperatureDataParticleKey.TEMP1: {'type': float, 'value': 19.16},
        D1000TemperatureDataParticleKey.TEMP2: {'type': float, 'value': 19.17},
        D1000TemperatureDataParticleKey.TEMP3: {'type': float, 'value': 19.18},
    }

    # Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values=False, verify_sample_interval=False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)
        if verify_sample_interval:
            self.assertEqual(current_parameters[Parameter.SAMPLE_INTERVAL],
                             self._driver_parameters[Parameter.SAMPLE_INTERVAL][self.VALUE],
                             "sample_interval %d != expected value %r" % (current_parameters[Parameter.SAMPLE_INTERVAL],
                                                                          self._driver_parameters[
                                                                              Parameter.SAMPLE_INTERVAL][self.VALUE]))

    def assert_sample_interval_parameter(self, current_parameters, verify_values=False):
        """
        Verify that sample_interval parameter is correct and potentially verify value.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, False)
        self.assertEqual(current_parameters[Parameter.SAMPLE_INTERVAL],
                         self._driver_parameters[Parameter.SAMPLE_INTERVAL][self.VALUE],
                         "sample_interval %d != expected value %r" % (current_parameters[Parameter.SAMPLE_INTERVAL],
                                                                      self._driver_parameters[
                                                                          Parameter.SAMPLE_INTERVAL][self.VALUE]))

    ###
    # Data Particle Parameters Methods
    ### 
    def assert_data_particle_sample(self, data_particle, verify_values=False):
        """
        Verify a sample data particle
        @param data_particle: D1000 Temperature data particle
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_header(data_particle, DataParticleType.D1000_PARSED)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)


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
class TestUNIT(InstrumentDriverUnitTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    print '----- unit test -----'

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilities
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(Command())

        # Test capabilities for duplicates, then verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, self.SAMPLE_DATA1)
        self.assert_chunker_sample_with_noise(chunker, self.SAMPLE_DATA1)
        self.assert_chunker_fragmented_sample(chunker, self.SAMPLE_DATA1)
        self.assert_chunker_combined_sample(chunker, self.SAMPLE_DATA1)

    def test_corrupt_data_sample(self):
        particle = D1000TemperatureDataParticle(self.SAMPLE_DATA1.replace('19', 'foo'),
                                                port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

    def test_missing_checksum_data_sample(self):
        particle = D1000TemperatureDataParticle(self.SAMPLE_DATA_MISSING_CHECKSUM,
                                                port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

    def test_wrong_checksum_data_sample(self):
        particle = D1000TemperatureDataParticle(self.SAMPLE_DATA_WRONG_CHECKSUM,
                                                port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # validating data particles are published
        self.assert_particle_published(driver, self.SAMPLE_DATA1, self.assert_data_particle_sample, True)

        # validate that a duplicate sample is not published - TODO
        # self.assert_particle_not_published(driver, self.SAMPLE_DATA1, self.assert_data_particle_sample, True)

        # validate that a new sample is published
        self.assert_particle_published(driver, self.SAMPLE_DATA2, self.assert_data_particle_sample, False)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
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
            ProtocolState.UNKNOWN: [ProtocolEvent.DISCOVER],
            ProtocolState.COMMAND: [ProtocolEvent.GET,
                                    ProtocolEvent.SET,
                                    ProtocolEvent.ACQUIRE_SAMPLE,
                                    ProtocolEvent.START_AUTOSAMPLE,
                                    ProtocolEvent.START_DIRECT,
            ],
            ProtocolState.AUTOSAMPLE: [ProtocolEvent.STOP_AUTOSAMPLE,
                                       ProtocolEvent.ACQUIRE_SAMPLE,
            ],
            ProtocolState.DIRECT_ACCESS: [ProtocolEvent.STOP_DIRECT,
                                          ProtocolEvent.EXECUTE_DIRECT,
            ]
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

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
class TestINT(InstrumentDriverIntegrationTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def assert_async_particle_not_generated(self, particle_type, timeout=10):
        end_time = time.time() + timeout

        while end_time > time.time():
            if len(self.get_sample_events(particle_type)) > 0:
                self.fail("assert_async_particle_not_generated: a particle of type %s was published" % particle_type)
            time.sleep(.3)

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample.
        To test status particle instrument must be off and powered on will test is waiting
        """
        # put driver into autosample mode
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        # test that sample particle is generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for instrument data")
        self.assert_async_particle_generation(DataParticleType.D1000_PARSED, self.assert_data_particle_sample,
                                              timeout=60)

        # take driver out of autosample mode
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        # test that sample particle is not generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for no instrument data")
        self.clear_events()
        self.assert_async_particle_not_generated(DataParticleType.D1000_PARSED, timeout=60)

        # put driver back in autosample mode
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        # test that sample particle is generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for instrument data")
        self.assert_async_particle_generation(DataParticleType.D1000_PARSED, self.assert_data_particle_sample,
                                              timeout=60)

    def test_parameters(self):
        """
        Verify that we can set the parameters

        1. Cannot set read only parameters
        2. Can set read/write parameters
        3. Can set read/write parameters w/direct access only
        """
        self.assert_initialize_driver()

        # verify we cannot set readonly parameters
        self.assert_set_exception(Parameter.CHANNEL_ADDRESS, 0x31)
        self.assert_set_exception(Parameter.LINEFEED, False)
        self.assert_set_exception(Parameter.PARITY_TYPE, 0)
        self.assert_set_exception(Parameter.PARITY_ENABLE, 0)
        self.assert_set_exception(Parameter.EXTENDED_ADDRESSING, False)
        self.assert_set_exception(Parameter.BAUD_RATE, 9600)
        self.assert_set_exception(Parameter.ALARM_ENABLE, False)
        self.assert_set_exception(Parameter.LOW_ALARM_LATCH, False)
        self.assert_set_exception(Parameter.HIGH_ALARM_LATCH, False)
        self.assert_set_exception(Parameter.RTD_4_WIRE, True)
        self.assert_set_exception(Parameter.TEMP_UNITS, False)
        self.assert_set_exception(Parameter.ECHO, True)
        self.assert_set_exception(Parameter.COMMUNICATION_DELAY, 0)
        self.assert_set_exception(Parameter.PRECISION, 6)
        self.assert_set_exception(Parameter.LARGE_SIGNAL_FILTER_C, 0)
        self.assert_set_exception(Parameter.SMALL_SIGNAL_FILTER_C, 0.25)

        # verify setting parameters out of range throws exception
        self.assert_set_exception(Parameter.SAMPLE_INTERVAL, -1)
        self.assert_set_exception(Parameter.SAMPLE_INTERVAL, 3601)


    def test_acquire_sample(self):
        """
        Test that we can generate sample particle with command
        """
        self.assert_initialize_driver()
        self.assert_particle_generation(ProtocolEvent.START_AUTOSAMPLE, DataParticleType.D1000_PARSED,
                                        self.assert_data_particle_sample, timeout=10)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class TestQUAL(InstrumentDriverQualificationTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    # def assert_sample_polled(self, sample_data_assert, sample_queue, timeout=10):
    #     """
    #     Test observatory polling function.
    #
    #     Verifies the acquire_status command.
    #     """
    #     # Set up all data subscriptions.  Stream names are defined
    #     # in the driver PACKET_CONFIG dictionary
    #     self.data_subscribers.start_data_subscribers()
    #     self.addCleanup(self.data_subscribers.stop_data_subscribers)
    #
    #     self.assert_enter_command_mode()
    #
    #     ###
    #     # Poll for a sample
    #     ###
    #
    #     # make sure there aren't any junk samples in the parsed
    #     # data queue.
    #     log.debug("Acquire Sample")
    #     self.data_subscribers.clear_sample_queue(sample_queue)
    #
    #     cmd = AgentCommand(command=DriverEvent.ACQUIRE_SAMPLE)
    #     self.instrument_agent_client.execute_resource(cmd, timeout=timeout)
    #
    #     # Watch the parsed data queue and return once a sample
    #     # has been read or the default timeout has been reached.
    #     samples = self.data_subscribers.get_samples(sample_queue, 1, timeout=timeout)
    #     self.assertGreaterEqual(len(samples), 1)
    #     log.error("SAMPLE: %s" % samples)
    #
    #     # Verify
    #     for sample in samples:
    #         sample_data_assert(sample)
    #
    #     self.assert_reset()
    #     self.doCleanups()

    def test_discover(self):
        """
        verify we can discover our instrument state from streaming and autosample.
        Overloaded to account for this instrument returning to command mode instead of streaming.
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver which holds the current
        # instrument state.
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)

        # Now put the instrument in streaming and reset the driver again.
        self.assert_start_autosample()
        self.assert_reset()

        # When the driver reconnects it should be in command mode
        self.assert_discover(ResourceAgentState.COMMAND)
        self.assert_reset()

    def test_poll(self):
        """
        poll for a single sample
        """
        self.assert_sample_polled(self.assert_data_particle_sample,
                                  DataParticleType.D1000_PARSED)

    def test_autosample(self):
        """
        start and stop autosample and verify data particle
        """
        self.assert_sample_autosample(self.assert_data_particle_sample,
                                      DataParticleType.D1000_PARSED,
                                      sample_count=1,
                                      timeout=60)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test automatically tests that the Instrument Driver properly supports direct access to the physical
        instrument. (telnet mode)
        """
        self.assert_enter_command_mode()

        # go into direct access
        self.assert_direct_access_start_telnet(timeout=600)
        self.tcp_client.send_data("#1WE\r\n")
        if not self.tcp_client.expect("*1WEF7\r\n"):
            self.fail("test_direct_access_telnet_mode: unable to enable write mode")
        self.tcp_client.send_data("#1SU310214C2\r\n")
        if not self.tcp_client.expect("*1SU310214C2A3\r\n"):
            self.fail("test_direct_access_telnet_mode: unable to perform setup command or bad checksum returned")
        self.assert_direct_access_stop_telnet()

        # ensure that setup has been restored after exiting direct access
        self.assert_direct_access_start_telnet(timeout=600)
        self.tcp_client.send_data("$1RS\r\n")
        if not self.tcp_client.expect("*31021482\r\n"):
            self.fail("test_direct_access_telnet_mode: setup was not restored")
        self.assert_direct_access_stop_telnet()

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        fn = 'test_get_capabilities'
        # log.debug('%s: assert_enter_command_mode', fn)
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
                ProtocolEvent.ACQUIRE_SAMPLE,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        # log.debug('%s: assert_capabilities', fn)
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [
            ProtocolEvent.ACQUIRE_SAMPLE,
            ProtocolEvent.STOP_AUTOSAMPLE,
        ]

        # log.debug('%s: assert_start_autosample', fn)
        self.assert_start_autosample()
        # log.debug('%s: assert_capabilities', fn)
        self.assert_capabilities(capabilities)
        # log.debug('%s: assert_stop_autosample', fn)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        # log.debug('%s: assert_direct_access_start_telnet', fn)
        self.assert_direct_access_start_telnet()
        # log.debug('%s: assert_capabilities', fn)
        self.assert_capabilities(capabilities)
        # log.debug('%s: assert_direct_access_stop_telnet', fn)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        # log.debug('%s: assert_reset', fn)
        self.assert_reset()
        # log.debug('%s: assert_capabilities', fn)
        self.assert_capabilities(capabilities)

    def test_parameters(self):
        """
        @brief Check ability to set and get parameters.
        """
        self.assert_enter_command_mode()

        # verify access of parameters - default values
        self.assert_get_parameter(Parameter.SAMPLE_INTERVAL, 15)
        self.assert_get_parameter(Parameter.CHANNEL_ADDRESS, 0x31)
        self.assert_get_parameter(Parameter.LINEFEED, False)
        self.assert_get_parameter(Parameter.PARITY_TYPE, 0)
        self.assert_get_parameter(Parameter.PARITY_ENABLE, 0)
        self.assert_get_parameter(Parameter.EXTENDED_ADDRESSING, False)
        self.assert_get_parameter(Parameter.BAUD_RATE, 9600)
        self.assert_get_parameter(Parameter.ALARM_ENABLE, False)
        self.assert_get_parameter(Parameter.LOW_ALARM_LATCH, False)
        self.assert_get_parameter(Parameter.HIGH_ALARM_LATCH, False)
        self.assert_get_parameter(Parameter.RTD_4_WIRE, True)
        self.assert_get_parameter(Parameter.TEMP_UNITS, False)
        self.assert_get_parameter(Parameter.ECHO, True)
        self.assert_get_parameter(Parameter.COMMUNICATION_DELAY, 0)
        self.assert_get_parameter(Parameter.PRECISION, 6)
        self.assert_get_parameter(Parameter.LARGE_SIGNAL_FILTER_C, 0)
        self.assert_get_parameter(Parameter.SMALL_SIGNAL_FILTER_C, 0.50)

        # verify we can set read/write parameters
        self.assert_set_parameter(Parameter.SAMPLE_INTERVAL, 2)

