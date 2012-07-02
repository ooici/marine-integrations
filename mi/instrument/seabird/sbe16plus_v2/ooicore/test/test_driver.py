#!/usr/bin/env python

"""
@package ion.services.mi.drivers.sbe16_plus_v2.test.test_sbe16_driver
@file ion/services/mi/drivers/sbe16_plus_v2/test_sbe16_driver.py
@author David Everett 
@brief Test cases for SBE16Driver
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

# Ensure the test class is monkey patched for gevent
from gevent import monkey; monkey.patch_all()
import gevent

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

from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import PACKET_CONFIG
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import SBE16Driver
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import SBE16ProtocolState
from mi.instrument.seabird.sbe16plus_v2.ooicore.driver import SBE16Parameter
from ion.agents.port.logger_process import EthernetDeviceLogger

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

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
DVR_CLS = 'SBE16Driver'

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
    SBE16Parameter.OUTPUTSAL : bool,
    SBE16Parameter.OUTPUTSV : bool,
    SBE16Parameter.NAVG : int,
    SBE16Parameter.SAMPLENUM : int,
    SBE16Parameter.INTERVAL : int,
    SBE16Parameter.TXREALTIME : bool,
    SBE16Parameter.SYNCMODE : bool,
    # DHE this doesn't show up in the status unless the
    # SYNCMODE is enabled.  Need to change the test to
    # test for SYNCMODE and if true test for SYNCWAIT
    #SBE16Parameter.SYNCWAIT : int,
    SBE16Parameter.TCALDATE : tuple,
    SBE16Parameter.TA0 : float,
    SBE16Parameter.TA1 : float,
    SBE16Parameter.TA2 : float,
    SBE16Parameter.TA3 : float,
    SBE16Parameter.CCALDATE : tuple,
    SBE16Parameter.CG : float,
    SBE16Parameter.CH : float,
    SBE16Parameter.CI : float,
    SBE16Parameter.CJ : float,
    SBE16Parameter.CTCOR : float,
    # Our SBE 16plus doesn't have a pressure sensor
    #SBE16Parameter.CPCOR : float,
    #SBE16Parameter.PCALDATE : tuple,
    #SBE16Parameter.PA0 : float,
    #SBE16Parameter.PA1 : float,
    #SBE16Parameter.PA2 : float,
    #SBE16Parameter.PTCA0 : float,
    #SBE16Parameter.PTCA1 : float,
    #SBE16Parameter.PTCA2 : float,
    #SBE16Parameter.PTCB0 : float,
    #SBE16Parameter.PTCB1 : float,
    #SBE16Parameter.PTCB2 : float,
    #SBE16Parameter.POFFSET : float,
    #SBE16Parameter.RCALDATE : tuple,
    #SBE16Parameter.RTCA0 : float,
    #SBE16Parameter.RTCA1 : float,
    #SBE16Parameter.RTCA2 : float
}


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
    pass

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
    
    def test_config(self):
        """
        Test to configure the driver process for device comms and transition
        to disconnected state.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver returned state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        
    def test_connect(self):
        """
        Test configuring and connecting to the device through the port
        agent. Discover device state.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        
    #@unittest.skip('DHE: TESTTESTTEST')
    def test_get_set(self):
        """
        Test device parameter access.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.UNKNOWN)
                
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get', SBE16Parameter.ALL)
        self.assertParamDict(reply, True)

        # Remember original configuration.
        orig_config = reply
        
        # Grab a subset of parameters.
        params = [
            SBE16Parameter.TA0,
            SBE16Parameter.INTERVAL,
            #SBE16Parameter.STORETIME,
            SBE16Parameter.TCALDATE
            ]
        reply = self.driver_client.cmd_dvr('get', params)
        self.assertParamDict(reply)        

        # Remember the original subset.
        orig_params = reply
        
        # Construct new parameters to set.
        old_date = orig_params[SBE16Parameter.TCALDATE]
        new_params = {
            SBE16Parameter.TA0 : orig_params[SBE16Parameter.TA0] * 1.2,
            SBE16Parameter.INTERVAL : orig_params[SBE16Parameter.INTERVAL] + 1,
            #SBE16Parameter.STORETIME : not orig_params[SBE16Parameter.STORETIME],
            SBE16Parameter.TCALDATE : (old_date[0], old_date[1], old_date[2] + 1)
        }

        # Set parameters and verify.
        reply = self.driver_client.cmd_dvr('set', new_params)
        reply = self.driver_client.cmd_dvr('get', params)
        self.assertParamVals(reply, new_params)
        
        # Restore original parameters and verify.
        reply = self.driver_client.cmd_dvr('set', orig_params)
        reply = self.driver_client.cmd_dvr('get', params)
        self.assertParamVals(reply, orig_params)

        # Retrieve the configuration and ensure it matches the original.
        # Remove samplenum as it is switched by autosample and storetime.
        reply = self.driver_client.cmd_dvr('get', SBE16Parameter.ALL)
        reply.pop('SAMPLENUM')
        orig_config.pop('SAMPLENUM')
        self.assertParamVals(reply, orig_config)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is disconnected.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)        
    
    #@unittest.skip('DHE: TESTTESTTEST')
    def test_poll(self):
        """
        Test sample polling commands and events.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.UNKNOWN)
                
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_acquire_sample')
        self.assertSampleDict(reply)
        
        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_acquire_sample')
        self.assertSampleDict(reply)

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_acquire_sample')
        self.assertSampleDict(reply)
        
        # Confirm that 3 samples arrived as published events.
        gevent.sleep(1)
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        self.assertEqual(len(sample_events), 3)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

    #@unittest.skip('DHE: TESTTESTTEST')
    def test_autosample(self):
        """
        Test autosample mode.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)
        
        # Make sure the device parameters are set to sample frequently and
        # to transmit.
        params = {
            SBE16Parameter.NAVG : 1,
            SBE16Parameter.INTERVAL : 10, # Our borrowed SBE16plus takes no less than 10
            SBE16Parameter.TXREALTIME : True
        }
        reply = self.driver_client.cmd_dvr('set', params)
        
        reply = self.driver_client.cmd_dvr('execute_start_autosample')

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.AUTOSAMPLE)
        
        # Wait for a few samples to roll in.
        #gevent.sleep(30)
        # DHE sleep long enough for a couple of samples
        gevent.sleep(40)
        
        # Return to command mode. Catch timeouts and retry if necessary.
        count = 0
        while True:
            try:
                reply = self.driver_client.cmd_dvr('execute_stop_autosample')
            
            except InstrumentTimeoutException:
                count += 1
                if count >= 5:
                    self.fail('Could not wakeup device to leave autosample mode.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)

        # Verify we received at least 2 samples.
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        self.assertTrue(len(sample_events) >= 2)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

    #@unittest.skip('Not supported by simulator and very long (> 5 min).')
    def test_test(self):
        """
        Test the hardware testing mode.
        """
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)

        start_time = time.time()
        reply = self.driver_client.cmd_dvr('execute_test')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.TEST)
        
        while state != SBE16ProtocolState.COMMAND:
            gevent.sleep(5)
            elapsed = time.time() - start_time
            log.info('Device testing %f seconds elapsed.' % elapsed)
            state = self.driver_client.cmd_dvr('get_current_state')

        # Verify we received the test result and it passed.
        test_results = [evt for evt in self.events if evt['type']==DriverAsyncEvent.TEST_RESULT]
        self.assertTrue(len(test_results) == 1)
        self.assertEqual(test_results[0]['value']['success'], 'Passed')

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

    def test_errors(self):
        """
        Test response to erroneous commands and parameters.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Assert for an unknown driver command.
        with self.assertRaises(InstrumentCommandException):
            reply = self.driver_client.cmd_dvr('bogus_command')

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_acquire_sample')

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
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_acquire_sample')

        reply = self.driver_client.cmd_dvr('connect')
                
        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.UNKNOWN)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_acquire_sample')
                
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_acquire_sample')
        self.assertSampleDict(reply)

        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('execute_stop_autosample')
        
        # Assert for a known command, invalid state.
        with self.assertRaises(InstrumentStateException):
            reply = self.driver_client.cmd_dvr('connect')

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get', SBE16Parameter.ALL)
        self.assertParamDict(reply, True)
        
        # Assert get fails without a parameter.
        with self.assertRaises(InstrumentParameterException):
            reply = self.driver_client.cmd_dvr('get')
            
        # Assert get fails without a bad parameter (not ALL or a list).
        with self.assertRaises(InstrumentParameterException):
            bogus_params = 'I am a bogus param list.'
            reply = self.driver_client.cmd_dvr('get', bogus_params)
            
        # Assert get fails without a bad parameter (not ALL or a list).
        #with self.assertRaises(InvalidParameterValueError):
        with self.assertRaises(InstrumentParameterException):
            bogus_params = [
                'a bogus parameter name',
                SBE16Parameter.INTERVAL,
                #SBE16Parameter.STORETIME,
                SBE16Parameter.TCALDATE
                ]
            reply = self.driver_client.cmd_dvr('get', bogus_params)        
        
        # Assert we cannot set a bogus parameter.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                'a bogus parameter name' : 'bogus value'
            }
            reply = self.driver_client.cmd_dvr('set', bogus_params)
            
        # Assert we cannot set a real parameter to a bogus value.
        with self.assertRaises(InstrumentParameterException):
            bogus_params = {
                SBE16Parameter.INTERVAL : 'bogus value'
            }
            reply = self.driver_client.cmd_dvr('set', bogus_params)
        
        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')
        
        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        
        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
    
    @unittest.skip('Not supported by simulator.')
    def test_discover_autosample(self):
        """
        Test the device can discover autosample mode.
        """
        
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)
        
        # Make sure the device parameters are set to sample frequently.
        params = {
            SBE16Parameter.NAVG : 1,
            SBE16Parameter.INTERVAL : 5
        }
        reply = self.driver_client.cmd_dvr('set', params)
        
        reply = self.driver_client.cmd_dvr('execute_start_autosample')

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.AUTOSAMPLE)
    
        # Let a sample or two come in.
        gevent.sleep(30)
    
        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        # Wait briefly before we restart the comms.
        gevent.sleep(10)
    
        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.UNKNOWN)

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
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.AUTOSAMPLE)

        # Let a sample or two come in.
        # This device takes awhile to begin transmitting again after you
        # prompt it in autosample mode.
        gevent.sleep(30)

        # Return to command mode. Catch timeouts and retry if necessary.
        count = 0
        while True:
            try:
                reply = self.driver_client.cmd_dvr('execute_stop_autosample')
            
            except InstrumentTimeoutException:
                count += 1
                if count >= 5:
                    self.fail('Could not wakeup device to leave autosample mode.')

            else:
                break

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, SBE16ProtocolState.COMMAND)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')
    
        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        
        

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

