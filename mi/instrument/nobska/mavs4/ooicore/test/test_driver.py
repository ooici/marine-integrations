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

# 3rd party imports
from nose.plugins.attrib import attr

from prototype.sci_data.stream_defs import ctd_stream_definition

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException

from mi.instrument.nobska.mavs4.ooicore.driver import DataParticleType
from mi.instrument.nobska.mavs4.ooicore.driver import mavs4InstrumentDriver
from mi.instrument.nobska.mavs4.ooicore.driver import ProtocolStates
from mi.instrument.nobska.mavs4.ooicore.driver import ProtocolEvent
from mi.instrument.nobska.mavs4.ooicore.driver import InstrumentParameters

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.core.tcp_client import TcpClient

# MI logger
from mi.core.log import get_logger ; log = get_logger()
from interface.objects import AgentCommand

from ion.agents.instrument.instrument_agent import InstrumentAgentState

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

# 'will echo' command sequence to be sent from DA telnet server
# see RFCs 854 & 857
WILL_ECHO_CMD = '\xff\xfd\x03\xff\xfb\x03\xff\xfb\x01'
# 'do echo' command sequence to be sent back from telnet client
DO_ECHO_CMD   = '\xff\xfb\x03\xff\xfd\x03\xff\xfd\x01'

# Used to validate param config retrieved from driver.
parameter_types = {
    InstrumentParameters.SYS_CLOCK : str,
    InstrumentParameters.NOTE1 : str,
    InstrumentParameters.NOTE2 : str,
    InstrumentParameters.NOTE3 : str,
    InstrumentParameters.VELOCITY_FRAME : int,
    InstrumentParameters.MONITOR : str,
    InstrumentParameters.LOG_DISPLAY_TIME : str,
    InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND : str,
    InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES : str,
    InstrumentParameters.QUERY_MODE : str,
    InstrumentParameters.FREQUENCY : float,

}

parameter_list = [
    InstrumentParameters.SYS_CLOCK,
    InstrumentParameters.NOTE1,
    InstrumentParameters.NOTE2,
    InstrumentParameters.NOTE3,
    InstrumentParameters.VELOCITY_FRAME,
    InstrumentParameters.MONITOR,
    InstrumentParameters.LOG_DISPLAY_TIME,
    InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND,
    InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES,
    InstrumentParameters.QUERY_MODE,
    InstrumentParameters.FREQUENCY,
    """
    InstrumentParameters.MEASUREMENTS_PER_SAMPLE,
    InstrumentParameters.SAMPLE_PERIOD,
    InstrumentParameters.SAMPLES_PER_BURST,
    InstrumentParameters.BURST_INTERVAL,
    """
]
    
## Initialize the test configuration
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.nobska.mavs4.ooicore.driver',
    driver_class="mavs4InstrumentDriver",

    instrument_agent_resource_id = 'nobska_mavs4_ooicore',
    instrument_agent_name = 'nobska_mavs4_ooicore_agent',
    instrument_agent_packet_config = DataParticleType()
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

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################

@attr('UNIT', group='mi')
class Testmavs4_UNIT(InstrumentDriverTestCase):
    """Unit Test Container"""
    
    def setUp(self):
        """
        @brief initialize mock objects for the protocol object.
        """
        #self.callback = Mock(name='callback')
        #self.logger = Mock(name='logger')
        #self.logger_client = Mock(name='logger_client')
        #self.protocol = mavs4InstrumentProtocol()
    
        #self.protocol.configure(self.comm_config)
        #self.protocol.initialize()
        #self.protocol._logger = self.logger 
        #self.protocol._logger_client = self.logger_client
        #self.protocol._get_response = Mock(return_value=('$', None))
        
        # Quick sanity check to make sure the logger got mocked properly
        #self.assertEquals(self.protocol._logger, self.logger)
        #self.assertEquals(self.protocol._logger_client, self.logger_client)
        
    ###
    #    Add driver specific unit tests
    ###
    
    
###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class Testmavs4_INT(InstrumentDriverIntegrationTestCase):
    """Integration Test Container"""
    
    @staticmethod
    def driver_module():
        return 'mi.instrument.nobska.mavs4.ooicore.driver'
        
    @staticmethod
    def driver_class():
        return 'mavs4InstrumentDriver'    
    

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
            self.assertEqual(val, correct_params[key],
                             '%s: %s != %s' %(key, val, correct_params[key]))

    def assertParamList(self, pl):
        """
        Verify all device parameters.
        """
        self.assertEqual(pl, TestInstrumentParameters.list())
    
    @unittest.skip("override & skip while in development")
    def test_driver_process(self):
        pass 

    
    def test_instrument_wakeup(self):
        """
        @brief Test for instrument wakeup, expects instrument to be in 'command' state
        """
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms and in disconnected state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Connect to instrument and transition to unknown.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.UNKNOWN)

        # discover instrument state and transition to command.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.COMMAND)
                
               
    def test_get_set(self):
        """
        Test device parameter access.
        """
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms and in disconnected state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Connect to instrument and transition to unknown.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.UNKNOWN)

        # discover instrument state and transition to command.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.COMMAND)

        # get the list of device parameters
        reply = self.driver_client.cmd_dvr('get_resource', InstrumentParameters.ALL)
        #self.assertParamDictionariesEqual(reply, parameter_types, True)

        """
        # Get all device parameters. Confirm all expected keys are retrieved
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', InstrumentParameters.ALL)
        self.assertParamDict(reply, True)

        log.debug("test_get_set: parameters:" )
        for parameter in parameter_list:
            log.debug("%s = %s" %(parameter, reply[parameter]))
        
        # Remember original configuration.
        orig_config = reply
        """
        
        # Grab a subset of parameters.
        #params = [InstrumentParameters.SYS_CLOCK]
        #params = [InstrumentParameters.NOTE3]
        #params = [InstrumentParameters.VELOCITY_FRAME]
        """
        params = [InstrumentParameters.MONITOR,
                  InstrumentParameters.LOG_DISPLAY_TIME,
                  InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND,
                  InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES]
        """
        #params = [InstrumentParameters.QUERY_MODE]
        params = [InstrumentParameters.FREQUENCY]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamDictionariesEqual(reply, parameter_types)
        for (name, value) in reply.iteritems():
            log.debug('parameter %s=%s' %(name, value))        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        #new_params = {InstrumentParameters.SYS_CLOCK : '03/29/2002 11:11:42'}
        #new_params = {InstrumentParameters.NOTE3 : 'New note3 at %s' %time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())}
        #new_params = {InstrumentParameters.VELOCITY_FRAME : 4}
        """
        new_params = {InstrumentParameters.MONITOR : 'n',
                      InstrumentParameters.LOG_DISPLAY_TIME : 'y',
                      InstrumentParameters.LOG_DISPLAY_FRACTIONAL_SECOND : 'y',
                      InstrumentParameters.LOG_DISPLAY_ACOUSTIC_AXIS_VELOCITIES : 'SI'}
        """
        #new_params = {InstrumentParameters.QUERY_MODE : 'n'}
        new_params = {InstrumentParameters.FREQUENCY : 3.3}
        # Set parameters and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        reply = self.driver_client.cmd_dvr('get_resource', params)
        for (name, value) in reply.iteritems():
            log.debug('name=%s, set=%s, got=%s' %(name, new_params[name], value))
        self.assertParamVals(reply, new_params)
        
        """
        # Restore original parameters and verify.
        reply = self.driver_client.cmd_dvr('set_resource', orig_params)
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamVals(reply, orig_params)

        # Retrieve the configuration and ensure it matches the original.
        reply = self.driver_client.cmd_dvr('get_resource', InstrumentParameters.ALL)
        self.assertParamVals(reply, orig_config)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is disconnected.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED) 
        """       

    def test_instrumment_autosample(self):
        """
        @brief Test for instrument wakeup, expects instrument to be in 'command' state
        """
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms and in disconnected state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Connect to instrument and transition to unknown.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.UNKNOWN)

        # discover instrument state and transition to command.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.COMMAND)
                
        # start auto-sample.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvents.START_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, ProtocolStates.AUTOSAMPLE)
                
        # stop auto-sample.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvents.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolStates.COMMAND)
                

    ###
    #    Add driver specific integration tests
    ###

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
               
