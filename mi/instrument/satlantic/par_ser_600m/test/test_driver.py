#!/usr/bin/env python

'''
@file ion/services/mi/drivers/satlantic_par/test/test_satlantic_par.py
@author Steve Foley
@test ion.services.mi.drivers.satlantic_par
Unit test suite to test Satlantic PAR sensor
@todo Find a way to test timeouts?
'''

from gevent import monkey; monkey.patch_all()
import gevent

import unittest
import time
import json
from mock import Mock, call, DEFAULT
from pyon.util.unit_test import PyonTestCase
from nose.plugins.attrib import attr
from unittest import TestCase

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import InstErrorCode
from mi.core.instrument.instrument_driver import DriverState
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_protocol import InterfaceType
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue
from mi.core.instrument.chunker import StringChunker

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentDataException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentParameterException

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import AgentCapabilityType

from mi.instrument.satlantic.par_ser_600m.driver import SatlanticPARInstrumentProtocol
from mi.instrument.satlantic.par_ser_600m.driver import PARProtocolState
from mi.instrument.satlantic.par_ser_600m.driver import PARProtocolEvent
from mi.instrument.satlantic.par_ser_600m.driver import Parameter
from mi.instrument.satlantic.par_ser_600m.driver import Command
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticChecksumDecorator
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticPARDataParticle
from mi.instrument.satlantic.par_ser_600m.driver import SatlanticPARDataParticleKey

from interface.objects import AgentCommand
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent
from pyon.core.exception import Conflict

VALID_SAMPLE = "SATPAR0229,10.01,2206748544,234\r\n"
# Make tests verbose and provide stdout
# bin/nosetests -s -v ion/services/mi/drivers/test/test_satlantic_par.py
# All unit tests: add "-a UNIT" to end, integration add "-a INT"
# Test device is at 10.180.80.173, port 2001

VALID_HEADER = "Satlantic Digital PAR Sensor\r\n" + \
               "Copyright (C) 2003, Satlantic Inc. All rights reserved.\r\n" + \
               "Instrument: SATPAR\r\n" + \
               "S/N: 0226\r\n" + \
               "Firmware: 1.0.0\r\n"
VALID_FIRMWARE = "1.0.0"
VALID_SERIAL = "0226"
VALID_INSTRUMENT = "SATPAR"

@attr('UNIT', group='mi')
class SatlanticParProtocolUnitTest(InstrumentDriverUnitTestCase):
    """
    @todo test timeout exceptions while transitioning states and handling commands
    """
        
    #def setUp(self):
    """
    Mocked up stuff
    
    def response_side_effect(*args, **kwargs):
        if args[0] == Command.SAMPLE:
            mi_logger.debug("Side effecting!")
            return "SATPAR0229,10.01,2206748544,234"
        else:
            return DEFAULT
        
    self.mock_callback = Mock(name='callback')
    self.mock_logger = Mock(name='logger')
    self.mock_logger_client = Mock(name='logger_client')
    self.mock_fsm = Mock(name='fsm')
#        self.mock_logger_client.send = Mock()
    self.par_proto = SatlanticPARInstrumentProtocol(self.mock_callback)
    self.config_params = {'device_addr':'1.1.1.1',
                          'device_port':1,
                          'server_addr':'2.2.2.2',
                          'server_port':2}
    self.par_proto._fsm = self.mock_fsm
    self.par_proto.configure(self.config_params)
    self.par_proto.initialize()
    self.par_proto._logger = self.mock_logger 
    self.par_proto._logger_client = self.mock_logger_client
    self.par_proto._get_response = Mock(return_value=('$', None))
    # Quick sanity check to make sure the logger got mocked properly
    self.assertEquals(self.par_proto._logger, self.mock_logger)
    self.assertEquals(self.par_proto._logger_client, self.mock_logger_client)
    self.assertEquals(self.par_proto._fsm, self.mock_fsm)
    self.mock_logger_client.reset_mock()
    """
    

    @unittest.skip("Need better mocking of FSM or smaller testing chunks")
    def test_get_param(self):
        # try single
        result = self.par_proto.get([Parameter.MAXRATE])
        self.mock_logger_client.send.assert_called_with("show %s\n" %
                                                        Parameter.MAXRATE)
        
        # try group
        result = self.par_proto.get(Parameter.list())
        
        # try empty set
        self.mock_logger_client.reset_mock()
        result = self.par_proto.get([])
        self.assertEquals(result, {})
        self.assertEquals(self.mock_logger_client.send.call_count, 0)
        
        # try bad param
        self.assertRaises(InstrumentProtocolException, self.par_proto.get, None)
        self.assertRaises(InstrumentProtocolException,
                          self.par_proto.get,['bad_param'])

    @unittest.skip("Need better mocking of FSM or smaller testing chunks")    
    def test_set_param(self):
        #@todo deal with success/fail flag or catch everywhere?
        #@todo add save checks?
        self.par_proto.set({Parameter.TELBAUD:9600})
        self.mock_logger_client.send.assert_called_with("set %s 9600\n" %
                                                        Parameter.TELBAUD)
        self.mock_logger_client.send.assert_called_with("save")
        
        self.par_proto.set({Parameter.MAXRATE:10})
        self.mock_logger_client.send.assert_called_with("set %s 10\n" %
                                                        Parameter.MAXRATE)
        self.mock_logger_client.send.assert_called_with("save")
        
        # try group
        self.mock_logger_client.reset_mock()
        self.par_proto.set({Parameter.TELBAUD:4800,Parameter.MAXRATE:9})
        self.assertEquals(self.mock_logger_client.send.call_count, 3)

        # try empty set
        self.mock_logger_client.reset_mock()
        result = self.par_proto.set({})
        self.assertEquals(self.mock_logger_client.send.call_count, 0)
        self.assertEquals(result, {})
        
        # some error cases
        self.assertRaises(InstrumentProtocolException, self.par_proto.set, [])
        self.assertRaises(InstrumentProtocolException, self.par_proto.set, None)
        self.assertRaises(InstrumentProtocolException, self.par_proto.set, ['foo'])
        
        # try bad param
        self.assertRaises(InstrumentProtocolException,
                          self.par_proto.set,{'bad_param':0})
    
    @unittest.skip("Need better mocking of FSM or smaller testing chunks")
    def test_get_config(self):
        fetched_config = {}
        fetched_config = self.par_proto.get_config()
        self.assert_(isinstance(fetched_config, dict))
        calls = [call("show %s\n" % Parameter.TELBAUD),
                 call("show %s\n" % Parameter.MAXRATE)]
        self.mock_logger_client.send.assert_has_calls(calls, any_order=True)
        
        self.assertEquals(len(fetched_config), 2)
        self.assertTrue(fetched_config.has_key(Parameter.TELBAUD))
        self.assertTrue(fetched_config.has_key(Parameter.MAXRATE))
    
    @unittest.skip("Need better mocking of FSM or smaller testing chunks")
    def test_restore_config(self):
        self.assertRaises(InstrumentProtocolException,
                          self.par_proto.restore_config, None)    
     
        self.assertRaises(InstrumentProtocolException,
                          self.par_proto.restore_config, {})
        
        self.assertRaises(InstrumentProtocolException,
                          self.par_proto.restore_config, {'bad_param':0})

        test_config = {Parameter.TELBAUD:19200, Parameter.MAXRATE:2}
        restore_result = self.par_proto.restore_config(test_config)
        calls = [call("set %s %s\n" % (Parameter.TELBAUD, 19200)),
                 call("set %s %s\n" % (Parameter.MAXRATE, 2))]
        self.mock_logger_client.send.assert_has_calls(calls, any_order=True)
        
    @unittest.skip("Need better mocking of FSM or smaller testing chunks")
    def test_get_single_value(self):
        result = self.par_proto.execute_poll()
        calls = [call("%s\n" % Command.EXIT),
                 call(Command.STOP),
                 call(Command.SAMPLE),
                 call(Command.AUTOSAMPLE),
                 call(Command.BREAK)]
        self.mock_logger_client.send.assert_has_calls(calls, any_order=False)
        
    @unittest.skip("Need better mocking of FSM or smaller testing chunks")
    def test_breaks(self):
        # test kick to autosample, then back
        result = self.par_proto.execute_exit()        
        self.mock_callback.reset_mock()
        result = self.par_proto.execute_break()
        self.mock_logger_client.send.assert_called_with(Command.BREAK)        
        self.assertEqual(self.mock_callback.call_count, 1)

        # test autosample to poll change
        result = self.par_proto.execute_exit()
        self.mock_callback.reset_mock()
        result = self.par_proto.execute_stop()
        self.mock_logger_client.send.assert_called_with(Command.STOP)
        self.assertEqual(self.mock_callback.call_count, 1)

        result = self.par_proto.execute_autosample()
        self.mock_callback.reset_mock()
        result = self.par_proto.execute_reset()
        self.mock_logger_client.send.assert_called_with(Command.RESET)
        self.assertEqual(self.mock_callback.call_count, 1)

        self.mock_callback.reset_mock()
        result = self.par_proto.execute_break()
        self.mock_logger_client.send.assert_called_with(Command.BREAK)
        self.assertEqual(self.mock_callback.call_count, 1)
  
    @unittest.skip("Need better mocking of FSM or smaller testing chunks")
    def test_got_data(self):
        # Cant trigger easily since the async command/response, so short circut
        # the test early.
        self.mock_callback.reset_mock()
        result = self.par_proto.execute_exit()
        self.assertEqual(self.mock_callback.call_count, 1)
        self.assert_(result)
        self.mock_callback.reset_mock()
        result = self.par_proto._got_data("SATPAR0229,10.01,2206748544,234\n")
        # check for publish
        self.assertEqual(self.mock_callback.call_count, 2)

        # check for correct parse
        
    @unittest.skip("Need better mocking of FSM or smaller testing chunks")
    def test_connect_disconnect(self):
        pass
    
    @unittest.skip("Need better mocking of FSM or smaller testing chunks")
    def test_get_status(self):
        pass
    
    def test_sample_format(self):
        """
        Test to make sure we can get sample data out in a reasonable format.
        Parsed is all we care about...raw is tested in the base DataParticle tests
        VALID_SAMPLE = "SATPAR0229,10.01,2206748544,234"
        """
        
        port_timestamp = 3555423720.711772
        internal_timestamp = 3555423721.711772
        driver_timestamp = 3555423722.711772
        particle = SatlanticPARDataParticle(VALID_SAMPLE,
                                            port_timestamp=port_timestamp,
                                            internal_timestamp=internal_timestamp)
        # perform the extraction into a structure for parsed
        sample_parsed_particle = {
            DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
            DataParticleKey.PKT_VERSION: 1,
            DataParticleKey.STREAM_NAME: DataParticleValue.PARSED,
            DataParticleKey.PORT_TIMESTAMP: port_timestamp,
            DataParticleKey.DRIVER_TIMESTAMP: driver_timestamp,
            DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
            DataParticleKey.QUALITY_FLAG: DataParticleValue.OK,
            DataParticleKey.VALUES: [
                {DataParticleKey.VALUE_ID:SatlanticPARDataParticleKey.SERIAL_NUM,
                 DataParticleKey.VALUE:"0229"},
                {DataParticleKey.VALUE_ID:SatlanticPARDataParticleKey.TIMER,
                 DataParticleKey.VALUE:10.01},
                {DataParticleKey.VALUE_ID:SatlanticPARDataParticleKey.COUNTS,
                 DataParticleKey.VALUE: 2206748544},
                {DataParticleKey.VALUE_ID:SatlanticPARDataParticleKey.CHECKSUM,
                 DataParticleKey.VALUE: 234}
                ]
            }
        
        self.compare_parsed_data_particle(SatlanticPARDataParticle,
                                         VALID_SAMPLE,
                                         sample_parsed_particle)


    def test_chunker(self):
        """
        Tests the chunker
        """
        # This will want to be created in the driver eventually...
        chunker = StringChunker(SatlanticPARInstrumentProtocol.sieve_function)

        self.assert_chunker_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_sample(chunker, VALID_HEADER)

        self.assert_chunker_fragmented_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, VALID_HEADER)

        self.assert_chunker_combined_sample(chunker, VALID_SAMPLE)
        self.assert_chunker_combined_sample(chunker, VALID_HEADER)

        self.assert_chunker_sample_with_noise(chunker, VALID_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, VALID_HEADER)

    def test_extract_header(self):
        '''
        Test if we can extract the firmware, serial number and instrument label
        from the header.
        '''
        def event_callback(event):
            pass

        protocol = SatlanticPARInstrumentProtocol(event_callback)
        protocol._extract_header(VALID_HEADER)

        self.assertEqual(protocol._firmware, VALID_FIRMWARE)
        self.assertEqual(protocol._serial, VALID_SERIAL)
        self.assertEqual(protocol._instrument, VALID_INSTRUMENT)


#@unittest.skip("Need a VPN setup to test against RSN installation")
@attr('INT', group='mi')
class SatlanticParProtocolIntegrationTest(InstrumentDriverIntegrationTestCase):
    
    def check_state(self, expected_state):
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, expected_state)
        

    def put_instrument_in_command_mode(self):
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
        self.check_state(PARProtocolState.UNKNOWN)

        # Discover what state the instrument is in and set the protocol state accordingly.
        self.driver_client.cmd_dvr('discover_state')

        # Test that the driver protocol is in state command.
        self.check_state(PARProtocolState.COMMAND)


    def _start_stop_autosample(self):
        """Wrap the steps and asserts for going into and out of auto sample.
           May be used in multiple test cases.
        """
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_AUTOSAMPLE)

        self.check_state(PARProtocolState.AUTOSAMPLE)
        
        # @todo check samples arriving here
        # @todo check publishing samples from here
        
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)
                
        self.check_state(PARProtocolState.COMMAND)
        

    def test_configuration(self):
        """
        Test to configure the driver process for device comms and transition
        to disconnected state.
        """

        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver and transition to disconnected.
        self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Re-Initialize the driver and transition to unconfigured.
        self.driver_client.cmd_dvr('initialize')

        # Test that the driver returned to state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)
        

    def test_connect_disconnect(self):
        """
        Test configuring and connecting to the device through the port
        agent. Discover device state.  Then disconnect and re-initialize
        """
        self.put_instrument_in_command_mode()
        
        # Stop comms and transition to disconnected.
        self.driver_client.cmd_dvr('disconnect')

        # Test that the driver is in state disconnected.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Re-Initialize the driver and transition to unconfigured.
        self.driver_client.cmd_dvr('initialize')
    
        # Test that the driver returned to state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)
        

    def test_get(self):
        
        self.put_instrument_in_command_mode()

        params = {
                   Parameter.MAXRATE: 1,
                   Parameter.FIRMWARE: "1.0.0",
                   Parameter.SERIAL: "0226",
                   Parameter.INSTRUMENT: "SATPAR"
        }

        reply = self.driver_client.cmd_dvr('get_resource',
                                           params.keys(),
                                           timeout=20)
        
        self.assertEquals(reply, params)
        
        self.assertRaises(InstrumentCommandException,
                          self.driver_client.cmd_dvr,
                          'bogus', [Parameter.MAXRATE])

        # Assert get fails without a parameter.
        self.assertRaises(InstrumentParameterException,
                          self.driver_client.cmd_dvr, 'get_resource')
            
        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            self.driver_client.cmd_dvr('get_resource', bogus_params)
            
        # Assert get fails with a bad parameter in a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                Parameter.MAXRATE
                ]
            self.driver_client.cmd_dvr('get_resource', bogus_params)        
        

    def test_set(self):
        config_key = Parameter.MAXRATE
        value_A = 12
        value_B = 1
        config_A = {config_key:value_A}
        config_B = {config_key:value_B}
        
        self.put_instrument_in_command_mode()
        
        reply = self.driver_client.cmd_dvr('set_resource', config_A, timeout=20)
        self.assertEquals(reply[config_key], value_A)
                 
        reply = self.driver_client.cmd_dvr('get_resource', [config_key], timeout=20)
        self.assertEquals(reply, config_A)
        
        reply = self.driver_client.cmd_dvr('set_resource', config_B, timeout=20)
        self.assertEquals(reply[config_key], value_B)
         
        reply = self.driver_client.cmd_dvr('get_resource', [config_key], timeout=20)
        self.assertEquals(reply, config_B)

        # Assert we cannot set a bogus parameter.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name' : 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                Parameter.MAXRATE : 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
        
        
    #@unittest.skip('temp for debugging')
    def test_error_conditions(self):
        # Test that the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Assert we forgot the comms parameter.
        self.assertRaises(InstrumentParameterException,
                          self.driver_client.cmd_dvr, 'configure')

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
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        # Setup the protocol state machine and the connection to port agent.
        self.driver_client.cmd_dvr('connect')

        # Test that the driver protocol is in state unknown.
        self.check_state(PARProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        # Discover what state the instrument is in and set the protocol state accordingly.
        self.driver_client.cmd_dvr('discover_state')

        # Test that the driver protocol is in state command.
        self.check_state(PARProtocolState.COMMAND)

        # tests when driver is in command mode
        # Test a bad driver command 
        self.assertRaises(InstrumentCommandException, 
                          self.driver_client.cmd_dvr, 'bogus_command')
        
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'connect')

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.RESET)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_POLL)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.EXECUTE_DIRECT)

        # tests when driver is in auto-sample mode
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_AUTOSAMPLE)
        self.check_state(PARProtocolState.AUTOSAMPLE)

        # Test a bad driver command 
        self.assertRaises(InstrumentCommandException, 
                          self.driver_client.cmd_dvr, 'bogus_command')
        
        # Test get from wrong state
        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'get_resource', [Parameter.MAXRATE])

        # Test set from wrong state
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'set_resource', {Parameter.MAXRATE:10})

        # test commands for invalid state
        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.EXECUTE_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_POLL)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_AUTOSAMPLE)

        # tests when driver is in poll mode
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_POLL)
        self.check_state(PARProtocolState.POLL)

        # Test a bad driver command 
        self.assertRaises(InstrumentCommandException, 
                          self.driver_client.cmd_dvr, 'bogus_command')
        
        # Test get from wrong state
        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'get_resource', [Parameter.MAXRATE])

        # Test set from wrong state
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'set_resource', {Parameter.MAXRATE:10})

        # test commands for invalid state
        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.EXECUTE_DIRECT)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)

        self.assertRaises(InstrumentStateException, 
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_POLL)


    def test_stop_from_slow_autosample(self):
        # test break from autosample at low data rates
        self.put_instrument_in_command_mode()
        
        self.driver_client.cmd_dvr('set_resource', {Parameter.MAXRATE:1}, timeout=20)

        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_AUTOSAMPLE)
        #time.sleep(5)
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)
        self.check_state(PARProtocolState.COMMAND)


    def test_stop_from_fast_autosample(self):
        # test break from autosample at high data rates
        self.put_instrument_in_command_mode()
        
        self.driver_client.cmd_dvr('set_resource', {Parameter.MAXRATE:12}, timeout=20)

        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_AUTOSAMPLE)
        #time.sleep(5)
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.STOP_AUTOSAMPLE)
        self.check_state(PARProtocolState.COMMAND)
        self.driver_client.cmd_dvr('set_resource', {Parameter.MAXRATE:1}, timeout=20)



    def test_start_stop_autosample(self):
        """
        Test moving into and out of autosample, gathering some data, and
        seeing it published
        @todo check the publishing, integrate this with changes in march 2012
        """

        self.put_instrument_in_command_mode()
        self._start_stop_autosample()
                

    def test_start_stop_poll(self):
        self.put_instrument_in_command_mode()
        
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.START_POLL)
        self.check_state(PARProtocolState.POLL)
        time.sleep(2)

        # Already in poll mode, so this shouldn't give us anything
        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr, 'execute_resource', PARProtocolEvent.START_POLL)
        
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.ACQUIRE_SAMPLE)

        # @todo check samples arriving here
        # @todo check publishing samples from here
        
        self.driver_client.cmd_dvr('execute_resource', PARProtocolEvent.STOP_POLL)        
        self.check_state(PARProtocolState.COMMAND)




    @unittest.skip('Need to write this test')
    def test_reset(self):
        pass

        
@attr('UNIT', group='mi')
class SatlanticParDecoratorTest(PyonTestCase):
    
    def setUp(self):
        self.checksum_decorator = SatlanticChecksumDecorator()
    
    def test_checksum(self):
        self.assertEquals(("SATPAR0229,10.01,2206748544,234","SATPAR0229,10.01,2206748544,234"),
            self.checksum_decorator.handle_incoming_data("SATPAR0229,10.01,2206748544,234","SATPAR0229,10.01,2206748544,234"))
        self.assertRaises(InstrumentDataException,
                          self.checksum_decorator.handle_incoming_data,
                          "SATPAR0229,10.01,2206748544,235",
                          "SATPAR0229,10.01,2206748544,235")


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class SatlanticParProtocolQualificationTest(InstrumentDriverQualificationTestCase):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  

    def assertSampleDataParticle(self, val):
        """
        Verify the value for a par sample data particle

        {
          'quality_flag': 'ok',
          'preferred_timestamp': 'driver_timestamp',
          'stream_name': 'parsed',
          'pkt_format_id': 'JSON_Data',
          'pkt_version': 1,
          'driver_timestamp': 3559843883.8029947,
          'values': [
            {'value_id': 'serial_num', 'value': '0226'},
            {'value_id': 'timer', 'value': 7.17},
            {'value_id': 'counts', 'value': 2157033280},
            {'value_id': 'checksum', 'value': 27}
          ],
        }
        """

        if (isinstance(val, SatlanticPARDataParticle)):
            sample_dict = json.loads(val.generate_parsed())
        else:
            sample_dict = val

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
            DataParticleValue.PARSED)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
            DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
            list))
        self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        for x in sample_dict['values']:
            self.assertTrue(x['value_id'] in ['serial_num', 'timer', 'counts', 'checksum'])
            log.debug("ID: %s value: %s type: %s" % (x['value_id'], x['value'], type(x['value'])))
            if(x['value_id'] == 'timer'):
                self.assertTrue(isinstance(x['value'], float))
            elif(x['value_id'] == 'serial_num'):
                self.assertTrue(isinstance(x['value'], str))
            elif(x['value_id'] == 'counts'):
                self.assertTrue(isinstance(x['value'], int))
            elif(x['value_id'] == 'checksum'):
                self.assertTrue(isinstance(x['value'], int))
            else:
                # Shouldn't get here.  If we have then we aren't checking a parameter
                self.assertFalse(True)

    @unittest.skip("Just because")
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("\r\n")
        self.tcp_client.expect("Invalid command")

        self.assert_direct_access_stop_telnet()

    @unittest.skip("polled mode note implemented")
    def test_poll(self):
        '''
        No polling for a single sample
        '''

        #self.assert_sample_polled(self.assertSampleDataParticle,
        #                          DataParticleValue.PARSED)

    def test_autosample(self):
        '''
        start and stop autosample and verify data particle
        '''
        self.assert_sample_autosample(self.assertSampleDataParticle,
                                      DataParticleValue.PARSED)


    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get set properly
        '''
        self.assert_enter_command_mode()

        self.assert_set_parameter(Parameter.MAXRATE, 4)
        self.assert_set_parameter(Parameter.MAXRATE, 1)

        self.assert_get_parameter(Parameter.FIRMWARE, "1.0.0")
        self.assert_get_parameter(Parameter.SERIAL, "0226")
        self.assert_get_parameter(Parameter.INSTRUMENT, "SATPAR")

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
            AgentCapabilityType.AGENT_COMMAND: [
                ResourceAgentEvent.CLEAR,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_DIRECT_ACCESS,
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.PAUSE
            ],
            AgentCapabilityType.AGENT_PARAMETER: ['example'],
            AgentCapabilityType.RESOURCE_COMMAND: [
                DriverEvent.SET, DriverEvent.ACQUIRE_SAMPLE, DriverEvent.GET,
                PARProtocolEvent.START_POLL, DriverEvent.START_AUTOSAMPLE
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: [
                Parameter.INSTRUMENT, Parameter.SERIAL, Parameter.MAXRATE, Parameter.FIRMWARE

            ],
        }

        self.assert_capabilities(capabilities)

        ##################
        #  Polled Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [
            ResourceAgentEvent.CLEAR,
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.GO_DIRECT_ACCESS,
            ResourceAgentEvent.GO_INACTIVE,
            ResourceAgentEvent.PAUSE,
        ]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [
            DriverEvent.START_AUTOSAMPLE, DriverEvent.RESET, PARProtocolEvent.STOP_POLL
        ]

        self.assert_switch_driver_state(PARProtocolEvent.START_POLL, DriverProtocolState.POLL)

        self.assert_capabilities(capabilities)

        self.assert_switch_driver_state(PARProtocolEvent.STOP_POLL, DriverProtocolState.COMMAND)


        ##################
        #  Streaming Mode
        ##################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ ResourceAgentEvent.RESET, ResourceAgentEvent.GO_INACTIVE ]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            PARProtocolEvent.START_POLL,
            DriverEvent.STOP_AUTOSAMPLE,
            DriverEvent.RESET
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        #######################
        #  Uninitialized Mode
        #######################

        capabilities[AgentCapabilityType.AGENT_COMMAND] = [ResourceAgentEvent.INITIALIZE]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)

