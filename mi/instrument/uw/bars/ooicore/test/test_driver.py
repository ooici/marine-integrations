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
from pyon.agent.agent import ResourceAgentEvent

from mi.core.instrument.logger_client import LoggerClient
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.exceptions import InstrumentTimeoutException

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase, ParameterTestConfigKey
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import AgentCapabilityType
from mi.idk.util import convert_enum_to_dict


from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.instrument.data_particle import DataParticleValue

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentParameterException

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.uw.bars.ooicore.driver import Protocol
from mi.instrument.uw.bars.ooicore.driver import InstrumentDriver
from mi.instrument.uw.bars.ooicore.driver import ProtocolState
from mi.instrument.uw.bars.ooicore.driver import ProtocolEvent
from mi.instrument.uw.bars.ooicore.driver import Parameter, VisibleParameters
from mi.instrument.uw.bars.ooicore.driver import Command
from mi.instrument.uw.bars.ooicore.driver import Capability
from mi.instrument.uw.bars.ooicore.driver import SubMenu
from mi.instrument.uw.bars.ooicore.driver import Prompt
from mi.instrument.uw.bars.ooicore.driver import BarsDataParticle, BarsDataParticleKey
from mi.instrument.uw.bars.ooicore.driver import COMMAND_CHAR
from mi.instrument.uw.bars.ooicore.driver import DataParticleType


###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.uw.bars.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'QN341A',
    instrument_agent_name = 'uw_bars_ooicore',
    instrument_agent_packet_config = DataParticleType(),
    driver_startup_config = {
        DriverConfigKey.PARAMETERS : {
            Parameter.CYCLE_TIME : 20,
            Parameter.VERBOSE : 1,
            Parameter.METADATA_POWERUP : 0,
            Parameter.METADATA_RESTART : 0
        }
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
MANGLED_SAMPLE = ".  4.  .095  4.095  0.014  0.048  1.995  1.041  24.74  0.000   24.7   9.2\r\n"
LETTER_SAMPLE = "1.448  4.095  4.095  A.BCD  0.014  0.048  1.995  1.041  24.74  0.000   24.7   9.2\r\n"
FULL_SAMPLE = "1.448  4.095  4.095  0.004  0.014  0.048  1.995  1.041  24.74  0.000   24.7   9.2\r\n"
SAMPLE_FRAGMENT_1 = "1.448  4.095  4.095  0.004  0.014  0.0" 
SAMPLE_FRAGMENT_2 = "48  1.995  1.041  24.74  0.000   24.7   9.2\r\n"

STARTUP_TIMEOUT = 120
EXECUTE_TIMEOUT = 60



CYCLE_TIME_VALUE = 20
EH_ISOLATION_AMP_POWER_VALUE = 1
HYDROGEN_POWER_VALUE = 1
INST_AMP_POWER_VALUE = 1
METADATA_POWERUP_VALUE = 0
METADATA_RESTART_VALUE = 0
REFERENCE_TEMP_POWER_VALUE = 1
RES_SENSOR_POWER_VALUE = 1
VERBOSE_VALUE = None

###############################################################################
#                           DRIVER TEST MIXIN        		                  #
#     Defines a set of constants and assert methods used for data particle    #
#     verification 														      #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.									  #
###############################################################################
class TRHPHMixinSub(DriverTestMixin):

    global VALUE
    InstrumentDriver = InstrumentDriver

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

    INVALID_SAMPLE  = "This is an invalid sample; it had better cause an exception."
    VALID_SAMPLE_01 = "0.000  0.000  0.000  0.001  0.021  0.042  1.999  1.173  20.75  0.016   24.7   9.3"
    VALID_SAMPLE_02 = "0.000  0.000  0.000  0.002  0.021  0.040  1.999  1.173  20.75  0.015   24.4   9.2"


    _driver_capabilities = {
        # capabilities defined in the IOS
        Capability.START_AUTOSAMPLE : {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_AUTOSAMPLE : {STATES: [ProtocolState.AUTOSAMPLE]},
        Capability.START_DIRECT : {STATES: [ProtocolState.COMMAND]},
        Capability.STOP_DIRECT : {STATES: [ProtocolState.DIRECT_ACCESS]},
        Capability.GET : {STATES: [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]},
        Capability.SET : {STATES: [ProtocolState.COMMAND]},
        Capability.EXECUTE_DIRECT : {STATES: [ProtocolState.DIRECT_ACCESS]},
    }


    ###
    #  Parameter and Type Definitions
    ###
    _driver_parameters = {
        # Parameters defined in the IOS

        Parameter.CYCLE_TIME : {TYPE: int, READONLY: False, DA: True, STARTUP: True, DEFAULT: 20, VALUE: 20},
        Parameter.VERBOSE : {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 1, VALUE: 1, REQUIRED: False},
        Parameter.METADATA_POWERUP : {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.METADATA_RESTART : {TYPE: int, READONLY: True, DA: True, STARTUP: True, DEFAULT: 0, VALUE: 0},
        Parameter.RES_SENSOR_POWER : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1, VALUE: 1},
        Parameter.INST_AMP_POWER : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1, VALUE: 1},
        Parameter.EH_ISOLATION_AMP_POWER : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1, VALUE: 1},
        Parameter.HYDROGEN_POWER : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1, VALUE: 1},
        Parameter.REFERENCE_TEMP_POWER : {TYPE: int, READONLY: True, DA: False, STARTUP: False, DEFAULT: 1, VALUE: 1},
    }

    _sample_parameters = {
        BarsDataParticleKey.RESISTIVITY_5: {TYPE: float, VALUE: 1.234, REQUIRED: True },
        BarsDataParticleKey.RESISTIVITY_X1: {TYPE: float, VALUE: 1.345, REQUIRED: True },
        BarsDataParticleKey.RESISTIVITY_X5: {TYPE: float, VALUE: 8414, REQUIRED: True },
        BarsDataParticleKey.HYDROGEN_5: {TYPE: float, VALUE: 8362, REQUIRED: True },
        BarsDataParticleKey.HYDROGEN_X1: {TYPE: float, VALUE: 1.234, REQUIRED: True },
        BarsDataParticleKey.HYDROGEN_X5: {TYPE: float, VALUE: 1.234, REQUIRED: True },
        BarsDataParticleKey.EH_SENSOR: {TYPE: float, VALUE: 1.234, REQUIRED: True },
        BarsDataParticleKey.REFERENCE_TEMP_VOLTS: {TYPE: float, VALUE: 1.234, REQUIRED: True },
        BarsDataParticleKey.REFERENCE_TEMP_DEG_C: {TYPE: float, VALUE: 1.234, REQUIRED: True },
        BarsDataParticleKey.RESISTIVITY_TEMP_VOLTS: {TYPE: float, VALUE: 1.234, REQUIRED: True },
        BarsDataParticleKey.RESISTIVITY_TEMP_DEG_C: {TYPE: float, VALUE: 1.234, REQUIRED: True },
        BarsDataParticleKey.BATTERY_VOLTAGE: {TYPE: float, VALUE: 1.234, REQUIRED: True },

    }

    def assert_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify sample particle
        @param data_particle:  THSPHDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_keys(BarsDataParticleKey, self._sample_parameters)
        self.assert_data_particle_header(data_particle, DataParticleType.PARSED, require_instrument_timestamp=False)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)



    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)



###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class DriverUnitTest(InstrumentDriverUnitTestCase, TRHPHMixinSub):
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

        # Test capabilites for duplicates, then verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())


    def test_driver_schema(self):
        """
        get the driver schema and verify it is configured properly
        """
        driver = self.InstrumentDriver(self._got_data_event_callback)
        self.assert_driver_schema(driver, self._driver_parameters, self._driver_capabilities)

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)
        self.assert_chunker_sample(chunker, self.VALID_SAMPLE_01)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_SAMPLE_01)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_SAMPLE_01)
        self.assert_chunker_combined_sample(chunker, self.VALID_SAMPLE_01)

        self.assert_chunker_sample(chunker, self.VALID_SAMPLE_02)
        self.assert_chunker_sample_with_noise(chunker, self.VALID_SAMPLE_02)
        self.assert_chunker_fragmented_sample(chunker, self.VALID_SAMPLE_02)
        self.assert_chunker_combined_sample(chunker, self.VALID_SAMPLE_02)


    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # Start validating data particles
        self.assert_particle_published(driver, self.VALID_SAMPLE_01, self.assert_particle_sample, True)
        self.assert_particle_published(driver, self.VALID_SAMPLE_02, self.assert_particle_sample, True)


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
        test_driver = InstrumentDriver(self.my_event_callback)
        
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

    @unittest.skip("needs rework with new publishing mech")
    def test_valid_complete_sample(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=LoggerClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """       
        test_driver = InstrumentDriver(self.my_event_callback)
        
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

    @unittest.skip("needs to be updated post publisher change")
    def test_invalid_complete_sample(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=LoggerClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """       
        test_driver = InstrumentDriver(self.my_event_callback)
        
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

    @unittest.skip("update port publishing change")
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
        test_driver = InstrumentDriver(self.my_event_callback)
        
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

    @unittest.skip("update port publishing change")
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
        test_driver = InstrumentDriver(self.my_event_callback)
        
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
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, TRHPHMixinSub):
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

        rhan
        """
        self.assert_initialize_driver()

    """
    def test_connect(self):
    """
    """
        Test configuring and connecting to the device through the port
        agent. Discover device state.
    """
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
    """

    def test_direct_access(self):
        """
        Verify we can enter the direct access state
        rhan
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_DIRECT)
        self.assert_state_change(ProtocolState.DIRECT_ACCESS, 5)

    def test_state_transition(self):
        """
        Tests to see if we can make transition to different states
        rhan
        """
        self.assert_initialize_driver(ProtocolState.COMMAND)
        self.assert_state_change(ProtocolState.COMMAND, 5)
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.DISCOVER)
        self.assert_state_change(ProtocolState.COMMAND, 5)

        # Test transition to auto sample
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)
        self.assert_state_change(ProtocolState.AUTOSAMPLE, 5)

        # Test transition back to command state
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        self.assert_state_change(ProtocolState.COMMAND, 5)

        # Test transition to direct access state
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_DIRECT)
        self.assert_state_change(ProtocolState.DIRECT_ACCESS, 5)

        # Test transition back to command state
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_DIRECT)
        self.assert_state_change(ProtocolState.COMMAND, 5)

    def test_parameters(self):
        """
        Test driver parameters and verify their type.  Startup parameters also verify the parameter
        value.  This test confirms that parameters are being read/converted properly and that
        the startup has been applied.
        rhan
        """
        self.assert_initialize_driver()
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_driver_parameters(reply, True)

        # verify we can set read/write parameters
        self.assert_set(Parameter.CYCLE_TIME, 20)


    def test_readonly_set(self):
        # verify we cannot set read only parameters
        self.assert_initialize_driver()
        self.assert_set_exception(Parameter.VERBOSE)
        self.assert_set_exception(Parameter.METADATA_POWERUP)
        self.assert_set_exception(Parameter.METADATA_RESTART)
        self.assert_set_exception(Parameter.RES_SENSOR_POWER)
        self.assert_set_exception(Parameter.INST_AMP_POWER)
        self.assert_set_exception(Parameter.EH_ISOLATION_AMP_POWER)
        self.assert_set_exception(Parameter.HYDROGEN_POWER)
        self.assert_set_exception(Parameter.REFERENCE_TEMP_POWER)


    def test_get_params(self):
        self.assert_initialize_driver()
        self.assert_get(Parameter.CYCLE_TIME, CYCLE_TIME_VALUE)
        self.assert_get(Parameter.EH_ISOLATION_AMP_POWER, EH_ISOLATION_AMP_POWER_VALUE)
        self.assert_get(Parameter.HYDROGEN_POWER, HYDROGEN_POWER_VALUE)
        self.assert_get(Parameter.INST_AMP_POWER, INST_AMP_POWER_VALUE)
        self.assert_get(Parameter.METADATA_POWERUP, METADATA_POWERUP_VALUE)
        self.assert_get(Parameter.METADATA_RESTART, METADATA_RESTART_VALUE)
        self.assert_get(Parameter.REFERENCE_TEMP_POWER, REFERENCE_TEMP_POWER_VALUE)
        self.assert_get(Parameter.RES_SENSOR_POWER, RES_SENSOR_POWER_VALUE)

    def test_autosample_on(self):
        """
        @brief Test for turning data on
        """
        self.assert_initialize_driver()
        self.assert_particle_generation(ProtocolEvent.START_AUTOSAMPLE,
                                        DataParticleType.PARSED,
                                        self.assert_particle_sample,
                                        delay=60)

        response = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)


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
        
    def test_readonly_set_old(self):
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
        value_B = 244
	value_B_rounded = (value_B // 60) * 60
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
        self.assertEquals(reply, {config_key:value_B_rounded})
	
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
	self.driver_client.cmd_dvr('set_init_params', {DriverConfigKey.PARAMETERS:
						       config_A})
	self.driver_client.cmd_dvr('apply_startup_params')
	
	# verify they made it to the kooky values
	reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL, timeout=20)
	reply[Parameter.VERBOSE] = 1  # Hack it since it doesnt update
        self.assertEqual(reply, config_A)
	
	# set them back
	self.driver_client.cmd_dvr('set_init_params', {DriverConfigKey.PARAMETERS:
						       config_B})
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

    def assert_sample_data_particle(self, particle):
	"""
	Assert that a parsed structure is valid
	@param particle A dict representation of a data particle structure or a
	JSON string that can be turned into one.
	"""
	if (isinstance(particle, BarsDataParticle)):
            sample_dict = json.loads(particle.generate_parsed())
        else:
            sample_dict = particle
	
	self.assert_v1_particle_headers(sample_dict)
        
	# now for the individual values
	for x in sample_dict['values']:
            self.assertTrue(x['value_id'] in convert_enum_to_dict(BarsDataParticleKey).values())
            log.debug("ID: %s value: %s type: %s" % (x['value_id'], x['value'], type(x['value'])))
            self.assertTrue(isinstance(x['value'], float))
	
    ###
    #    Add instrument specific qualification tests
    ###
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet(timeout=STARTUP_TIMEOUT)
        self.assertTrue(self.tcp_client)
	log.info("Successfully entered DA start telnet")

        self.tcp_client.send_data("\r\n")
        result = self.tcp_client.expect(Prompt.CMD_PROMPT, sleep_time=8)
	self.assertTrue(result)

	log.info("Successfully sent DA command and got prompt")
        self.assert_direct_access_stop_telnet()
	log.info("Successfully left direct access")

    def test_get_set_parameters(self):
        '''
        verify that all parameters can be get and set properly
        '''
        self.assert_enter_command_mode()

	self.assert_get_parameter(Parameter.CYCLE_TIME, 20) #initial config
	
        self.assert_set_parameter(Parameter.CYCLE_TIME, 24)
        self.assert_get_parameter(Parameter.CYCLE_TIME, 24)
	
        self.assert_set_parameter(Parameter.CYCLE_TIME, 240)
        self.assert_get_parameter(Parameter.CYCLE_TIME, 240)

        self.assert_get_parameter(Parameter.VERBOSE, None)
        self.assert_get_parameter(Parameter.METADATA_POWERUP, 0)
        self.assert_get_parameter(Parameter.METADATA_RESTART, 0)
        self.assert_get_parameter(Parameter.RES_SENSOR_POWER, 1)
        self.assert_get_parameter(Parameter.INST_AMP_POWER, 1)
        self.assert_get_parameter(Parameter.EH_ISOLATION_AMP_POWER, 1)
        self.assert_get_parameter(Parameter.HYDROGEN_POWER, 1)
        self.assert_get_parameter(Parameter.REFERENCE_TEMP_POWER, 1)

        self.assert_reset()

    def test_autosample(self):
        '''
        Start and stop autosample and verify data particle
        '''
        self.assert_sample_autosample(self.assert_sample_data_particle,
                                      DataParticleValue.PARSED)

    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        self.assert_enter_command_mode()

        #  Command Mode
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: [
                ResourceAgentEvent.CLEAR,
                ResourceAgentEvent.RESET,
                ResourceAgentEvent.GO_DIRECT_ACCESS,
                ResourceAgentEvent.GO_INACTIVE,
                ResourceAgentEvent.PAUSE,
            ],
            AgentCapabilityType.AGENT_PARAMETER: ['example'],
            AgentCapabilityType.RESOURCE_COMMAND: [
                DriverEvent.SET, DriverEvent.GET,
                DriverEvent.START_AUTOSAMPLE,
		DriverEvent.START_DIRECT
            ],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: [
                Parameter.CYCLE_TIME,
		Parameter.ALL,
            ],
        }

        self.assert_capabilities(capabilities)

        #  Streaming Mode
        capabilities[AgentCapabilityType.AGENT_COMMAND] = [
	    ResourceAgentEvent.RESET,
	    ResourceAgentEvent.GO_INACTIVE
	    ]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] =  [
            DriverEvent.STOP_AUTOSAMPLE
        ]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        #  Uninitialized Mode
        capabilities[AgentCapabilityType.AGENT_COMMAND] = [
	    ResourceAgentEvent.INITIALIZE]
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)
