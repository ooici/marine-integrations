#!/usr/bin/env python

"""
@package mi.instrument.nobska.mavs4.mavs4.test.test_driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4/mavs4/driver.py
@author Bill Bollenbacher
@brief Test cases for mavs4 driver
 
USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nobska/mavs4 -a QUAL
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

# Ensure the test class is monkey patched for gevent
from gevent import monkey; monkey.patch_all()
from gevent.timeout import Timeout
import gevent
import socket

# Standard lib imports
import time
import unittest
import ntplib
import datetime

# 3rd party imports
from nose.plugins.attrib import attr

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException

from mi.instrument.nobska.mavs4.ooicore.driver import mavs4InstrumentDriver
from mi.instrument.nobska.mavs4.ooicore.driver import DataParticleType
from mi.instrument.nobska.mavs4.ooicore.driver import ProtocolStates
from mi.instrument.nobska.mavs4.ooicore.driver import ProtocolEvent
from mi.instrument.nobska.mavs4.ooicore.driver import mavs4InstrumentProtocol
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentParameters
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentCmds
from mi.instrument.nobska.mavs4.ooicore.driver import Capability
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentPrompts
from mi.instrument.nobska.mavs4.ooicore.driver import Mavs4StatusDataParticleKey
from mi.instrument.nobska.mavs4.ooicore.driver import Mavs4SampleDataParticleKey
from mi.instrument.nobska.mavs4.ooicore.driver import DeployMenuParameters
from mi.instrument.nobska.mavs4.ooicore.driver import SystemConfigurationMenuParameters
from mi.instrument.nobska.mavs4.ooicore.driver import VelocityOffsetParameters
from mi.instrument.nobska.mavs4.ooicore.driver import CompassOffsetParameters
from mi.instrument.nobska.mavs4.ooicore.driver import CompassScaleFactorsParameters
from mi.instrument.nobska.mavs4.ooicore.driver import TiltOffsetParameters
from mi.instrument.nobska.mavs4.ooicore.driver import SubMenues

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey
from mi.idk.unit_test import DriverStartupConfigKey

from mi.core.instrument.chunker import StringChunker

from mi.core.tcp_client import TcpClient

# MI logger
from mi.core.log import get_logger ; log = get_logger()
from interface.objects import AgentCommand

from ion.agents.instrument.instrument_agent import InstrumentAgentState

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

## Initialize the test configuration
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nobska.mavs4.ooicore.driver',
    driver_class="mavs4InstrumentDriver",

    instrument_agent_resource_id = 'nobska_mavs4_ooicore',
    instrument_agent_name = 'nobska_mavs4_ooicore_agent',
    instrument_agent_packet_config = DataParticleType(),
    
    driver_startup_config = {
        DriverStartupConfigKey.PARAMETERS: {
            InstrumentParameters.VELOCITY_FRAME: '3',
        },
    }
)

# 'will echo' command sequence to be sent from DA telnet server
# see RFCs 854 & 857
WILL_ECHO_CMD = '\xff\xfd\x03\xff\xfb\x03\xff\xfb\x01'
# 'do echo' command sequence to be sent back from telnet client
DO_ECHO_CMD   = '\xff\xfb\x03\xff\xfd\x03\xff\xfd\x01'

TIME_TO_SET = '03/29/2002 11:11:42'

# Create some short names for the parameter test config
TYPE = ParameterTestConfigKey.TYPE
READONLY = ParameterTestConfigKey.READONLY
STARTUP = ParameterTestConfigKey.STARTUP
DA = ParameterTestConfigKey.DIRECT_ACCESS
VALUE = ParameterTestConfigKey.VALUE
REQUIRED = ParameterTestConfigKey.REQUIRED
DEFAULT = ParameterTestConfigKey.DEFAULT
    
class Mavs4Mixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constants and common data assertion methods.
    '''
    
    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        InstrumentParameters.SYS_CLOCK : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.NOTE1 : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.NOTE2 : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.NOTE3 : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.VELOCITY_FRAME : {TYPE: str, READONLY: True, DA: False, STARTUP: True, DEFAULT: '3', VALUE: '3'},
        InstrumentParameters.MONITOR : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.LOG_DISPLAY_TIME : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.QUERY_MODE : {TYPE: str, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.FREQUENCY : {TYPE: float, READONLY: False, DA: False, STARTUP: False, DEFAULT: 1.0},
        InstrumentParameters.MEASUREMENTS_PER_SAMPLE : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 1},
        InstrumentParameters.SAMPLE_PERIOD : {TYPE: float, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.SAMPLES_PER_BURST : {TYPE: int, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.BURST_INTERVAL_DAYS : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0},
        InstrumentParameters.BURST_INTERVAL_HOURS : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0},
        InstrumentParameters.BURST_INTERVAL_MINUTES : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0},
        InstrumentParameters.BURST_INTERVAL_SECONDS : {TYPE: int, READONLY: False, DA: False, STARTUP: False, DEFAULT: 0},
        InstrumentParameters.SI_CONVERSION : {TYPE: float, READONLY: False, DA: False, STARTUP: False},
        InstrumentParameters.WARM_UP_INTERVAL : {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: 'fast'},
        InstrumentParameters.THREE_AXIS_COMPASS : {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: 'y'},
        InstrumentParameters.THERMISTOR : {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: 'y'},
        InstrumentParameters.PRESSURE : {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: 'n'},
        InstrumentParameters.AUXILIARY_1 : {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: 'n'},
        InstrumentParameters.AUXILIARY_2 : {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: 'n'},
        InstrumentParameters.AUXILIARY_3 : {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: 'n'},
        InstrumentParameters.SENSOR_ORIENTATION : {TYPE: str, READONLY: False, DA: False, STARTUP: False, DEFAULT: '2'},
        InstrumentParameters.SERIAL_NUMBER : {TYPE: str, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.VELOCITY_OFFSET_PATH_A : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.VELOCITY_OFFSET_PATH_B : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.VELOCITY_OFFSET_PATH_C : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.VELOCITY_OFFSET_PATH_D : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.COMPASS_OFFSET_0 : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.COMPASS_OFFSET_1 : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.COMPASS_OFFSET_2 : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.COMPASS_SCALE_FACTORS_0 : {TYPE: float, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.COMPASS_SCALE_FACTORS_1 : {TYPE: float, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.COMPASS_SCALE_FACTORS_2 : {TYPE: float, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.TILT_PITCH_OFFSET : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
        InstrumentParameters.TILT_ROLL_OFFSET : {TYPE: int, READONLY: True, DA: False, STARTUP: False},
    }

    _status_sample_parameters = {
        Mavs4StatusDataParticleKey.VELOCITY_OFFSET_PATH_A: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.VELOCITY_OFFSET_PATH_B: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.VELOCITY_OFFSET_PATH_C: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.VELOCITY_OFFSET_PATH_D: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.COMPASS_OFFSET_0: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.COMPASS_OFFSET_1: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.COMPASS_OFFSET_2: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.COMPASS_SCALE_FACTORS_0: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.COMPASS_SCALE_FACTORS_1: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.COMPASS_SCALE_FACTORS_2: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.TILT_PITCH_OFFSET: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.TILT_ROLL_OFFSET: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.SAMPLE_PERIOD: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.SAMPLES_PER_BURST: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.BURST_INTERVAL_DAYS: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.BURST_INTERVAL_HOURS: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.BURST_INTERVAL_MINUTES: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.BURST_INTERVAL_SECONDS: {TYPE: unicode, VALUE: u'' },
        Mavs4StatusDataParticleKey.SI_CONVERSION: {TYPE: unicode, VALUE: u'' },
    }
        
    _sample_parameters = {
        Mavs4SampleDataParticleKey.TIMESTAMP: {TYPE: float, VALUE: 3565047050.0},
        Mavs4SampleDataParticleKey.FRACTIONAL_SECOND: {TYPE: int, VALUE: 40},
        Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_A: {TYPE: int, VALUE: 64965},
        Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_B: {TYPE: int, VALUE: 65392},
        Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_C: {TYPE: int, VALUE: 65307},
        Mavs4SampleDataParticleKey.ACOUSTIC_AXIS_VELOCITY_D: {TYPE: int, VALUE: 65420},
        Mavs4SampleDataParticleKey.VELOCITY_FRAME_EAST: {TYPE: float, VALUE: 1.2},
        Mavs4SampleDataParticleKey.VELOCITY_FRAME_NORTH: {TYPE: float, VALUE: 3.4},
        Mavs4SampleDataParticleKey.VELOCITY_FRAME_WEST: {TYPE: float, VALUE: 5.6},
        Mavs4SampleDataParticleKey.TEMPERATURE: {TYPE: float, VALUE: 22.21},
        Mavs4SampleDataParticleKey.COMPASS_MX: {TYPE: float, VALUE: 0.96},
        Mavs4SampleDataParticleKey.COMPASS_MY: {TYPE: float, VALUE: 0.28},
        Mavs4SampleDataParticleKey.PITCH: {TYPE: float, VALUE: 3.0},
        Mavs4SampleDataParticleKey.ROLL: {TYPE: float, VALUE: -5.1},
    }

    SAMPLE = "12 20 2012 18 50 50.40 FDC5 FF70 FF1B FF8C 1.2 3.4 5.6 22.21 0.96 0.28 3.0 -5.1\n"
    
    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusTideSampleDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_particle_status(self, data_particle, verify_values = False):
        '''
        Verify a status data particle
        @param data_particle:  status data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_sample_parameters, verify_values)


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

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################

@attr('UNIT', group='mi')
class Testmavs4_UNIT(InstrumentDriverUnitTestCase, Mavs4Mixin):
    """Unit Test Container"""
    
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)
    
    def test_driver_enums(self):
        """
        Verify that all driver enumerations have no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(InstrumentPrompts())
        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(ProtocolStates())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(InstrumentParameters())
        self.assert_enum_has_no_duplicates(DeployMenuParameters())
        self.assert_enum_has_no_duplicates(SystemConfigurationMenuParameters())
        self.assert_enum_has_no_duplicates(VelocityOffsetParameters())
        self.assert_enum_has_no_duplicates(CompassOffsetParameters())
        self.assert_enum_has_no_duplicates(CompassScaleFactorsParameters())
        self.assert_enum_has_no_duplicates(TiltOffsetParameters())
        self.assert_enum_has_no_duplicates(SubMenues())

        # Test capabilites for duplicates, then verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(mavs4InstrumentProtocol.chunker_sieve_function)

        self.assert_chunker_sample(chunker, self.SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, self.SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, self.SAMPLE)
        self.assert_chunker_combined_sample(chunker, self.SAMPLE)
    
    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = mavs4InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # validate data particle
        self.assert_particle_published(driver, self.SAMPLE, self.assert_particle_sample, True)
        

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class Testmavs4_INT(InstrumentDriverIntegrationTestCase, Mavs4Mixin):
    """Integration Test Container"""
    
    @staticmethod
    def driver_module():
        return 'mi.instrument.nobska.mavs4.ooicore.driver'
        
    @staticmethod
    def driver_class():
        return 'mavs4InstrumentDriver'    
    

    def check_state(self, expected_state):
        self.protocol_state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(self.protocol_state, expected_state)
        return 
        
    def assertParamDictionariesEqual(self, pd1, pd2, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd1.keys()), set(pd2.keys()))
            #print str(pd1)
            #print str(pd2)
            for (key, type_val) in pd2.iteritems():
                #print key
                #print type_val
                self.assertTrue(isinstance(pd1[key], type_val))
        else:
            for (key, val) in pd1.iteritems():
                self.assertTrue(pd2.has_key(key))
                self.assertTrue(isinstance(val, pd2[key]))
        
    def assertParamVals(self, params, correct_params):
        """
        Verify parameters take the correct values.
        """
        self.assertEqual(set(params.keys()), set(correct_params.keys()),
                         '%s != %s' %(params.keys(), correct_params.keys()))
        for (key, val) in params.iteritems():
            if key == InstrumentParameters.SYS_CLOCK:
                # verify that the dates match 
                local_time_str = TIME_TO_SET
                #print("lts=%s, val=%s" %(local_time_str, val))
                self.assertTrue(local_time_str[:12].upper() in val.upper())
                
                # verify that the times match closely
                lt_sec = int(local_time_str[-2:])
                it_sec = int(val[-2:])
                #print("lts=%d, its=%d" %(lt_sec, it_sec))
                if abs(lt_sec - it_sec) > 15:
                    self.fail("time delta too large after clock sync")      

            else:
                self.assertEqual(val, correct_params[key],
                                 '%s: %s != %s' %(key, val, correct_params[key]))
    
    @unittest.skip("override & skip while in development")
    def test_driver_process(self):
        pass 

    
    def test_instrument_wakeup(self):
        """
        @brief Test for instrument wakeup, expects instrument to be in 'command' state
        """
        self.put_driver_in_command_mode()
                
               
    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', InstrumentParameters.ALL)
        self.assert_parameters(reply, self._driver_parameters, True)


    def test_get_set(self):
        """
        Test device parameter access.
        """
        self.assert_initialize_driver()

        # parameter values to test.
        paramter_values = {InstrumentParameters.SYS_CLOCK : TIME_TO_SET,
                           InstrumentParameters.NOTE1 : 'New note1 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                           InstrumentParameters.NOTE2 : 'New note2 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                           InstrumentParameters.NOTE3 : 'New note3 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                           InstrumentParameters.VELOCITY_FRAME : '4',
                           InstrumentParameters.MONITOR : 'y',
                           InstrumentParameters.LOG_DISPLAY_TIME : 'y',
                           InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND : 'y',
                           InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES : 'DEC',
                           InstrumentParameters.QUERY_MODE : 'n',
                           InstrumentParameters.FREQUENCY : 3.3,
                           InstrumentParameters.MEASUREMENTS_PER_SAMPLE : 3,
                           InstrumentParameters.SAMPLE_PERIOD : 2.5,
                           InstrumentParameters.SAMPLES_PER_BURST : 2,
                           InstrumentParameters.BURST_INTERVAL_DAYS : 1,
                           InstrumentParameters.BURST_INTERVAL_HOURS : 2,
                           InstrumentParameters.BURST_INTERVAL_MINUTES : 3,
                           InstrumentParameters.BURST_INTERVAL_SECONDS : 4,
                           InstrumentParameters.SI_CONVERSION : .00231,
                           InstrumentParameters.WARM_UP_INTERVAL : 'Fast',
                           InstrumentParameters.THREE_AXIS_COMPASS : 'y',
                           InstrumentParameters.THERMISTOR : 'y',
                           InstrumentParameters.PRESSURE : 'n',
                           InstrumentParameters.AUXILIARY_1 : 'n',
                           InstrumentParameters.AUXILIARY_2 : 'n',
                           InstrumentParameters.AUXILIARY_3 : 'n',
                           InstrumentParameters.SENSOR_ORIENTATION : '2'
                           }
        
        # construct values dynamically to get time stamp for notes
        new_parameter_values = {}
        for key in paramter_values.iterkeys():
            new_parameter_values[key] = paramter_values[key]
               
        # Set parameters and verify.
        self.assert_set_bulk(new_parameter_values)
        

    def test_instrumment_autosample(self):
        """
        @brief Test for instrument autosample, puts instrument in 'command' state first
        """
        self.put_driver_in_command_mode()
                
        # start auto-sample.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.AUTOSAMPLE)
                
        # stop auto-sample.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.COMMAND)

    def test_instrument_start_stop_autosample(self):
        """
        @brief Test for putting instrument in 'auto-sample' state
        """
        self.put_driver_in_command_mode()

        # command the instrument to auto-sample mode.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        self.check_state(ProtocolStates.AUTOSAMPLE)
           
        # wait for some samples to be generated
        log.debug('test_instrument_start_stop_autosample: waiting 5 seconds for samples')
        gevent.sleep(5)

        # Verify we received at least 2 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_stop_autosample: # 0f samples = %d' %len(sample_events))
        for sample in sample_events:
            if sample['value'].find(DataParticleType.PARSED) != -1:
                log.debug('parsed sample=%s\n' %sample)
                sample_dict = eval(sample['value'])     # turn string into dictionary
                values = sample_dict['values']          # get particle dictionary
                # pull timestamp out of particle
                ntp_timestamp = [item for item in values if item["value_id"] == "timestamp"][0]['value']
                float_timestamp = ntplib.ntp_to_system_time(ntp_timestamp)
                log.debug('dt=%s' %time.ctime(float_timestamp))
        self.assertTrue(len(sample_events) >= 2)

        # stop autosample and return to command mode
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
                
        self.check_state(ProtocolStates.COMMAND)
    ###
    #    Add driver specific integration tests
    ###

    
    def test_polled_particle_generation(self):
        """
        Test that we can generate particles with commands
        """
        self.assert_initialize_driver()

        self.assert_particle_generation(ProtocolEvent.ACQUIRE_STATUS, DataParticleType.STATUS, self.assert_particle_status, delay=20)
        

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class Testmavs4_QUAL(InstrumentDriverQualificationTestCase):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  


    @unittest.skip("skip for automatic tests")
    def test_direct_access_telnet_mode_manually(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent power_down; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent power_up; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent initialize; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent go_active; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        print("sent run; IA state = %s" %str(retval.result))
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        gevent.sleep(5)  # wait for mavs4 to go back to sleep if it was sleeping
        
        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={'session_type': DirectAccessTypes.telnet,
                                   #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        
        gevent.sleep(600)  # wait for manual telnet session to be run


    #@unittest.skip("skip for now")
    def test_direct_access_telnet_mode(self):
        """
        @brief This test verifies that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        gevent.sleep(5)  # wait for mavs4 to go back to sleep if it was sleeping
        
        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={'session_type': DirectAccessTypes.telnet,
                                   #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))

        # start 'telnet' client with returned address and port
        s = TcpClient(retval.result['ip_address'], retval.result['port'])

        # look for and swallow 'Username' prompt
        try_count = 0
        while s.peek_at_buffer().find("Username: ") == -1:
            log.debug("WANT 'Username:' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count += 1
            if try_count > 10:
                raise Timeout('It took longer than 10 seconds to get a Username: prompt')
        s.remove_from_buffer("Username: ")
        # send some username string
        s.send_data("bob\r\n", "1")
        
        # look for and swallow 'token' prompt
        try_count = 0
        while s.peek_at_buffer().find("token: ") == -1:
            log.debug("WANT 'token: ' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count += 1
            if try_count > 10:
                raise Timeout('It took longer than 10 seconds to get a token: prompt')
        s.remove_from_buffer("token: ")
        # send the returned token
        s.send_data(retval.result['token'] + "\r\n", "1")
        
        # look for and swallow telnet negotiation string
        try_count = 0
        while s.peek_at_buffer().find(WILL_ECHO_CMD) == -1:
            log.debug("WANT %s READ ==> %s" %(WILL_ECHO_CMD, str(s.peek_at_buffer())))
            gevent.sleep(1)
            try_count += 1
            if try_count > 10:
                raise Timeout('It took longer than 10 seconds to get the telnet negotiation string')
        s.remove_from_buffer(WILL_ECHO_CMD)
        # send the telnet negotiation response string
        s.send_data(DO_ECHO_CMD, "1")

        # look for and swallow 'connected' indicator
        try_count = 0
        while s.peek_at_buffer().find("connected\r\n") == -1:
            log.debug("WANT 'connected\n' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count += 1
            if try_count > 10:
                raise Timeout('It took longer than 10 seconds to get a connected prompt')
        s.remove_from_buffer("connected\r\n")
        
        # try to interact with the instrument 
        try_count = 0
        while ((s.peek_at_buffer().find("Enter <CTRL>-<C> now to wake up") == -1) and
              (s.peek_at_buffer().find("Main Menu") == -1)):
            self.assertNotEqual(try_count, 5)
            try_count += 1
            log.debug("WANT %s or %s; READ ==> %s" %("'Enter <CTRL>-<C> now to wake up'", "'Main Menu'", str(s.peek_at_buffer())))
            s.send_data("\r\n\r\n", "1")
            gevent.sleep(2)
               
