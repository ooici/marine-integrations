"""
@package mi.instrument.seabird.sbe54tps.ooicore.test.test_driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore -a INT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe54tps/ooicore -a QUAL
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock
import re

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.instrument.seabird.sbe54tps.ooicore.driver import InstrumentDriver
from mi.instrument.seabird.sbe54tps.ooicore.driver import ProtocolState
from mi.instrument.seabird.sbe54tps.ooicore.driver import Parameter
from mi.instrument.seabird.sbe54tps.ooicore.driver import PACKET_CONFIG

# SAMPLE DATA FOR TESTING
from mi.instrument.seabird.sbe54tps.ooicore.test.sample_data import *
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent
###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe54tps.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = 'IQM9B7',
    instrument_agent_name = 'seabird_sbe54tps_ooicore',
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
            stream_type = sample_value['stream_name']
            if stream_type == 'raw':
                self.raw_stream_received = True
            elif stream_type == 'parsed':
                self.parsed_stream_received = True
    
    ###
    #    Add instrument specific unit tests
    ###
    @unittest.skip('Instrument Driver Developer: test_valid_complete_sample skipped: please complete this test!')
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
        
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to the DISCONNECTED state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        """
        - Reset test verification variables.
        - Construct a complete sample
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        self.reset_test_vars()
        test_sample = "Insert sample here with appropriate line terminator"

        test_driver._protocol.got_data(test_sample)
        
        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)

    @unittest.skip('Instrument Driver Developer: test_invalid_sample skipped: please complete this test!')
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
        
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to the DISCONNECTED state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        """
        - Reset test verification variables.
        - Construct a complete sample
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        self.reset_test_vars()
        test_sample = "Invalid Sample"

        test_driver._protocol.got_data(test_sample)
        
        self.assertFalse(self.raw_stream_received)
        self.assertFalse(self.parsed_stream_received)

    @unittest.skip('Instrument Driver Developer: test_fragmented_complete_sample skipped: please complete this test!')
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
        
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to that state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        """
        - Reset test verification variables.
        - Construct a fragment of a sample stream
        - Pass to got_data()
        - Verify that raw and parsed streams have NOT been received
        """
        self.reset_test_vars()
        test_sample = "Insert a fragment of a sample here, i.e., the beginning " + \
        	"of a sample, but not a complete sample.  The remainder will be " + \
        	"sent in a separate message."

        test_driver._protocol.got_data(test_sample)
        
        self.assertFalse(self.raw_stream_received)
        self.assertFalse(self.parsed_stream_received)

        """
        - Construct the remaining fragment of the sample stream
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        test_sample = "Insert a remainder of the above sample here"

        test_driver._protocol.got_data(test_sample)
        
        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)
                
    @unittest.skip('Instrument Driver Developer: test_concatenated_fragmented_sample skipped: please complete this test!')
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
        
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to that state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_current_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver into AUTOSAMPLE state so that it will parse and 
        publish samples
        """        
        test_driver.set_test_mode(True)
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_current_state()
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
        test_sample = "Insert a complete sample here."

        """
        - Add the beginning of another sample stream
        - Pass to got_data()
        """
        test_sample += "Add the beginning of another sample stream here, but just a fragment: the rest will come" + \
            "in another message." 

        test_driver._protocol.got_data(test_sample)
        
        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)

        """
        - Reset test verification variables
        - Construct the final fragment of a sample stream
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        self.reset_test_vars()
        test_sample = \
            "Insert the remainder of the fragmented sample that was added to the stream above."

        test_driver._protocol.got_data(test_sample)
        
        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)


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


    def check_state(self, desired_state):
        """
        Transitions to the desired state, then verifies it has indeed made it to that state.
        @param desired_state: the state to transition to.
        """
        #@todo promote this to base class already....

        current_state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(current_state, desired_state)

    def assert_command_and_state(self, agent_command, desired_state):
        """
        Execute an agent command, and verify the desired state is achieved.
        @param agent_command: the agent command to execute
        @param desired_state: the state that should result
        """

        cmd = AgentCommand(command=agent_command)
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.check_state(desired_state)


    def assert_SBE54tpsStatusDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsStatusDataParticle or FAIL!!!!
        """
        if (isinstance(potential_sample, SBE54tpsStatusDataParticle)):

            log.debug("GOT A SBE54tpsStatusDataParticle")
            sample_dict = json.loads(val.generate_parsed())

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
                self.assertTrue(x['value_id'] in [
                    SBE54tpsStatusDataParticle.DEVICE_TYPE,
                    SBE54tpsStatusDataParticle.SERIAL_NUMBER,
                    SBE54tpsStatusDataParticle.DATE_TIME,
                    SBE54tpsStatusDataParticle.EVENT_COUNT,
                    SBE54tpsStatusDataParticle.MAIN_SUPPLY_VOLTAGE,
                    SBE54tpsStatusDataParticle.NUMBER_OF_SAMPLES,
                    SBE54tpsStatusDataParticle.BYTES_USED,
                    SBE54tpsStatusDataParticle.BYTES_FREE
                ])

                # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
                # str
                if x['value_id'] in [
                    SBE54tpsStatusDataParticleKey.DEVICE_TYPE
                ]:
                    self.assertTrue(isinstance(x['value'], str))
                # int
                elif x['value_id'] in [
                    SBE54tpsStatusDataParticleKey.SERIAL_NUMBER,
                    SBE54tpsStatusDataParticleKey.EVENT_COUNT,
                    SBE54tpsStatusDataParticleKey.NUMBER_OF_SAMPLES,
                    SBE54tpsStatusDataParticleKey.BYTES_USED,
                    SBE54tpsStatusDataParticleKey.BYTES_FREE
                ]:
                    self.assertTrue(isinstance(x['value'], int))
                #float
                elif x['value_id'] in [
                    SBE54tpsStatusDataParticleKey.MAIN_SUPPLY_VOLTAGE
                ]:
                    self.assertTrue(isinstance(x['value'], float))
                # datetime
                elif x['value_id'] in [
                    SBE54tpsStatusDataParticleKey.DATE_TIME
                ]:
                    # @TODO add a date_time parser here
                    self.assertTrue(isinstance(x['value'], time.struct_time))
                else:
                    # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                    self.assertTrue(False)

    def assert_SBE54tpsConfigurationDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsStatusDataParticle or FAIL!!!!
        """
        if (isinstance(potential_sample, SBE54tpsConfigurationDataParticle)):

            log.debug("GOT A SBE54tpsConfigurationDataParticle")
            sample_dict = json.loads(val.generate_parsed())

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
                self.assertTrue(x['value_id'] in [
                    SBE54tpsConfigurationDataParticleKey.DEVICE_TYPE,
                    SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM,
                    SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER,
                    SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE,
                    SBE54tpsConfigurationDataParticleKey.ENABLE_ALERTS,
                    SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE,
                    SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD,
                    SBE54tpsConfigurationDataParticleKey.FRA0,
                    SBE54tpsConfigurationDataParticleKey.FRA1,
                    SBE54tpsConfigurationDataParticleKey.FRA2,
                    SBE54tpsConfigurationDataParticleKey.FRA3,
                    SBE54tpsConfigurationDataParticleKey.PU0,
                    SBE54tpsConfigurationDataParticleKey.PY1,
                    SBE54tpsConfigurationDataParticleKey.PY2,
                    SBE54tpsConfigurationDataParticleKey.PY3,
                    SBE54tpsConfigurationDataParticleKey.PC1,
                    SBE54tpsConfigurationDataParticleKey.PC2,
                    SBE54tpsConfigurationDataParticleKey.PC3,
                    SBE54tpsConfigurationDataParticleKey.PD1,
                    SBE54tpsConfigurationDataParticleKey.PD2,
                    SBE54tpsConfigurationDataParticleKey.PT1,
                    SBE54tpsConfigurationDataParticleKey.PT2,
                    SBE54tpsConfigurationDataParticleKey.PT3,
                    SBE54tpsConfigurationDataParticleKey.PT4,
                    SBE54tpsConfigurationDataParticleKey.PRESSURE_OFFSET,
                    SBE54tpsConfigurationDataParticleKey.PRESSURE_RANGE,
                    SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE,
                    SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE
                ])

                # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
                # str
                if key in [
                    SBE54tpsConfigurationDataParticleKey.DEVICE_TYPE,
                    SBE54tpsConfigurationDataParticleKey.PRESSURE_SERIAL_NUM,
                    ]:
                    self.assertTrue(isinstance(x['value'], str))

                # int
                elif key in [
                    SBE54tpsConfigurationDataParticleKey.SERIAL_NUMBER,
                    SBE54tpsConfigurationDataParticleKey.BATTERY_TYPE,
                    SBE54tpsConfigurationDataParticleKey.ENABLE_ALERTS,
                    SBE54tpsConfigurationDataParticleKey.UPLOAD_TYPE,
                    SBE54tpsConfigurationDataParticleKey.SAMPLE_PERIOD,
                ]:
                    self.assertTrue(isinstance(x['value'], int))

                #float
                elif key in [
                    SBE54tpsConfigurationDataParticleKey.FRA0,
                    SBE54tpsConfigurationDataParticleKey.FRA1,
                    SBE54tpsConfigurationDataParticleKey.FRA2,
                    SBE54tpsConfigurationDataParticleKey.FRA3,
                    SBE54tpsConfigurationDataParticleKey.PU0,
                    SBE54tpsConfigurationDataParticleKey.PY1,
                    SBE54tpsConfigurationDataParticleKey.PY2,
                    SBE54tpsConfigurationDataParticleKey.PY3,
                    SBE54tpsConfigurationDataParticleKey.PC1,
                    SBE54tpsConfigurationDataParticleKey.PC2,
                    SBE54tpsConfigurationDataParticleKey.PC3,
                    SBE54tpsConfigurationDataParticleKey.PD1,
                    SBE54tpsConfigurationDataParticleKey.PD2,
                    SBE54tpsConfigurationDataParticleKey.PT1,
                    SBE54tpsConfigurationDataParticleKey.PT2,
                    SBE54tpsConfigurationDataParticleKey.PT3,
                    SBE54tpsConfigurationDataParticleKey.PT4,
                    SBE54tpsConfigurationDataParticleKey.PRESSURE_OFFSET,
                    SBE54tpsConfigurationDataParticleKey.PRESSURE_RANGE,
                ]:
                    self.assertTrue(isinstance(x['value'], float))

                # date
                elif key in [
                    SBE54tpsConfigurationDataParticleKey.ACQ_OSC_CAL_DATE,
                    SBE54tpsConfigurationDataParticleKey.PRESSURE_CAL_DATE
                ]:
                    # @TODO add a date parser here
                    self.assertTrue(isinstance(x['value'], time.struct_time))
                else:
                    # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                    self.assertTrue(False)

    def assert_SBE54tpsEventCounterDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsEventCounterDataParticle or FAIL!!!!
        """
        if (isinstance(potential_sample, SBE54tpsEventCounterDataParticle)):

            log.debug("GOT A SBE54tpsEventCounterDataParticle")
            sample_dict = json.loads(val.generate_parsed())

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
                self.assertTrue(x['value_id'] in [
                    SBE54tpsEventCounterDataParticleKey.NUMBER_EVENTS,
                    SBE54tpsEventCounterDataParticleKey.MAX_STACK,
                    SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE,
                    SBE54tpsEventCounterDataParticleKey.SERIAL_NUMBER,
                    SBE54tpsEventCounterDataParticleKey.POWER_ON_RESET,
                    SBE54tpsEventCounterDataParticleKey.POWER_FAIL_RESET,
                    SBE54tpsEventCounterDataParticleKey.SERIAL_BYTE_ERROR,
                    SBE54tpsEventCounterDataParticleKey.COMMAND_BUFFER_OVERFLOW,
                    SBE54tpsEventCounterDataParticleKey.SERIAL_RECEIVE_OVERFLOW,
                    SBE54tpsEventCounterDataParticleKey.LOW_BATTERY,
                    SBE54tpsEventCounterDataParticleKey.SIGNAL_ERROR,
                    SBE54tpsEventCounterDataParticleKey.ERROR_10,
                    SBE54tpsEventCounterDataParticleKey.ERROR_12
                ])

                # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
                # int
                if key in [
                    SBE54tpsEventCounterDataParticleKey.NUMBER_EVENTS,
                    SBE54tpsEventCounterDataParticleKey.MAX_STACK,
                    SBE54tpsEventCounterDataParticleKey.DEVICE_TYPE,
                    SBE54tpsEventCounterDataParticleKey.SERIAL_NUMBER,
                    SBE54tpsEventCounterDataParticleKey.POWER_ON_RESET,
                    SBE54tpsEventCounterDataParticleKey.POWER_FAIL_RESET,
                    SBE54tpsEventCounterDataParticleKey.SERIAL_BYTE_ERROR,
                    SBE54tpsEventCounterDataParticleKey.COMMAND_BUFFER_OVERFLOW,
                    SBE54tpsEventCounterDataParticleKey.SERIAL_RECEIVE_OVERFLOW,
                    SBE54tpsEventCounterDataParticleKey.LOW_BATTERY,
                    SBE54tpsEventCounterDataParticleKey.SIGNAL_ERROR,
                    SBE54tpsEventCounterDataParticleKey.ERROR_10,
                    SBE54tpsEventCounterDataParticleKey.ERROR_12
                ]:
                    self.assertTrue(isinstance(x['value'], int))
                else:
                    # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                    self.assertTrue(False)

    def assert_SBE54tpsHardwareDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsHardwareDataParticle or FAIL!!!!
        """
        if (isinstance(potential_sample, SBE54tpsHardwareDataParticle)):

            log.debug("GOT A SBE54tpsHardwareDataParticle")
            sample_dict = json.loads(val.generate_parsed())

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
                self.assertTrue(x['value_id'] in [
                    SBE54tpsHardwareDataParticleKey.DEVICE_TYPE,
                    SBE54tpsHardwareDataParticleKey.MANUFACTURER,
                    SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION,
                    SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION,
                    SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER,
                    SBE54tpsHardwareDataParticleKey.PCB_TYPE,
                    SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER,
                    SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE,
                    SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE
                ])

                # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
                # str
                if key in [
                    SBE54tpsHardwareDataParticleKey.DEVICE_TYPE,
                    SBE54tpsHardwareDataParticleKey.MANUFACTURER,
                    SBE54tpsHardwareDataParticleKey.FIRMWARE_VERSION,
                    SBE54tpsHardwareDataParticleKey.HARDWARE_VERSION,
                    SBE54tpsHardwareDataParticleKey.PCB_SERIAL_NUMBER,
                    SBE54tpsHardwareDataParticleKey.PCB_TYPE
                    ]:
                    self.assertTrue(isinstance(x['value'], str))

                # int
                elif key in [
                    SBE54tpsHardwareDataParticleKey.SERIAL_NUMBER
                    ]:
                    self.assertTrue(isinstance(x['value'], int))

                # date
                elif key in [
                    SBE54tpsHardwareDataParticleKey.FIRMWARE_DATE,
                    SBE54tpsHardwareDataParticleKey.MANUFACTUR_DATE
                ]:
                    # @TODO add a date parser here
                    self.assertTrue(isinstance(x['value'], time.struct_time))
                else:
                    # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                    self.assertTrue(False)

    def assert_SBE54tpsSampleDataParticle(self, prospective_particle):
        """
        @param prospective_particle: a perfect particle of SBE54tpsSampleDataParticle or FAIL!!!!
        """
        if (isinstance(potential_sample, SBE54tpsSampleDataParticle)):

            log.debug("GOT A SBE54tpsSampleDataParticle")
            sample_dict = json.loads(val.generate_parsed())

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
                self.assertTrue(x['value_id'] in [
                    SBE54tpsSampleDataParticleKey.SAMPLE_TYPE,
                    SBE54tpsSampleDataParticleKey.SAMPLE_NUMBER,
                    SBE54tpsSampleDataParticleKey.PRESSURE,
                    SBE54tpsSampleDataParticleKey.PRESSURE_TEMP,
                    SBE54tpsSampleDataParticleKey.SAMPLE_TIMESTAMP
                ])

                # CHECK THAT THE TYPES ARE CORRECT IN THE DICT.
                # str
                if key in [
                    SBE54tpsSampleDataParticleKey.SAMPLE_TYPE
                    ]:
                    self.assertTrue(isinstance(x['value'], str))

                # int
                elif key in [
                    SBE54tpsSampleDataParticleKey.SAMPLE_NUMBER
                    ]:
                    self.assertTrue(isinstance(x['value'], int))

                #float
                elif key in [
                    SBE54tpsSampleDataParticleKey.PRESSURE,
                    SBE54tpsSampleDataParticleKey.PRESSURE_TEMP
                    ]:
                    self.assertTrue(isinstance(x['value'], float))

                # date
                elif key in [
                    SBE54tpsSampleDataParticleKey.SAMPLE_TIMESTAMP
                ]:
                    # @TODO add a date parser here
                    self.assertTrue(isinstance(x['value'], time.struct_time))
                else:
                    # SHOULD NEVER GET HERE. IF WE DO FAIL, SO IT IS INVESTIGATED
                    self.assertTrue(False)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)

        stop
        <WARNING>
        Instrument will automatically start sampling
        if no valid commands received for 2 minutes
        </WARNING>
        <Executed/>
        S>SetSamplePeriod=99
        SetSamplePeriod=99
        <Executed/>
        S>
        """


        self.check_state(ResourceAgentState.UNINITIALIZED)
        self.assert_command_and_state(ResourceAgentEvent.INITIALIZE, ResourceAgentState.INACTIVE)

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverConnectionState.UNCONFIGURED)
        state = self.instrument_agent_client.get_agent_state()
        log.debug("RESOURCE_STATE = " + repr(res_state))
        log.debug("AGENT_STATE = " + repr(state))
        '''
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: RESOURCE_STATE = 'DRIVER_STATE_UNCONFIGURED'
        mi.instrument.seabird.sbe54tps.ooicore.test.test_driver: DEBUG: AGENT_STATE = 'RESOURCE_AGENT_STATE_INACTIVE'
        '''



        self.assert_command_and_state(ResourceAgentEvent.GO_ACTIVE, ResourceAgentState.COMMAND)

        self.assert_enter_command_mode()



        #self.assert_enter_command_mode()

        param_name = Parameter.XXXXXXXXXXXXXXXXXXXXXREPLACE
        param_new_value = 90


        params = [param_name]
        check_new_params = self.instrument_agent_client.get_resource(params)
        self.assertTrue(check_new_params[param_name])

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data(param_name + "=" + str(param_new_value) + "\r\n")
        self.tcp_client.expect("S>")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()
        params = [param_name]
        check_new_params = self.instrument_agent_client.get_resource(params)
        self.assertTrue(check_new_params[param_name])

    def test_autosample(self):
        """
        @brief Test instrument driver execute interface to start and stop streaming
        mode.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)


        self.assert_enter_command_mode()

        # lets sample FAST!
        params = {
            SET_SAMPLE_PERIOD: 10
        }

        self.instrument_agent_client.set_resource(params, timeout=10)

        # Begin streaming.
        cmd = AgentCommand(command=ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        self.data_subscribers.clear_sample_queue(DataParticleValue.PARSED)

        # wait for 3 samples, then test them!
        samples = self.data_subscribers.get_samples('parsed', 3, timeout=60) # 1 minutes
        self.assert_SBE54tpsSampleDataParticle(samples.pop())
        self.assert_SBE54tpsSampleDataParticle(samples.pop())
        self.assert_SBE54tpsSampleDataParticle(samples.pop())

        # Halt streaming.
        cmd = AgentCommand(command=ProtocolEvent.STOP_AUTOSAMPLE)

        retval = self.instrument_agent_client.execute_resource(cmd, timeout=10)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=10)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)


    def assert_capabilitys_present(self, agent_capabilities, required_capabilities):
        """
        Verify that both lists are the same, order independent.
        @param agent_capabilities
        @param required_capabilities
        """

        for agent_capability in agent_capabilities:
            self.assertTrue(agent_capability in required_capabilities)

        for desired_capability in required_capabilities:
            self.assertTrue(desired_capability in agent_capabilities)


    def get_current_capabilities(self):
        """
        return a list of currently available capabilities
        """
        result = self.instrument_agent_client.get_capabilities()

        agent_capabilities = []
        unknown = []
        driver_capabilities = []
        driver_vars = []

        for x in result:
            if x.cap_type == 1:
                agent_capabilities.append(x.name)
            elif x.cap_type == 2:
                unknown.append(x.name)
            elif x.cap_type == 3:
                driver_capabilities.append(x.name)
            elif x.cap_type == 4:
                driver_vars.append(x.name)
            else:
                log.debug("*UNKNOWN* " + str(repr(x)))

        return (agent_capabilities, unknown, driver_capabilities, driver_vars)


    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.

        This one needs to be re-written rather than copy/pasted to develop a better more reusable pattern.
        """

        self.check_state(ResourceAgentState.UNINITIALIZED)
        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_INITIALIZE'])
        self.assert_capabilitys_present(driver_capabilities, [])

        log.debug("%%% STATE NOW ResourceAgentState.UNINITIALIZED")

        self.assert_command_and_state(ResourceAgentEvent.INITIALIZE, ResourceAgentState.INACTIVE)
        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_ACTIVE', 'RESOURCE_AGENT_EVENT_RESET'])
        self.assert_capabilitys_present(driver_capabilities, [])

        log.debug("%%% STATE NOW ResourceAgentState.INACTIVE")

        self.assert_command_and_state(ResourceAgentEvent.GO_ACTIVE, ResourceAgentState.IDLE)
        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_INACTIVE', 'RESOURCE_AGENT_EVENT_RESET',
                                                             'RESOURCE_AGENT_EVENT_RUN'])
        self.assert_capabilitys_present(driver_capabilities, [])

        log.debug("%%% STATE NOW ResourceAgentState.IDLE")

        self.assert_command_and_state(ResourceAgentEvent.RUN, ResourceAgentState.COMMAND)

        log.debug("%%% STATE NOW ResourceAgentState.COMMAND")

        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_CLEAR', 'RESOURCE_AGENT_EVENT_RESET',
                                                             'RESOURCE_AGENT_EVENT_GO_DIRECT_ACCESS',
                                                             'RESOURCE_AGENT_EVENT_GO_INACTIVE',
                                                             'RESOURCE_AGENT_EVENT_PAUSE'])
        log.debug("DRIVER_CAPABILITIES = " + repr(driver_capabilities))
        self.assert_capabilitys_present(driver_capabilities, ['DRIVER_EVENT_ACQUIRE_STATUS',
                                                              'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                                              'DRIVER_EVENT_START_AUTOSAMPLE',
                                                              'DRIVER_EVENT_CLOCK_SYNC'])


        log.debug("%%%%%%%%%%%% CREATING AGENT COMMAND")
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            kwargs={'session_type': DirectAccessTypes.telnet,
                    #kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        log.debug("%%%%%%%%%%%% RUNNING AGENT COMMAND")
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("%%%%%%%%%%%% COMPLETED AGENT COMMAND")

        self.check_state(ResourceAgentState.DIRECT_ACCESS)
        (agent_capabilities, unknown, driver_capabilities, driver_vars) = self.get_current_capabilities()
        self.assert_capabilitys_present(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_COMMAND'])
        self.assert_capabilitys_present(driver_capabilities, [])


        # Can we walk the states backwards?
        #self.assert_command_and_state(ResourceAgentEvent.INITIALIZE, ResourceAgentEvent.RUN)
        #self.assert_command_and_state(ResourceAgentEvent.INITIALIZE, ResourceAgentEvent.GO_ACTIVE)
        #self.assert_command_and_state(ResourceAgentEvent.INITIALIZE, ResourceAgentState.INACTIVE)

    # BROKE
    def test_execute_clock_sync(self):
        """
        @brief Test Test EXECUTE_CLOCK_SYNC command.
        """
        self.assert_enter_command_mode()

        self.assert_command_and_state(ProtocolEvent.CLOCK_SYNC, ProtocolState.COMMAND)
        # clocl should now be synced

        # Now verify that at least the date matches
        params = [Parameter.DS_DEVICE_DATE_TIME]
        check_new_params = self.instrument_agent_client.get_resource(params)
        lt = time.strftime("%d %b %Y  %H:%M:%S", time.gmtime(time.mktime(time.localtime())))

    # BROKE
    def test_connect_disconnect(self):

        self.assert_enter_command_mode()

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        self.check_state(ResourceAgentState.UNINITIALIZED)