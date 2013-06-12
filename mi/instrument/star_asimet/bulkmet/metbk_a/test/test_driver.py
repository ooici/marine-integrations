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
        Capability.CLOCK_SYNC : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.ACQUIRE_SAMPLE : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.ACQUIRE_STATUS : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.FLASH_STATUS : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
    }

    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {Parameter.CLOCK: {TYPE: str, READONLY: True, DA: False, STARTUP: False, VALUE: "2013/05/21  15:46:30", REQUIRED: True},
                          Parameter.SAMPLE_INTERVAL: {TYPE: int, READONLY: True, DA: False, STARTUP: True, VALUE: 30, REQUIRED: True}}

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
                print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$ got the != exception")
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
                                          'EXECUTE_DIRECT']
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

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample.
        To test status particle instrument must be off and powered on will test is waiting
        """
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        print("waiting 60 seconds for instrument data")
        self.assert_async_particle_generation(DataParticleType.METBK_PARSED, self.assert_data_particle_sample, timeout=60)
        self.assert_driver_command(ProtocolEvent.STOP_AUTOSAMPLE, state=ProtocolState.COMMAND, delay=1)

    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, verify_sample_interval=True)

    def test_flash_status_command_mode(self):
        """
        Test flash status in command mode.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.FLASH_STATUS)
        regex = re.compile('Compact Flash Card present - Compact Flash OK!\r\n\r\r\nVolume in drive is .+ bytes free\r\r\n', re.DOTALL)
        match = regex.match(reply[1])

        self.assertNotEqual(match, None, "TestINT.test_flash_status: status response not correct")

    def test_flash_status_autosample_mode(self):
        """
        Test flash status in autosample mode.
        """
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.FLASH_STATUS)
        regex = re.compile('Compact Flash Card present - Compact Flash OK!\r\n\r\r\nVolume in drive is .+ bytes free\r\r\n', re.DOTALL)
        match = regex.match(reply[1])

        self.assertNotEqual(match, None, "TestINT.test_flash_status: status response not correct")

    def test_execute_clock_sync_command_mode(self):
        """
        Verify we can synchronize the instrument internal clock in command mode
        """
        self.assert_initialize_driver()

        # command the instrument to sync clock.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)

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

    def test_execute_clock_sync_autossample_mode(self):
        """
        Verify we can synchronize the instrument internal clock in autosample mode
        """
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        # command the instrument to sync clock.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)

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

    @staticmethod
    def sort_capabilities(caps_list):
        '''
        sort a return value into capability buckets.
        @retval agt_cmds, agt_pars, res_cmds, res_iface, res_pars
        '''
        agt_cmds = []
        agt_pars = []
        res_cmds = []
        res_iface = []
        res_pars = []

        if len(caps_list)>0 and isinstance(caps_list[0], AgentCapability):
            agt_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.AGT_CMD]
            agt_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.AGT_PAR]
            res_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_CMD]
            #res_iface = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_IFACE]
            res_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_PAR]

        elif len(caps_list)>0 and isinstance(caps_list[0], dict):
            agt_cmds = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.AGT_CMD]
            agt_pars = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.AGT_PAR]
            res_cmds = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_CMD]
            #res_iface = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_IFACE]
            res_pars = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_PAR]

        agt_cmds.sort()
        agt_pars.sort()
        res_cmds.sort()
        res_iface.sort()
        res_pars.sort()
        
        return agt_cmds, agt_pars, res_cmds, res_iface, res_pars
    
    def ia_capabilities(self):
        state = self.instrument_agent_client.get_agent_state()
        log.critical("ia_capabilities: IA state=%s" %state)
        retval = self.instrument_agent_client.get_capabilities()
        agt_cmds, agt_pars, res_cmds, res_iface, res_pars = TestQUAL.sort_capabilities(retval)
        log.critical("ia_capabilities: IA commands:\n%s" %agt_cmds)
        log.critical("ia_capabilities: resource commands:\n%s" %res_cmds)
    
    def command_ia(self, cmd):
        log.critical("command_ia: executing %s." %cmd)
        try:
            self.instrument_agent_client.execute_agent(cmd) 
            self.ia_capabilities()
        except Exception as e:
            log.critical("command_ia: exception raised - %s" %e)
    
    @unittest.skip('Only enabled and used for manual testing of vendor SW')
    def test_direct_access_telnet_mode(self):
        """
        @brief This test automatically tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()
        self.ia_capabilities()

        # go into direct access
        self.assert_direct_access_start_telnet(timeout=600)
        self.ia_capabilities()
        self.tcp_client.send_data("#D\r\n")
        self.tcp_client.expect("\r\n")
        
        self.tcp_client.disconnect()
        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        self.command_ia(cmd)
        gevent.sleep(10)
        self.ia_capabilities()

        #self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        #self.assert_enter_command_mode()

    @unittest.skip('Only enabled and used for manual testing of vendor SW')
    def test_direct_access_telnet_mode_manual(self):
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

    @unittest.skip('not tested yet')
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


    @unittest.skip('not tested yet')
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

    def test_execute_clock_sync(self):
        """
        Verify we can synchronize the instrument internal clock
        """
        self.assert_enter_command_mode()

        self.assert_execute_resource(ProtocolEvent.CLOCK_SYNC)

        # get the time from the driver
        check_new_params = self.instrument_agent_client.get_resource([Parameter.CLOCK])
        # convert driver's time from formatted date/time string to seconds integer
        instrument_time = time.mktime(time.strptime(check_new_params.get(Parameter.CLOCK).lower(), "%Y %m %d %H:%M:%S"))

        # need to convert local machine's time to date/time string and back to seconds to 'drop' the DST attribute so test passes
        # get time from local machine
        lt = time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        # convert local time from formatted date/time string to seconds integer to drop DST
        local_time = time.mktime(time.strptime(lt, "%d %b %Y %H:%M:%S"))

        # Now verify that the time matches to within 5 seconds
        self.assertLessEqual(abs(instrument_time - local_time), 5)
