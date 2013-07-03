"""
@package mi.instrument.star_asimet.bulkmet.metbk_a.test.test_driver
@file marine-integrations/mi/instrument/star_aismet/bulkmet/metbk_a/test/test_driver.py
@author Bill Bollenbacher
@brief Test cases for metbk_a driver

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
import time
import re

from interface.objects import AgentCapability
from interface.objects import CapabilityType

from nose.plugins.attrib import attr
from mock import Mock
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import InstrumentDriverPublicationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.unit_test import DriverStartupConfigKey

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

from mi.instrument.star_asimet.bulkmet.metbk_a.driver import InstrumentDriver
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import DataParticleType
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import Command
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import ProtocolState
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import ProtocolEvent
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import Capability
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import Parameter
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import Protocol
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import Prompt
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import NEWLINE
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import METBK_SampleDataParticleKey
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import METBK_SampleDataParticle
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import METBK_StatusDataParticleKey
from mi.instrument.star_asimet.bulkmet.metbk_a.driver import METBK_StatusDataParticle

from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException, InstrumentCommandException, Conflict
from interface.objects import AgentCommand

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from pyon.agent.agent import ResourceAgentEvent
from pyon.agent.agent import ResourceAgentState
from mi.idk.exceptions import IDKException

from struct import pack

# Globals
raw_stream_received = False
parsed_stream_received = False

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.star_asimet.bulkmet.metbk_a.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'DQPJJX',
    instrument_agent_name = 'star_aismet_ooicore',
    instrument_agent_packet_config = DataParticleType(),
    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            Parameter.SAMPLE_INTERVAL: 20,
        },
    }
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

    METBK_STATUS_DATA = "Model: NEWLGR53" + NEWLINE +\
                        "SerNum: 17DEC12" + NEWLINE +\
                        "CfgDat: 17DEC12" + NEWLINE +\
                        "Firmware: LOGR53 v4.11cf" + NEWLINE +\
                        "RTClock: 2013/05/21  13:55:51" + NEWLINE +\
                        "Logging Interval: 60; Current Tick: 6" + NEWLINE +\
                        "R-interval: 1" + NEWLINE +\
                        "Compact Flash Card present - Compact Flash OK!" + NEWLINE +\
                        "Main Battery Voltage:  12.50" + NEWLINE +\
                        "Failed last attempt to update PTT module" + NEWLINE +\
                        "TMP failed" + NEWLINE +\
                        "46B1BAD3E8E9FF7F9681300017D1F446ADBED76909FE7F9601200017D1F4706A" + NEWLINE +\
                        "46A9BED82911FE7F9601400017D1F446A5C2D668F1FE7F9581400017D1F4FFA6" + NEWLINE +\
                        "46A1BED628D9FE7F9581400017D1F4469DC2D7E8C1FE7F9501500017D1F40B4F" + NEWLINE +\
                        "Sampling GO" + NEWLINE
    
    METBK_SAMPLE_DATA1 = "1012.53  44.543  24.090    0.0    1.12  24.240  0.0000 32788.7   -0.03   -0.02  0.0000 12.50" + NEWLINE
    METBK_SAMPLE_DATA2 = "1013.53  44.543  24.090    0.0    1.12  24.240  0.0000 32788.7   -0.03   -0.02  0.0000 12.50" + NEWLINE
    
    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.START_AUTOSAMPLE : {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_AUTOSAMPLE : {STATES: [ProtocolState.AUTOSAMPLE]},
        Capability.CLOCK_SYNC : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE, ProtocolState.SYNC_CLOCK]},
        Capability.ACQUIRE_SAMPLE : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.ACQUIRE_STATUS : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.FLASH_STATUS : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
    }

    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {Parameter.CLOCK: {TYPE: str, READONLY: True, DA: False, STARTUP: False, VALUE: "2013/05/21  15:46:30", REQUIRED: True},
                          Parameter.SAMPLE_INTERVAL: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 20, REQUIRED: True}}

    ###
    # Data Particle Parameters
    ### 
    _sample_parameters = {
        # particle data defined in the OPTAA Driver doc
        METBK_SampleDataParticleKey.BAROMETRIC_PRESSURE : {'type': float, 'value': 1012.53},
        METBK_SampleDataParticleKey.RELATIVE_HUMIDITY : {'type': float, 'value': 44.543},
        METBK_SampleDataParticleKey.AIR_TEMPERATURE : {'type': float, 'value': 24.09},
        METBK_SampleDataParticleKey.LONGWAVE_IRRADIANCE : {'type': float, 'value': 0.0},
        METBK_SampleDataParticleKey.PRECIPITATION : {'type': float, 'value': 1.12},
        METBK_SampleDataParticleKey.SEA_SURFACE_TEMPERATURE : {'type': float, 'value': 24.24},
        METBK_SampleDataParticleKey.SEA_SURFACE_CONDUCTIVITY : {'type': float, 'value': 0.0},
        METBK_SampleDataParticleKey.SHORTWAVE_IRRADIANCE : {'type': float, 'value': 32788.7},
        METBK_SampleDataParticleKey.EASTWARD_WIND_VELOCITY : {'type': float, 'value': -0.03},
        METBK_SampleDataParticleKey.NORTHWARD_WIND_VELOCITY : {'type': float, 'value': -0.02}
        }   
                        
    _status_parameters = {
        METBK_StatusDataParticleKey.INSTRUMENT_MODEL : {'type': unicode, 'value': 'NEWLGR53'},
        METBK_StatusDataParticleKey.SERIAL_NUMBER : {'type': unicode, 'value': '17DEC12'},
        METBK_StatusDataParticleKey.CALIBRATION_DATE : {'type': unicode, 'value': '17DEC12'},
        METBK_StatusDataParticleKey.FIRMWARE_VERSION : {'type': unicode, 'value': 'LOGR53 v4.11cf'},
        METBK_StatusDataParticleKey.DATE_TIME_STRING : {'type': unicode, 'value': '2013/05/21  13:55:51'},
        METBK_StatusDataParticleKey.LOGGING_INTERVAL : {'type': int, 'value': 60},
        METBK_StatusDataParticleKey.CURRENT_TICK : {'type': int, 'value': 6},
        METBK_StatusDataParticleKey.RECENT_RECORD_INTERVAL : {'type': int, 'value': 1},
        METBK_StatusDataParticleKey.FLASH_CARD_PRESENCE : {'type': unicode, 'value': 'Compact Flash Card present - Compact Flash OK!'},
        METBK_StatusDataParticleKey.BATTERY_VOLTAGE_MAIN : {'type': float, 'value': 12.50},
        METBK_StatusDataParticleKey.FAILURE_MESSAGES : {'type': list, 'value': ["Failed last attempt to update PTT module",
                                                                                "TMP failed"]},
        METBK_StatusDataParticleKey.PTT_ID1 : {'type': unicode, 'value': '46B1BAD3E8E9FF7F9681300017D1F446ADBED76909FE7F9601200017D1F4706A'},
        METBK_StatusDataParticleKey.PTT_ID2 : {'type': unicode, 'value': '46A9BED82911FE7F9601400017D1F446A5C2D668F1FE7F9581400017D1F4FFA6'},
        METBK_StatusDataParticleKey.PTT_ID3 : {'type': unicode, 'value': '46A1BED628D9FE7F9581400017D1F4469DC2D7E8C1FE7F9501500017D1F40B4F'},
        METBK_StatusDataParticleKey.SAMPLING_STATE : {'type': unicode, 'value': 'GO'},
        }

# Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False, verify_sample_interval=False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)
        if verify_sample_interval:
            self.assertEqual(current_parameters[Parameter.SAMPLE_INTERVAL], 
                             self._driver_parameters[Parameter.SAMPLE_INTERVAL][self.VALUE], 
                             "sample_interval %d != expected value %d" %(current_parameters[Parameter.SAMPLE_INTERVAL],
                                                          self._driver_parameters[Parameter.SAMPLE_INTERVAL][self.VALUE]))

    def assert_sample_interval_parameter(self, current_parameters, verify_values = False):
        """
        Verify that sample_interval parameter is correct and potentially verify value.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, False)
        self.assertEqual(current_parameters[Parameter.SAMPLE_INTERVAL], 
                         self._driver_parameters[Parameter.SAMPLE_INTERVAL][self.VALUE], 
                         "sample_interval %d != expected value %d" %(current_parameters[Parameter.SAMPLE_INTERVAL],
                                                      self._driver_parameters[Parameter.SAMPLE_INTERVAL][self.VALUE]))

    ###
    # Data Particle Parameters Methods
    ### 
    def assert_data_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify an optaa sample data particle
        @param data_particle: OPTAAA_SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.METBK_PARSED)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_data_particle_status(self, data_particle, verify_values = False):
        """
        Verify an optaa status data particle
        @param data_particle: OPTAAA_StatusDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_header(data_particle, DataParticleType.METBK_STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_parameters, verify_values)
        
    def assert_particle_not_published(self, driver, sample_data, particle_assert_method, verify_values = False):
        try:
            self.assert_particle_published(driver, sample_data, particle_assert_method, verify_values)
        except AssertionError as e:
            if str(e) == "0 != 1":
                return
            else:
                raise e
        else:
            raise IDKException("assert_particle_not_published: particle was published")
        
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
        self.assert_enum_has_no_duplicates(Command())

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())  


    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, self.METBK_SAMPLE_DATA1)
        self.assert_chunker_sample_with_noise(chunker, self.METBK_SAMPLE_DATA1)
        self.assert_chunker_fragmented_sample(chunker, self.METBK_SAMPLE_DATA1)
        self.assert_chunker_combined_sample(chunker, self.METBK_SAMPLE_DATA1)        
        
        self.assert_chunker_sample(chunker, self.METBK_STATUS_DATA)
        self.assert_chunker_sample_with_noise(chunker, self.METBK_STATUS_DATA)
        self.assert_chunker_fragmented_sample(chunker, self.METBK_STATUS_DATA)
        self.assert_chunker_combined_sample(chunker, self.METBK_STATUS_DATA)

    def test_corrupt_data_sample(self):
        # garbage is not okay
        particle = METBK_SampleDataParticle(self.METBK_SAMPLE_DATA1.replace('-0.03', 'foo'),
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

        # validating data particles are published
        self.assert_particle_published(driver, self.METBK_STATUS_DATA, self.assert_data_particle_status, True)
        self.assert_particle_published(driver, self.METBK_SAMPLE_DATA1, self.assert_data_particle_sample, True)
        
        # validate that a duplicate sample is not published
        self.assert_particle_not_published(driver, self.METBK_SAMPLE_DATA1, self.assert_data_particle_sample, True)
        
        # validate that a new sample is published
        self.assert_particle_published(driver, self.METBK_SAMPLE_DATA2, self.assert_data_particle_sample, False)


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
                                    'DRIVER_EVENT_START_DIRECT',
                                    'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                    'DRIVER_EVENT_ACQUIRE_STATUS',
                                    'DRIVER_EVENT_CLOCK_SYNC',
                                    'DRIVER_EVENT_FLASH_STATUS'],
            ProtocolState.AUTOSAMPLE: ['DRIVER_EVENT_STOP_AUTOSAMPLE',
                                       'DRIVER_EVENT_GET',
                                       'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                       'DRIVER_EVENT_ACQUIRE_STATUS',
                                       'DRIVER_EVENT_CLOCK_SYNC',
                                       'DRIVER_EVENT_FLASH_STATUS'],
            ProtocolState.DIRECT_ACCESS: ['DRIVER_EVENT_STOP_DIRECT', 
                                          'EXECUTE_DIRECT'],
            ProtocolState.SYNC_CLOCK: ['DRIVER_EVENT_CLOCK_SYNC']
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
                self.fail("assert_async_particle_not_generated: a particle of type %s was published" %particle_type)
            time.sleep(.3)

    def test_acquire_sample(self):
        """
        Test that we can generate sample particle with command
        """
        self.assert_initialize_driver()
        self.assert_particle_generation(ProtocolEvent.ACQUIRE_SAMPLE, DataParticleType.METBK_PARSED, self.assert_data_particle_sample)

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample.
        To test status particle instrument must be off and powered on will test is waiting
        """
        # put driver into autosample mode
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        # test that sample particle is generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for instrument data")
        self.assert_async_particle_generation(DataParticleType.METBK_PARSED, self.assert_data_particle_sample, timeout=90)
        
        # take driver out of autosample mode
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)
        
        # test that sample particle is not generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for no instrument data")
        self.clear_events()
        self.assert_async_particle_not_generated(DataParticleType.METBK_PARSED, timeout=90)
        
        # put driver back in autosample mode
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        
        # test that sample particle is generated
        log.debug("test_autosample_particle_generation: waiting 60 seconds for instrument data")
        self.assert_async_particle_generation(DataParticleType.METBK_PARSED, self.assert_data_particle_sample, timeout=90)

    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, verify_sample_interval=True)

    def assert_clock_synced(self):
        """
        Verify the clock is set to the current time with in a few seconds.
        """
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.CLOCK)

        # convert driver's time from formatted date/time string to seconds integer
        instrument_time = time.mktime(time.strptime(reply.get(Parameter.CLOCK).lower(), "%Y/%m/%d %H:%M:%S"))

        # need to convert local machine's time to date/time string and back to seconds to 'drop' the DST attribute so test passes
        # get time from local machine
        lt = time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        # convert local time from formatted date/time string to seconds integer to drop DST
        local_time = time.mktime(time.strptime(lt, "%d %b %Y %H:%M:%S"))

        # Now verify that the time matches to within 5 seconds
        self.assertLessEqual(abs(instrument_time - local_time), 5)

    def test_commands(self):
        """
        Run instrument commands from both command and streaming mode.
        """
        self.assert_initialize_driver()

        ####
        # First test in command mode
        ####
        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC, assert_function=self.assert_clock_synced)
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(DataParticleType.METBK_PARSED, self.assert_data_particle_sample, timeout=90)

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'.*Sampling STOPPED')
        self.assert_driver_command(ProtocolEvent.FLASH_STATUS, regex=r'Compact Flash Card present - Compact Flash OK!\r\n\r\r\nVolume in drive is .+ bytes free\r\r\n')

        ####
        # Test in streaming mode
        ####
        # Put us in streaming
        self.assert_driver_command(ProtocolEvent.START_AUTOSAMPLE, state=ProtocolState.AUTOSAMPLE, delay=1)
        self.assert_async_particle_generation(DataParticleType.METBK_PARSED, self.assert_data_particle_sample, timeout=90)

        self.assert_driver_command(ProtocolEvent.CLOCK_SYNC, assert_function=self.assert_clock_synced)
        self.assert_driver_command(ProtocolEvent.ACQUIRE_STATUS, regex=r'.*Sampling GO')
        self.assert_driver_command(ProtocolEvent.FLASH_STATUS, regex=r'Compact Flash Card present - Compact Flash OK!\r\n\r\r\nVolume in drive is .+ bytes free\r\r\n')

        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

        ####
        # Test a bad command
        ####
        self.assert_driver_command_exception('ima_bad_command', exception_class=InstrumentCommandException)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class TestQUAL(InstrumentDriverQualificationTestCase, UtilMixin):
    def assert_sample_polled(self, sampleDataAssert, sampleQueue, timeout = 10):
        """
        Test observatory polling function.

        Verifies the acquire_status command.
        """
        # Set up all data subscriptions.  Stream names are defined
        # in the driver PACKET_CONFIG dictionary
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        ###
        # Poll for a sample
        ###

        # make sure there aren't any junk samples in the parsed
        # data queue.
        log.debug("Acquire Sample")
        self.data_subscribers.clear_sample_queue(sampleQueue)

        cmd = AgentCommand(command=DriverEvent.ACQUIRE_SAMPLE)
        self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        # Watch the parsed data queue and return once a sample
        # has been read or the default timeout has been reached.
        samples = self.data_subscribers.get_samples(sampleQueue, 1, timeout = timeout)
        self.assertGreaterEqual(len(samples), 1)
        log.error("SAMPLE: %s" % samples)

        # Verify
        for sample in samples:
            sampleDataAssert(sample)

        self.assert_reset()
        self.doCleanups()
        
    def test_poll(self):
        '''
        poll for a single sample
        '''
        self.assert_sample_polled(self.assert_data_particle_sample, 
                                  DataParticleType.METBK_PARSED)

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        self.assert_sample_autosample(self.assert_data_particle_sample,
                                      DataParticleType.METBK_PARSED,
                                      sample_count=1,
                                      timeout = 60)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test automatically tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()

        # go into direct access
        self.assert_direct_access_start_telnet(timeout=600)
        self.tcp_client.send_data("#D\r\n")
        self.assertTrue(self.tcp_client.expect("\r\n"))

        self.assert_direct_access_stop_telnet()

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        ##################
        #  Command Mode
        ##################

        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [
                ProtocolEvent.GET, 
                ProtocolEvent.CLOCK_SYNC,
                ProtocolEvent.START_AUTOSAMPLE,
                ProtocolEvent.ACQUIRE_SAMPLE,
                ProtocolEvent.FLASH_STATUS,
                ProtocolEvent.ACQUIRE_STATUS,
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()
            }

        log.debug("test_get_capabilities: enter command")
        self.assert_enter_command_mode()
        log.debug("test_get_capabilities: in command")
        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            ProtocolEvent.GET, 
            ProtocolEvent.CLOCK_SYNC,
            ProtocolEvent.ACQUIRE_STATUS,
            ProtocolEvent.ACQUIRE_SAMPLE,
            ProtocolEvent.FLASH_STATUS,
            ProtocolEvent.STOP_AUTOSAMPLE,
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

        # Can't call get capabilities when uninitialized anymore?
        #self.assert_reset()
        #self.assert_capabilities(capabilities)

    def test_execute_clock_sync(self):
        """
        Verify we can synchronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)

        # get the time from the driver
        check_new_params = self.instrument_agent_client.get_resource([Parameter.CLOCK])
        # convert driver's time from formatted date/time string to seconds integer
        instrument_time = time.mktime(time.strptime(check_new_params.get(Parameter.CLOCK).lower(), "%Y/%m/%d  %H:%M:%S"))

        # need to convert local machine's time to date/time string and back to seconds to 'drop' the DST attribute so test passes
        # get time from local machine
        lt = time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        # convert local time from formatted date/time string to seconds integer to drop DST
        local_time = time.mktime(time.strptime(lt, "%d %b %Y %H:%M:%S"))

        # Now verify that the time matches to within 5 seconds
        self.assertLessEqual(abs(instrument_time - local_time), 5)

    @unittest.skip("Needs new agent code that automatically inits startup params")
    def test_get_parameters(self):
        '''
        verify that parameters can be gotten properly
        '''
        self.assert_enter_command_mode()
        
        reply = self.instrument_agent_client.get_resource(Parameter.ALL)
        self.assert_driver_parameters(reply, verify_sample_interval=True)
        

###############################################################################
#                             PUBLICATION TESTS                               #
# Device specific pulication tests are for                                    #
# testing device specific capabilities                                        #
###############################################################################
@attr('PUB', group='mi')
class TestPUB(InstrumentDriverPublicationTestCase, UtilMixin):
    def test_granule_generation(self):
        self.assert_initialize_driver()

        # Currently these tests only verify that the data granule is generated, but the values
        # are not tested.  We will eventually need to replace log.debug with a better callback
        # function that actually tests the granule.
        self.assert_sample_async("raw data", log.debug, DataParticleType.RAW, timeout=10)

        self.assert_sample_async(self.METBK_SAMPLE_DATA, log.debug, DataParticleType.METBK_PARSED, timeout=10)
        self.assert_sample_async(self.METBK_STATUS_DATA, log.debug, DataParticleType.METBK_STATUS, timeout=10)
