#!/usr/bin/env python

"""
@package ion.services.mi.drivers.sbe16_plus_v2.test.test_sbe16_driver
@file ion/services/mi/drivers/sbe16_plus_v2/test_sbe16_driver.py
@author David Everett 
@brief Test cases for InstrumentDriver
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

# Ensure the test class is monkey patched for gevent
from gevent import monkey; monkey.patch_all()
import gevent


# Standard lib imports
import time
import json
import unittest

# 3rd party imports
from nose.plugins.attrib import attr
from mock import Mock
from mock import patch
from pyon.core.bootstrap import CFG

from prototype.sci_data.stream_defs import ctd_stream_definition

from mi.core.common import BaseEnum

from mi.core.instrument.port_agent_client import PortAgentClient
from mi.core.instrument.port_agent_client import PortAgentPacket

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException

from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import PACKET_CONFIG
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import SBE16DataParticle
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import InstrumentDriver
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import ProtocolState
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import ProtocolEvent
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import Capability
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import Parameter
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import Prompt
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from ion.agents.port.logger_process import EthernetDeviceLogger

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
#from mi.idk.unit_test import RequiredCapabilities
#from mi.idk.unit_test import RequiredAutoSampleCapabilities
from interface.objects import AgentCommand
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent
from pyon.core.exception import Conflict

# MI logger
from mi.core.log import get_logger ; log = get_logger()

# Make tests verbose and provide stdout
# Note: currently the inheritance chain is backwards, so we're doing this:
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_process
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_config
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_connect
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_get_set
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_poll
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_autosample
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_test
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_errors
# bin/nosetests -s -v mi/instrument/seabird/sbe16plus_v2/ooicore/test/test_driver.py:IntFromIDK.test_discover_autosample

# Driver module and class.
DVR_MOD = 'mi.instrument.seabird.sbe16plus_v2.ooicore.driver'
DVR_CLS = 'InstrumentDriver'

## Initialize the test parameters
InstrumentDriverTestCase.initialize(
    driver_module = DVR_MOD,
    driver_class = DVR_CLS,
    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
)

# Driver and port agent configuration

# Work dir and logger delimiter.
WORK_DIR = '/tmp/'
DELIM = ['<<','>>']

# Used to validate param config retrieved from driver.
PARAMS = {
    Parameter.OUTPUTSAL : bool,
    Parameter.OUTPUTSV : bool,
    Parameter.NAVG : int,
    Parameter.SAMPLENUM : int,
    Parameter.INTERVAL : int,
    Parameter.TXREALTIME : bool,
    Parameter.SYNCMODE : bool,
    Parameter.TCALDATE : tuple,
    Parameter.TA0 : float,
    Parameter.TA1 : float,
    Parameter.TA2 : float,
    Parameter.TA3 : float,
    Parameter.CCALDATE : tuple,
    Parameter.CG : float,
    Parameter.CH : float,
    Parameter.CI : float,
    Parameter.CJ : float,
    Parameter.CTCOR : float,
    Parameter.CPCOR : float,
    Parameter.PCALDATE : tuple,
    Parameter.PA0 : float,
    Parameter.PA1 : float,
    Parameter.PA2 : float,
    Parameter.PTCA0 : float,
    Parameter.PTCA1 : float,
    Parameter.PTCA2 : float,
    Parameter.PTCB0 : float,
    Parameter.PTCB1 : float,
    Parameter.PTCB2 : float,
    Parameter.POFFSET : float,
    Parameter.DATE_TIME : str
    # DHE this doesn't show up in the status unless the
    # SYNCMODE is enabled.  Need to change the test to
    # test for SYNCMODE and if true test for SYNCWAIT
    #Parameter.SYNCWAIT : int,
}

class RequiredCapabilities(BaseEnum):
    """
    Required Capabilities
    """
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE

class RequiredCommandCapabilities(BaseEnum):
    """
    Required Capabilities for Command State
    """
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE

class RequiredAutoSampleCapabilities(BaseEnum):
    """
    Required Capabilities for Autosample state
    """
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    GET = DriverEvent.GET

"""
Test Inputs
"""
VALID_SAMPLE = "24.0088,  0.00001,   -0.000,   0.0117, 03 Oct 2012 20:59:04\r\n"
# A beginning fragment (truncated)
VALID_SAMPLE_FRAG_01 = "24.0088,  0.00001"
# Ending fragment (the remainder of the above frag)
VALID_SAMPLE_FRAG_02 = ", -0.000,   0.0117, 03 Oct 2012 20:59:04\r\n"
# A full sample plus a beginning frag of another sample
VALID_SAMPLE_FRAG_03 = "24.0088,  0.00001, -0.000,   0.0117, 03 Oct 2012 20:59:04\r\n24.0088,  0.00001"
# A full sample plus a beginning frag of another sample
INVALID_SAMPLE = "bogus sample 03 Oct 2012 20:59:04\r\n24.0088,  0.00001"


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
class SBEUnitTestCase(InstrumentDriverUnitTestCase):
    """Unit Test Container"""

    def assertParams(self, pd, all_params=False):
        """
        Verify given (or all) device parameters exist.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))
    
    def reset_test_vars(self):
        self.raw_stream_received = 0
        self.parsed_stream_received = 0


    def my_event_callback(self, event):
        event_type = event['type']
        print "my_event_callback received: " + str(event)
        if event_type == DriverAsyncEvent.SAMPLE:
            sample_value = event['value']
            """
            DHE: Need to pull the list out of here.  It's coming out as a
            string like it is.
            """
            particle_dict = json.loads(sample_value)
            stream_type = particle_dict['stream_name']
            if stream_type == 'raw':
                self.raw_stream_received += 1
            elif stream_type == 'parsed':
                self.parsed_stream_received += 1


    """
    Test that the get_resource_params() method returns a list of params
    that matches what we expect.
    """
    def test_params(self):

        mock_port_agent = Mock(spec=PortAgentClient)
        test_driver = InstrumentDriver(self.my_event_callback)
        capability = test_driver.get_resource_params()
        # Manually add Parameter.ALL to the list of PARAMS 
        PARAMS.update({Parameter.ALL: list})
        self.assert_set_complete(capability, PARAMS)


    """
    Test that, given the complete ProtocolEvent list, the 
    filter_capabilities returns a list equal to Capabilities
    """        
    def test_filter_capabilities(self):

        mock_port_agent = Mock(spec=PortAgentClient)
        test_driver = InstrumentDriver(self.my_event_callback)

        """
        invoke configure and connect to set up the _protocol attribute
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        driver_events = ProtocolEvent.list()
        events = test_driver._protocol._filter_capabilities(driver_events)
        self.assertTrue(events)
        driver_capabilities = Capability.list()
        self.assertEqual(events, driver_capabilities)


    """
    Test that the driver returns the required capabilities. 
    """        
    def test_capabilities(self):

        mock_port_agent = Mock(spec=PortAgentClient)
        test_driver = InstrumentDriver(self.my_event_callback)

        """
        invoke configure and connect to set up the _protocol attribute
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        required_capabilities = RequiredCapabilities.list()
        driver_capabilities = test_driver._protocol._protocol_fsm.get_events(current_state=False)
        self.assert_set_complete(required_capabilities, driver_capabilities)


    """
    Test that the driver returns the required capabilities. 
    """        
    def test_all_params(self):

        mock_port_agent = Mock(spec=PortAgentClient)
        test_driver = InstrumentDriver(self.my_event_callback)

        """
        invoke configure and connect to set up the _protocol attribute
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        (next_state, all_params) = test_driver._protocol._handler_command_autosample_test_get(Parameter.ALL)
        self.assertParams(all_params, True)
        
    """
    Test that the driver returns the current capabilities when in autosample. 
    """        
    def test_autosample_capabilities(self):

        mock_port_agent = Mock(spec=PortAgentClient)
        test_driver = InstrumentDriver(self.my_event_callback)

        """
        Put the driver into test mode
        """
        test_driver.set_test_mode(True)

        """
        invoke configure and connect to set up the _protocol attribute
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        """
        Force the driver state to AUTOSAMPLE to test current capabilities
        """
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        required_capabilities = RequiredAutoSampleCapabilities.list()
        driver_capabilities = test_driver._protocol._protocol_fsm.get_events()
        self.assert_set_complete(required_capabilities, driver_capabilities)
        self.assertTrue(DriverEvent.START_AUTOSAMPLE not in driver_capabilities)


    """
    Test that the fsm is initialized with the full list of states
    """        
    def test_states(self):

        mock_port_agent = Mock(spec=PortAgentClient)
        test_driver = InstrumentDriver(self.my_event_callback)

        """
        invoke configure and connect to set up the _protocol attribute
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        test_driver.connect()
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)

        driver_fsm_states = test_driver._protocol._protocol_fsm.states.list()
        self.assertTrue(driver_fsm_states)
        driver_states = ProtocolState.list()
        self.assertEqual(driver_fsm_states, driver_states)
        

    """
    Test that the got_data method consumes a sample and publishes raw and
    parsed particles
    """        
    def test_valid_sample(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = InstrumentDriver(self.my_event_callback)
        
        """
        Put the driver into test mode
        """
        test_driver.set_test_mode(True)

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
        Force driver to AUTOSAMPLE state
        """
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        self.reset_test_vars()
        test_sample = VALID_SAMPLE
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 1)
        self.assertTrue(self.parsed_stream_received is 1)
        

    """
    Test that the got_data method does not publish an invalid sample
    """        
    def test_invalid_sample(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = InstrumentDriver(self.my_event_callback)
        
        """
        Put the driver into test mode
        """
        test_driver.set_test_mode(True)

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
        Force driver to AUTOSAMPLE state
        """
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        self.reset_test_vars()
        test_sample = INVALID_SAMPLE
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 0)
        self.assertTrue(self.parsed_stream_received is 0)


    """
    Test that the got_data method does not publish an invalid sample
    """        
    def test_invalid_sample_with_concatenated_valid(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = InstrumentDriver(self.my_event_callback)
        
        """
        Put the driver into test mode
        """
        test_driver.set_test_mode(True)

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
        Force driver to AUTOSAMPLE state
        """
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        self.reset_test_vars()
        test_sample = INVALID_SAMPLE
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 0)
        self.assertTrue(self.parsed_stream_received is 0)
        
        """
        This valid sample should not be published because it will be concatenated
        to the prior invalid fragment (trailing the CR LF).
        """
        test_sample = VALID_SAMPLE
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 0)
        self.assertTrue(self.parsed_stream_received is 0)
        
        """
        This valid sample SHOULD be published because the _linebuf should be cleared
        after the prior sample.
        """
        test_sample = VALID_SAMPLE
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 1)
        self.assertTrue(self.parsed_stream_received is 1)
        

    """
    Test that the got_data method consumes a fragmented sample and publishes raw and
    parsed particles
    """        
    def test_sample_fragment(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = InstrumentDriver(self.my_event_callback)
        
        """
        Put the driver into test mode
        """
        test_driver.set_test_mode(True)

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
        Force driver to AUTOSAMPLE state
        """
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        self.reset_test_vars()
        test_sample = VALID_SAMPLE_FRAG_01
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 0)
        self.assertTrue(self.parsed_stream_received is 0)
        
        test_sample = VALID_SAMPLE_FRAG_02
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 1)
        self.assertTrue(self.parsed_stream_received is 1)
        
    """
    Test that the got_data method consumes a sample that has a concatenated fragment
    """        
    def test_sample_concatenated_fragment(self):

        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = InstrumentDriver(self.my_event_callback)
        
        """
        Put the driver into test mode
        """
        test_driver.set_test_mode(True)

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
        Force driver to AUTOSAMPLE state
        """
        test_driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        self.reset_test_vars()
        test_sample = VALID_SAMPLE_FRAG_03
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 1)
        self.assertTrue(self.parsed_stream_received is 1)
        
        test_sample = VALID_SAMPLE_FRAG_02
        
        paPacket = PortAgentPacket()         
        paPacket.attach_data(test_sample)
        paPacket.pack_header()
  
        test_driver._protocol.got_data(paPacket)
        
        self.assertTrue(self.raw_stream_received is 2)
        self.assertTrue(self.parsed_stream_received is 2)
        

    @unittest.skip("Doesn't work because the set_handler tries to update variables.")    
    def test_set(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

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

        self.reset_test_vars()
        
        test_driver._protocol._handler_command_set({Parameter.OUTPUTSAL: True})

        
    def test_parse_ds(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

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

        self.reset_test_vars()
        test_ds_response = "output salinity = yes, output sound velocity = no\r\n"
        
        test_driver._protocol._parse_dsdc_response(test_ds_response, '<Executed/>')
 
      
    def test_protocol_handler_command_enter(self):
        """
        """
        test_driver = InstrumentDriver(self.my_event_callback)
        test_driver._build_protocol()
        test_protocol = test_driver._protocol
        _update_params_mock = Mock(spec="_update_params")
        test_protocol._update_params = _update_params_mock

        _update_driver_event = Mock(spec="driver_event")
        test_protocol._driver_event = _update_driver_event
        args = []
        kwargs =  dict({'timeout': 30,})

        ret = test_protocol._handler_command_enter(*args, **kwargs)
        self.assertEqual(ret, None)
        self.assertEqual(str(_update_params_mock.mock_calls), "[call()]")
        self.assertEqual(str(_update_driver_event.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")


    def test_initialize_time(self):
        """
        """
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

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

        _wakeup = Mock(spec="_wakeup")
        test_driver._protocol._wakeup = _wakeup
        
        def side_effect(timeout):
            return Prompt.EXECUTED
        _wakeup.side_effect = side_effect


        args = []
        kwargs = dict({})
        ret = test_driver._protocol._handler_unknown_discover(*args, **kwargs)


    @unittest.skip("Doesn't work because the set_handler tries to update variables.")    
    def test_fsm_handler(self):
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=PortAgentClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = InstrumentDriver(self.my_event_callback)
        
        """
        Put the driver into test mode
        """
        test_driver.set_test_mode(True)

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

        self.reset_test_vars()
        
        _update_params_mock = Mock(spec="_update_params")
        test_driver._protocol._update_params = _update_params_mock

        #_update_driver_event = Mock(spec="driver_event")
        test_driver._protocol._driver_event = self.my_event_callback
        args = []
        kwargs =  dict({'timeout': 30,})

        """
        Force the driver state to COMMAND
        """
        test_driver.test_force_state(state = DriverProtocolState.COMMAND)
        current_state = test_driver.get_resource_state()
        self.assertEqual(current_state, DriverProtocolState.COMMAND)

        args = [{Parameter.OUTPUTSAL: True}]
        kwargs = {}

        test_driver._connection_fsm.on_event(DriverEvent.SET, DriverEvent.SET, *args, **kwargs)
        #test_driver._protocol._handler_command_set({Parameter.OUTPUTSAL: True})

        


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minmum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class SBEIntTestCase(InstrumentDriverIntegrationTestCase):
    """
    Integration tests for the sbe16 driver. This class tests and shows
    use patterns for the sbe16 driver as a zmq driver process.
    """    
    
    def assertSampleDict(self, val):
        """
        Verify the value is a sample dictionary for the sbe16.
        """
        #{'p': [-6.945], 'c': [0.08707], 't': [20.002], 'time': [1333752198.450622]}        
        self.assertTrue(isinstance(val, dict))
        self.assertTrue(val.has_key('c'))
        self.assertTrue(val.has_key('t'))
        # DHE: Our SBE16 doesn't have a pressure sensor
        #self.assertTrue(val.has_key('p'))
        self.assertTrue(val.has_key('time'))
        c = val['c'][0]
        t = val['t'][0]
        time = val['time'][0]
        # DHE
        #p = val['p'][0]
    
        self.assertTrue(isinstance(c, float))
        self.assertTrue(isinstance(t, float))
        self.assertTrue(isinstance(time, float))
        # DHE
        #self.assertTrue(isinstance(p, float))
    
    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))
            #print str(pd)
            #print str(PARAMS)
            for (key, type_val) in PARAMS.iteritems():
                #print key
                self.assertTrue(isinstance(pd[key], type_val))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))
                self.assertTrue(isinstance(val, PARAMS[key]))
    
    def assertParamVals(self, params, correct_params):
        """
        Verify parameters take the correct values.
        """
        self.assertEqual(set(params.keys()), set(correct_params.keys()))
        for (key, val) in params.iteritems():
            correct_val = correct_params[key]
            if isinstance(val, float):
                # Verify to 5% of the larger value.
                max_val = max(abs(val), abs(correct_val))
                #
                # DHE TEMPTEMP
                #
                print 'val = ' + str(val) + ', correct_val = ' + str(correct_val) + ', delta = ' + str(max_val*.01)
                self.assertAlmostEqual(val, correct_val, delta=max_val*.01)

            else:
                # int, bool, str, or tuple of same
                self.assertEqual(val, correct_val)
    
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
        
    def test_capabilities(self):
        """
        Test get_resource_capaibilties in command state and autosample state;
        should be different in each.
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

        required_capabilities = RequiredCommandCapabilities.list()
        # Get the capabilities of the driver.
        driver_capabilities = self.driver_client.cmd_dvr('get_resource_capabilities')
        driver_capabilities = driver_capabilities[0]
        self.assert_set_complete(required_capabilities, driver_capabilities)

        # Put the driver in autosample
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)

        required_capabilities = RequiredAutoSampleCapabilities.list()
        # Get the capabilities of the driver.
        driver_capabilities = self.driver_client.cmd_dvr('get_resource_capabilities')
        driver_capabilities = driver_capabilities[0]
        self.assert_set_complete(required_capabilities, driver_capabilities)

        # Put the driver back in command mode
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        
    #@unittest.skip('DHE: TESTTESTTEST')
    def test_get_set(self):
        """
        Test device parameter access.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply, True)

        # Remember original configuration.
        orig_config = reply
        
        # Grab a subset of parameters.
        params = [
            Parameter.TA0,
            Parameter.INTERVAL,
            #Parameter.STORETIME,
            Parameter.TCALDATE
            ]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamDict(reply)        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        old_date = orig_params[Parameter.TCALDATE]
        new_params = {
            Parameter.TA0 : orig_params[Parameter.TA0] * 1.2,
            Parameter.INTERVAL : orig_params[Parameter.INTERVAL] + 1,
            #Parameter.STORETIME : not orig_params[Parameter.STORETIME],
            Parameter.TCALDATE : (old_date[0], old_date[1], old_date[2] + 1)
        }

        # Set parameters and verify.
        reply = self.driver_client.cmd_dvr('set_resource', new_params)
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamVals(reply, new_params)
        
        # Restore original parameters and verify.
        reply = self.driver_client.cmd_dvr('set_resource', orig_params)
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamVals(reply, orig_params)

        # Retrieve the configuration and ensure it matches the original.
        # Remove samplenum as it is switched by autosample and storetime.
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        reply.pop('SAMPLENUM')
        orig_config.pop('SAMPLENUM')
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
    
    #@unittest.skip('DHE: TESTTESTTEST')
    def test_poll(self):
        """
        Test sample polling commands and events.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
        #self.assertSampleDict(reply[1])
        
        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
        #self.assertSampleDict(reply[1])

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
        #self.assertSampleDict(reply[1])
        
        # Confirm that 6 samples (2 types, raw and parsed, for each poll) arrived as published events.
        gevent.sleep(1)
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        self.assertEqual(len(sample_events), 6)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

    #@unittest.skip('DHE: TESTTESTTEST')
    def test_autosample(self):
        """
        Test autosample mode.
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
        
        # Make sure the device parameters are set to sample frequently and
        # to transmit.
        params = {
            Parameter.NAVG : 1,
            Parameter.INTERVAL : 10, # Our borrowed SBE16plus takes no less than 10
            Parameter.TXREALTIME : True
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)
        
        # Wait for a few samples to roll in.
        #gevent.sleep(30)
        # DHE sleep long enough for a couple of samples
        gevent.sleep(40)
        
        # Return to command mode. Catch timeouts and retry if necessary.
        count = 0
        while True:
            try:
                reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
            
            except InstrumentTimeoutException:
                count += 1
                if count >= 5:
                    self.fail('Could not wakeup device to leave autosample mode.')

            else:
                break

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

    #@unittest.skip('Not supported by simulator and very long (> 5 min).')
    def test_test(self):
        """
        Test the hardware testing mode.
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

        start_time = time.time()
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.TEST)

        # Test the driver is in test state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.TEST)
        
        while state != ProtocolState.COMMAND:
            gevent.sleep(5)
            elapsed = time.time() - start_time
            log.info('Device testing %f seconds elapsed.' % elapsed)
            state = self.driver_client.cmd_dvr('get_resource_state')

        # Verify we received the test result and it passed.
        #test_results = [evt for evt in self.events if evt['type']==DriverAsyncEvent.TEST_RESULT]
        test_results = [evt for evt in self.events if evt['type']==DriverAsyncEvent.RESULT]
        self.assertTrue(len(test_results) == 1)
        self.assertEqual(test_results[0]['value']['success'], 'Passed')

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

    def test_errors(self):
        """
        Test response to erroneous commands and parameters.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Assert for an unknown driver command.
        with self.assertRaises(InstrumentCommandException):
            reply = self.driver_client.cmd_dvr('bogus_command')

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        # Assert we forgot the comms parameter.
        with self.assertRaises(InstrumentParameterException):
            reply = self.driver_client.cmd_dvr('configure')

        # Assert we send a bad config object (not a dict).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = 'not a config dict'            
            reply = self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
            
        # Assert we send a bad config object (missing addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG.pop('addr')
            reply = self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)

        # Assert we send a bad config object (bad addr value).
        with self.assertRaises(InstrumentParameterException):
            BOGUS_CONFIG = self.port_agent_comm_config().copy()
            BOGUS_CONFIG['addr'] = ''
            reply = self.driver_client.cmd_dvr('configure', BOGUS_CONFIG)
        
        # Configure for comms.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        """
        DHE: This doesn't work; the sample is now a particle that assertSampleDict does not parse
        correctly.
        """
        # Poll for a sample and confirm result.
        #reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
        #self.assertSampleDict(reply[1])

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
        
        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('connect')

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply, True)
        
        # Assert get fails without a parameter.
        with self.assertRaises(InstrumentParameterException):
            reply = self.driver_client.cmd_dvr('get_resource')
            
        # Assert get fails without a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            reply = self.driver_client.cmd_dvr('get_resource', bogus_params)
            
        # Assert get fails without a bad parameter (not ALL or a list).
        #with self.assertRaises(InvalidParameterValueError):
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                Parameter.INTERVAL,
                #Parameter.STORETIME,
                Parameter.TCALDATE
                ]
            reply = self.driver_client.cmd_dvr('get_resource', bogus_params)        
        
        # Assert we cannot set a bogus parameter.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name' : 'bogus value'
            }
            reply = self.driver_client.cmd_dvr('set_resource', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                Parameter.INTERVAL : 'bogus value'
            }
            reply = self.driver_client.cmd_dvr('set_resource', bogus_params)
        
        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
    
    @unittest.skip('Not supported by simulator.')
    def test_discover_autosample(self):
        """
        Test the device can discover autosample mode.
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
        
        # Make sure the device parameters are set to sample frequently.
        params = {
            Parameter.NAVG : 1,
            Parameter.INTERVAL : 5
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)
    
        # Let a sample or two come in.
        gevent.sleep(30)
    
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

        # Wait briefly before we restart the comms.
        gevent.sleep(10)
    
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
        count = 0
        while True:
            try:        
                reply = self.driver_client.cmd_dvr('discover')

            except InstrumentTimeoutException:
                count += 1
                if count >=5:
                    self.fail('Could not discover device state.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)

        # Let a sample or two come in.
        # This device takes awhile to begin transmitting again after you
        # prompt it in autosample mode.
        gevent.sleep(30)

        # Return to command mode. Catch timeouts and retry if necessary.
        count = 0
        while True:
            try:
                reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.STOP_AUTOSAMPLE)
            
            except InstrumentTimeoutException:
                count += 1
                if count >= 5:
                    self.fail('Could not wakeup device to leave autosample mode.')

            else:
                break

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
        
        

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class SBEQualTestCase(InstrumentDriverQualificationTestCase):
    """Qualification Test Container"""

    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.
    pass

    def assertSampleDataParticle(self, val):
        """
        Verify the value for a sbe16 sample data particle

        {
          'quality_flag': 'ok',
          'preferred_timestamp': 'driver_timestamp',
          'stream_name': 'parsed',
          'pkt_format_id': 'JSON_Data',
          'pkt_version': 1,
          'driver_timestamp': 3559843883.8029947,
          'values': [
            {
              'value_id': 'temp',
              'value': 67.4448
            },
            {
              'value_id': 'conductivity',
              'value': 44.69101
            },
            {
              'value_id': 'pressure',
              'value': 865.096
            }
            {
              'value_id': 'salinity',
              'value': 0.0114
            }
          ],
        }
        """

        if (isinstance(val, SBE16DataParticle)):
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
            self.assertTrue(x['value_id'] in ['temp', 'conductivity', 'depth', 'salinity'])
            self.assertTrue(isinstance(x['value'], float))


    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 2400}}})
    def test_direct_access_telnet_mode(self):
        """
        @brief This test verifies that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)


        gevent.sleep(5)  # wait for mavs4 to go back to sleep if it was sleeping
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
                            kwargs={'session_type': DirectAccessTypes.telnet,
                                    #kwargs={'session_type':DirectAccessTypes.vsp,
                                    'session_timeout':6000,
                                    'inactivity_timeout':6000})

        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()

        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        log.info("GO_DIRECT_ACCESS retval=" + str(retval.result))

        """
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

        s.send_data("\r\n", "1")
        gevent.sleep(2)

        try_count = 0
        while s.peek_at_buffer().find("S>") == -1:
            log.debug("BUFFER = '" + repr(s.peek_at_buffer()) + "'")
            self.assertNotEqual(try_count, 15)
            try_count += 1
            gevent.sleep(2)
        log.debug("FELL OUT!")

        s.remove_from_buffer("\r\nS>")
        s.remove_from_buffer("S>")
        try_count = 0
        s.send_data("ts\r\n", "1")

        while s.peek_at_buffer().find("ts") == -1:
            log.debug("BUFFER = '" + repr(s.peek_at_buffer()) + "'")
            self.assertNotEqual(try_count, 15)
            try_count += 1
            gevent.sleep(20)
        s.remove_from_buffer("ts")

        while s.peek_at_buffer().find("\r\nS>") == -1:
            log.debug("BUFFER = '" + repr(s.peek_at_buffer()) + "'")
            self.assertNotEqual(try_count, 15)
            try_count += 1
            gevent.sleep(20)

        #pattern = re.compile(" ([0-9\-\.]+) +([0-9\-\.]+) +([0-9\-\.]+) +([0-9\-\.]+) +([0-9\-\.]+)")
        pattern = re.compile(" ([0-9\-\.]+) +([0-9\-\.]+) +([0-9\-\.]+)")

        matches = 0
        n = 0
        while n < 100:
            n = n + 1
            gevent.sleep(1)
            data = s.peek_at_buffer()
            log.debug("READ ==>" + str(repr(data)))
            m = pattern.search(data)
            if m != None:
                log.debug("MATCHES ==>" + str(m.lastindex))
                matches = m.lastindex
                if matches == 3:
                    break

        log.debug("MATCHES = " + str(matches))
        #self.assertTrue(matches == 3) # verify that we found at least 3 fields.

        # RAW READ GOT ''ts -159.0737 -8387.75  -3.2164 -1.02535   0.0000\r\nS>''

        # exit direct access
        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)


        # verify params are restored. TBD
        """

    #@unittest.skip("Do not include until direct_access gets implemented")
    def my_test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)
    
        with self.assertRaises(Conflict):
            res_state = self.instrument_agent_client.get_resource_state()
    
        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        print("sent initialize; IA state = %s" %str(state))
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverConnectionState.UNCONFIGURED)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        print("sent go_active; IA state = %s" %str(state))
        self.assertEqual(state, ResourceAgentState.IDLE)

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverProtocolState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        print("sent run; IA state = %s" %str(state))
        self.assertEqual(state, ResourceAgentState.COMMAND)

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverProtocolState.COMMAND)

        # go direct access
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
                           kwargs={'session_type': DirectAccessTypes.telnet,
                                   #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))
        
        gevent.sleep(600)  # wait for manual telnet session to be run

    def test_parameter_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.
        """

        self.assertEqual(Parameter.ALL, DriverParameter.ALL)

        self.assertTrue(self.check_for_reused_values(DriverParameter))
        self.assertTrue(self.check_for_reused_values(Parameter))


    def test_protocol_event_enum(self):
        """
        @brief ProtocolState enum test

            1. test that ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.
        """

        self.assertEqual(ProtocolEvent.ENTER, DriverEvent.ENTER)
        self.assertEqual(ProtocolEvent.EXIT, DriverEvent.EXIT)
        self.assertEqual(ProtocolEvent.GET, DriverEvent.GET)
        self.assertEqual(ProtocolEvent.SET, DriverEvent.SET)
        self.assertEqual(ProtocolEvent.DISCOVER, DriverEvent.DISCOVER)
        self.assertEqual(ProtocolEvent.ACQUIRE_SAMPLE, DriverEvent.ACQUIRE_SAMPLE)
        self.assertEqual(ProtocolEvent.START_AUTOSAMPLE, DriverEvent.START_AUTOSAMPLE)
        self.assertEqual(ProtocolEvent.STOP_AUTOSAMPLE, DriverEvent.STOP_AUTOSAMPLE)
        self.assertEqual(ProtocolEvent.TEST, DriverEvent.TEST)
        self.assertEqual(ProtocolEvent.RUN_TEST, DriverEvent.RUN_TEST)
        self.assertEqual(ProtocolEvent.CALIBRATE, DriverEvent.CALIBRATE)
        self.assertEqual(ProtocolEvent.EXECUTE_DIRECT, DriverEvent.EXECUTE_DIRECT)
        self.assertEqual(ProtocolEvent.START_DIRECT, DriverEvent.START_DIRECT)
        self.assertEqual(ProtocolEvent.STOP_DIRECT, DriverEvent.STOP_DIRECT)

        self.assertTrue(self.check_for_reused_values(DriverEvent))
        self.assertTrue(self.check_for_reused_values(ProtocolEvent))


    def test_protocol_state_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.

        """

        self.assertEqual(ProtocolState.UNKNOWN, DriverProtocolState.UNKNOWN)
        self.assertEqual(ProtocolState.COMMAND, DriverProtocolState.COMMAND)
        self.assertEqual(ProtocolState.AUTOSAMPLE, DriverProtocolState.AUTOSAMPLE)
        self.assertEqual(ProtocolState.TEST, DriverProtocolState.TEST)
        self.assertEqual(ProtocolState.CALIBRATE, DriverProtocolState.CALIBRATE)
        self.assertEqual(ProtocolState.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS)

        self.assertTrue(self.check_for_reused_values(DriverProtocolState))
        self.assertTrue(self.check_for_reused_values(ProtocolState))


    def test_autosample(self):
        """
        Test instrument driver execute interface to start and stop streaming
        mode.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)


        # Make sure the sampling rate and transmission are sane.
        params = {
            Parameter.NAVG : 1,
            Parameter.INTERVAL : 5,
            Parameter.TXREALTIME : True
        }
        self.instrument_agent_client.set_resource(params)

        self.data_subscribers.clear_sample_queue('parsed')

        # Begin streaming.
        cmd = AgentCommand(command=ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=30)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        # Assert we got 3 samples.
        samples = self.data_subscribers.get_samples(DataParticleValue.PARSED, 3, timeout=60)
        self.assertGreaterEqual(len(samples), 3)

        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())

        # Halt streaming.
        cmd = AgentCommand(command=ProtocolEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=30)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        self.doCleanups()


    def test_acquire_sample(self):
        """
        Test observatory polling function.
        """
        # Set up all data subscriptions.  Stream names are defined
        # in the driver PACKET_CONFIG dictionary
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        ###
        # Poll for a few samples
        ###

        # make sure there aren't any junk samples in the parsed
        # data queue.
        self.data_subscribers.clear_sample_queue(DataParticleValue.PARSED)
        cmd = AgentCommand(command=ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        cmd = AgentCommand(command=ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        cmd = AgentCommand(command=ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        # Watch the parsed data queue and return once three samples
        # have been read or the default timeout has been reached.
        samples = self.data_subscribers.get_samples(DataParticleValue.PARSED, 3)
        self.assertGreaterEqual(len(samples), 3)

        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        self.doCleanups()


    def test_execute_reset(self):
        """
        @brief Walk the driver into command mode and perform a reset
        verifying it goes back to UNINITIALIZED, then walk it back to
        COMMAND to test there are no glitches in RESET
        """
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Test RESET

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)


    #@unittest.skip("Not working; not sure why...ServerError: 500 - 500 - gevent is only usable from a single thread...")
    def test_execute_test(self):
        """
        Test the hardware testing mode.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        #### From herehere down convert to agent-version
        start_time = time.time()
        cmd = AgentCommand(command=ProtocolEvent.TEST)
        retval = self.instrument_agent_client.execute_resource(cmd)

        # Test the driver is in test state.
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.TEST)
        
        while state != ResourceAgentState.COMMAND:
            gevent.sleep(5)
            elapsed = time.time() - start_time
            state = self.instrument_agent_client.get_agent_state()
            log.info('Device testing %f seconds elapsed. ResourceAgentState: %s' % (elapsed, state))

        """
        # Verify we received the test result and it passed.
        #test_results = [evt for evt in self.events if evt['type']==DriverAsyncEvent.TEST_RESULT]
        test_results = [evt for evt in self.events if evt['type']==DriverAsyncEvent.RESULT]
        self.assertTrue(len(test_results) == 1)
        self.assertEqual(test_results[0]['value']['success'], 'Passed')

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        """

    def test_acquire_status(self):
        """
        Test ACQUIRE_STATUS 
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        #### From herehere down convert to agent-version
        start_time = time.time()
        cmd = AgentCommand(command=ProtocolEvent.ACQUIRE_SAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)



