#!/usr/bin/env python

"""
@package mi.instrument.satlantic.isusv3.ooicore.test.test_driver
@file /Users/foley/sandbox/ooici/marine-integrations/mi/instrument/satlantic/isusv3/ooicore/driver.py
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
       $ bin/nosetests -s -v .../mi/instrument/satlantic/isusv3/ooicore
       $ bin/nosetests -s -v .../mi/instrument/satlantic/isusv3/ooicore -a UNIT
       $ bin/nosetests -s -v .../mi/instrument/satlantic/isusv3/ooicore -a INT
       $ bin/nosetests -s -v .../mi/instrument/satlantic/isusv3/ooicore -a QUAL
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

#from mock import Mock, call, DEFAULT

#from nose.plugins.attrib import attr

# Standard imports.
import time

# 3rd party imports.
from nose.plugins.attrib import attr
from mock import Mock

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentCommandException

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase


# MI logger
from mi.core.log import get_logger ; log = get_logger()

from mi.instrument.satlantic.isusv3.ooicore.driver import ooicoreInstrumentDriver
from mi.instrument.satlantic.isusv3.ooicore.driver import State
from mi.instrument.satlantic.isusv3.ooicore.driver import Parameter
from mi.instrument.satlantic.isusv3.ooicore.driver import PACKET_CONFIG
#from mi.instrument.satlantic.isusv3.ooicore.driver import Event
#from mi.instrument.satlantic.isusv3.ooicore.driver import Error
#from mi.instrument.satlantic.isusv3.ooicore.driver import Status
#from mi.instrument.satlantic.isusv3.ooicore.driver import Prompt
#from mi.instrument.satlantic.isusv3.ooicore.driver import Channel
#from mi.instrument.satlantic.isusv3.ooicore.driver import Command
#from mi.instrument.satlantic.isusv3.ooicore.driver import Capability
#from mi.instrument.satlantic.isusv3.ooicore.driver import MetadataParameter
#from mi.instrument.satlantic.isusv3.ooicore.driver import ooicoreInstrumentProtocol
#from mi.instrument.satlantic.isusv3.ooicore.driver import ooicoreInstrumentDriver

# ION imports.
from interface.objects import StreamQuery
from interface.services.dm.itransform_management_service import TransformManagementServiceClient
from interface.services.cei.iprocess_dispatcher_service import ProcessDispatcherServiceClient
from interface.services.icontainer_agent import ContainerAgentClient
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from pyon.public import StreamSubscriberRegistrar
from prototype.sci_data.stream_defs import ctd_stream_definition
from pyon.agent.agent import ResourceAgentClient
from interface.objects import AgentCommand
from pyon.util.int_test import IonIntegrationTestCase
from pyon.util.context import LocalContextMixin
from pyon.public import CFG
from pyon.event.event import EventSubscriber, EventPublisher

from pyon.core.exception import InstParameterError


# MI imports.
from ion.agents.port.logger_process import EthernetDeviceLogger
from ion.agents.instrument.instrument_agent import InstrumentAgentState
# next line should match the above line mostly
from mi.instrument.satlantic.isusv3.ooicore.driver import ooicoreParameter

## Initialize the test parameters
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.satlantic.isusv3.ooicore.driver',
    driver_class="ooicoreInstrumentDriver",

    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
)

# Used to validate param config retrieved from driver.
PARAMS = {
    Parameter.BAUDRATE: int,
    Parameter.DEPLOYMENT_COUNTER: int,
    Parameter.DEPLOYMENT_MODE: str
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
class ISUS3UnitTestCase(InstrumentDriverUnitTestCase):
    """Unit Test Container"""
    def reset_test_vars(self):
        self.raw_stream_received = False
        self.parsed_stream_received = False
        
    def test_event_callback(self, event):
        event_type = event['type']
        print str(event)
        if event_type == DriverAsyncEvent.SAMPLE:
            sample_value = event['value']
            stream_type = sample_value['stream_name']
            if stream_type == 'raw':
                self.raw_stream_received = True
            elif stream_type == 'parsed':
                self.parsed_stream_received = True
    
    def test_sample(self):
        # instantiate a mock object for port agent client
        # not sure doing that here is that helpful...

        """
        Currently passing mocked port agent client.  To test fragmentation,
        I should be able to call the got_data method directly.
        """
        """
        Create a mock port agent
        """
        mock_port_agent = Mock(spec=LoggerClient)

        """
        Instantiate the driver class directly (no driver client, no driver
        client, no zmq driver process, no driver process; just own the driver)
        """                  
        test_driver = ooicoreInstrumentDriver(self.test_event_callback)
        
        current_state = test_driver.get_current_state()
        print "DHE: DriverConnectionState: " + str(current_state)
        self.assertEqual(current_state, DriverConnectionState.UNCONFIGURED)
        
        """
        Now configure the driver with the mock_port_agent, verifying
        that the driver transitions to that state
        """
        config = {'mock_port_agent' : mock_port_agent}
        test_driver.configure(config = config)
        current_state = test_driver.get_current_state()
        print "DHE: DriverConnectionState: " + str(current_state)
        self.assertEqual(current_state, DriverConnectionState.DISCONNECTED)
        
        """
        Invoke the connect method of the driver: should connect to mock
        port agent.  Verify that the connection FSM transitions to CONNECTED,
        (which means that the FSM should now be reporting the ProtocolState).
        """
        test_driver.connect()
        current_state = test_driver.get_current_state()
        print "DHE: DriverConnectionState: " + str(current_state)
        self.assertEqual(current_state, DriverProtocolState.UNKNOWN)
        
        test_driver.execute_test_autosample()
        current_state = test_driver.get_current_state()
        print "DHE: DriverConnectionState: " + str(current_state)
        self.assertEqual(current_state, DriverProtocolState.AUTOSAMPLE)

        """
        - Reset test verification variables.
        - Construct a bogus stream
        - Pass to got_data()
        - Verify that raw and parsed streams have NOT been received
        """
        self.reset_test_vars()
        test_sample = "this is a bogus test\r\n"
        
        test_driver._protocol.got_data(test_sample)
        
        self.assertFalse(self.raw_stream_received)
        self.assertFalse(self.parsed_stream_received)
        
        """
        - Reset test verification variables.
        - Construct a sample dark full frame stream
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        self.reset_test_vars()
        test_sample = "SATNDF0196,2012219,18.770632,0.00,0.00,0.00,0.00,0.000000,24.38,23.31,18.53,255095,19.41,12.04," + \
            "4.95,11.57,1087.36,217.87,929.20,951.43,933,939,929,921,924,926,919,933,934,923,925,913,910,933,922,930," + \
            "914,918,919,925,930,919,929,926,927,921,949,922,932,924,929,931,929,943,921,938,921,914,933,913,920,929," + \
            "931,922,929,927,926,934,923,945,938,941,929,933,920,926,919,931,935,953,939,936,953,947,956,942,941,931," + \
            "935,938,951,943,921,936,934,949,933,933,938,953,949,939,942,944,951,929,935,935,945,949,938,937,948,952," + \
            "945,950,952,961,946,954,945,954,957,941,948,939,948,938,937,939,933,945,926,940,953,949,933,948,923,925," + \
            "941,954,947,955,965,951,965,937,949,939,929,955,958,954,970,967,973,976,979,985,993,970,966,973,988,966," + \
            "964,978,970,991,981,983,994,990,980,985,981,978,971,974,974,987,985,982,977,980,953,953,964,964,959,954," + \
            "947,966,950,963,961,967,964,977,973,974,979,977,984,966,960,957,948,970,968,980,967,979,984,970,967,979," + \
            "963,961,969,963,988,979,989,991,977,982,977,969,965,971,961,978,972,984,977,971,979,987,965,964,970,973," + \
            "949,938,945,953,959,951,957,976,952,953,953,949,949,951,945,961,945,953,949,956,970,974,973,957,948,954," + \
            "956,957,946,948,946,946,247\r\n"

        test_driver._protocol.got_data(test_sample)
        
        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)
        
        """
        - Reset test verification variables.
        - Construct a sample light full frame stream
        - Pass to got_data()
        - Verify that raw and parsed streams have been received
        """
        self.reset_test_vars()
        test_sample = "SATNLF0196,2012219,18.770960,82.83,52.29,-1201.21,2.99,0.000026,23.62,23.31,18.51,255096,19.43," + \
            "12.04,5.01,11.57,10434.65,248.53,940.20,951.43,933,937,951,939,941,939,933,947,938,931,931,926,937,958," + \
            "979,1070,1162,1321,1438,1543,1628,1716,1791,1879,1965,2086,2215,2382,2602,2827,3081,3369,3686,4032,4363," + \
            "4705,4994,5262,5473,5655,5786,5924,6024,6147,6301,6503,6748,7049,7415,7871,8389,9002,9721,10522,11440," + \
            "12425,13479,14601,15706,16805,17858,18786,19545,20131,20478,20574,20449,20146,19638,19031,18349,17653," + \
            "16981,16342,15767,15278,14862,14542,14279,14124,13996,13969,13985,14095,14245,14461,14742,15091,15464," + \
            "15903,16377,16869,17390,17861,18322,18762,19109,19370,19451,19449,19351,19083,18692,18225,17681,17097," + \
            "16509,15941,15362,14866,14421,14024,13707,13450,13227,13094,13019,12994,13019,13097,13223,13443,13662," + \
            "13991,14377,14809,15301,15861,16477,17141,17839,18549,19323,20085,20867,21642,22429,23163,23770,24420," + \
            "24959,25409,25784,26054,26208,26225,26190,26050,25792,25458,25041,24602,24096,23560,23040,22475,21925," + \
            "21401,20862,20404,19922,19509,19125,18769,18431,18135,17873,17621,17391,17142,16929,16709,16514,16324," + \
            "16167,16044,15923,15842,15737,15741,15725,15747,15789,15847,15897,15959,16037,16108,16178,16211,16246," + \
            "16289,16293,16383,16402,16437,16425,16428,16408,16387,16366,16315,16253,16154,16065,15943,15811,15638," + \
            "15444,15238,14999,14728,14439,14172,13849,13549,13239,12946,12631,12355,12069,11746,11398,11086,10761," + \
            "10486,10255,10023,9832,9661,9511,9356,9247,9171,9119,8986,8809,8656,8520,8411,8293,8196,8107,8026,8020," + \
            "7991,7960,7866,7829,7872,7882,7750,7361,6756,6098,6098,170\r\n"

        test_driver._protocol.got_data(test_sample)

        self.assertTrue(self.raw_stream_received)
        self.assertTrue(self.parsed_stream_received)
        


###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minmum requirement for ION ingestion)       #
###############################################################################

@attr('INT', group='mi')
class ISUS3IntTestCase(InstrumentDriverIntegrationTestCase):
    """Integration Test Container"""
    
    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """
        if all_params:
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))
            print '-----> DHE: keys: ' +  str(pd.keys())
            for (key, type_val) in PARAMS.iteritems():
                print key
                #self.assertTrue(isinstance(pd[key], type_val))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))
                self.assertTrue(isinstance(val, PARAMS[key]))


    def test_isus_config(self):
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
        log.info("test_connect test started")

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
        self.assertEqual(state, State.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover')

        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, State.COMMAND)

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
    def test_get(self):
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
        self.assertEqual(state, State.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, State.COMMAND)

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)

        # DHE TEMPTEMP
        # This should get the list of all parameters supported by the driver
        print "DHE: test_driver: reply to Parameter.ALL is: " + str(reply)

        # Now test getting a specific parameter
        params = [
            Parameter.BAUDRATE,
            Parameter.DEPLOYMENT_COUNTER,
            Parameter.DEPLOYMENT_MODE
        ]
        reply = self.driver_client.cmd_dvr('get', params)

        self.assertParamDict(reply, True)

        #
        # DHE: Added set testing here to compare with original gets
        # Remember the original subset.
        orig_params = reply


    #@unittest.skip('DHE: TESTTESTTEST')
    def test_set(self):
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
        self.assertEqual(state, State.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, State.COMMAND)

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)

        # DHE TEMPTEMP
        # This should get the list of all parameters supported by the driver
        print "DHE: test_driver: reply to Parameter.ALL is: " + str(reply)

        # Now test getting a specific parameter
        params = {
            #Parameter.BAUDRATE,
            Parameter.DEPLOYMENT_COUNTER : 4
        }
        reply = self.driver_client.cmd_dvr('set', params)

        # DHE TEMPTEMP
        #print "DHE: test_driver: reply: " + str(reply)

        #self.assertParamDict(reply, True)


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
        self.assertEqual(state, State.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, State.COMMAND)

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
        self.assertEqual(state, State.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, State.COMMAND)

        reply = self.driver_client.cmd_dvr('execute_start_autosample')

        # Test the driver is in autosample mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        self.assertEqual(state, State.AUTOSAMPLE)

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



###############################################################################
#                            HARDWARE TESTS                                   #
# Device specific hardware tests are for testing against actual device        #
# hardware when available                                                     #
###############################################################################

"""
Remaining tests:

* Parameter manipulation
** Get read/write parameter
** Set read/write parameter
** Get read-only parameter
** Set read-only parameter (and fail)
** Get direct-access-only parameter (and fail)
** Set direct-access-only parameter (and fail)
* Get status values
** Lamp odometer
** Disk info
** Build info
** Clock info
* Enter and exit all operating modes
* Menu navigation
* Get next operating mode (can be mocked?)
* File Commands:
** List commands
*** LP (list program file)
*** LC (list coefficient file)
*** LL (list log files)
*** LD (list data files)
** Output Commands
*** OE (output extinction coefficient file)
*** OW (output wavelength coefficient file)
*** OS (output schedule file)
*** OL (output log file)
*** OD (output Data files)
** Upload Commands (direct access only)?
*** US (upload schedule file)
*** UE (upload extinction coefficient file)
*** UP (upload program file)
** Erase Commands
*** EE (erase extinction coefficient file)
*** EL (erase log files)
*** ED (erase data files)
*** EAD (erase all data files)
* Commands
** Reboot
** Submit schedule?
** Submit calibration?
** Get calibrations?

"""

@attr('HARDWARE', group='mi')
class Testooicore_HW(InstrumentDriverTestCase):
    """Hardware Test Container"""
    
    def setUp(self):
        driver_module = 'mi.instrument.satlantic.isusv3.ooicore.driver'
        driver_class = 'OoiCoreInstrumentProtocol'
        # @todo Make this configurable
        
        # test_device_addr = "67.58.40.195"
        # test_device_port = 2001
        test_device_addr = self.comm_config.device_addr
        test_device_port = self.comm_config.device_port
        delim = ['<<', '>>']
        
        # Zmq parameters used by driver process and client.
        self.config_params = {'addr': 'localhost'}                
        self._support = DriverIntegrationTestSupport(driver_module,
                                                     driver_class,
                                                     test_device_addr,
                                                     test_device_port,
                                                     delim)
        # Clear the driver event list
        self._events = []
        self._pagent = None
        self._dvr_proc = None

        mi_logger.info("Starting port agent")
        self.config_params['port'] = self._support.start_pagent()
        self.addCleanup(self._support.stop_pagent)
        
        mi_logger.info("Starting Satlantic ISUSv3 driver")
        self._dvr_client = self._support.start_driver()
        self.addCleanup(self._support.stop_driver)
        
        self._dvr_client = self._support._dvr_client
        
        # we never get to the protocol if we never connect!
        self._connect()

    def _clean_up(self):
        # set back to command mode
        if self._dvr_client:
            try:
                reply = self._dvr_client.cmd_dvr('execute_break')
            except InstrumentStateError:
                # no biggie if we are already in cmd mode
                pass
            # clean up our parameters?
            #reply = self._dvr_client.cmd_dvr('set',
            #                                 {Parameter.MAXRATE:1},
            #                                  timeout=20)
            self._disconnect()
        
        self._support.stop_driver()

    def tearDown(self):
        super(Testooicore_HW, self).tearDown()
        self._clean_up()

    def _initialize(self):
        reply = self._dvr_client.cmd_dvr('execute_init_device')
        time.sleep(1)

    def _connect(self):
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.UNCONFIGURED, reply)
        configs = self.config_params
        reply = self._dvr_client.cmd_dvr('configure', configs)
        self.assertEqual(reply, None)
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.DISCONNECTED, reply)
        reply = self._dvr_client.cmd_dvr('connect')
        self.assertEqual(reply, None)
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverProtocolState.UNKNOWN, reply)

        self._initialize()
        
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(PARProtocolState.COMMAND_MODE, reply)

        time.sleep(1)

    def _disconnect(self):
        reply = self._dvr_client.cmd_dvr('disconnect')
        reply = self._dvr_client.cmd_dvr('get_current_state')
        self.assertEqual(DriverState.DISCONNECTED, reply)
        time.sleep(1)

    def test_connect_disconnect(self):
        """ Just a place holder for running just the basic setUp, teardown
        routines that handle connecting and disconnecting """
        pass
    
    def test_get_RW_param(self):
        """ Test getting a read-write parameter """
        reply = self._dvr_client.cmd_dvr('get', [Parameter.INITIAL_DELAY,
                                                 Parameter.STATUS_MESSSAGES])

    def test_get_RO_param(self):
        """ Test getting a read-only parameter """
        self._assert(False)

    def test_get_DA_param(self):
        """ Test getting a direct access parameter """
        self._assert(False)
        
    def test_range_params(self):
        """ Some parameters like the nitrate DAC range have min and max values
        set via one menu path (min first, max next). Make sure they can be
        set. This will involve checking some logic that a min or a max value
        can be set and returned to a prompt properly.
        """
        self._assert(False)
        
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################

@attr('QUAL', group='mi')
class ISUS3QualificationTestCase(InstrumentDriverQualificationTestCase):
    """Qualification Test Container"""
    
    # Qualification tests live in the base class.  This class is extended
    # here so that when running this test from 'nosetests' all tests
    # (UNIT, INT, and QUAL) are run.  
    pass

