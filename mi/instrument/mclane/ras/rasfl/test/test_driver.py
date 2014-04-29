"""
@package mi.instrument.mclane.ras.ooicore.test.test_driver
@file marine-integrations/mi/instrument/mclane/ras/ooicore/test/test_driver.py
@author Bill Bollenbacher & Dan Mergens
@brief Test cases for rasfl driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""
from mi.core.instrument.instrument_driver import DriverConfigKey, DriverProtocolState

__author__ = 'Bill Bollenbacher & Dan Mergens'
__license__ = 'Apache 2.0'

import unittest
import time

import gevent
from mock import Mock
from nose.plugins.attrib import attr
from mi.core.log import get_logger


log = get_logger()

# MI imports.
from mi.idk.unit_test import \
    InstrumentDriverTestCase, \
    InstrumentDriverUnitTestCase, \
    InstrumentDriverIntegrationTestCase, \
    InstrumentDriverQualificationTestCase, \
    DriverTestMixin, \
    ParameterTestConfigKey, \
    AgentCapabilityType

from mi.core.instrument.chunker import StringChunker

from mi.instrument.mclane.driver import \
    ProtocolState, \
    ProtocolEvent, \
    Capability, \
    Prompt, \
    NEWLINE, \
    McLaneSampleDataParticleKey

from mi.instrument.mclane.ras.rasfl.driver import \
    InstrumentDriver, \
    DataParticleType, \
    Command, \
    Parameter, \
    Protocol, \
    RASFLSampleDataParticle

from mi.core.exceptions import SampleException, \
    InstrumentParameterException

from interface.objects import AgentCommand

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from pyon.agent.agent import \
    ResourceAgentEvent, \
    ResourceAgentState

# Globals
raw_stream_received = False
parsed_stream_received = False

ACQUIRE_TIMEOUT = 45 * 60 + 50
CLEAR_TIMEOUT = 110

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.mclane.ras.ras.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id='DQPJJX',
    instrument_agent_name='mclane_ras_rasfl',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={DriverConfigKey.PARAMETERS: {
        Parameter.CLEAR_VOLUME: 10,
        Parameter.FILL_VOLUME: 10,
        Parameter.FLUSH_VOLUME: 10,
    }},
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

    # battery voltage request response - TODO not implemented
    RASFL_BATTERY_DATA = "Battery: 29.9V [Alkaline, 18V minimum]" + NEWLINE

    # bag capacity response - TODO not implemented
    RASFL_CAPACITY_DATA = "Bag capacity: 500" + NEWLINE

    RASFL_VERSION_DATA = \
        "Version:" + NEWLINE + \
        NEWLINE + \
        "McLane Research Laboratories, Inc." + NEWLINE + \
        "CF2 Adaptive Remote Sampler" + NEWLINE + \
        "Version 3.02 of Jun  6 2013 15:38" + NEWLINE + \
        "Pump type: Maxon 125ml" + NEWLINE + \
        "Bag capacity: 500" + NEWLINE

    # response from collect sample meta command (from FORWARD or REVERSE command)
    RASFL_SAMPLE_DATA1 = "Status 00 |  75 100  25   4 |   1.5  90.7  .907*  1 031514 001727 | 29.9 0" + NEWLINE
    RASFL_SAMPLE_DATA2 = "Status 00 |  75 100  25   4 |   3.2 101.2 101.2*  2 031514 001728 | 29.9 0" + NEWLINE
    RASFL_SAMPLE_DATA3 = "Result 00 |  75 100  25   4 |  77.2  98.5  99.1  47 031514 001813 | 29.8 1" + NEWLINE

    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.CLOCK_SYNC: {STATES: [ProtocolState.COMMAND]},
    }

    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {
        Parameter.FLUSH_VOLUME: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 150, REQUIRED: True},
        Parameter.FLUSH_FLOWRATE: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 100, REQUIRED: True},
        Parameter.FLUSH_MINFLOW: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 25, REQUIRED: True},
        Parameter.FILL_VOLUME: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 425, REQUIRED: True},
        Parameter.FILL_FLOWRATE: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 75, REQUIRED: True},
        Parameter.FILL_MINFLOW: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 25, REQUIRED: True},
        Parameter.CLEAR_VOLUME: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 75, REQUIRED: True},
        Parameter.CLEAR_FLOWRATE: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 100, REQUIRED: True},
        Parameter.CLEAR_MINFLOW: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 25, REQUIRED: True}}

    ###
    # Data Particle Parameters
    ### 
    _sample_parameters = {
        McLaneSampleDataParticleKey.PORT: {'type': int, 'value': 0},
        McLaneSampleDataParticleKey.VOLUME_COMMANDED: {'type': int, 'value': 75},
        McLaneSampleDataParticleKey.FLOW_RATE_COMMANDED: {'type': int, 'value': 100},
        McLaneSampleDataParticleKey.MIN_FLOW_COMMANDED: {'type': int, 'value': 25},
        McLaneSampleDataParticleKey.TIME_LIMIT: {'type': int, 'value': 4},
        McLaneSampleDataParticleKey.VOLUME_ACTUAL: {'type': float, 'value': 1.5},
        McLaneSampleDataParticleKey.FLOW_RATE_ACTUAL: {'type': float, 'value': 90.7},
        McLaneSampleDataParticleKey.MIN_FLOW_ACTUAL: {'type': float, 'value': 0.907},
        McLaneSampleDataParticleKey.TIMER: {'type': int, 'value': 1},
        McLaneSampleDataParticleKey.TIME: {'type': unicode, 'value': '031514 001727'},
        McLaneSampleDataParticleKey.BATTERY: {'type': float, 'value': 29.9},
        McLaneSampleDataParticleKey.CODE: {'type': int, 'value': 0},
    }

    ###
    # Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values=False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    ###
    # Data Particle Parameters Methods
    ### 
    def assert_data_particle_sample(self, data_particle, verify_values=False):
        """
        Verify an RASFL sample data particle
        @param data_particle: OPTAAA_SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_header(data_particle, DataParticleType.RASFL_PARSED)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_data_particle_status(self, data_particle, verify_values=False):
        """
        Verify a RASFL pump status data particle
        @param data_particle: RASFL_StatusDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        """
        # self.assert_data_particle_header(data_particle, DataParticleType.RASFL_STATUS)
        # self.assert_data_particle_parameters(data_particle, self._status_parameters, verify_values)

    def assert_time_synched(self, ras_time, tolerance=5):
        """
        Verify the retrieved time is within acceptable tolerance
        """
        ras_time = time.strptime(ras_time + 'UTC', '%m/%d/%y %H:%M:%S %Z')
        current_time = time.gmtime()
        diff = time.mktime(current_time) - time.mktime(ras_time)
        log.info('clock synched within %d seconds', diff)

        # Verify that the time matches to within tolerance (seconds)
        self.assertLessEqual(diff, tolerance)


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
        do a little extra validation for the Capabilites
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

        self.assert_chunker_sample(chunker, self.RASFL_SAMPLE_DATA1)
        self.assert_chunker_sample_with_noise(chunker, self.RASFL_SAMPLE_DATA1)
        self.assert_chunker_fragmented_sample(chunker, self.RASFL_SAMPLE_DATA1)
        self.assert_chunker_combined_sample(chunker, self.RASFL_SAMPLE_DATA1)

        self.assert_chunker_sample(chunker, self.RASFL_SAMPLE_DATA2)
        self.assert_chunker_sample_with_noise(chunker, self.RASFL_SAMPLE_DATA2)
        self.assert_chunker_fragmented_sample(chunker, self.RASFL_SAMPLE_DATA2)
        self.assert_chunker_combined_sample(chunker, self.RASFL_SAMPLE_DATA2)

        self.assert_chunker_sample(chunker, self.RASFL_SAMPLE_DATA3)
        self.assert_chunker_sample_with_noise(chunker, self.RASFL_SAMPLE_DATA3)
        self.assert_chunker_fragmented_sample(chunker, self.RASFL_SAMPLE_DATA3)
        self.assert_chunker_combined_sample(chunker, self.RASFL_SAMPLE_DATA3)

    def test_corrupt_data_sample(self):
        # garbage is not okay
        particle = RASFLSampleDataParticle(self.RASFL_SAMPLE_DATA1.replace('00', 'foo'),
                                           port_timestamp=3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver, initial_protocol_state=ProtocolState.FILL)

        self.assert_raw_particle_published(driver, True)

        # validating data particles are published
        self.assert_particle_published(driver, self.RASFL_SAMPLE_DATA1, self.assert_data_particle_sample, True)

        # validate that a duplicate sample is not published - TODO
        #self.assert_particle_not_published(driver, self.RASFL_SAMPLE_DATA1, self.assert_data_particle_sample, True)

        # validate that a new sample is published
        self.assert_particle_published(driver, self.RASFL_SAMPLE_DATA2, self.assert_data_particle_sample, False)

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
            ProtocolState.UNKNOWN: [
                ProtocolEvent.DISCOVER,
            ],
            ProtocolState.COMMAND: [
                ProtocolEvent.GET,
                ProtocolEvent.SET,
                ProtocolEvent.INIT_PARAMS,
                ProtocolEvent.START_DIRECT,
                ProtocolEvent.ACQUIRE_SAMPLE,
                ProtocolEvent.CLEAR,
                ProtocolEvent.CLOCK_SYNC,
            ],
            ProtocolState.FLUSH: [
                ProtocolEvent.FLUSH,
                ProtocolEvent.PUMP_STATUS,
                ProtocolEvent.INSTRUMENT_FAILURE,
            ],
            ProtocolState.FILL: [
                ProtocolEvent.FILL,
                ProtocolEvent.PUMP_STATUS,
                ProtocolEvent.INSTRUMENT_FAILURE,
            ],
            ProtocolState.CLEAR: [
                ProtocolEvent.CLEAR,
                ProtocolEvent.PUMP_STATUS,
                ProtocolEvent.INSTRUMENT_FAILURE,
            ],
            ProtocolState.RECOVERY: [
            ],
            ProtocolState.DIRECT_ACCESS: [
                ProtocolEvent.STOP_DIRECT,
                ProtocolEvent.EXECUTE_DIRECT,
            ],
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

    #@unittest.skip('not completed yet')
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

    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        log.debug('Startup parameters: %s', reply)
        self.assert_driver_parameters(reply)

        # self.assert_get(Parameter.FLUSH_VOLUME, value=150)
        self.assert_get(Parameter.FLUSH_VOLUME, value=10)
        self.assert_get(Parameter.FLUSH_FLOWRATE, value=100)
        self.assert_get(Parameter.FLUSH_MINFLOW, value=25)
        # self.assert_get(Parameter.FILL_VOLUME, value=425)
        self.assert_get(Parameter.FILL_VOLUME, value=10)
        self.assert_get(Parameter.FILL_FLOWRATE, value=75)
        self.assert_get(Parameter.FILL_MINFLOW, value=25)
        # self.assert_get(Parameter.CLEAR_VOLUME, value=75)
        self.assert_get(Parameter.CLEAR_VOLUME, value=10)
        self.assert_get(Parameter.CLEAR_FLOWRATE, value=100)
        self.assert_get(Parameter.CLEAR_MINFLOW, value=25)

        # Verify that readonly/immutable parameters cannot be set (throw exception)
        self.assert_set_exception(Parameter.FLUSH_VOLUME, exception_class=InstrumentParameterException)
        self.assert_set_exception(Parameter.FLUSH_FLOWRATE)
        self.assert_set_exception(Parameter.FLUSH_MINFLOW)
        self.assert_set_exception(Parameter.FILL_VOLUME)
        self.assert_set_exception(Parameter.FILL_FLOWRATE)
        self.assert_set_exception(Parameter.FILL_MINFLOW)
        self.assert_set_exception(Parameter.CLEAR_VOLUME)
        self.assert_set_exception(Parameter.CLEAR_FLOWRATE)
        self.assert_set_exception(Parameter.CLEAR_MINFLOW)

    def test_execute_clock_sync_command_mode(self):
        """
        Verify we can synchronize the instrument internal clock in command mode
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)

        # compare instrument prompt time (after processing clock sync) with current system time
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)
        ras_time = reply[1]['time']
        self.assert_time_synched(ras_time)

    def test_acquire_sample(self):
        """
        Test that we can generate sample particle with command
        """
        self.assert_initialize_driver()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE, driver_timeout=ACQUIRE_TIMEOUT)
        self.assert_state_change(ProtocolState.FLUSH, ACQUIRE_TIMEOUT)
        self.assert_state_change(ProtocolState.FILL, ACQUIRE_TIMEOUT)
        self.assert_state_change(ProtocolState.CLEAR, ACQUIRE_TIMEOUT)
        self.assert_state_change(ProtocolState.COMMAND, ACQUIRE_TIMEOUT)
        self.assert_async_particle_generation(DataParticleType.RASFL_PARSED, Mock(), 7)

    def test_clear(self):
        """
        Test user clear command
        """
        self.assert_initialize_driver()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLEAR)
        self.assert_state_change(ProtocolState.CLEAR, CLEAR_TIMEOUT)
        self.assert_state_change(ProtocolState.COMMAND, CLEAR_TIMEOUT)

    @unittest.skip('not completed yet')
    def test_obstructed_flush(self):
        """
        Test condition when obstruction limits flow rate during initial flush
        """
        # TODO

    @unittest.skip('not completed yet')
    def test_obstructed_fill(self):
        """
        Test condition when obstruction occurs during collection of sample
        """
        # TODO


################################################################################
#                            QUALIFICATION TESTS                               #
# Device specific qualification tests are for doing final testing of ion       #
# integration.  They generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                 #
################################################################################
@attr('QUAL', group='mi')
class TestQUAL(InstrumentDriverQualificationTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_discover(self):
        """
        over-ridden because instrument doesn't actually have an autosample mode and therefore
        driver will always go to command mode during the discover process after a reset.
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver and cause it to re-discover which
        # will always go back to command for this instrument
        self.assert_reset()
        self.assert_discover(ResourceAgentState.COMMAND)

    # RASFL does not poll or autosample
    # def test_poll(self):
    #     """
    #     poll for a single sample
    #     """
    #     #self.assert_sample_polled(self.assert_data_particle_sample,
    #     #                          DataParticleType.METBK_PARSED)
    #
    # def test_autosample(self):
    #     """
    #     start and stop autosample and verify data particle
    #     """
    #     #self.assert_sample_autosample(self.assert_data_particle_sample,
    #     #                              DataParticleType.METBK_PARSED,
    #     #                              sample_count=1,
    #     #                              timeout=60)

    def test_reset(self):
        """
        Verify the agent can be reset
        """
        self.assert_enter_command_mode()
        self.assert_reset()

        self.assert_enter_command_mode()
        self.assert_direct_access_start_telnet(inactivity_timeout=60, session_timeout=60)
        self.assert_state_change(ResourceAgentState.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS, 30)
        self.assert_reset()

    def test_direct_access_telnet_mode(self):
        """
        @brief This test automatically tests that the Instrument Driver properly supports direct access to the physical
        instrument. (telnet mode)
        """
        self.assert_enter_command_mode()

        # go into direct access
        self.assert_direct_access_start_telnet(timeout=600)
        self.tcp_client.send_data("port\r\n")
        if not self.tcp_client.expect("Port: 00\r\n"):
            self.fail("test_direct_access_telnet_mode: did not get expected response")

        self.assert_direct_access_stop_telnet()

    @unittest.skip('Only enabled and used for manual testing of vendor SW')
    def test_direct_access_telnet_mode_manual(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical
        instrument. (virtual serial port mode)
        """
        self.assert_enter_command_mode()

        # go direct access
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
                           kwargs={'session_type': DirectAccessTypes.vsp,
                                   'session_timeout': 600,
                                   'inactivity_timeout': 600})
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=600)
        log.warn("go_direct_access retval=" + str(retval.result))

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        print("test_direct_access_telnet_mode: waiting 120 seconds for manual testing")
        gevent.sleep(120)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

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
                ProtocolEvent.ACQUIRE_SAMPLE,
                ProtocolEvent.CLEAR,
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.GET,
                ProtocolEvent.SET,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode - no autosample for RAS
        ##################

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

    def test_execute_clock_sync(self):
        """
        Verify we can synchronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        reply = self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)

        ras_time = reply.result['time']
        self.assert_time_synched(ras_time)
