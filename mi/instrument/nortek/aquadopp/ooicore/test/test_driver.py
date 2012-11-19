"""
@package mi.instrument.nortek.aquadopp.ooicore.test.test_driver
@file /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore/driver.py
@author Bill Bollenbacher
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a INT
       $ bin/nosetests -s -v /Users/Bill/WorkSpace/marine-integrations/mi/instrument/nortek/aquadopp/ooicore -a QUAL
"""

__author__ = 'Bill Bollenbacher'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import unittest
import re

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue

from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException

from mi.instrument.nortek.aquadopp.ooicore.driver import Capability
from mi.instrument.nortek.aquadopp.ooicore.driver import ProtocolState
from mi.instrument.nortek.aquadopp.ooicore.driver import ProtocolEvent
from mi.instrument.nortek.aquadopp.ooicore.driver import Parameter
from mi.instrument.nortek.aquadopp.ooicore.driver import PACKET_CONFIG
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwDiagnosticHeaderDataParticle
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwDiagnosticHeaderDataParticleKey
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwVelocityDataParticle
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwVelocityDataParticleKey
from mi.instrument.nortek.aquadopp.ooicore.driver import AquadoppDwDiagnosticDataParticle

from interface.objects import AgentCommand
from interface.objects import CapabilityType

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from pyon.agent.agent import ResourceAgentEvent

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nortek.aquadopp.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'nortek_aquadopp_dw_ooicore',
    instrument_agent_name = 'nortek_aquadopp_dw_ooicore_agent',
    instrument_agent_packet_config = PACKET_CONFIG,
    #instrument_agent_stream_definition = {}
    driver_startup_config = {
        Parameter.AVG_INTERVAL : 61
    }
)

params_dict = {
    Parameter.TRANSMIT_PULSE_LENGTH : int,
    Parameter.BLANKING_DISTANCE : int,
    Parameter.RECEIVE_LENGTH : int,
    Parameter.TIME_BETWEEN_PINGS : int,
    Parameter.TIME_BETWEEN_BURST_SEQUENCES : int,
    Parameter.NUMBER_PINGS : int,
    Parameter.AVG_INTERVAL : int,
    Parameter.USER_NUMBER_BEAMS : int,
    Parameter.TIMING_CONTROL_REGISTER : int,
    Parameter.POWER_CONTROL_REGISTER : int,
    Parameter.COMPASS_UPDATE_RATE : int,
    Parameter.COORDINATE_SYSTEM : int,
    Parameter.NUMBER_BINS : int,
    Parameter.BIN_LENGTH : int,
    Parameter.MEASUREMENT_INTERVAL : int,
    Parameter.DEPLOYMENT_NAME : str,
    Parameter.WRAP_MODE : int,
    Parameter.CLOCK_DEPLOY : str,
    Parameter.DIAGNOSTIC_INTERVAL : str,
    Parameter.MODE : int,
    Parameter.ADJUSTMENT_SOUND_SPEED : int,
    Parameter.NUMBER_SAMPLES_DIAGNOSTIC : int,
    Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC : int,
    Parameter.NUMBER_PINGS_DIAGNOSTIC : int,
    Parameter.MODE_TEST : int,
    Parameter.ANALOG_INPUT_ADDR : int,
    Parameter.SW_VERSION : int,
    Parameter.VELOCITY_ADJ_TABLE : str,
    Parameter.COMMENTS : str,
    Parameter.WAVE_MEASUREMENT_MODE : int,
    Parameter.DYN_PERCENTAGE_POSITION : int,
    Parameter.WAVE_TRANSMIT_PULSE : int,
    Parameter.WAVE_BLANKING_DISTANCE : int,
    Parameter.WAVE_CELL_SIZE : int,
    Parameter.NUMBER_DIAG_SAMPLES : int,
    Parameter.ANALOG_OUTPUT_SCALE : int,
    Parameter.CORRELATION_THRESHOLD : int,
    Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG : int,
    Parameter.QUAL_CONSTANTS : str}


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
class UnitFromIDK(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    ###
    #    Add instrument specific unit tests
    ###


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(InstrumentDriverIntegrationTestCase):
    
    protocol_state = ''
    
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

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
                self.assertTrue(isinstance(pd1[key], type_val))
        else:
            for (key, val) in pd1.iteritems():
                self.assertTrue(pd2.has_key(key))
                self.assertTrue(isinstance(val, pd2[key]))
    
    def check_state(self, expected_state):
        self.protocol_state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(self.protocol_state, expected_state)
        return 
        
    def put_driver_in_command_mode(self):
        """Wrap the steps and asserts for going into command mode.
           May be used in multiple test cases.
        """
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('connect')

        # Test that the driver protocol is in state unknown.
        self.check_state(ProtocolState.UNKNOWN)

        # Discover what state the instrument is in and set the protocol state accordingly.
        self.driver_client.cmd_dvr('discover_state')

        try:
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)
        except:
            self.assertEqual(self.protocol_state, ProtocolState.AUTOSAMPLE)
            # Put the driver in command mode
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
            # Test that the driver protocol is in state command.
            self.check_state(ProtocolState.COMMAND)

 
    def test_startup_configuration(self):
        '''
        Test that the startup configuration is applied correctly
        '''
        self.put_instrument_in_command_mode()

        value_before = self.driver_client.cmd_dvr('get_resource', [Parameter.AVG_INTERVAL])
    
        result = self.driver_client.cmd_dvr('apply_startup_params')

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.AVG_INTERVAL])

        self.assertEquals(reply, {Parameter.AVG_INTERVAL: 61})

        reply = self.driver_client.cmd_dvr('set_resource', {Parameter.AVG_INTERVAL: value_before})

        reply = self.driver_client.cmd_dvr('get_resource', [Parameter.AVG_INTERVAL])

        self.assertEquals(reply, {Parameter.AVG_INTERVAL: value_before})


    def test_instrument_wakeup(self):
        """
        @brief Test for instrument wakeup, puts instrument in 'command' state
        """
        self.put_driver_in_command_mode()


    def test_instrument_read_clock(self):
        """
        @brief Test for reading instrument clock
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to read the clock.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_CLOCK)
        
        log.debug("read clock returned: %s", response)
        self.assertTrue(re.search(r'.*/.*/.*:.*:.*', response[1]))
 

    def test_instrument_read_mode(self):
        """
        @brief Test for reading what mode
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to read the mode.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_MODE)
        
        log.debug("what mode returned: %s", response)
        self.assertTrue(2, response[1])


    def test_instrument_power_down(self):
        """
        @brief Test for power_down
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to power down.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.POWER_DOWN)
        

    def test_instrument_read_battery_voltage(self):
        """
        @brief Test for reading battery voltage
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to read the battery voltage.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_BATTERY_VOLTAGE)
        
        log.debug("read battery voltage returned: %s", response)
        self.assertTrue(isinstance(response[1], int))


    def test_instrument_read_id(self):
        """
        @brief Test for reading ID
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to read the ID.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.READ_ID)
        
        log.debug("read ID returned: %s", response)
        self.assertTrue(re.search(r'AQD 9984.*', response[1]))


    def test_instrument_read_hw_config(self):
        """
        @brief Test for reading HW config
        """
        
        hw_config = {'Status': 4, 
                     'RecSize': 144, 
                     'SerialNo': 'AQD 9984      ', 
                     'FWversion': '3.37', 
                     'Frequency': 65535, 
                     'PICversion': 0, 
                     'HWrevision': 4, 
                     'Config': 4}
        
        self.put_driver_in_command_mode()
        
        # command the instrument to read the hw config.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.GET_HW_CONFIGURATION)
        
        log.debug("read HW config returned: %s", response)
        self.assertEqual(hw_config, response[1])


    def test_instrument_read_head_config(self):
        """
        @brief Test for reading HEAD config
        """
        
        head_config = {'Config': 16447, 
                       'SerialNo': 'A3L 5258\x00\x00\x00\x00', 
                       'System': 'QQBBAEEAAADFCx76HvoAAM/1MQqfDJ8MnwzTs1v8AC64/8aweQHgLsP/uAsAAAAA//8AAAEAAAABAAAAAAAAAAAA//8AAP//AAD//wAAAAAAAP//AQAAAAAA/////wAAAAAJALLvww7JBQMB2BtnKsnLL/yuJ9oAIs20AcQmAP//f2sDov9rA7R97f31/oD+5XsiAC4A9f8AAAAAAAAAAAAAAAAAAAAAVRUQDhAOECc=', 
                       'Frequency': 2000, 
                       'NBeams': 3, 
                       'Type': 0}

        self.put_driver_in_command_mode()
        
        # command the instrument to read the head config.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.GET_HEAD_CONFIGURATION)
        
        log.debug("read HEAD config returned: %s", response)
        self.assertEqual(head_config, response[1])


    @unittest.skip("skip until issue with instrument recorder resolved, command fails with NACK from instrument")
    def test_instrument_start_measurement_immediate(self):
        """
        @brief Test for starting measurement immediate
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to start measurement immediate.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_MEASUREMENT_IMMEDIATE)
        gevent.sleep(100)  # wait for measurement to complete               


    @unittest.skip("skip until issue with instrument recorder resolved, command fails with NACK from instrument")
    def test_instrument_start_measurement_at_specific_time(self):
        """
        @brief Test for starting measurement immediate
        """
        self.put_driver_in_command_mode()
        
        # command the instrument to start measurement immediate.
        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME)
        gevent.sleep(100)  # wait for measurement to complete               


    def test_instrument_set(self):
        """
        @brief Test for setting instrument parameter
        """
        self.put_driver_in_command_mode()

        # Get all device parameters. Confirm all expected keys are retrieved
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDictionariesEqual(reply, params_dict, True)

        # Grab a subset of parameters.
        params = [
            Parameter.WRAP_MODE
            ]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        #self.assertParamDict(reply)        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        new_wrap_mode = 1 if orig_params[Parameter.WRAP_MODE]==0 else 0
        log.debug('old=%d, new=%d' %(orig_params[Parameter.WRAP_MODE], new_wrap_mode))
        new_params = {
            Parameter.WRAP_MODE : new_wrap_mode
        }
        
        # Set parameter and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertEqual(new_params[Parameter.WRAP_MODE], reply[Parameter.WRAP_MODE])

        # Reset parameter to original value and verify.
        reply = self.driver_client.cmd_dvr('set_resource', orig_params)
        
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertEqual(orig_params[Parameter.WRAP_MODE], reply[Parameter.WRAP_MODE])

        # set wrap_mode to 1 to leave instrument with wrap mode enabled
        new_params = {
            Parameter.WRAP_MODE : 1
        }
        
        # Set parameter and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertEqual(new_params[Parameter.WRAP_MODE], reply[Parameter.WRAP_MODE])
        
    def test_instrument_poll(self):
        """
        Test sample polling commands and events.
        """

        self.put_driver_in_command_mode()

        # command the instrument to auto-sample mode.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        # wait for some samples to be generated
        gevent.sleep(100)

        # Verify we received at least 4 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_stop_autosample: # 0f samples = %d' %len(sample_events))
        #log.debug('samples=%s' %sample_events)
        self.assertTrue(len(sample_events) >= 4)

    def test_instrument_start_stop_autosample(self):
        """
        @brief Test for putting instrument in 'auto-sample' state
        """
        self.put_driver_in_command_mode()

        # command the instrument to auto-sample mode.
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        self.check_state(ProtocolState.AUTOSAMPLE)
           
        # re-initialize the driver and re-discover instrument state (should be in autosample)
        # Transition driver to disconnected.
        self.driver_client.cmd_dvr('disconnect')

        # Test the driver is disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Transition driver to unconfigured.
        self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('connect')

        # Test that the driver protocol is in state unknown.
        self.check_state(ProtocolState.UNKNOWN)

        # Discover what state the instrument is in and set the protocol state accordingly.
        self.driver_client.cmd_dvr('discover_state')

        self.check_state(ProtocolState.AUTOSAMPLE)

        # wait for some samples to be generated
        gevent.sleep(100)

        # Verify we received at least 4 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        log.debug('test_instrument_start_stop_autosample: # 0f samples = %d' %len(sample_events))
        #log.debug('samples=%s' %sample_events)
        self.assertTrue(len(sample_events) >= 4)

        # stop autosample and return to command mode
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
                
        self.check_state(ProtocolState.COMMAND)
                        
    def test_capabilities(self):
        """
        Test get_resource_capaibilties in command state and autosample state;
        should be different in each.
        """
        
        command_capabilities = ['EXPORTED_INSTRUMENT_CMD_READ_ID', 
                                'EXPORTED_INSTRUMENT_CMD_GET_HW_CONFIGURATION', 
                                'DRIVER_EVENT_SET', 
                                'DRIVER_EVENT_GET', 
                                'EXPORTED_INSTRUMENT_CMD_READ_CLOCK', 
                                'EXPORTED_INSTRUMENT_CMD_GET_HEAD_CONFIGURATION', 
                                'EXPORTED_INSTRUMENT_CMD_POWER_DOWN', 
                                'EXPORTED_INSTRUMENT_CMD_READ_MODE', 
                                'EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_AT_SPECIFIC_TIME', 
                                'EXPORTED_INSTRUMENT_CMD_READ_BATTERY_VOLTAGE', 
                                'EXPORTED_INSTRUMENT_CMD_START_MEASUREMENT_IMMEDIATE', 
                                'DRIVER_EVENT_START_AUTOSAMPLE',
                                'DRIVER_EVENT_ACQUIRE_SAMPLE']
        
        autosample_capabilities = ['DRIVER_EVENT_STOP_AUTOSAMPLE']
        
        params_list = [
            Parameter.TRANSMIT_PULSE_LENGTH,
            Parameter.BLANKING_DISTANCE,
            Parameter.RECEIVE_LENGTH,
            Parameter.TIME_BETWEEN_PINGS,
            Parameter.TIME_BETWEEN_BURST_SEQUENCES, 
            Parameter.NUMBER_PINGS,
            Parameter.AVG_INTERVAL,
            Parameter.USER_NUMBER_BEAMS, 
            Parameter.TIMING_CONTROL_REGISTER,
            Parameter.POWER_CONTROL_REGISTER,
            Parameter.COMPASS_UPDATE_RATE,  
            Parameter.COORDINATE_SYSTEM,
            Parameter.NUMBER_BINS,
            Parameter.BIN_LENGTH,
            Parameter.MEASUREMENT_INTERVAL,
            Parameter.DEPLOYMENT_NAME,
            Parameter.WRAP_MODE,
            Parameter.CLOCK_DEPLOY,
            Parameter.DIAGNOSTIC_INTERVAL,
            Parameter.MODE,
            Parameter.ADJUSTMENT_SOUND_SPEED,
            Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
            Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
            Parameter.NUMBER_PINGS_DIAGNOSTIC,
            Parameter.MODE_TEST,
            Parameter.ANALOG_INPUT_ADDR,
            Parameter.SW_VERSION,
            Parameter.VELOCITY_ADJ_TABLE,
            Parameter.COMMENTS,
            Parameter.WAVE_MEASUREMENT_MODE,
            Parameter.DYN_PERCENTAGE_POSITION,
            Parameter.WAVE_TRANSMIT_PULSE,
            Parameter.WAVE_BLANKING_DISTANCE,
            Parameter.WAVE_CELL_SIZE,
            Parameter.NUMBER_DIAG_SAMPLES,
            Parameter.ANALOG_OUTPUT_SCALE,
            Parameter.CORRELATION_THRESHOLD,
            Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
            Parameter.QUAL_CONSTANTS,
            ]
        
        self.put_driver_in_command_mode()

        # Get the capabilities of the driver.
        driver_capabilities = self.driver_client.cmd_dvr('get_resource_capabilities')
        self.assertTrue(sorted(command_capabilities) == sorted(driver_capabilities[0]))
        #log.debug('dc=%s' %sorted(driver_capabilities[1]))
        #log.debug('pl=%s' %sorted(params_list))
        self.assertTrue(sorted(params_list) == sorted(driver_capabilities[1]))

        # Put the driver in autosample
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        self.check_state(ProtocolState.AUTOSAMPLE)

        # Get the capabilities of the driver.
        driver_capabilities = self.driver_client.cmd_dvr('get_resource_capabilities')
        log.debug('test_capabilities: autosample mode capabilities=%s' %driver_capabilities)
        self.assertTrue(autosample_capabilities == driver_capabilities[0])
               
    def test_errors(self):
        """
        Test response to erroneous commands and parameters.
        """
        
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Assert for an unknown driver command.
        with self.assertRaises(InstrumentCommandException):
            self.driver_client.cmd_dvr('bogus_command')

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        # Assert we forgot the comms parameter.
        with self.assertRaises(InstrumentParameterException):
            self.driver_client.cmd_dvr('configure')

        # Assert we send a bad config object (not a dict).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = 'not a config dict'            
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
            
        # Assert we send a bad config object (missing addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG.pop('addr')
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)

        # Assert we send a bad config object (bad addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG['addr'] = ''
            self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
        
        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        self.check_state(ProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        self.check_state(ProtocolState.COMMAND)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        
        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            self.driver_client.cmd_dvr('connect')
        
        # Assert get fails without a parameter.
        with self.assertRaises(InstrumentParameterException):
            self.driver_client.cmd_dvr('get_resource')
            
        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            self.driver_client.cmd_dvr('get_resource', bogus_params)
            
        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                Parameter.ADJUSTMENT_SOUND_SPEED
                ]
            self.driver_client.cmd_dvr('get_resource', bogus_params)        
        
        # Assert we cannot set a bogus parameter.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name' : 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                Parameter.ADJUSTMENT_SOUND_SPEED : 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
        

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(InstrumentDriverQualificationTestCase):
    
    def assert_resource_capabilities(self, capabilities):

        def sort_capabilities(caps_list):
            '''
            sort a return value into capability buckets.
            @return res_cmds, res_pars
            '''
            res_cmds = []
            res_pars = []

            if(not capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)):
                capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
            if(not capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)):
                capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

            res_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_CMD]
            res_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_PAR]

            return res_cmds, res_pars

        retval = self.instrument_agent_client.get_capabilities()
        res_cmds, res_pars = sort_capabilities(retval)

        log.debug("Resource Commands: %s " % str(res_cmds))
        log.debug("Resource Parameters: %s " % str(res_pars))
        
        log.debug("Expected Resource Commands: %s " % str(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)))
        log.debug("Expected Resource Parameters: %s " % str(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)))

        self.assertEqual(sorted(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)), sorted(res_cmds))
        self.assertEqual(sorted(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)), sorted(res_pars))

    def get_parameter(self, name):
        '''
        get parameter, assumes we are in command mode.
        '''
        getParams = [ name ]

        result = self.instrument_agent_client.get_resource(getParams)

        return result[name]

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
        reply = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        # Watch the parsed data queue and return once a sample
        # has been read or the default timeout has been reached.
        samples = self.data_subscribers.get_samples(sampleQueue, 4, timeout = timeout)
        self.assertGreaterEqual(len(samples), 4)
        log.error("SAMPLE: %s" % samples)

        # Verify
        for sample in samples:
            sampleDataAssert(sample)

        self.assert_reset()
        self.doCleanups()

    def assertSampleDataParticle(self, sample):
        log.debug('assertSampleDataParticle: sample=%s' %sample)
        self.assertTrue(sample[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample.get(DataParticleKey.PREFERRED_TIMESTAMP))
        
        values = sample['values']
        value_ids = []
        for value in values:
            value_ids.append(value['value_id'])
        if AquadoppDwVelocityDataParticleKey.TIMESTAMP in value_ids:
            log.debug('assertSampleDataParticle: AquadoppDwVelocityDataParticle/AquadoppDwDiagnosticDataParticle detected')
            self.assertEqual(sorted(value_ids), sorted(AquadoppDwVelocityDataParticleKey.list()))
            for value in values:
                if value['value_id'] == AquadoppDwVelocityDataParticleKey.TIMESTAMP:
                    self.assertTrue(isinstance(value['value'], str))
                else:
                    self.assertTrue(isinstance(value['value'], int))
        elif AquadoppDwDiagnosticHeaderDataParticleKey.RECORDS in value_ids:
            log.debug('assertSampleDataParticle: AquadoppDwDiagnosticHeaderDataParticle detected')
            self.assertEqual(sorted(value_ids), sorted(AquadoppDwDiagnosticHeaderDataParticleKey.list()))
            for value in values:
                self.assertTrue(isinstance(value['value'], int))
        else:
            self.fail('Unknown data particle')

    @unittest.skip("skip for automatic tests")
    def test_direct_access_telnet_mode_manually(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()

        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={#'session_type': DirectAccessTypes.telnet,
                                   'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        
        gevent.sleep(600)  # wait for manual telnet session to be run

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("K1W%!Q")
        self.tcp_client.expect("DW-AQUADOPP")

        self.assert_direct_access_stop_telnet()

    def test_poll(self):
        '''
        poll for a single sample
        '''

        self.assert_sample_polled(self.assertSampleDataParticle,
                                  DataParticleValue.PARSED,
                                  timeout = 100)

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        self.assert_sample_autosample(self.assertSampleDataParticle,
                                  DataParticleValue.PARSED,
                                  timeout = 100)

    def test_get_set_parameters(self):
        '''
        verify that parameters can be get set properly
        '''
        self.assert_enter_command_mode()
        
        value_before_set = self.get_parameter(Parameter.BLANKING_DISTANCE)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, 40)
        self.assert_set_parameter(Parameter.BLANKING_DISTANCE, value_before_set)

        value_before_set = self.get_parameter(Parameter.AVG_INTERVAL)
        self.assert_set_parameter(Parameter.AVG_INTERVAL, 4)
        self.assert_set_parameter(Parameter.AVG_INTERVAL, value_before_set)

        self.assert_reset()
        
    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        ##################
        #  Command Mode
        ##################

        capabilities = {
            AgentCapabilityType.RESOURCE_COMMAND: [
                DriverEvent.SET, 
                DriverEvent.ACQUIRE_SAMPLE, 
                DriverEvent.GET, 
                DriverEvent.START_AUTOSAMPLE,
                ProtocolEvent.GET_HEAD_CONFIGURATION,
                ProtocolEvent.GET_HW_CONFIGURATION,
                ProtocolEvent.POWER_DOWN,
                ProtocolEvent.READ_BATTERY_VOLTAGE,
                ProtocolEvent.READ_CLOCK, 
                ProtocolEvent.READ_ID,
                ProtocolEvent.READ_MODE,
                ProtocolEvent.START_MEASUREMENT_AT_SPECIFIC_TIME,
                ProtocolEvent.START_MEASUREMENT_IMMEDIATE
            ],
            AgentCapabilityType.RESOURCE_PARAMETER: [
                Parameter.TRANSMIT_PULSE_LENGTH,
                Parameter.BLANKING_DISTANCE,
                Parameter.RECEIVE_LENGTH,
                Parameter.TIME_BETWEEN_PINGS,
                Parameter.TIME_BETWEEN_BURST_SEQUENCES, 
                Parameter.NUMBER_PINGS,
                Parameter.AVG_INTERVAL,
                Parameter.USER_NUMBER_BEAMS, 
                Parameter.TIMING_CONTROL_REGISTER,
                Parameter.POWER_CONTROL_REGISTER,
                Parameter.COMPASS_UPDATE_RATE,  
                Parameter.COORDINATE_SYSTEM,
                Parameter.NUMBER_BINS,
                Parameter.BIN_LENGTH,
                Parameter.MEASUREMENT_INTERVAL,
                Parameter.DEPLOYMENT_NAME,
                Parameter.WRAP_MODE,
                Parameter.CLOCK_DEPLOY,
                Parameter.DIAGNOSTIC_INTERVAL,
                Parameter.MODE,
                Parameter.ADJUSTMENT_SOUND_SPEED,
                Parameter.NUMBER_SAMPLES_DIAGNOSTIC,
                Parameter.NUMBER_BEAMS_CELL_DIAGNOSTIC,
                Parameter.NUMBER_PINGS_DIAGNOSTIC,
                Parameter.MODE_TEST,
                Parameter.ANALOG_INPUT_ADDR,
                Parameter.SW_VERSION,
                Parameter.VELOCITY_ADJ_TABLE,
                Parameter.COMMENTS,
                Parameter.WAVE_MEASUREMENT_MODE,
                Parameter.DYN_PERCENTAGE_POSITION,
                Parameter.WAVE_TRANSMIT_PULSE,
                Parameter.WAVE_BLANKING_DISTANCE,
                Parameter.WAVE_CELL_SIZE,
                Parameter.NUMBER_DIAG_SAMPLES,
                Parameter.ANALOG_OUTPUT_SCALE,
                Parameter.CORRELATION_THRESHOLD,
                Parameter.TRANSMIT_PULSE_LENGTH_SECOND_LAG,
                Parameter.QUAL_CONSTANTS
            ],
        }

        self.assert_resource_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [DriverEvent.STOP_AUTOSAMPLE]

        self.assert_start_autosample()
        self.assert_resource_capabilities(capabilities)
        self.assert_stop_autosample()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_resource_capabilities(capabilities)


