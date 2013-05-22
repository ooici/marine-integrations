"""
@package mi.instrument.star.asimet.ooicore.test.test_driver
@file marine-integrations/mi/instrument/star/aismet/ooicore/driver.py
@author Bill Bollenbacher
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

import unittest
import gevent

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.common import BaseEnum
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue

from mi.instrument.star.asimet.ooicore.driver import InstrumentDriver
from mi.instrument.star.asimet.ooicore.driver import DataParticleType
from mi.instrument.star.asimet.ooicore.driver import Command
from mi.instrument.star.asimet.ooicore.driver import ProtocolState
from mi.instrument.star.asimet.ooicore.driver import ProtocolEvent
from mi.instrument.star.asimet.ooicore.driver import Capability
from mi.instrument.star.asimet.ooicore.driver import Parameter
from mi.instrument.star.asimet.ooicore.driver import Protocol
from mi.instrument.star.asimet.ooicore.driver import Prompt
from mi.instrument.star.asimet.ooicore.driver import NEWLINE
from mi.instrument.star.asimet.ooicore.driver import METBK_SampleDataParticleKey
from mi.instrument.star.asimet.ooicore.driver import METBK_SampleDataParticle
from mi.instrument.star.asimet.ooicore.driver import METBK_StatusDataParticleKey
from mi.instrument.star.asimet.ooicore.driver import METBK_StatusDataParticle

from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException, InstrumentCommandException, Conflict
from interface.objects import AgentCommand

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from pyon.agent.agent import ResourceAgentEvent
from pyon.agent.agent import ResourceAgentState

from struct import pack


METBK_STATUS_DATA = "??" + NEWLINE +\
                    "Model: NEWLGR53" + NEWLINE +\
                    "SerNum: 17DEC12" + NEWLINE +\
                    "CfgDat: 17DEC12" + NEWLINE +\
                    "Firmware: LOGR53 v4.11cf" + NEWLINE +\
                    "RTClock: 2013/05/21  13:55:51" + NEWLINE +\
                    "Logging Interval: 60; Current Tick: 6" + NEWLINE +\
                    "R-interval: 1" + NEWLINE +\
                    "Compact Flash Card present - Compact Flash OK!" + NEWLINE +\
                    "Main Battery Voltage:  12.50" + NEWLINE +\
                    "Failed last attempt to update PTT module" + NEWLINE +\
                    "46B1BAD3E8E9FF7F9681300017D1F446ADBED76909FE7F9601200017D1F4706A" + NEWLINE +\
                    "46A9BED82911FE7F9601400017D1F446A5C2D668F1FE7F9581400017D1F4FFA6" + NEWLINE +\
                    "46A1BED628D9FE7F9581400017D1F4469DC2D7E8C1FE7F9501500017D1F40B4F" + NEWLINE +\
                    "Sampling GO" + NEWLINE

# Globals
raw_stream_received = False
parsed_stream_received = False

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.star.asimet.ooicore.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'DQPJJX',
    instrument_agent_name = 'star_aismet_ooicore',
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
    '''
    Mixin class used for storing data particle constants and common data assertion methods.
    '''
    # Create some short names for the parameter test config
    TYPE      = ParameterTestConfigKey.TYPE
    READONLY  = ParameterTestConfigKey.READONLY
    STARTUP   = ParameterTestConfigKey.STARTUP
    DA        = ParameterTestConfigKey.DIRECT_ACCESS
    VALUE     = ParameterTestConfigKey.VALUE
    REQUIRED  = ParameterTestConfigKey.REQUIRED
    DEFAULT   = ParameterTestConfigKey.DEFAULT
    STATES    = ParameterTestConfigKey.STATES

    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {Parameter.CLOCK: {TYPE: unicode, VALUE: "2013/05/21  15:46:30", REQUIRED: True}}

    ###
    # Data Particle Parameters
    ### 
    _sample_parameters = {
        # particle data defined in the OPTAA Driver doc
        METBK_SampleDataParticleKey.RECORD_LENGTH : {'type': int, 'value': 680 },
        METBK_SampleDataParticleKey.PACKET_TYPE : {'type': int, 'value': 5 },
        METBK_SampleDataParticleKey.METER_TYPE : {'type': int, 'value': 83 },
        METBK_SampleDataParticleKey.SERIAL_NUMBER : {'type': int, 'value': 130},
        METBK_SampleDataParticleKey.A_REFERENCE_DARK_COUNTS : {'type': int, 'value': 0x1ce },
        METBK_SampleDataParticleKey.PRESSURE_COUNTS : {'type': int, 'value': 0xffff },
        METBK_SampleDataParticleKey.A_SIGNAL_DARK_COUNTS : {'type': int, 'value': 0x2b0 },
        METBK_SampleDataParticleKey.EXTERNAL_TEMP_RAW : {'type': int, 'value': 0x6e47 },
        METBK_SampleDataParticleKey.INTERNAL_TEMP_RAW : {'type': int, 'value': 0xa84f },
        METBK_SampleDataParticleKey.C_REFERENCE_DARK_COUNTS : {'type': int, 'value': 0x1d5 },
        METBK_SampleDataParticleKey.C_SIGNAL_DARK_COUNTS : {'type': int, 'value': 0x2bd },
        METBK_SampleDataParticleKey.ELAPSED_RUN_TIME : {'type': int, 'value': 0x0000284d },
        METBK_SampleDataParticleKey.NUM_WAVELENGTHS : {'type': int, 'value': 81 },
        METBK_SampleDataParticleKey.C_REFERENCE_COUNTS : {'type': list, 'value': [1391, 1632, 1889, 2168, 2473, 2817, 3196, 3611, 4060, 4532, 
                                                                                  5020, 5530, 6058, 6645, 7292, 7964, 8657, 9387, 10139, 10907, 
                                                                                  11687, 12495, 13313, 14139, 14990, 15888, 16843, 17865, 18964, 20119, 
                                                                                  21298, 22437, 23526, 24538, 25494, 26419, 27271, 28060, 28759, 29311, 
                                                                                  29941, 30478, 30928, 31284, 31536, 31673, 31706, 31630, 31449, 31170, 
                                                                                  30786, 30326, 29767, 29146, 28508, 27801, 27011, 26145, 25186, 23961, 
                                                                                  22897, 22027, 21024, 19988, 18945, 17919, 16928, 15976, 15070, 14210, 
                                                                                  13386, 12602, 11856, 11145, 10493, 9884, 9317, 8785, 8292, 7835, 
                                                                                  7418]},
        METBK_SampleDataParticleKey.A_REFERENCE_COUNTS : {'type': list, 'value': [1273, 1499, 1744, 2012, 2304, 2632, 2995, 3395, 3825, 4283, 
                                                                                  4759, 5262, 5780, 6358, 7001, 7668, 8360, 9089, 9848, 10630, 
                                                                                  11421, 12252, 13103, 13961, 14849, 15792, 16786, 17853, 19000, 20216, 
                                                                                  21461, 22682, 23850, 24975, 26048, 27059, 28020, 28925, 29739, 30363, 
                                                                                  31158, 31855, 32457, 32970, 33385, 33680, 33849, 33911, 33858, 33705, 
                                                                                  33440, 33074, 32609, 32047, 31455, 30828, 30101, 29283, 28383, 27271, 
                                                                                  26039, 25148, 24144, 23069, 21974, 20877, 19811, 18773, 17771, 16822, 
                                                                                  15905, 15025, 14190, 13383, 12622, 11927, 11270, 10655, 10081, 9547,
                                                                                   9054]},
        METBK_SampleDataParticleKey.C_SIGNAL_COUNTS : {'type': list, 'value':    [1225, 1471, 1743, 2040, 2369, 2739, 3159, 3616, 4118, 4652, 
                                                                                  5210, 5797, 6409, 7074, 7834, 8620, 9436, 10292, 11191, 12109, 
                                                                                  13049, 14020, 15015, 16023, 17058, 18145, 19307, 20544, 21881, 23294, 
                                                                                  24745, 26163, 27517, 28808, 29991, 31187, 32273, 33304, 34225, 35010, 
                                                                                  35858, 36596, 37226, 37743, 38136, 38389, 38509, 38499, 38352, 38088, 
                                                                                  37686, 37197, 36591, 35870, 35148, 34353, 33438, 32425, 31315, 29877, 
                                                                                  28439, 27497, 26268, 24992, 23712, 22441, 21210, 20025, 18889, 17816, 
                                                                                  16790, 15808, 14876, 13982, 13165, 12405, 11693, 11025, 10408, 9838, 
                                                                                  9313]},
        METBK_SampleDataParticleKey.A_SIGNAL_COUNTS : {'type': list, 'value':    [918, 1159, 1419, 1696, 1994, 2325, 2693, 3100, 3544, 4020, 
                                                                                  4524, 5059, 5620, 6249, 6953, 7691, 8466, 9294, 10160, 11062, 
                                                                                  11989, 12968, 13982, 15017, 16095, 17242, 18459, 19770, 21185, 22692, 
                                                                                  24244, 25782, 27277, 28734, 30144, 31494, 32790, 34031, 35172, 36101, 
                                                                                  37239, 38270, 39191, 40009, 40707, 41269, 41678, 41953, 42084, 42087, 
                                                                                  41950, 41680, 41279, 40748, 40160, 39515, 38734, 37824, 36791, 35473, 
                                                                                  33988, 32910, 31676, 30340, 28963, 27574, 26213, 24882, 23594, 22367, 
                                                                                  21182, 20041, 18950, 17898, 16905, 15993, 15133, 14323, 13567, 12864, 
                                                                                  12217]}
        }   
                        
    _status_parameters = {
        METBK_StatusDataParticleKey.FIRMWARE_VERSION : {'type': unicode, 'value': '1.10'},
        METBK_StatusDataParticleKey.FIRMWARE_DATE : {'type': unicode, 'value': 'May 16 2005 09:40:13' },
        METBK_StatusDataParticleKey.PERSISTOR_CF_SERIAL_NUMBER : {'type': int, 'value': 12154 },
        METBK_StatusDataParticleKey.PERSISTOR_CF_BIOS_VERSION : {'type': unicode, 'value': '2.28'},
        METBK_StatusDataParticleKey.PERSISTOR_CF_PICODOS_VERSION : {'type': unicode, 'value': '2.28'},
        }

# Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    ###
    # Data Particle Parameters Methods
    ### 
    def assert_sample_data_particle(self, data_particle):
        '''
        Verify a particle is a known particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unknown type produced by the driver
        '''
        sample_dict = self.convert_data_particle_to_dict(data_particle)
        if (sample_dict[DataParticleKey.STREAM_NAME] == DataParticleType.METBK_SAMPLE):
            self.assert_data_particle_sample(data_particle)
        elif (sample_dict[DataParticleKey.STREAM_NAME] == DataParticleType.METBK_STATUS):
            self.assert_data_particle_status(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_data_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify an optaa sample data particle
        @param data_particle: OPTAAA_SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.METBK_SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_data_particle_short_sample(self, data_particle, verify_values = False):
        '''
        Verify an optaa short sample data particle
        @param data_particle: OPTAAA_SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.METBK_SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._short_sample_parameters, verify_values)

    def assert_data_particle_status(self, data_particle, verify_values = False):
        """
        Verify an optaa status data particle
        @param data_particle: OPTAAA_StatusDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_header(data_particle, DataParticleType.METBK_STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_parameters, verify_values)
        
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

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        #self.assert_enum_complete(Capability(), ProtocolEvent())  Capability is empty, so this test fails


    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, ShortSample())
        self.assert_chunker_sample_with_noise(chunker, ShortSample())
        self.assert_chunker_fragmented_sample(chunker, ShortSample())
        self.assert_chunker_combined_sample(chunker, ShortSample())

        self.assert_chunker_sample(chunker, METBK_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, METBK_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, METBK_SAMPLE)
        self.assert_chunker_combined_sample(chunker, METBK_SAMPLE)

        self.assert_chunker_sample(chunker, METBK_STATUS_DATA)
        self.assert_chunker_sample_with_noise(chunker, METBK_STATUS_DATA)
        self.assert_chunker_fragmented_sample(chunker, METBK_STATUS_DATA)
        self.assert_chunker_combined_sample(chunker, METBK_STATUS_DATA)


    def test_corrupt_data_sample(self):
        # garbage is not okay
        particle = METBK_SampleDataParticle(METBK_SAMPLE.replace('\x00\x00\x7b', 'foo'),
                                            port_timestamp = 3558720820.531179)
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

        # validating data particles
        """
        self.assert_particle_published(driver, METBK_STATUS_DATA, self.assert_data_particle_status, True)
        self.assert_particle_published(driver, METBK_SAMPLE, self.assert_data_particle_sample, True)
        """
        self.assert_particle_published(driver, ShortSample(), self.assert_data_particle_sample, True)


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
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.COMMAND: ['DRIVER_EVENT_GET',
                                    'DRIVER_EVENT_SET',
                                    'DRIVER_EVENT_START_AUTOSAMPLE',
                                    'DRIVER_EVENT_START_DIRECT'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 
                                          'EXECUTE_DIRECT']
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)


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

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample.
        To test status particle instrument must be off and powered on will test is waiting
        """
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        print("waiting 30 seconds for instrument data")
        self.assert_async_particle_generation(DataParticleType.METBK_PARSED, self.assert_sample_data_particle, timeout=30)

    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply)


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

    @unittest.skip('Only enabled and used for manual testing of vendor SW')
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (virtual serial port mode)
        """
        self.assert_enter_command_mode()

        # go direct access
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            kwargs={'session_type': DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=600)
        log.warn("go_direct_access retval=" + str(retval.result))

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)
        
        print("test_direct_access_telnet_mode: waiting 120 seconds for manual testing")
        gevent.sleep(120)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        retval = self.instrument_agent_client.execute_agent(cmd) 

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

    def test_discover(self):
        """
        over-ridden because instrument doesn't actually have a command mode and therefore
        driver will always go to autosample mode during the discover process after a reset.
        verify we can discover our instrument state from streaming and autosample.  This
        method assumes that the instrument has a command and streaming mode. If not you will
        need to explicitly overload this test in your driver tests.
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver and cause it to re-discover which
        # will always go back to autosample for this instrument
        self.assert_reset()
        self.assert_discover(ResourceAgentState.STREAMING)


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
                DriverEvent.START_AUTOSAMPLE
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
            }

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            DriverEvent.STOP_AUTOSAMPLE,
        ]

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
