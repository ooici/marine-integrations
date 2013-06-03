"""
@package mi.instrument.hightech.hti90u_pa.ooicore.test.test_driver
@file marine-integrations/mi/instrument/hightech/hti90u_pa/ooicore/driver.py
@author Jeff Laughlin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Jeff Laughlin'
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

# Does not exist
#from mi.idk.unit_test import InstrumentDriverDataParticleMixin

# from https://github.com/unwin/marine-integrations/blob/master/mi/instrument/teledyne/workhorse_monitor_75_khz/test/test_driver.py#L37
from mi.idk.unit_test import DriverTestMixin

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.hightech.hti90u_pa.ooicore.driver import InstrumentDriver
from mi.instrument.hightech.hti90u_pa.ooicore.driver import DataParticleType
from mi.instrument.hightech.hti90u_pa.ooicore.driver import InstrumentCommand
from mi.instrument.hightech.hti90u_pa.ooicore.driver import ProtocolState
from mi.instrument.hightech.hti90u_pa.ooicore.driver import ProtocolEvent
from mi.instrument.hightech.hti90u_pa.ooicore.driver import Capability
from mi.instrument.hightech.hti90u_pa.ooicore.driver import Parameter
from mi.instrument.hightech.hti90u_pa.ooicore.driver import Protocol
from mi.instrument.hightech.hti90u_pa.ooicore.driver import Prompt
from mi.instrument.hightech.hti90u_pa.ooicore.driver import NEWLINE

import pickle

# Pickled Packet object with single sample in data channel
SHORT_SAMPLE_DICT =  {
'channels': [
              {'calib': 0.0,
               'calper': -1.0,
               'chan': 'HNE',
               'cuser1': '',
               'cuser2': '',
               'data': (-15294,),
               'duser1': 0.0,
               'duser2': 0.0,
               'iuser1': 0,
               'iuser2': 0,
               'iuser3': 0,
               'loc': '',
               'net': 'AZ',
               'nsamp': 100,
               'samprate': 100.0,
               'segtype': 'V',
               'sta': 'MONP2',
               'time': 1368920824.968393}],
 'db': (-102, -102, -102, -102),
 'dfile': None,
 'pf': {},
 'srcname': {'chan': '',
             'joined': 'AZ_MONP2/MGENC/M100',
             'loc': '',
             'net': 'AZ',
             'sta': 'MONP2',
             'subcode': 'M100',
             'suffix': 'MGENC'},
 'string': None,
 'time': 1368920824.968393,
 'type': ({'bodycode': 0,
           'content': 1,
           'desc': 'Multiplexed generic compressed data frame packet',
           'hdrcode': 0,
           'name': 'MGENC',
           'suffix': 'MGENC'},),
 'version': 2}

SHORT_SAMPLE = pickle.dumps(SHORT_SAMPLE_DICT)

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.hightech.hti90u_pa.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'FGQV9I',
    instrument_agent_name = 'hightech_hti90u_pa_ooicore',
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
class DataParticleMixin(DriverTestMixin):

    _sample_parameters = {
        HYDLF_SampleDataParticleKey.CALIB: {'type': float, 'value': SHORT_SAMPLE_DICT['channels'][0]['calib']},
        HYDLF_SampleDataParticleKey.CALPER: {'type': float, 'value': SHORT_SAMPLE_DICT['channels'][0]['calper']},
        HYDLF_SampleDataParticleKey.CHAN: {'type': str, 'value': SHORT_SAMPLE_DICT['channels'][0]['chan']},
        HYDLF_SampleDataParticleKey.LOC: {'type': str, 'value': SHORT_SAMPLE_DICT['channels'][0]['loc']},
        HYDLF_SampleDataParticleKey.NET: {'type': str, 'value': SHORT_SAMPLE_DICT['channels'][0]['net']},
        HYDLF_SampleDataParticleKey.NSAMP: {'type': float, 'value': SHORT_SAMPLE_DICT['channels'][0]['nsamp']},
        HYDLF_SampleDataParticleKey.SAMPRATE: {'type': float, 'value': SHORT_SAMPLE_DICT['channels'][0]['samprate']},
        HYDLF_SampleDataParticleKey.SEGTYPE: {'type': str, 'value': SHORT_SAMPLE_DICT['channels'][0]['segtype']},
        HYDLF_SampleDataParticleKey.STA: {'type': str, 'value': SHORT_SAMPLE_DICT['channels'][0]['sta']},
        HYDLF_SampleDataParticleKey.TIME: {'type': float, 'value': SHORT_SAMPLE_DICT['channels'][0]['time']},
        HYDLF_SampleDataParticleKey.SAMPLE_IDX: {'type': int, 'value': 0},
        HYDLF_SampleDataParticleKey.SAMPLE: {'type': int, 'value': SHORT_SAMPLE_DICT['channels'][0]['data'][0]},
    }

    def assert_sample_data_particle(self, data_particle):
        '''
        Verify a particle is a known particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unknown type produced by the driver
        '''
        sample_dict = self.convert_data_particle_to_dict(data_particle)
        if (sample_dict[DataParticleKey.STREAM_NAME] == DataParticleType.HYDLF_SAMPLE):
            self.assert_data_particle_sample(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_data_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify an optaa sample data particle
        @param data_particle: HYDLFA_SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.HYDLF_SAMPLE)
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
class DriverUnitTest(InstrumentDriverUnitTestCase, DataParticleMixin):
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

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        #self.assert_enum_complete(Capability(), ProtocolEvent())  Capability is empty, so this test fails


    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_particle_published(driver, SHORT_SAMPLE, self.assert_data_particle_sample, True)

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
