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
import logging
import time
from mock import Mock, call, DEFAULT
from pyon.util.unit_test import PyonTestCase
from nose.plugins.attrib import attr
from unittest import TestCase

from mi.core.common import InstErrorCode
from mi.core.instrument.instrument_driver import DriverState
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_protocol import InterfaceType

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentDataException
from mi.core.exceptions import InstrumentCommandException
from mi.core.exceptions import InstrumentStateException

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from mi.instrument.satlantic.par_ser_600m.ooicore.driver import SatlanticPARInstrumentProtocol
from mi.instrument.satlantic.par_ser_600m.ooicore.driver import PARProtocolState
from mi.instrument.satlantic.par_ser_600m.ooicore.driver import Parameter
from mi.instrument.satlantic.par_ser_600m.ooicore.driver import Command
from mi.instrument.satlantic.par_ser_600m.ooicore.driver import SatlanticChecksumDecorator
from mi.instrument.satlantic.par_ser_600m.ooicore.driver import sample_regex

mi_logger = logging.getLogger('mi_logger')

# Make tests verbose and provide stdout
# bin/nosetests -s -v ion/services/mi/drivers/test/test_satlantic_par.py
# All unit tests: add "-a UNIT" to end, integration add "-a INT"
# Test device is at 10.180.80.173, port 2001

InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.satlantic.par_ser_600m.ooicore.driver',
    driver_class="SatlanticPARInstrumentDriver",

    instrument_agent_resource_id = 'satlantic_par_ser_600m_ooicore',
    instrument_agent_name = 'satlantic_par_ser_600m_ooicore_agent',
    #instrument_agent_packet_config = PACKET_CONFIG,
    #instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
)

@unittest.skip("Need better mocking of FSM or smaller testing chunks")
@attr('UNIT', group='mi')
class SatlanticParProtocolUnitTest(InstrumentDriverUnitTestCase):
    """
    @todo test timeout exceptions while transitioning states and handling commands
    """
        
    def setUp(self):
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
    
    def test_get_param(self):
        # try single
        result = self.par_proto.get([Parameter.TELBAUD])
        self.mock_logger_client.send.assert_called_with("show %s\n" %
                                                        Parameter.TELBAUD)
        
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
        
    def test_get_single_value(self):
        result = self.par_proto.execute_poll()
        calls = [call("%s\n" % Command.EXIT),
                 call(Command.STOP),
                 call(Command.SAMPLE),
                 call(Command.AUTOSAMPLE),
                 call(Command.BREAK)]
        self.mock_logger_client.send.assert_has_calls(calls, any_order=False)
        
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
        
    def test_connect_disconnect(self):
        pass
    
    def test_get_status(self):
        pass

#@unittest.skip("Need a VPN setup to test against RSN installation")
@attr('INT', group='mi')
class SatlanticParProtocolIntegrationTest(InstrumentDriverIntegrationTestCase):
    def _clean_up(self):
        # set back to command mode
        if self.driver_client:
            try:
                reply = self.driver_client.cmd_dvr('execute_break')
            except InstrumentStateError:
                # no biggie if we are already in cmd mode
                pass
            reply = self.driver_client.cmd_dvr('set',
                                             {Parameter.MAXRATE:1},
                                              timeout=20)
            self._disconnect()
        

    def tearDown(self):
        super(SatlanticParProtocolIntegrationTest, self).tearDown()
        self._clean_up()

    def _initialize(self):
        reply = self.driver_client.cmd_dvr('execute_init_device')
        time.sleep(1)

    def _connect(self):
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.UNCONFIGURED, reply)
        configs = self.config_params
        reply = self.driver_client.cmd_dvr('configure', configs)
        self.assertEqual(reply, None)
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.DISCONNECTED, reply)
        reply = self.driver_client.cmd_dvr('connect')
        self.assertEqual(reply, None)
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverProtocolState.UNKNOWN, reply)

        self._initialize()
        
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)

        time.sleep(1)

    def _disconnect(self):
        reply = self.driver_client.cmd_dvr('disconnect')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.DISCONNECTED, reply)
        time.sleep(1)

    def _start_stop_autosample(self):
        """Wrap the steps and asserts for going into and out of auto sample.
        May be used in multiple test cases.
        """
        reply = self.driver_client.cmd_dvr('execute_start_autosample')

        time.sleep(5)
        
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.AUTOSAMPLE_MODE, reply)
        
        # @todo check samples arriving here
        # @todo check publishing samples from here
        
        reply = self.driver_client.cmd_dvr('execute_stop_autosample')
                
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)

    def test_connect_disconnect(self):
        """Instrument connect and disconnect"""
        # Basic behavior for all tests includes connect and disconnect
        # in test harness
        pass
    
    def test_bad_driver_command(self):
        """Test a bad driver command being sent to the driver client"""
        self.assertRaises(InstrumentCommandException,
                          self.driver_client.cmd_dvr, 'get_status')
        
    def test_start_stop_autosample(self):
        """
        Test moving into and out of autosample, gathering some data, and
        seeing it published
        @todo check the publishing, integrate this with changes in march 2012
        """
        # get into command mode and try it
        reply = self.driver_client.cmd_dvr('execute_break')

        self._start_stop_autosample()
        
        # try it from autosample mode now
        reply = self.driver_client.cmd_dvr('execute_poll')

        self._start_stop_autosample()
        
    def test_get(self):
        # Should default to command mode
        reply = self.driver_client.cmd_dvr('get', [Parameter.TELBAUD,
                                                   Parameter.MAXRATE],
                                           timeout=20)
        self.assertEquals(reply, {Parameter.TELBAUD:19200,
                                  Parameter.MAXRATE:1})
        
        self.assertRaises(InstrumentCommandException,
                          self.driver_client.cmd_dvr,
                          'bogus', [Parameter.TELBAUD])

    def test_set(self):
        config_key = Parameter.MAXRATE
        config_A = {config_key:2}
        config_B = {config_key:1}
        
        # Should default to command mode
        reply = self.driver_client.cmd_dvr('set', config_A, timeout=20)
        self.assertEquals(reply[config_key], 2)
                 
        reply = self.driver_client.cmd_dvr('get', [config_key], timeout=20)
        self.assertEquals(reply, config_A)
        
        reply = self.driver_client.cmd_dvr('set', config_B, timeout=20)
        self.assertEquals(reply[config_key], 1)
         
        reply = self.driver_client.cmd_dvr('get', [config_key], timeout=20)
        self.assertEquals(reply, config_B)
        
    def test_get_from_wrong_state(self):
        """Test get() from wrong state
        
        @todo Fix this to handle exceptions/errors across the zmq boundry
        """
        self.driver_client.cmd_dvr('execute_start_autosample')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.AUTOSAMPLE_MODE, reply)

        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr,
                          'get', [Parameter.MAXRATE])

    def test_set_from_wrong_state(self):
        """Test set() from wrong state
        @todo exception across thread
        """
        self.driver_client.cmd_dvr('execute_start_autosample')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.AUTOSAMPLE_MODE, reply)

        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr,
                          'set', {Parameter.MAXRATE:10})

    def test_get_config(self):
        """
        """
        # Should default to command mode
        reply = self.driver_client.cmd_dvr('get_config')
        self.assertEquals(len(reply.items()), 2)
        self.assertEquals(reply[Parameter.TELBAUD], 19200)
        self.assertEquals(reply[Parameter.MAXRATE], 1)

        # Put in the wrong mode, then try it
        reply = self.driver_client.cmd_dvr('execute_start_autosample')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.AUTOSAMPLE_MODE, reply)

        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr,
                          'get_config')
        
    def test_restore_config(self):
        """
        """
        config = self.driver_client.cmd_dvr('get_config')
        self.assertEquals(len(config.items()), 2)
        self.assertEquals(config[Parameter.TELBAUD], 19200)
        self.assertEquals(config[Parameter.MAXRATE], 1)

        config[Parameter.MAXRATE] = 2
        config = self.driver_client.cmd_dvr('restore_config', config)
        self.assertEquals(config[Parameter.MAXRATE], 2)
        
        config = self.driver_client.cmd_dvr('get_config')
        self.assertEquals(len(config.items()), 2)
        self.assertEquals(config[Parameter.TELBAUD], 19200)
        self.assertEquals(config[Parameter.MAXRATE], 2)

        # clean up
        config[Parameter.MAXRATE] = 1
        config = self.driver_client.cmd_dvr('restore_config', config)
        self.assertEquals(config[Parameter.MAXRATE], 1)

        # test from wrong state
        reply = self.driver_client.cmd_dvr('execute_start_autosample')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.AUTOSAMPLE_MODE, reply)

        self.assertRaises(InstrumentStateException,
                          self.driver_client.cmd_dvr,
                          'restore_config', config)

    def test_break_from_slow_autosample(self):
        # test break from autosample at low data rates
        reply = self.driver_client.cmd_dvr('execute_start_autosample')
        time.sleep(5)
        reply = self.driver_client.cmd_dvr('execute_break')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)

    def test_break_from_fast_autosample(self):
        # test break from autosample at high data rates
        reply = self.driver_client.cmd_dvr('set',
                                           {Parameter.MAXRATE:12},
                                           timeout=20)

        reply = self.driver_client.cmd_dvr('execute_start_autosample')
        time.sleep(5)
        reply = self.driver_client.cmd_dvr('execute_break')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)


    def test_break_from_poll(self):
        # Now try it from poll mode
        self.driver_client.cmd_dvr('execute_poll')
        time.sleep(2)

        # Already in poll mode, so this shouldnt give us anything
        self.assertRaises(InstrumentStateException,
                  self.driver_client.cmd_dvr,
                  'execute_poll')
        
        reply = self.driver_client.cmd_dvr('execute_break')        
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)
    
    """
    @todo Test reset function
    def test_reset(self):
        pass
    """
    """
    @todo test any commands not already tested
    def test_commands(self):
        # check all the exec commands that havent been tested already
        pass
    """
    def test_get_sample_from_cmd_mode(self):
        """Get some samples directly from command mode"""
        reply_1 = self.driver_client.cmd_dvr('execute_acquire_sample')
        self.assertTrue(sample_regex.match(reply_1))        
    
        # Get data
        reply_2 = self.driver_client.cmd_dvr('execute_acquire_sample')
        self.assertTrue(sample_regex.match(reply_2))
        self.assertNotEqual(reply_1, reply_2)
        
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)
        
    def test_double_poll_mode(self):
        """Mainly check the format of the manual sample that comes out
        @todo Finish this out...is the transition right for getting into poll mode?
        """
        self.driver_client.cmd_dvr('execute_poll')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.POLL_MODE, reply)
        
        # Get data
        result = self.driver_client.cmd_dvr('execute_acquire_sample')        
        self.assertTrue(sample_regex.match(result))
        
    def test_get_data_sample_via_poll_mode(self):
        """Mainly check the format of the manual sample that comes out
        @todo Finish this out...is the transition right for getting into poll mode?
        """
        self.driver_client.cmd_dvr('execute_poll')
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.POLL_MODE, reply)
        
        # Get data
        reply_1 = self.driver_client.cmd_dvr('execute_acquire_sample')
        
        self.assertTrue(sample_regex.match(reply_1))        
    
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.POLL_MODE, reply)

        # Get data
        reply_2 = self.driver_client.cmd_dvr('execute_acquire_sample')
        
        self.assertTrue(sample_regex.match(reply_2))
        self.assertNotEqual(reply_1, reply_2)

        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.POLL_MODE, reply)
        
        self.driver_client.cmd_dvr('execute_break')
        
        reply = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)
        
    '''
    def test_publish(self):
        """Test publishing of data...somehow"""
    '''
    def test_save(self):
        """Test saving parameters, regardless of specific save since we save
        at every set."""
        config_key = Parameter.MAXRATE
        config_A = {config_key:2}
        config_B = {config_key:1}
        
        # get max rate value
        reply = self.driver_client.cmd_dvr('get', [config_key], timeout=10)
        self.assertEquals(reply, config_B)
        
        # change it to something else, save, reset
        reply = self.driver_client.cmd_dvr('set', config_A, timeout=10)
        self.assertEquals(reply, config_A)
        reply = self.driver_client.cmd_dvr('execute_exit_and_reset',
                                           timeout=20)
        reply = self.driver_client.cmd_dvr('execute_break',
                                           timeout=20)
        
        # get max rate value, verify equal to saved value
        reply = self.driver_client.cmd_dvr('get', [config_key], timeout=10)
        self.assertEquals(reply, config_A)
        
        # change maxrate value, do NOT save, reset and check
        reply = self.driver_client.cmd_dvr('set', config_B, timeout=10)
        self.assertEquals(reply, config_B)
        reply = self.driver_client.cmd_dvr('get', [config_key], timeout=10)
        self.assertEquals(reply, config_B)
        reply = self.driver_client.cmd_dvr('execute_exit_and_reset',
                                           timeout=20)
        reply = self.driver_client.cmd_dvr('execute_break',
                                           timeout=20)
        
        # get max rate value, verify equal to saved value
        reply = self.driver_client.cmd_dvr('get', [config_key], timeout=10)
        self.assertEquals(reply, config_B)
        
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


@attr('QUAL', group='mi')
class QualFromIDK(InstrumentDriverQualificationTestCase):
    pass

