"""
@package mi.instrument.ooici.mi.test_driver.test.test_driver
@file marine-integrations/mi/instrument/ooici/mi/test_driver/driver.py
@author Bill French
@brief Test cases for test_driver driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import unittest
import gevent

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.data_particle import RawDataParticle
from mi.core.instrument.data_particle import DataParticleKey

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.ooici.mi.test_driver.driver import InstrumentDriver
from mi.instrument.ooici.mi.test_driver.driver import DataParticleType
from mi.instrument.ooici.mi.test_driver.driver import InstrumentCommand
from mi.instrument.ooici.mi.test_driver.driver import ProtocolState
from mi.instrument.ooici.mi.test_driver.driver import ProtocolEvent
from mi.instrument.ooici.mi.test_driver.driver import Capability
from mi.instrument.ooici.mi.test_driver.driver import ParameterName
from mi.instrument.ooici.mi.test_driver.driver import Protocol
from mi.instrument.ooici.mi.test_driver.driver import Prompt
from mi.instrument.ooici.mi.test_driver.driver import NEWLINE

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.ooici.mi.test_driver.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'TB6W7G',
    instrument_agent_name = 'ooici_mi_test_driver',
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
    def assertSampleDataParticle(self, data_particle):
        '''
        Verify a particle is a know particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''
        particle = self.convert_data_particle_to_dict(data_particle)
        stream_name = particle[DataParticleKey.STREAM_NAME]

        if (stream_name == DataParticleType.RAW):
            self.assert_particle_raw(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % particle)
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
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())


    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)


    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)


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
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, DriverTestMixinSub):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def init_port_agent(self):
        pass

    def stop_port_agent(self):
        pass

    def port_agent_comm_config(self):
        return {
            'addr': 'localhost',
            'port': 8080,
            'cmd_port': 8081
        }

    def test_driver_process(self):
        pass

    def test_set(self):
        self.assert_initialize_driver()

        # Verify defaults
        self.assert_get(ParameterName.PAYLOAD_SIZE, 1024)
        self.assert_get(ParameterName.SAMPLE_INTERVAL, 1)

        # Try and update
        self.assert_set(ParameterName.PAYLOAD_SIZE, 2048, False)
        self.assert_set(ParameterName.SAMPLE_INTERVAL, 2, False)

    def test_autosample(self):
        """
        Verify that we can enter streaming and that all particles are produced
        properly.

        Because we have to test for three different data particles we can't use
        the common assert_sample_autosample method
        """
        duration = 10

        self.assert_initialize_driver()
        self.assert_set(ParameterName.SAMPLE_INTERVAL, 1)
        self.assert_set(ParameterName.PAYLOAD_SIZE, 1024*1024)

        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)

        gevent.sleep(duration)
        samples = self.get_sample_events(DataParticleType.RAW)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        self.assertGreaterEqual(len(samples), duration-1)

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

    def init_port_agent(self):
        pass

    def stop_port_agent(self):
        pass

    def port_agent_comm_config(self):
        return {
            'addr': 'localhost',
            'port': 8080,
            'cmd_port': 8081
        }

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        self.assert_enter_command_mode()
        self.assert_start_autosample()

        gevent.sleep(10)

        self.assert_stop_autosample()

    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get set properly, this includes
        ensuring that read only parameters fail on set.
        '''
        self.assert_enter_command_mode()
        self.assert_set_parameter(ParameterName.PAYLOAD_SIZE, 2048)
        self.assert_set_parameter(ParameterName.SAMPLE_INTERVAL, 1)

    ###
    #   Global tests that don't work with this driver
    ###
    def test_reset(self):
        pass

    def test_instrument_agent_common_state_model_lifecycle(self):
        pass

    def test_direct_access_telnet_closed(self):
        pass

    def test_discover(self):
        pass




