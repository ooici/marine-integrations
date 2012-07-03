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

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState

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
from mi.core.log import log

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
    pass

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
        self.assertEqual(state, State.UNCONFIGURED_MODE)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover')

        # DHE THIS DOESN'T WORK
        # isusv3 driver doesn't have a discover handler that puts it
        # in command mode...
        # Test the driver is in command mode.
        #state = self.driver_client.cmd_dvr('get_current_state')
        #self.assertEqual(state, State.MENU_MODE)

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
        self.assertEqual(state, State.UNCONFIGURED_MODE)

        reply = self.driver_client.cmd_dvr('discover')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_current_state')
        # Currently using ROOT_MENU as "COMMAND" state
        #self.assertEqual(state, State.MENU_MODE)
        self.assertEqual(state, State.ROOT_MENU)

        # Get all device parameters. Confirm all expected keys are retrived
        # and have correct type.
        reply = self.driver_client.cmd_dvr('get', Parameter.ALL)

        # DHE TEMPTEMP
        # This should get the list of all parameters supported by the driver
        print "DHE: test_driver: reply to Parameter.ALL is: " + str(reply)

        # Now test getting a specific parameter
        params = [
            Parameter.BAUDRATE,
            Parameter.DEPLOYMENT_COUNTER
        ]
        reply = self.driver_client.cmd_dvr('get', params)

        # DHE TEMPTEMP
        #print "DHE: test_driver: reply: " + str(reply)

        #self.assertParamDict(reply, True)



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

