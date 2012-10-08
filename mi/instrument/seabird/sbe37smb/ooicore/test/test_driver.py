#!/usr/bin/env python

"""
@package ion.services.mi.instrument.sbe37.test.test_sbe37_driver
@file ion/services/mi/instrument/sbe37/test/test_sbe37_driver.py
@author Edward Hunter
@brief Test cases for InstrumentDriver
"""

__author__ = 'Edward Hunter'
__license__ = 'Apache 2.0'

# Ensure the test class is monkey patched for gevent


from mock import patch
from pyon.core.bootstrap import CFG

from gevent import monkey; monkey.patch_all()
import gevent
import socket
import re
import json

# Standard lib imports
import time
import unittest

# 3rd party imports
from nose.plugins.attrib import attr

from prototype.sci_data.stream_defs import ctd_stream_definition

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException

from mi.instrument.seabird.sbe37smb.ooicore.driver import PACKET_CONFIG
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37DataParticle
from mi.instrument.seabird.sbe37smb.ooicore.driver import InstrumentDriver
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37ProtocolState
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37Parameter
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37ProtocolEvent
from mi.instrument.seabird.sbe37smb.ooicore.driver import SBE37Capability
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

# MI logger
from mi.core.log import get_logger ; log = get_logger()
from interface.objects import AgentCommand

from ion.agents.instrument.instrument_agent import InstrumentAgentState

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from mi.core.instrument.instrument_driver import DriverEvent

from mi.core.instrument.instrument_driver import DriverProtocolState

from prototype.sci_data.stream_parser import PointSupplementStreamParser
from prototype.sci_data.constructor_apis import PointSupplementConstructor
from prototype.sci_data.stream_defs import ctd_stream_definition
from prototype.sci_data.stream_defs import SBE37_CDM_stream_definition
import numpy
from prototype.sci_data.stream_parser import PointSupplementStreamParser

from pyon.core import exception
from pyon.core.exception import InstParameterError
from pyon.core import exception as iex

from gevent.timeout import Timeout

from pyon.agent.agent import ResourceAgentClient
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from pyon.core.exception import BadRequest
from pyon.core.exception import Conflict


from interface.objects import CapabilityType
from interface.objects import AgentCapability

# Make tests verbose and provide stdout
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_process
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_config
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_connect
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_get_set
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_poll
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_autosample
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_test
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_errors
# bin/nosetests -s -v mi/instrument/seabird/sbe37smb/ooicore/test/test_driver.py:TestSBE37Driver.test_discover_autosample


## Initialize the test parameters
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe37smb.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
)
#

# Used to validate param config retrieved from driver.
PARAMS = {
    SBE37Parameter.OUTPUTSAL : bool,
    SBE37Parameter.OUTPUTSV : bool,
    SBE37Parameter.NAVG : int,
    SBE37Parameter.SAMPLENUM : int,
    SBE37Parameter.INTERVAL : int,
    SBE37Parameter.STORETIME : bool,
    SBE37Parameter.TXREALTIME : bool,
    SBE37Parameter.SYNCMODE : bool,
    SBE37Parameter.SYNCWAIT : int,
    SBE37Parameter.TCALDATE : tuple,
    SBE37Parameter.TA0 : float,
    SBE37Parameter.TA1 : float,
    SBE37Parameter.TA2 : float,
    SBE37Parameter.TA3 : float,
    SBE37Parameter.CCALDATE : tuple,
    SBE37Parameter.CG : float,
    SBE37Parameter.CH : float,
    SBE37Parameter.CI : float,
    SBE37Parameter.CJ : float,
    SBE37Parameter.WBOTC : float,
    SBE37Parameter.CTCOR : float,
    SBE37Parameter.CPCOR : float,
    SBE37Parameter.PCALDATE : tuple,
    SBE37Parameter.PA0 : float,
    SBE37Parameter.PA1 : float,
    SBE37Parameter.PA2 : float,
    SBE37Parameter.PTCA0 : float,
    SBE37Parameter.PTCA1 : float,
    SBE37Parameter.PTCA2 : float,
    SBE37Parameter.PTCB0 : float,
    SBE37Parameter.PTCB1 : float,
    SBE37Parameter.PTCB2 : float,
    SBE37Parameter.POFFSET : float,
    SBE37Parameter.RCALDATE : tuple,
    SBE37Parameter.RTCA0 : float,
    SBE37Parameter.RTCA1 : float,
    SBE37Parameter.RTCA2 : float
}

class my_sock():
    buf = ""
    def __init__(self, host, port):
        self.buf = ""
        self.host = host
        self.port = port
        # log.debug("OPEN SOCKET HOST = " + str(host) + " PORT = " + str(port))
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, self.port))
        self.s.settimeout(0.0)

    def read_a_char(self):
        c = None
        if len(self.buf) > 0:
            c = self.buf[0:1]
            self.buf = self.buf[1:]
        else:
            self.buf = self.s.recv(1024)
            log.debug("RAW READ GOT '" + str(repr(self.buf)) + "'")

        return c


    def peek_at_buffer(self):
        if len(self.buf) == 0:
            try:
                self.buf = self.s.recv(1024)
                log.debug("RAW READ GOT '" + str(repr(self.buf)) + "'")
            except:
                """
                Ignore this exception, its harmless
                """

        return self.buf

    def remove_from_buffer(self, remove):
        log.debug("BUF WAS " + str(repr(self.buf)))
        self.buf = self.buf.replace(remove, "")
        log.debug("BUF IS '" + str(repr(self.buf)) + "'")

    def get_data(self):
        data = ""
        try:
            ret = ""

            while True:
                c = self.read_a_char()
                if c == None:
                    break
                if c == '\n' or c == '':
                    ret += c
                    break
                else:
                    ret += c

            data = ret
        except AttributeError:
            log.debug("CLOSING - GOT AN ATTRIBUTE ERROR")
            self.s.close()
        except:
            data = ""

        if data:
            data = data.lower()
            log.debug("IN  [" + repr(data) + "]")
        return data

    def send_data(self, data, debug):
        try:
            log.debug("OUT [" + repr(data) + "]")
            self.s.sendall(data)
        except:
            log.debug("*** send_data FAILED [" + debug + "] had an exception sending [" + data + "]")


@attr('UNIT', group='mi')
class SBEUnitTestCase(InstrumentDriverUnitTestCase):
    """Unit Test Container"""
    pass

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class SBEIntTestCase(InstrumentDriverIntegrationTestCase):
    """
    Integration tests for the sbe37 driver. This class tests and shows
    use patterns for the sbe37 driver as a zmq driver process.
    """    

    def assertSampleDict(self, val):
        """
        Verify the value is an SBE37DataParticle with a few key fields or a
        dict with 'raw' and 'parsed' tags.
        """
        
        if (isinstance(val, SBE37DataParticle)):
            raw_dict = json.loads(val.generate_raw())
            parsed_dict = json.loads(val.generate_parsed())
        else:
            self.assertTrue(val['raw'])
            raw_dict = val['raw']
            self.assertTrue(val['parsed'])
            parsed_dict = val['parsed']
            
        self.assertTrue(raw_dict[DataParticleKey.STREAM_NAME],
                        DataParticleValue.RAW)
        self.assertTrue(raw_dict[DataParticleKey.PKT_FORMAT_ID],
                        DataParticleValue.JSON_DATA)
        self.assertTrue(raw_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(raw_dict[DataParticleKey.VALUES],
                        list))
        
        self.assertTrue(parsed_dict[DataParticleKey.STREAM_NAME],
                        DataParticleValue.PARSED)
        self.assertTrue(parsed_dict[DataParticleKey.PKT_FORMAT_ID],
                        DataParticleValue.JSON_DATA)
        self.assertTrue(parsed_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertTrue(isinstance(parsed_dict[DataParticleKey.VALUES],
                        list))
        
    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))
            for (key, type_val) in PARAMS.iteritems():
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
        log.info("test_connect test started")

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
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

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
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', SBE37Parameter.ALL)
        self.assertParamDict(reply, True)

        # Remember original configuration.
        orig_config = reply
        
        # Grab a subset of parameters.
        params = [
            SBE37Parameter.TA0,
            SBE37Parameter.INTERVAL,
            SBE37Parameter.STORETIME,
            SBE37Parameter.TCALDATE
            ]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamDict(reply)        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        old_date = orig_params[SBE37Parameter.TCALDATE]
        new_params = {
            SBE37Parameter.TA0 : orig_params[SBE37Parameter.TA0] * 1.2,
            SBE37Parameter.INTERVAL : orig_params[SBE37Parameter.INTERVAL] + 1,
            SBE37Parameter.STORETIME : not orig_params[SBE37Parameter.STORETIME],
            SBE37Parameter.TCALDATE : (old_date[0], old_date[1], old_date[2] + 1)
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
        reply = self.driver_client.cmd_dvr('get_resource', SBE37Parameter.ALL)
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
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)
        self.assertSampleDict(reply[1])
        
        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)
        self.assertSampleDict(reply[1])

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)
        self.assertSampleDict(reply[1])
        
        # Confirm that 3 samples arrived as published events.
        gevent.sleep(1)
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        # @TODO Set this properly (3) when only one set of events are sent
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
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)
        
        # Make sure the device parameters are set to sample frequently.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.AUTOSAMPLE)
        
        # Wait for a few samples to roll in.
        gevent.sleep(30)
        
        # Return to command mode. Catch timeouts and retry if necessary.
        count = 0
        while True:
            try:
                reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.STOP_AUTOSAMPLE)
            
            except InstrumentTimeoutException:
                count += 1
                if count >= 5:
                    self.fail('Could not wakeup device to leave autosample mode.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

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

    @unittest.skip('Not supported by simulator and very long (> 5 min).')
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
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        start_time = time.time()
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.TEST)

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.TEST)
        
        while state != SBE37ProtocolState.COMMAND:
            gevent.sleep(5)
            elapsed = time.time() - start_time
            log.info('Device testing %f seconds elapsed.' % elapsed)
            state = self.driver_client.cmd_dvr('get_resource_state')

        # Verify we received the test result and it passed.
        test_results = [evt for evt in self.events if evt['type']==DriverAsyncEvent.TEST_RESULT]
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
            reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)

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
            reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)
                
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.ACQUIRE_SAMPLE)
        self.assertSampleDict(reply[1])

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.STOP_AUTOSAMPLE)
        
        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('connect')

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get_resource', SBE37Parameter.ALL)
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
                SBE37Parameter.INTERVAL,
                SBE37Parameter.STORETIME,
                SBE37Parameter.TCALDATE
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
                SBE37Parameter.INTERVAL : 'bogus value'
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
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)
        
        # Make sure the device parameters are set to sample frequently.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        
        reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.START_AUTOSAMPLE)

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.AUTOSAMPLE)
    
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
        self.assertEqual(state, SBE37ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        count = 0
        while True:
            try:        
                reply = self.driver_client.cmd_dvr('discover_state')

            except InstrumentTimeoutException:
                count += 1
                if count >=5:
                    self.fail('Could not discover device state.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.AUTOSAMPLE)

        # Let a sample or two come in.
        # This device takes awhile to begin transmitting again after you
        # prompt it in autosample mode.
        gevent.sleep(30)

        # Return to command mode. Catch timeouts and retry if necessary.
        count = 0
        while True:
            try:
                reply = self.driver_client.cmd_dvr('execute_resource', SBE37Capability.STOP_AUTOSAMPLE)
            
            except InstrumentTimeoutException:
                count += 1
                if count >= 5:
                    self.fail('Could not wakeup device to leave autosample mode.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, SBE37ProtocolState.COMMAND)

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

    # Added tests below



#self._dvr_proc = self.driver_process
#self._pagent = self.port_agent
#self._dvr_client = self.driver_client
#self._events = self.events
#COMMS_CONFIG = self.port_agent_comm_config()
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class SBEQualificationTestCase(InstrumentDriverQualificationTestCase):
    """Qualification Test Container"""

    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.
    pass

    #@unittest.skip("Do not include until direct_access gets implemented")
    def test_direct_access_telnet_mode(self):
        """
        @brief This test verifies that the Instrument Driver
               properly supports direct access to the physical
               instrument. (telnet mode)
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

        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={'session_type': DirectAccessTypes.telnet,
                                   #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))

        s = my_sock(retval.result['ip_address'], retval.result['port'])
        
        try_count = 0
        while s.peek_at_buffer().find("Username: ") == -1:
            log.debug("WANT 'Username:' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count = try_count + 1
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a Username: prompt')

        s.remove_from_buffer("Username: ")
        s.send_data("bob\r\n", "1")

        try_count = 0
        while s.peek_at_buffer().find("token: ") == -1:
            log.debug("WANT 'token: ' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            try_count = try_count + 1
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a token: prompt')
        s.remove_from_buffer("token: ")
        s.send_data(retval.result['token'] + "\r\n", "1")

        try_count = 0
        while s.peek_at_buffer().find("connected\n") == -1:
            log.debug("WANT 'connected\n' READ ==>" + str(s.peek_at_buffer()))
            gevent.sleep(1)
            s.peek_at_buffer()
            try_count = try_count + 1
            if try_count > 10:
                raise Timeout('I took longer than 10 seconds to get a connected prompt')

        s.remove_from_buffer("connected\n")
        s.send_data("ts\r\n", "1")
        log.debug("SENT THE TS COMMAND")

        pattern = re.compile("^([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9\-\.]+),([ 0-9a-z]+),([ 0-9:]+)")

        matches = 0
        n = 0
        while n < 100:
            n = n + 1
            gevent.sleep(1)
            data = s.get_data()
            log.debug("READ ==>" + str(repr(data)))
            m = pattern.search(data)
            if m != None:
                matches = m.lastindex
                if matches == 7:
                    break

        self.assertTrue(matches == 7) # need to have found 7 conformant fields.

    @unittest.skip("Do not include until a good method is devised")
    def test_direct_access_virtual_serial_port_mode(self):
        """
        @brief This test verifies that the Instrument Driver
               properly supports direct access to the physical
               instrument. (virtual serial port mode)

        Status: Sample code for this test has yet to be written.
                WCB will implement next iteration

        UPDATE: Do not include for now. May include later as a
                good method is devised

        TODO:
        """
        pass

    def test_sbe37_parameter_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that SBE37ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.
        """

        self.assertEqual(SBE37Parameter.ALL, DriverParameter.ALL)

        self.assertTrue(self.check_for_reused_values(DriverParameter))
        self.assertTrue(self.check_for_reused_values(SBE37Parameter))


    def test_protocol_event_enum(self):
        """
        @brief ProtocolState enum test

            1. test that SBE37ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.
        """

        self.assertEqual(SBE37ProtocolEvent.ENTER, DriverEvent.ENTER)
        self.assertEqual(SBE37ProtocolEvent.EXIT, DriverEvent.EXIT)
        self.assertEqual(SBE37ProtocolEvent.GET, DriverEvent.GET)
        self.assertEqual(SBE37ProtocolEvent.SET, DriverEvent.SET)
        self.assertEqual(SBE37ProtocolEvent.DISCOVER, DriverEvent.DISCOVER)
        self.assertEqual(SBE37ProtocolEvent.ACQUIRE_SAMPLE, DriverEvent.ACQUIRE_SAMPLE)
        self.assertEqual(SBE37ProtocolEvent.START_AUTOSAMPLE, DriverEvent.START_AUTOSAMPLE)
        self.assertEqual(SBE37ProtocolEvent.STOP_AUTOSAMPLE, DriverEvent.STOP_AUTOSAMPLE)
        self.assertEqual(SBE37ProtocolEvent.TEST, DriverEvent.TEST)
        self.assertEqual(SBE37ProtocolEvent.RUN_TEST, DriverEvent.RUN_TEST)
        self.assertEqual(SBE37ProtocolEvent.CALIBRATE, DriverEvent.CALIBRATE)
        self.assertEqual(SBE37ProtocolEvent.EXECUTE_DIRECT, DriverEvent.EXECUTE_DIRECT)
        self.assertEqual(SBE37ProtocolEvent.START_DIRECT, DriverEvent.START_DIRECT)
        self.assertEqual(SBE37ProtocolEvent.STOP_DIRECT, DriverEvent.STOP_DIRECT)

        self.assertTrue(self.check_for_reused_values(DriverEvent))
        self.assertTrue(self.check_for_reused_values(SBE37ProtocolEvent))


    def test_protocol_state_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that SBE37ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.

        """

        self.assertEqual(SBE37ProtocolState.UNKNOWN, DriverProtocolState.UNKNOWN)
        self.assertEqual(SBE37ProtocolState.COMMAND, DriverProtocolState.COMMAND)
        self.assertEqual(SBE37ProtocolState.AUTOSAMPLE, DriverProtocolState.AUTOSAMPLE)
        self.assertEqual(SBE37ProtocolState.TEST, DriverProtocolState.TEST)
        self.assertEqual(SBE37ProtocolState.CALIBRATE, DriverProtocolState.CALIBRATE)
        self.assertEqual(SBE37ProtocolState.DIRECT_ACCESS, DriverProtocolState.DIRECT_ACCESS)


        #SBE37ProtocolState.UNKNOWN = SBE37ProtocolState.COMMAND
        #SBE37ProtocolState.UNKNOWN2 = SBE37ProtocolState.UNKNOWN

        self.assertTrue(self.check_for_reused_values(DriverProtocolState))
        self.assertTrue(self.check_for_reused_values(SBE37ProtocolState))


    @unittest.skip("Underlying method not yet implemented")
    def test_driver_memory_leaks(self):
        """
        @brief long running test that runs over a half hour, and looks for memory leaks.
               stub this out for now
        TODO: write test if time permits after all other tests are done.
        """
        pass

    @unittest.skip("SKIP for now.  This will come in around the time we split IA into 2 parts wet side dry side")
    def test_instrument_agent_data_decimation(self):
        """
        @brief This test verifies that the instrument driver,
               if required, can properly decimate sampling data.
                decimate here means send every 5th sample.

        """
        pass

    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 60}}})
    def test_data_stream_integrity_autosample_parsed(self):
        """
        @brief This tests verifies that the canonical data
               stream emitted by the driver properly conforms
               to the canonical format. parsed data stream in autosample mode
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

        self.data_subscribers.samples_received = []

        # Make sure the sampling rate and transmission are sane.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5,
            SBE37Parameter.TXREALTIME : True
        }
        self.instrument_agent_client.set_resource(params)

        self.data_subscribers.no_samples = 2

        # Begin streaming.
        cmd = AgentCommand(command=SBE37ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)


        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        # Wait for some samples to roll in.
        gevent.sleep(15)

        # Halt streaming.
        cmd = AgentCommand(command=SBE37ProtocolEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)


        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Assert we got some samples.


        self.data_subscribers.async_data_result.get(timeout=33)

        self.assertTrue(len(self.data_subscribers.samples_received)>=2)


        for x in self.data_subscribers.samples_received:

            psd = PointSupplementStreamParser(stream_definition=SBE37_CDM_stream_definition(), stream_granule=x)

            self.assertTrue(isinstance(psd, PointSupplementStreamParser))
            field_names = psd.list_field_names()

            self.assertTrue('conductivity' in field_names)
            self.assertTrue('pressure' in field_names)
            self.assertTrue('temperature' in field_names)
            self.assertTrue('time' in field_names)

            conductivity = psd.get_values('conductivity')
            pressure = psd.get_values('pressure')
            temperature = psd.get_values('temperature')
            time = psd.get_values('time')

            self.assertTrue(isinstance(conductivity[0], numpy.float64))
            self.assertTrue(isinstance(temperature[0], numpy.float64))
            self.assertTrue(isinstance(pressure[0], numpy.float64))
            self.assertTrue(isinstance(time[0], numpy.float64))



        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)



        pass

    @unittest.skip("raw mode not yet implemented")
    def test_data_stream_integrity_autosample_raw(self):
        """
        @brief This tests verifies that the canonical data
               stream emitted by the driver properly conforms
               to the canonical format. raw data stream in autosample mode
        """
        pass

    def assertSampleDict(self, val):
        """
        Verify the value is a sample dictionary for the sbe37.
        OLD FORMAT:
        #{'p': [-6.945], 'c': [0.08707], 't': [20.002], 'time': [1333752198.450622]}

        NEW FORMAT:

            'result': {
                'raw': {
                    'quality_flag': 'ok',
                    'preferred_timestamp': 'driver_timestamp',
                    'stream_name': 'raw',
                    'pkt_format_id': 'JSON_Data',
                    'pkt_version': 1,
                    'values': [
                        {
                            'binary': True,
                            'value_id': 'raw',
                            'value': 'MTA2LjgwODQsIDAuMTMxNzcsICAgLTkuNDExLCAgIDAuMjMxMCwgMTUzNS45MTcsIDA0IE1heSAxOTgwLCAwMjowNToxNw=='
                        }
                    ],
                    'driver_timestamp': 3557855046.123893
                },
                'parsed': {
                    'quality_flag': 'ok',
                    'preferred_timestamp': 'driver_timestamp',
                    'stream_name': 'parsed',
                    'pkt_format_id': 'JSON_Data',
                    'pkt_version': 1,
                    'values': [
                        {
                            'value_id': 'temp',
                            'value': 106.8084
                        },
                        {
                            'value_id': 'conductivity',
                            'value': 0.13177
                        },
                        {
                            'value_id': 'depth',
                            'value': -9.411
                        }
                    ],
                    'driver_timestamp': 3557855046.123893
                }
            },


        """

        for x in val['parsed']['values']:
            self.assertTrue(x['value_id'] in ['temp', 'conductivity', 'depth'])
            self.assertTrue(isinstance(x['value'], float))

        '''
        self.assertTrue(isinstance(val, dict))
        self.assertTrue(val.has_key('c'))
        self.assertTrue(val.has_key('t'))
        self.assertTrue(val.has_key('p'))
        self.assertTrue(val.has_key('time'))
        c = val['c'][0]
        t = val['t'][0]
        p = val['p'][0]
        time = val['time'][0]

        self.assertTrue(isinstance(c, float))
        self.assertTrue(isinstance(t, float))
        self.assertTrue(isinstance(p, float))
        self.assertTrue(isinstance(time, float))
        '''


    def test_data_stream_integrity_polled_parsed(self):
        """
        @brief This tests verifies that the canonical data
               stream emitted by the driver properly conforms
               to the canonical format. parsed data stream in polled mode
        """
        self.data_subscribers.samples_received = []

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


        # Lets get 3 samples.
        self.data_subscribers.no_samples = 3

        # Poll for a few samples.
        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)
        self.assertSampleDict(reply.result)

        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)
        self.assertSampleDict(reply.result)

        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)
        self.assertSampleDict(reply.result)

        # Assert we got 3 samples.
        self.data_subscribers.async_data_result.get(timeout=10)
        self.assertTrue(len(self.data_subscribers.samples_received)==self.data_subscribers.no_samples)

        for x in self.data_subscribers.samples_received:
            psd = PointSupplementStreamParser(stream_definition=SBE37_CDM_stream_definition(), stream_granule=x)

            self.assertTrue(isinstance(psd, PointSupplementStreamParser))
            field_names = psd.list_field_names()

            self.assertTrue('conductivity' in field_names)
            self.assertTrue('pressure' in field_names)
            self.assertTrue('temperature' in field_names)
            self.assertTrue('time' in field_names)

            conductivity = psd.get_values('conductivity')
            pressure = psd.get_values('pressure')
            temperature = psd.get_values('temperature')
            time = psd.get_values('time')

            self.assertTrue(isinstance(conductivity[0], numpy.float64))
            self.assertTrue(isinstance(temperature[0], numpy.float64))
            self.assertTrue(isinstance(pressure[0], numpy.float64))
            self.assertTrue(isinstance(time[0], numpy.float64))

        cmd = AgentCommand(command='reset')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        pass

    @unittest.skip("raw mode not yet implemented")
    def test_data_stream_integrity_polled_raw(self):
        """
        @brief This tests verifies that the canonical data
               stream emitted by the driver properly conforms
               to the canonical format. raw data stream in polled mode
        """
        pass

    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 60}}})
    def test_capabilities(self):
        """
        Test the ability to retrieve agent and resource parameter and command
        capabilities in various system states.
        """

        agt_cmds_all = [
            ResourceAgentEvent.INITIALIZE,
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.GO_ACTIVE,
            ResourceAgentEvent.GO_INACTIVE,
            ResourceAgentEvent.RUN,
            ResourceAgentEvent.CLEAR,
            ResourceAgentEvent.PAUSE,
            ResourceAgentEvent.RESUME,
            ResourceAgentEvent.GO_COMMAND,
            ResourceAgentEvent.GO_DIRECT_ACCESS
        ]

        agt_pars_all = ['example']

        res_cmds_all =[
            SBE37ProtocolEvent.TEST,
            SBE37ProtocolEvent.ACQUIRE_SAMPLE,
            SBE37ProtocolEvent.START_AUTOSAMPLE,
            SBE37ProtocolEvent.STOP_AUTOSAMPLE
        ]

        res_pars_all = PARAMS.keys()


        def sort_caps(caps_list):
            agt_cmds = []
            agt_pars = []
            res_cmds = []
            res_pars = []

            if len(caps_list)>0 and isinstance(caps_list[0], AgentCapability):
                agt_cmds = [x.name for x in retval if x.cap_type==CapabilityType.AGT_CMD]
                agt_pars = [x.name for x in retval if x.cap_type==CapabilityType.AGT_PAR]
                res_cmds = [x.name for x in retval if x.cap_type==CapabilityType.RES_CMD]
                res_pars = [x.name for x in retval if x.cap_type==CapabilityType.RES_PAR]

            elif len(caps_list)>0 and isinstance(caps_list[0], dict):
                agt_cmds = [x['name'] for x in retval if x['cap_type']==CapabilityType.AGT_CMD]
                agt_pars = [x['name'] for x in retval if x['cap_type']==CapabilityType.AGT_PAR]
                res_cmds = [x['name'] for x in retval if x['cap_type']==CapabilityType.RES_CMD]
                res_pars = [x['name'] for x in retval if x['cap_type']==CapabilityType.RES_PAR]

            return agt_cmds, agt_pars, res_cmds, res_pars


        ##################################################################
        # UNINITIALIZED
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities for state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_uninitialized = [
            ResourceAgentEvent.INITIALIZE
        ]
        self.assertItemsEqual(agt_cmds, agt_cmds_uninitialized)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)

        ##################################################################
        # INACTIVE
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities for state INACTIVE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_inactive = [
            ResourceAgentEvent.GO_ACTIVE,
            ResourceAgentEvent.RESET
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_inactive)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state INACTIVE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)

        ##################################################################
        # IDLE
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities for state IDLE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_idle = [
            ResourceAgentEvent.GO_INACTIVE,
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.RUN
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_idle)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states as read from IDLE.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state IDLE.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)

        ##################################################################
        # COMMAND
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities of state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        agt_cmds_command = [
            ResourceAgentEvent.CLEAR,
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.GO_DIRECT_ACCESS,
            ResourceAgentEvent.GO_INACTIVE,
            ResourceAgentEvent.PAUSE
        ]

        res_cmds_command = [
            SBE37ProtocolEvent.TEST,
            SBE37ProtocolEvent.ACQUIRE_SAMPLE,
            SBE37ProtocolEvent.START_AUTOSAMPLE
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_command)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_command)
        self.assertItemsEqual(res_pars, res_pars_all)

        # Get exposed capabilities in all states as read from state COMMAND.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_all)
        self.assertItemsEqual(res_pars, res_pars_all)

        cmd = AgentCommand(command=SBE37ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        ##################################################################
        # STREAMING
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities of state STREAMING
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)


        agt_cmds_streaming = [
            ResourceAgentEvent.RESET,
            ResourceAgentEvent.GO_INACTIVE
        ]

        res_cmds_streaming = [
            SBE37ProtocolEvent.STOP_AUTOSAMPLE
        ]

        self.assertItemsEqual(agt_cmds, agt_cmds_streaming)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_streaming)
        self.assertItemsEqual(res_pars, res_pars_all)

        # Get exposed capabilities in all states as read from state STREAMING.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_all)
        self.assertItemsEqual(res_pars, res_pars_all)

        gevent.sleep(5)

        cmd = AgentCommand(command=SBE37ProtocolEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        ##################################################################
        # COMMAND
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities of state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_command)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_command)
        self.assertItemsEqual(res_pars, res_pars_all)

        # Get exposed capabilities in all states as read from state STREAMING.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state COMMAND
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, res_cmds_all)
        self.assertItemsEqual(res_pars, res_pars_all)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        ##################################################################
        # UNINITIALIZED
        ##################################################################

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        # Get exposed capabilities in current state.
        retval = self.instrument_agent_client.get_capabilities()

        # Validate capabilities for state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_uninitialized)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

        # Get exposed capabilities in all states.
        retval = self.instrument_agent_client.get_capabilities(False)

        # Validate all capabilities as read from state UNINITIALIZED.
        agt_cmds, agt_pars, res_cmds, res_pars = sort_caps(retval)

        self.assertItemsEqual(agt_cmds, agt_cmds_all)
        self.assertItemsEqual(agt_pars, agt_pars_all)
        self.assertItemsEqual(res_cmds, [])
        self.assertItemsEqual(res_pars, [])

    def test_autosample(self):
        """
        Test instrument driver execute interface to start and stop streaming
        mode.
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


        # Make sure the sampling rate and transmission are sane.
        params = {
            SBE37Parameter.NAVG : 1,
            SBE37Parameter.INTERVAL : 5,
            SBE37Parameter.TXREALTIME : True
        }
        self.instrument_agent_client.set_resource(params)

        self.data_subscribers.no_samples = 2

        # Begin streaming.
        cmd = AgentCommand(command=SBE37ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)


        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        # Wait for some samples to roll in.
        gevent.sleep(15)

        # Halt streaming.
        cmd = AgentCommand(command=SBE37ProtocolEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)


        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Assert we got some samples.
        self.data_subscribers.async_data_result.get(timeout=10)
        self.assertTrue(len(self.data_subscribers.samples_received)>=2)


        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)


        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)


    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))
            for (key, type_val) in PARAMS.iteritems():
                if type_val == list or type_val == tuple:
                    self.assertTrue(isinstance(pd[key], (list, tuple)))
                else:
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
                self.assertAlmostEqual(val, correct_val, delta=max_val*.01)

            elif isinstance(val, (list, tuple)):
                # list of tuple.
                self.assertEqual(list(val), list(correct_val))

            else:
                # int, bool, str.
                self.assertEqual(val, correct_val)

    def test_get_set(self):
        """
        Test instrument driver get and set interface.
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

        # Retrieve all resource parameters.
        reply = self.instrument_agent_client.get_resource(SBE37Parameter.ALL)
        self.assertParamDict(reply, True)
        orig_config = reply

        # Retrieve a subset of resource parameters.
        params = [
            SBE37Parameter.OUTPUTSV,
            SBE37Parameter.NAVG,
            SBE37Parameter.TA0
        ]
        reply = self.instrument_agent_client.get_resource(params)
        self.assertParamDict(reply)
        orig_params = reply

        # Set a subset of resource parameters.
        new_params = {
            SBE37Parameter.OUTPUTSV : not orig_params[SBE37Parameter.OUTPUTSV],
            SBE37Parameter.NAVG : orig_params[SBE37Parameter.NAVG] + 1,
            SBE37Parameter.TA0 : orig_params[SBE37Parameter.TA0] * 2
        }
        self.instrument_agent_client.set_resource(new_params)
        check_new_params = self.instrument_agent_client.get_resource(params)
        self.assertParamVals(check_new_params, new_params)

        # Reset the parameters back to their original values.
        self.instrument_agent_client.set_resource(orig_params)
        reply = self.instrument_agent_client.get_resource(SBE37Parameter.ALL)
        reply.pop(SBE37Parameter.SAMPLENUM)
        orig_config.pop(SBE37Parameter.SAMPLENUM)
        self.assertParamVals(reply, orig_config)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 60}}})
    def test_poll(self):
        """
        Test observatory polling function.
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

        # Lets get 3 samples.
        self.data_subscribers.no_samples = 3

        # Poll for a few samples.
        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)
        self.assertSampleDict(reply.result)

        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)
        self.assertSampleDict(reply.result)

        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)
        self.assertSampleDict(reply.result)

        # Assert we got 3 samples.
        # note no samples are being caught by the default data subscriber.
        self.data_subscribers.async_data_result.get(timeout=10)
        log.debug("SAMPLES RECEIVED =====> " + str(self.data_subscribers.samples_received))
        self.assertTrue(len(self.data_subscribers.samples_received)==self.data_subscribers.no_samples)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)


    def test_instrument_driver_vs_invalid_commands(self):
        """
        @Author Edward Hunter
        @brief This test should send mal-formed, misspelled,
               missing parameter, or out of bounds parameters
               at the instrument driver in an attempt to
               confuse it.

               See: test_instrument_driver_to_physical_instrument_interoperability
               That test will provide the how-to of connecting.
               Once connected, send messed up commands.

               * negative testing


               Test illegal behavior and replies.
        """


        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)



        # Try to execute agent command with bogus command.
        with self.assertRaises(BadRequest):
            cmd = AgentCommand(command='BOGUS_COMMAND')
            retval = self.instrument_agent_client.execute_agent(cmd)


        # Can't go active in unitialized state.
        # Status 660 is state error.
        with self.assertRaises(Conflict):
            cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
            retval = self.instrument_agent_client.execute_agent(cmd)


        # Try to execute the resource, wrong state.
        with self.assertRaises(BadRequest):
            cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
            retval = self.instrument_agent_client.execute_agent(cmd)


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

        # OK, I can do this now.
        cmd = AgentCommand(command=SBE37ProtocolEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)
        self.assertSampleDict(reply.result)

        # 404 unknown agent command.
        with self.assertRaises(BadRequest):
            cmd = AgentCommand(command='kiss_edward')
            reply = self.instrument_agent_client.execute_agent(cmd)


        '''
        @todo this needs to be re-enabled eventually
        # 670 unknown driver command.
        cmd = AgentCommand(command='acquire_sample_please')
        retval = self.instrument_agent_client.execute(cmd)
        log.debug("retval = " + str(retval))

        # the return value will likely be changed in the future to return
        # to being 670... for now, lets make it work.
        #self.assertEqual(retval.status, 670)
        self.assertEqual(retval.status, -1)

        try:
            reply = self.instrument_agent_client.get_param('1234')
        except Exception as e:
            log.debug("InstrumentParameterException ERROR = " + str(e))

        #with self.assertRaises(XXXXXXXXXXXXXXXXXXXXXXXX):
        #    reply = self.instrument_agent_client.get_param('1234')

        # 630 Parameter error.
        #with self.assertRaises(InstParameterError):
        #    reply = self.instrument_agent_client.get_param('bogus bogus')

        cmd = AgentCommand(command='reset')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_agent_state')
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)
        '''
        pass
