"""
@package mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.test.test_driver
@file marine-integrations/mi/instrument/seabird/sbe16plus_v2/ctdpf_jb/driver.py
@author Tapana Gupta
@brief Test cases for ctdpf_jb driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Tapana Gupta'
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

from mi.instrument.seabird.sbe16plus_v2.test.test_driver import SBEUnitTestCase

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolState
from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolEvent
from mi.instrument.seabird.sbe16plus_v2.driver import Capability
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16Protocol
from mi.instrument.seabird.sbe16plus_v2.driver import Prompt

from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import SBE19InstrumentDriver
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import DataParticleType
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import InstrumentCommand
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import ProtocolState
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import ProtocolEvent
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import Capability
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import Parameter
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import Prompt
from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import NEWLINE

from mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver import SBE19Protocol

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe16plus_v2.ctdpf_jb.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'JI22B5',
    instrument_agent_name = 'seabird_sbe16plus_v2_ctdpf_jb',
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
#class DriverTestMixinSub(DriverTestMixin):
#    def assertSampleDataParticle(self, data_particle):
#        '''
#        Verify a particle is a know particle to this driver and verify the particle is
#        correct
#        @param data_particle: Data particle of unkown type produced by the driver
#        '''
#        if (isinstance(data_particle, RawDataParticle)):
#            self.assert_particle_raw(data_particle)
#        else:
#            log.error("Unknown Particle Detected: %s" % data_particle)
#            self.assertFalse(True)


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
class SBE19UnitTestCase(SBEUnitTestCase):


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
        pass


    def test_chunker(self):
        pass


    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = SBE19InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)


    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.TEST: ['DRIVER_EVENT_GET',
                                 'DRIVER_EVENT_RUN_TEST'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_ACQUIRE_SAMPLE',
                                    'DRIVER_EVENT_ACQUIRE_STATUS',
                                    'DRIVER_EVENT_CLOCK_SYNC',
                                    'DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_TEST',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT',
                                    'PROTOCOL_EVENT_GET_CONFIGURATION',
                                    'PROTOCOL_EVENT_RESET_EC',
                                    'DRIVER_EVENT_SCHEDULED_CLOCK_SYNC'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_GET',
                                       'PROTOCOL_EVENT_QUIT_SESSION',
                                       'DRIVER_EVENT_STOP_AUTOSAMPLE',
                                       'PROTOCOL_EVENT_GET_CONFIGURATION',
                                       'DRIVER_EVENT_SCHEDULED_CLOCK_SYNC',
                                       'DRIVER_EVENT_ACQUIRE_STATUS'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 'EXECUTE_DIRECT']
        }

        #driver = self.InstrumentDriver(self._got_data_event_callback)
        driver = SBE19InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


    def test_parse_ds(self):
        pass


    def test_parse_set_response(self):
        pass


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
