"""
@package mi.instrument.uw.bars.ooicore.test.test_driver
@file /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/uw/bars/ooicore/driver.py
@author Steve Foley
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/uw/bars/ooicore
       $ bin/nosetests -s -v /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/uw/bars/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/uw/bars/ooicore -a INT
       $ bin/nosetests -s -v /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/uw/bars/ooicore -a QUAL
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import unittest
import json
import time

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.exceptions import InstrumentTimeoutException

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.util import convert_enum_to_dict 

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.uw.bars.ooicore.driver import Protocol
from mi.instrument.uw.bars.ooicore.driver import ooicoreInstrumentDriver
from mi.instrument.uw.bars.ooicore.driver import Protocol
from mi.instrument.uw.bars.ooicore.driver import ProtocolState
from mi.instrument.uw.bars.ooicore.driver import ProtocolEvent
from mi.instrument.uw.bars.ooicore.driver import Parameter, VisibleParameters
from mi.instrument.uw.bars.ooicore.driver import Command
from mi.instrument.uw.bars.ooicore.driver import Capability
from mi.instrument.uw.bars.ooicore.driver import SubMenu
from mi.instrument.uw.bars.ooicore.driver import BarsDataParticleKey
from mi.instrument.uw.bars.ooicore.driver import COMMAND_CHAR
from mi.instrument.uw.bars.ooicore.driver import PACKET_CONFIG


###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.uw.bars.ooicore.driver',
    driver_class="ooicoreInstrumentDriver",

    instrument_agent_resource_id = 'QN341A',
    instrument_agent_name = 'uw_bars_ooicore',
    instrument_agent_packet_config = {},
    instrument_agent_stream_definition = {}
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
MANGLED_SAMPLE = ".  4.  .095  4.095  0.014  0.048  1.995  1.041  24.74  0.000   24.7   9.2\r\n"
LETTER_SAMPLE = "1.448  4.095  4.095  A.BCD  0.014  0.048  1.995  1.041  24.74  0.000   24.7   9.2\r\n"
FULL_SAMPLE = "1.448  4.095  4.095  0.004  0.014  0.048  1.995  1.041  24.74  0.000   24.7   9.2\r\n"
SAMPLE_FRAGMENT_1 = "1.448  4.095  4.095  0.004  0.014  0.0" 
SAMPLE_FRAGMENT_2 = "48  1.995  1.041  24.74  0.000   24.7   9.2\r\n"

STARTUP_TIMEOUT = 120

###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class UnitFromIDK(InstrumentDriverUnitTestCase):
	###
	# 	Reset test verification variables.  The purpose of this method is
	#	to reset the test verification variables to initial values.  The
	#	individual tests should cause the variables to be set (for instance,
	#	raw_stream_received would be set to True), and the tests should verify
	#	that the variables have been set to the expected values.
	###
	    
    def reset_test_vars(self):	
        self.raw_stream_received = False
        self.parsed_stream_received = False

	###
	#	This is the callback that would normally publish events 
	#	(streams, state transitions, etc.).
	#	Use this method to test for existence of events and to examine their
	#	attributes for correctness.
	###
	
    def my_event_callback(self, event):
        event_type = event['type']
        print str(event)
        if event_type == DriverAsyncEvent.SAMPLE:
            sample_value = event['value']
	    particle_dict = json.loads(sample_value)
	    stream_type = particle_dict['stream_name']	    
            if stream_type == 'raw':
                self.raw_stream_received = True
            elif stream_type == 'parsed':
                self.parsed_stream_received = True

    def test_get_current_capabilities(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=LoggerClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """       
        test_driver = ooicoreInstrumentDriver(self.my_event_callback)
        
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to the DISCONNECTED state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)
	result = test_driver._protocol.get_resource_capabilities()
	self.assertEqual(result[0], [])
	self.assertEqual(result[1], [Parameter.ALL, Parameter.CYCLE_TIME])

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)
	result = test_driver._protocol.get_resource_capabilities()
	self.assertEqual(result[0], [Capability.STOP_AUTOSAMPLE])
	self.assertEqual(result[1], [Parameter.ALL, Parameter.CYCLE_TIME])
	
	test_driver.test_force_state(state = DriverProtocolState.COMMAND)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.COMMAND)
	result = test_driver._protocol.get_resource_capabilities()
	self.assert_(Capability.START_AUTOSAMPLE in result[0])
	self.assert_(Capability.GET in result[0])
	self.assert_(Capability.SET in result[0])
	self.assert_(Capability.START_DIRECT in result[0])
	self.assertEqual(result[1], [Parameter.ALL, Parameter.CYCLE_TIME])

	test_driver.test_force_state(state = DriverProtocolState.DIRECT_ACCESS)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.DIRECT_ACCESS)
	result = test_driver._protocol.get_resource_capabilities()
	self.assert_(Capability.STOP_DIRECT in result[0])
	self.assert_(Capability.EXECUTE_DIRECT in result[0])
	self.assertEqual(result[1], [Parameter.ALL, Parameter.CYCLE_TIME])

    def test_enum_dups(self):
	self.assert_enum_has_no_duplicates(Command)
	self.assert_enum_has_no_duplicates(SubMenu)
	self.assert_enum_has_no_duplicates(ProtocolState)
	self.assert_enum_has_no_duplicates(ProtocolEvent)
	self.assert_enum_has_no_duplicates(Capability)
	self.assert_enum_has_no_duplicates(Parameter)
	self.assert_enum_has_no_duplicates(VisibleParameters)
	self.assert_enum_has_no_duplicates(BarsDataParticleKey)

	capability = convert_enum_to_dict(Capability)
	event = convert_enum_to_dict(ProtocolEvent)
	cmd = convert_enum_to_dict(Command)
	cmd_char = COMMAND_CHAR
	param = convert_enum_to_dict(Parameter)
	viz = convert_enum_to_dict(VisibleParameters)
	
	self.assert_set_complete(capability, event)
	self.assert_set_complete(cmd_char, cmd)
	self.assert_set_complete(viz, param)

    def test_valid_complete_sample(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=LoggerClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """       
        test_driver = ooicoreInstrumentDriver(self.my_event_callback)
        
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to the DISCONNECTED state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        """
        - Reset test verification variables.
        - Construct a complete sample
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        self.reset_test_vars()
	packet = PortAgentPacket() 
        header = "\xa3\x9d\x7a\x02\x00\x1c\x0b\x2e\x00\x00\x00\x01\x80\x00\x00\x00" 
        packet.unpack_header(header) 
        packet.attach_data(FULL_SAMPLE) 

        test_driver._protocol.got_data(packet)
        
        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)

    def test_invalid_complete_sample(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=LoggerClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """       
        test_driver = ooicoreInstrumentDriver(self.my_event_callback)
        
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to the DISCONNECTED state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        """
        - Reset test verification variables.
        - Construct a complete sample
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        self.reset_test_vars()
	
	packet = PortAgentPacket() 
        header = "\xa3\x9d\x7a\x02\x00\x1c\x0b\x2e\x00\x00\x00\x01\x80\x00\x00\x00" 
        packet.unpack_header(header) 
        packet.attach_data(MANGLED_SAMPLE) 
	test_driver._protocol.got_data(packet)        
        self.assertFalse(self.raw_stream_received)
        self.assertFalse(self.parsed_stream_received)

	packet = PortAgentPacket() 
        header = "\xa3\x9d\x7a\x02\x00\x1c\x0b\x2e\x00\x00\x00\x01\x80\x00\x00\x00" 
        packet.unpack_header(header) 
        packet.attach_data(LETTER_SAMPLE) 
	test_driver._protocol.got_data(packet)        
        self.assertFalse(self.raw_stream_received)
        self.assertFalse(self.parsed_stream_received)

	packet = PortAgentPacket() 
        header = "\xa3\x9d\x7a\x02\x00\x1c\x0b\x2e\x00\x00\x00\x01\x80\x00\x00\x00" 
        packet.unpack_header(header) 
        packet.attach_data(SAMPLE_FRAGMENT_1) 
	test_driver._protocol.got_data(packet)        
        self.assertFalse(self.raw_stream_received)
        self.assertFalse(self.parsed_stream_received)

    def test_fragmented_complete_sample(self):
        """
        Simulate a complete sample that arrives in separate invocations of got_data();
        result should be a complete sample published 
        """
        
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=LoggerClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = ooicoreInstrumentDriver(self.my_event_callback)
        
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to that state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        """
        - Reset test verification variables.
        - Construct a fragment of a sample stream
        - Pass to got_data()
        - Verify that raw and parsed streams have NOT been received
        """
        self.reset_test_vars()
	
	packet = PortAgentPacket() 
        header = "\xa3\x9d\x7a\x02\x00\x1c\x0b\x2e\x00\x00\x00\x01\x80\x00\x00\x00" 
        packet.unpack_header(header) 
        packet.attach_data(SAMPLE_FRAGMENT_1) 
	test_driver._protocol.got_data(packet)        
        self.assertFalse(self.raw_stream_received)
        self.assertFalse(self.parsed_stream_received)

        """
        - Construct the remaining fragment of the sample stream
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
	packet = PortAgentPacket() 
        header = "\xa3\x9d\x7a\x02\x00\x1c\x0b\x2e\x00\x00\x00\x01\x80\x00\x00\x00" 
        packet.unpack_header(header) 
        packet.attach_data(SAMPLE_FRAGMENT_2) 
	test_driver._protocol.got_data(packet)        
        
        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)
                
    def test_concatenated_fragmented_sample(self):
        """
        Simulate a complete sample that arrives in with a fragment concatenated.  The concatenated fragment
        should have have a terminator.  A separate invocations of got_data() will have the remainder;
        result should be a complete sample published 
        """
        
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=LoggerClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = ooicoreInstrumentDriver(self.my_event_callback)
        
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to that state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        """
        - Reset test verification variables.
        - Construct a sample stream with a concatenated fragment
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        - Later, when the final fragment has been send, verify that raw and
          parsed streams have been received.
        """
        self.reset_test_vars()

        """
        - Add the beginning of another sample stream
        - Pass to got_data()
        """
	packet = PortAgentPacket() 
        header = "\xa3\x9d\x7a\x02\x00\x1c\x0b\x2e\x00\x00\x00\x01\x80\x00\x00\x00" 
        packet.unpack_header(header) 
        packet.attach_data(FULL_SAMPLE+SAMPLE_FRAGMENT_1) 
	test_driver._protocol.got_data(packet)                
        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)

        """
        - Reset test verification variables
        - Construct the final fragment of a sample stream
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        self.reset_test_vars()
	packet = PortAgentPacket() 
	header = "\xa3\x9d\x7a\x02\x00\x1c\x0b\x2e\x00\x00\x00\x01\x80\x00\x00\x00" 
        packet.unpack_header(header) 
        packet.attach_data(SAMPLE_FRAGMENT_2) 
	test_driver._protocol.got_data(packet)                

        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)

    def test_chunker(self):
        """
        Tests the chunker
        """
        # This will want to be created in the driver eventually...
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, FULL_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, FULL_SAMPLE)
        self.assert_chunker_combined_sample(chunker, FULL_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, FULL_SAMPLE)
	
    def test_to_seconds(self):
	""" Test to second conversion. """
	self.assertEquals(240, Protocol._to_seconds(4, 1))
	self.assertEquals(59, Protocol._to_seconds(59, 0))
	self.assertEquals(60, Protocol._to_seconds(60, 0))
	self.assertEquals(3600, Protocol._to_seconds(60, 1))
	self.assertEquals(3660, Protocol._to_seconds(61, 1))
	self.assertRaises(InstrumentProtocolException,
			  Protocol._to_seconds, 1, 2)
	self.assertRaises(InstrumentProtocolException,
			  Protocol._to_seconds, 1, "foo")

    def test_from_seconds(self):
	self.assertEquals((1, 23), Protocol._from_seconds(23))
	self.assertEquals((1, 59), Protocol._from_seconds(59))
	self.assertEquals((2, 1), Protocol._from_seconds(60))
	self.assertEquals((2, 2), Protocol._from_seconds(120))
	self.assertEquals((2, 1), Protocol._from_seconds(119))
	self.assertRaises(InstrumentParameterException,
			  Protocol._from_seconds, 3601)
	self.assertRaises(InstrumentParameterException,
			  Protocol._from_seconds, 14)	

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class IntFromIDK(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    ###
    #    Add instrument specific integration tests
    ###
    def test_configuration(self):
        """
        Test to configure the driver process for device comms and transition
        to disconnected state.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver returned state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        
    def test_connect(self):
        """
        Test configuring and connecting to the device through the port
        agent. Discover device state.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
    
    def test_discover_state(self):
	""" Tests to see if we can discover the state of the instrument"""
	# put yourself in a known state for now
	self._get_to_cmd_mode()

	# run the discover transition to get back to command
	reply = self.driver_client.cmd_dvr('discover_state')

	# see if you figured it out okay
	state = self.driver_client.cmd_dvr('get_resource_state')
	self.assertEqual(state, ProtocolState.COMMAND)

	# try a different state...like auto sample
	self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
	state = self.driver_client.cmd_dvr('get_resource_state')
	self.assertEqual(state, ProtocolState.AUTOSAMPLE)

	# run the discover transition to get back to command
	reply = self.driver_client.cmd_dvr('discover_state')

	# see if you figured it out okay
	state = self.driver_client.cmd_dvr('get_resource_state')
	self.assertEqual(state, ProtocolState.COMMAND)

    def test_get(self):
        self._get_to_cmd_mode()

        params = {
                   Parameter.CYCLE_TIME: 20,
                   Parameter.VERBOSE: None,
                   Parameter.METADATA_POWERUP: 0,
                   Parameter.METADATA_RESTART: 0,
                   Parameter.RES_SENSOR_POWER: 1,
                   Parameter.INST_AMP_POWER: 1,
                   Parameter.EH_ISOLATION_AMP_POWER: 1,
                   Parameter.HYDROGEN_POWER: 1,
                   Parameter.REFERENCE_TEMP_POWER: 1,
        }

        reply = self.driver_client.cmd_dvr('get_resource',
                                           params.keys(),
                                           timeout=20)
        self.assertEquals(reply, params)
        
        # Assert get fails without a parameter.
        self.assertRaises(InstrumentParameterException,
                          self.driver_client.cmd_dvr, 'get_resource')
            
	# A bad parameter in a list
        self.assertRaises(InstrumentParameterException,
                          self.driver_client.cmd_dvr,
                          'get_resource', ['bogus_param'])

        # Assert get fails with a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            self.driver_client.cmd_dvr('get_resource', bogus_params)
    
        # Assert get fails with a bad parameter in a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                Parameter.CYCLE_TIME
                ]
            self.driver_client.cmd_dvr('get_resource', bogus_params)        
        
    def test_readonly_set(self):
	""" Tests the results of trying to set some read-only values """
        config_key = Parameter.CYCLE_TIME
	value_C = 16
        config_C = {config_key:value_C}
	ro_params = {
		   Parameter.CYCLE_TIME: value_C,
                   Parameter.VERBOSE: 1,
                   Parameter.METADATA_POWERUP: 0,
                   Parameter.METADATA_RESTART: 0,
                   Parameter.RES_SENSOR_POWER: 1,
                   Parameter.INST_AMP_POWER: 1,
                   Parameter.EH_ISOLATION_AMP_POWER: 1,
                   Parameter.HYDROGEN_POWER: 1,
		   Parameter.REFERENCE_TEMP_POWER: 1
		   }
        
        self._get_to_cmd_mode()

	# test read-only params do not get set
        reply = self.driver_client.cmd_dvr('set_resource', ro_params, timeout=20)
        self.assertEquals(reply[config_key], value_C)
         
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL, timeout=20)
      	reply[Parameter.VERBOSE] = 1  # Hack it since it doesnt update
	self.assertEquals(reply, ro_params)

    def test_bogus_set(self):
        """ Assert we cannot set a bogus parameter. """
        self._get_to_cmd_mode()

        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name' : 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                Parameter.CYCLE_TIME : 'bogus value'
            }
            self.driver_client.cmd_dvr('set_resource', bogus_params)	
    
    def test_simple_set(self):	
        config_key = Parameter.CYCLE_TIME
        value_A = 17
        value_B = 15
        config_A = {config_key:value_A}
        config_B = {config_key:value_B}
	
        self._get_to_cmd_mode()
        
        reply = self.driver_client.cmd_dvr('set_resource', config_A, timeout=20)
        self.assertEquals(reply[config_key], value_A)
                 
        reply = self.driver_client.cmd_dvr('get_resource', [config_key], timeout=20)
        self.assertEquals(reply, config_A)
        
        reply = self.driver_client.cmd_dvr('set_resource', config_B, timeout=20)
        self.assertEquals(reply[config_key], value_B)
         
        reply = self.driver_client.cmd_dvr('get_resource', [config_key], timeout=20)
        self.assertEquals(reply, config_B)
	
    def test_read_only_values(self):
        self._get_to_cmd_mode()

	config_A = {
		   Parameter.CYCLE_TIME: 30,
                   Parameter.VERBOSE: 1,
                   Parameter.METADATA_POWERUP: 1,
                   Parameter.METADATA_RESTART: 1,
                   Parameter.RES_SENSOR_POWER: 0,
                   Parameter.INST_AMP_POWER: 0,
                   Parameter.EH_ISOLATION_AMP_POWER: 0,
                   Parameter.HYDROGEN_POWER: 0,
		   Parameter.REFERENCE_TEMP_POWER: 0
	}
	
	config_B = {
		   Parameter.CYCLE_TIME: 20,
                   Parameter.VERBOSE: 0,
                   Parameter.METADATA_POWERUP: 0,
                   Parameter.METADATA_RESTART: 0,
                   Parameter.RES_SENSOR_POWER: 1,
                   Parameter.INST_AMP_POWER: 1,
                   Parameter.EH_ISOLATION_AMP_POWER: 1,
                   Parameter.HYDROGEN_POWER: 1,
		   Parameter.REFERENCE_TEMP_POWER: 1
	}
		
	# Set the values to something totally strange via init value?
	self.driver_client.cmd_dvr('set_init_params', config_A)
	self.driver_client.cmd_dvr('apply_startup_params')
	
	# verify they made it to the kooky values
	reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL, timeout=20)
	reply[Parameter.VERBOSE] = 1  # Hack it since it doesnt update
        self.assertEqual(reply, config_A)
	
	# set them back
	self.driver_client.cmd_dvr('set_init_params', config_B)
	self.driver_client.cmd_dvr('apply_startup_params')
	
	# confirm that they made it back to where they should be
	reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL, timeout=20)
	reply[Parameter.VERBOSE] = 0  # Hack it since it doesnt update
        self.assertEqual(reply, config_B)        
    
    def test_autosample(self):
        """
        Test autosample mode.
        """
        self._get_to_cmd_mode()
        
	# Make sure the device parameters are set to sample frequently and
        # to transmit.
        params = {Parameter.CYCLE_TIME : 15}
	
        reply = self.driver_client.cmd_dvr('set_resource', params)
        
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)
        
        time.sleep(40)
        
        # Return to command mode. Catch timeouts and retry if necessary.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
            
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Verify we received at least 2 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        self.assertTrue(len(sample_events) >= 2)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
	
	
    def _get_to_cmd_mode(self):
	""" Do some legwork to get to the command mode """
	
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)
	
	#reply = self.driver_client.cmd_dvr('apply_startup_params')
	

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualFromIDK(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    ###
    #    Add instrument specific qualification tests
    ###
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet(timeout=STARTUP_TIMEOUT)
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("\r\n")
        self.tcp_client.expect(Prompt.COMMAND)

        self.assert_direct_access_stop_telnet()

