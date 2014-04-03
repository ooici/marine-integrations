"""
@package mi.instrument.noaa.syst.ooicore.test.test_driver
@file marine-integrations/mi/instrument/noaa/syst/ooicore/driver.py
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
from mi.core.instrument.data_particle import RawDataParticle

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

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

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from pyon.core.exception import Conflict
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from mi.instrument.noaa.botpt.syst.driver import InstrumentDriver
from mi.instrument.noaa.botpt.syst.driver import DataParticleType
from mi.instrument.noaa.botpt.syst.driver import InstrumentCommand
from mi.instrument.noaa.botpt.syst.driver import ProtocolState
from mi.instrument.noaa.botpt.syst.driver import ProtocolEvent
from mi.instrument.noaa.botpt.syst.driver import Capability
from mi.instrument.noaa.botpt.syst.driver import Parameter
from mi.instrument.noaa.botpt.syst.driver import Protocol
from mi.instrument.noaa.botpt.syst.driver import Prompt
from mi.instrument.noaa.botpt.syst.driver import NEWLINE

GO_ACTIVE_TIMEOUT = 180

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.noaa.botpt.syst.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id='DZWXL3',
    instrument_agent_name='noaa_syst_ooicore',
    instrument_agent_packet_config=DataParticleType(),

    driver_startup_config={}
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
class BOTPTTestMixinSub(DriverTestMixin):
    def assert_sample_data_particle(self, data_particle):
        """
        Verify a particle is a know particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unknown type produced by the driver
        """
        if isinstance(data_particle, RawDataParticle):
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
class DriverUnitTest(InstrumentDriverUnitTestCase, BOTPTTestMixinSub):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

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

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        print 'Cabability: ' + repr(Capability().list())
        print 'Event: ' + repr(ProtocolEvent().list())
        self.assert_enum_has_no_duplicates(Capability())
        # DHE: there are no capabilities so this next test would fail.
        #self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        StringChunker(Protocol.sieve_function)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

    # noinspection PyProtectedMember
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

    def assert_initialize_driver(self, final_state=DriverProtocolState.AUTOSAMPLE):
        """
        Walk an uninitialized driver through it's initialize process.  Verify the final
        state is command mode.  If the final state is auto sample then we will stop
        which should land us in autosample
        """
        log.info("test_connect test started")

        # Test the driver is in state unconfigured.
        self.assert_current_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        self.assert_current_state(DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        self.assert_current_state(DriverProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        self.driver_client.cmd_dvr('discover_state')

        # Assert that this driver is in streaming mode
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverProtocolState.AUTOSAMPLE)


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

    # Overridden because does not apply for this driver
    def assert_sample_autosample(self, sample_data_assert, sample_queue,
                                 timeout=GO_ACTIVE_TIMEOUT, sample_count=3):
        pass

    # Overridden because base class tries to do direct access
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

    # Overridden because does not apply for this driver
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access
        to the physical instrument. (telnet mode)
        """
        pass

    # Overridden because does not apply for this driver
    def test_poll(self):
        """
        No polling for a single sample
        """

    # Overridden because does not apply for this driver
    def test_get_set_parameters(self):
        """
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        """
        pass

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

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()
