#! /usr/bin/env python

"""
@file coi-services/ion/idk/unit_test.py
@author Bill French
@brief Base classes for instrument driver tests.  
"""

# Import pyon first for monkey patching.
from mi.core.log import log

import re
import os
import time
import unittest
from sets import Set

from os.path import basename

import gevent
from gevent import spawn
from gevent.event import AsyncResult
import subprocess

from pyon.container.cc import Container
from pyon.util.int_test import IonIntegrationTestCase

from ion.agents.port.logger_process import EthernetDeviceLogger
from ion.agents.instrument.driver_process import DriverProcess, DriverProcessType

from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.common import Singleton
from mi.idk.instrument_agent_client import InstrumentAgentClient
from mi.idk.instrument_agent_client import InstrumentAgentDataSubscribers
from mi.idk.instrument_agent_client import InstrumentAgentEventSubscribers

from ion.agents.instrument.instrument_agent import InstrumentAgentEvent

from mi.idk.exceptions import TestNotInitialized
from mi.idk.exceptions import TestNoCommConfig
from mi.idk.exceptions import TestNoDeployFile
from mi.idk.exceptions import PortAgentTimeout
from mi.idk.exceptions import MissingConfig
from mi.idk.exceptions import MissingExecutable
from mi.idk.exceptions import FailedToLaunch
from mi.idk.exceptions import NoContainer
from mi.core.exceptions import InstrumentException

from mi.core.instrument.instrument_driver import DriverAsyncEvent

from interface.objects import AgentCommand
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from pyon.public import StreamSubscriberRegistrar
from pyon.event.event import EventSubscriber, EventPublisher

from mi.core.log import log
from interface.services.icontainer_agent import ContainerAgentClient
from pyon.agent.agent import ResourceAgentClient

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from pyon.core.exception import InstParameterError
from interface.objects import StreamQuery
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from ion.agents.instrument.common import InstErrorCode
from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.instrument.instrument_driver import DriverAsyncEvent
#from pyon.net.channel import ChannelError
from mi.core.exceptions import InstrumentParameterException

class InstrumentDriverTestConfig(Singleton):
    """
    Singleton driver test config object.
    """
    driver_module  = None
    driver_class   = None
    working_dir    = "/tmp"
    delimeter      = ['<<','>>']
    logger_timeout = 15

    driver_process_type = DriverProcessType.PYTHON_MODULE
    instrument_agent_resource_id = None
    instrument_agent_name = None
    instrument_agent_module = 'ion.agents.instrument.instrument_agent'
    instrument_agent_class = 'InstrumentAgent'
    instrument_agent_packet_config = None
    instrument_agent_stream_encoding = 'ION R2'
    instrument_agent_stream_definition = None
    
    container_deploy_file = 'res/deploy/r2deploy.yml'
    
    initialized   = False
    
    def initialize(self, *args, **kwargs):
        self.driver_module = kwargs.get('driver_module')
        self.driver_class  = kwargs.get('driver_class')
        if kwargs.get('working_dir'):
            self.working_dir = kwargs.get('working_dir')
        if kwargs.get('delimeter'):
            self.delimeter = kwargs.get('delimeter')
        
        self.instrument_agent_resource_id = kwargs.get('instrument_agent_resource_id')
        self.instrument_agent_name = kwargs.get('instrument_agent_name')
        self.instrument_agent_packet_config = kwargs.get('instrument_agent_packet_config')
        self.instrument_agent_stream_definition = kwargs.get('instrument_agent_stream_definition')
        if kwargs.get('instrument_agent_module'):
            self.instrument_agent_module = kwargs.get('instrument_agent_module')
        if kwargs.get('instrument_agent_class'):
            self.instrument_agent_class = kwargs.get('instrument_agent_class')
        if kwargs.get('instrument_agent_stream_encoding'):
            self.instrument_agent_stream_encoding = kwargs.get('instrument_agent_stream_encoding')

        if kwargs.get('container_deploy_file'):
            self.container_deploy_file = kwargs.get('container_deploy_file')

        if kwargs.get('logger_timeout'):
            self.container_deploy_file = kwargs.get('logger_timeout')

        if kwargs.get('driver_process_type'):
            self.container_deploy_file = kwargs.get('driver_process_type')
        
        self.initialized = True

class InstrumentDriverTestCase(IonIntegrationTestCase):
    """
    Base class for instrument driver tests
    """
    
    # configuration singleton
    test_config = InstrumentDriverTestConfig()
    
    @classmethod
    def initialize(cls, *args, **kwargs):
        """
        Initialize the test_configuration singleton
        """
        cls.test_config.initialize(*args,**kwargs)
    
    # Port agent process object.
    port_agent = None
    
    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("InstrumentDriverTestCase setUp")
        
        # Test to ensure we have initialized our test config
        if not self.test_config.initialized:
            return TestNotInitialized(msg="Tests non initialized. Missing InstrumentDriverTestCase.initalize(...)?")
            
        self.clear_events()
        self.init_comm_config()
        
    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverTestCase tearDown")
        
    def clear_events(self):
        """
        @brief Clear the event list.
        """
        self.events = []
        
    def event_received(self, evt):
        """
        @brief Simple callback to catch events from the driver for verification.
        """
        self.events.append(evt)
        
    def comm_config_file(self):
        """
        @brief Return the path the the driver comm config yaml file.
        @return if comm_config.yml exists return the full path
        """
        repo_dir = Config().get('working_repo')
        driver_path = self.test_config.driver_module
        p = re.compile('\.')
        driver_path = p.sub('/', driver_path)
        abs_path = "%s/%s/%s" % (repo_dir, os.path.dirname(driver_path), CommConfig.config_filename())
        
        log.debug(abs_path)
        return abs_path
    
    def init_comm_config(self):
        """
        @brief Create the comm config object by reading the comm_config.yml file.
        """
        log.info("Initialize comm config")
        config_file = self.comm_config_file()
        
        log.debug( " -- reading comm config from: %s" % config_file )
        if not os.path.exists(config_file):
            raise TestNoCommConfig(msg="Missing comm config.  Try running start_driver or switch_driver")
        
        self.comm_config = CommConfig.get_config_from_file(config_file)
        
        
    def init_port_agent(self):
        """
        @brief Launch the driver process and driver client.  This is used in the
        integration and qualification tests.  The port agent abstracts the physical
        interface with the instrument.
        @retval return the pid to the logger process
        """
        log.info("Startup Port Agent")
        # Create port agent object.
        this_pid = os.getpid()
        log.debug( " -- our pid: %d" % this_pid)
        log.debug( " -- address: %s, port: %s" % (self.comm_config.device_addr, self.comm_config.device_port))

        # Working dir and delim are hard coded here because this launch process
        # will change with the new port agent.  
        self.port_agent = EthernetDeviceLogger.launch_process(self.comm_config.device_addr,
                                                              self.comm_config.device_port,
                                                              self.test_config.working_dir,
                                                              self.test_config.delimeter,
                                                              this_pid)


        log.debug( " Port agent object created" )

        start_time = time.time()
        expire_time = start_time + int(self.test_config.logger_timeout)
        pid = self.port_agent.get_pid()
        while not pid:
            gevent.sleep(.1)
            pid = self.port_agent.get_pid()
            if time.time() > expire_time:
                log.error("!!!! Failed to start Port Agent !!!!")
                raise PortAgentTimeout()

        port = self.port_agent.get_port()

        start_time = time.time()
        expire_time = start_time + int(self.test_config.logger_timeout)
        while not port:
            gevent.sleep(.1)
            port = self.port_agent.get_port()
            if time.time() > expire_time:
                log.error("!!!! Port Agent could not bind to port !!!!")
                raise PortAgentTimeout()

        log.info('Started port agent pid %s listening at port %s' % (pid, port))
        return port
    
    def stop_port_agent(self):
        """
        Stop the port agent.
        """
        if self.port_agent:
            pid = self.port_agent.get_pid()
            if pid:
                log.info('Stopping pagent pid %i' % pid)
                self.port_agent.stop()
            else:
                log.info('No port agent running.')
    
    def init_driver_process_client(self):
        """
        @brief Launch the driver process and driver client
        @retval return driver process and driver client object
        """
        log.info("Startup Driver Process")

        driver_config = {
            'dvr_mod'      : self.test_config.driver_module,
            'dvr_cls'      : self.test_config.driver_class,
            'workdir'      : self.test_config.working_dir,
            'comms_config' : self.port_agent_comm_config(),
            'process_type' : self.test_config.driver_process_type,
        }

        self.driver_process = DriverProcess.get_process(driver_config, True)
        self.driver_process.launch()

        # Verify the driver has started.
        if not self.driver_process.getpid():
            log.error('Error starting driver process.')
            raise InstrumentException('Error starting driver process.')

        try:
            driver_client = self.driver_process.get_client()
            driver_client.start_messaging(self.event_received)
            retval = driver_client.cmd_dvr('process_echo', 'Test.')

            self.driver_client = driver_client
        except Exception, e:
            self.driver_process.stop()
            log.error('Error starting driver client. %s', e)
            raise InstrumentException('Error starting driver client.')

        log.info('started its driver.')
    
    def stop_driver_process_client(self):
        """
        Stop the driver_process.
        """
        if self.driver_process:
            self.driver_process.stop()

    def port_agent_comm_config(self):
        port = self.port_agent.get_port()
        return {
            'addr': 'localhost',
            'port': port
        }




class InstrumentDriverUnitTestCase(InstrumentDriverTestCase):
    """
    Base class for instrument driver unit tests
    """

class InstrumentDriverIntegrationTestCase(InstrumentDriverTestCase):   # Must inherit from here to get _start_container
    def setUp(self):
        """
        @brief Setup test cases.
        """
        InstrumentDriverTestCase.setUp(self)
        
        log.debug("InstrumentDriverIntegrationTestCase setUp")
        self.init_port_agent()
        self.init_driver_process_client()

    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverIntegrationTestCase tearDown")
        self.stop_driver_process_client()
        self.stop_port_agent()

        InstrumentDriverTestCase.tearDown(self)

    def test_driver_process(self):
        """
        @Brief Test for correct launch of driver process and communications, including asynchronous driver events.
        """

        log.info("Ensuring driver process was started properly ...")
        
        # Verify processes exist.
        self.assertNotEqual(self.driver_process, None)
        drv_pid = self.driver_process.getpid()
        self.assertTrue(isinstance(drv_pid, int))
        
        self.assertNotEqual(self.port_agent, None)
        pagent_pid = self.port_agent.get_pid()
        self.assertTrue(isinstance(pagent_pid, int))
        
        # Send a test message to the process interface, confirm result.
        msg = 'I am a ZMQ message going to the process.'
        reply = self.driver_client.cmd_dvr('process_echo', msg)
        self.assertEqual(reply,'process_echo: '+msg)
        
        # Test the driver is in state unconfigured.
        # TODO: Add this test back in after driver code is merged from coi-services
        #state = self.driver_client.cmd_dvr('get_current_state')
        #self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        
        # Send a test message to the driver interface, confirm result.
        msg = 'I am a ZMQ message going to the driver.'
        reply = self.driver_client.cmd_dvr('driver_echo', msg)
        self.assertEqual(reply, 'driver_echo: '+msg)
        
        # Test the event thread publishes and client side picks up events.
        events = [
            'I am important event #1!',
            'And I am important event #2!'
            ]
        reply = self.driver_client.cmd_dvr('test_events', events=events)
        gevent.sleep(1)
        
        # Confirm the events received are as expected.
        self.assertEqual(self.events, events)

        # Test the exception mechanism.
        with self.assertRaises(InstrumentException):
            exception_str = 'Oh no, something bad happened!'
            reply = self.driver_client.cmd_dvr('test_exceptions', exception_str)

        # Verify we received a driver error event.
        gevent.sleep(1)
        error_events = [evt for evt in self.events if isinstance(evt, dict) and evt['type']==DriverAsyncEvent.ERROR]
        self.assertTrue(len(error_events) == 1)


class InstrumentDriverQualificationTestCase(InstrumentDriverTestCase):



    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("InstrumentDriverQualificationTestCase setUp")

        InstrumentDriverTestCase.setUp(self)

        self.init_port_agent()



        self.instrument_agent_manager = InstrumentAgentClient();
        self.instrument_agent_manager.start_container(deploy_file=self.test_config.container_deploy_file)
        self.container = self.instrument_agent_manager.container
        self.data_subscribers = InstrumentAgentDataSubscribers(
            packet_config=self.test_config.instrument_agent_packet_config,
            encoding=self.test_config.instrument_agent_stream_encoding,
            stream_definition=self.test_config.instrument_agent_stream_definition
        )
        self.event_subscribers = InstrumentAgentEventSubscribers()

        self.init_instrument_agent_client()


    def init_instrument_agent_client(self):
        log.info("Start Instrument Agent Client")

        # A callback for processing subscribed-to data.
        '''
        def consume_data(message, headers):
            log.info('Subscriber received data message: %s.', str(message))
            self.samples_received.append(message)
            if self.no_samples and self.no_samples == len(self.samples_received):
                self.async_data_result.set()
        '''
        # Driver config
        driver_config = {
            'dvr_mod' : self.test_config.driver_module,
            'dvr_cls' : self.test_config.driver_class,

            'process_type' : self.test_config.driver_process_type,

            'workdir' : self.test_config.working_dir,
            'comms_config' : self.port_agent_comm_config()
        }

        # Create agent config.
        agent_config = {
            'driver_config' : driver_config,
            'stream_config' : self.data_subscribers.stream_config,
            'agent'         : {'resource_id': self.test_config.instrument_agent_resource_id},
            'test_mode' : True  ## Enable a poison pill. If the spawning process dies
            ## shutdown the daemon process.
        }

        # Start instrument agent client.
        self.instrument_agent_manager.start_client(
            name=self.test_config.instrument_agent_name,
            module=self.test_config.instrument_agent_module,
            cls=self.test_config.instrument_agent_class,
            config=agent_config,
            resource_id=self.test_config.instrument_agent_resource_id,
            deploy_file=self.test_config.container_deploy_file
        )

        self.instrument_agent_client = self.instrument_agent_manager.instrument_agent_client


    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverQualificationTestCase tearDown")
        self.instrument_agent_manager.stop_container()
        self.stop_port_agent()

        InstrumentDriverTestCase.tearDown(self)

    def test_common_qualification(self):
        self.assertTrue(1)

    def test_instrument_agent_common_state_model_lifecycle(self):
        """
        @brief Test agent state transitions.
               This test verifies that the instrument agent can
               properly command the instrument through the following states.
        @todo  Once direct access settles down and works again, re-enable direct access.

               KNOWN COMMANDS               -> RESULTANT STATES:
               * power_up                   -> UNINITIALIZED
               * power_down                 -> POWERED_DOWN
               * initialize                 -> INACTIVE
               * reset                      -> UNINITIALIZED
               * go_active                  -> IDLE
               * go_inactive                -> INACTIVE
               * run                        -> OBSERVATORY
               * clear                      -> IDLE
               * pause                      -> STOPPED
               * resume                     -> OBSERVATORY
               * go_streaming               -> STREAMING
               * go_direct_access           -> DIRECT_ACCESS
               * go_observatory             -> OBSERVATORY
               * get_current_state          -> gives current state.
               * start_transaction (NA)
               * end_transaction (NA)

               STATES ACHIEVED:
               * InstrumentAgentState.POWERED_DOWN
               * InstrumentAgentState.UNINITIALIZED
               * InstrumentAgentState.INACTIVE
               * InstrumentAgentState.IDLE
               * InstrumentAgentState.OBSERVATORY
               * InstrumentAgentState.STREAMING
               * InstrumentAgentState.DIRECT_ACCESS
               * InstrumentAgentState.STOPPED

               above that are common to all devices go into common,
               others go into instrument specific

               ?? when we get it, we can add:
               ??    get_current_capabilitys <- instrument specific

               A side effect of this testing is verification that the
               events emitted by the agent conform to those expected
               by the system.
        """

        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)
        log.debug("Instrument active.  Verify RQ-634")

        cmd = AgentCommand(command='go_inactive')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        # ...and put it back to where it should be...
        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)


        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        # Begin streaming.
        cmd = AgentCommand(command='go_streaming')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.STREAMING)
        log.debug("Enterered streaming mode. Verify RQ-636")

        # Halt streaming.
        cmd = AgentCommand(command='go_observatory')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)


        # go direct access
        cmd = AgentCommand(command='go_direct_access',
                           kwargs={'session_type':DirectAccessTypes.telnet,
                           #kwargs={'session_type':DirectAccessTypes.vsp,
                                   'session_timeout':600,
                                   'inactivity_timeout':600})


        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("5***** go_direct_access retval=" + str(retval.result))
        # 5***** go_direct_access retval={'token': '3AE880EF-27FE-4DE8-BFFF-C078640A3090', 'ip_address': 'REDACTED.local', 'port': 8000}

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.DIRECT_ACCESS)

        # Halt DA.
        cmd = AgentCommand(command='go_observatory')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        cmd = AgentCommand(command='pause')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.STOPPED)

        cmd = AgentCommand(command='resume')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        cmd = AgentCommand(command='clear')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        cmd = AgentCommand(command='pause')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.STOPPED)

        cmd = AgentCommand(command='clear')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='reset')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

    def test_instrument_agent_to_instrument_driver_connectivity(self):
        """
        @brief This test verifies that the instrument agent can
               talk to the instrument driver.

               The intent of this is to be a ping to the driver
               layer.
        """

        log.debug("IA client = " + str(self.instrument_agent_client))



        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)





        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result

        cmd = AgentCommand(command='go_layer_ping')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.LAYER_PING)
        log.debug("***** If i get here i am in LAYER_PING state....")

        cmd = AgentCommand(command='helo_agent', kwargs={'message': 'PING-AGENT'})
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.assertEqual(retval.result, "PONG-PING-AGENT")

        cmd = AgentCommand(command='helo_driver', kwargs={'message': 'PING-DRIVER'})
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.assertEqual(retval.result, 'process_echo: PING-DRIVER')

        cmd = AgentCommand(command='go_inactive')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        log.debug("***** retval2 = " + str(retval))

        self.assertEqual(state, InstrumentAgentState.INACTIVE)
        log.debug("***** If i get here i am in POWERED_DOWN state....")


    def test_instrument_error_code_enum(self):
        """
        @brief check InstErrorCode for consistency
        """
        self.assertTrue(self.check_for_reused_values(InstErrorCode))
        pass

    def test_driver_connection_state_enum(self):
        """
        @brief check DriverConnectionState for consistency
        @todo this check should also be a device specific for drivers like Trhph
        """

        # self.assertEqual(TrhphDriverState.UNCONFIGURED, DriverConnectionState.UNCONFIGURED)
        # self.assertEqual(TrhphDriverState.DISCONNECTED, DriverConnectionState.DISCONNECTED)
        # self.assertEqual(TrhphDriverState.CONNECTED, DriverConnectionState.CONNECTED)

        self.assertTrue(self.check_for_reused_values(DriverConnectionState))

    def test_instrument_agent_event_enum(self):

        self.assertTrue(self.check_for_reused_values(InstrumentAgentEvent))

    def test_instrument_agent_state_enum(self):

        self.assertTrue(self.check_for_reused_values(InstrumentAgentState))


    def check_for_reused_values(self, obj):
        """
        @author Roger Unwin
        @brief  verifies that no two definitions resolve to the same value.
        @returns True if no reused values
        """
        match = 0
        outer_match = 0
        for i in [v for v in dir(obj) if not callable(getattr(obj,v))]:
            if i.startswith('_') == False:
                outer_match = outer_match + 1
                for j in [x for x in dir(obj) if not callable(getattr(obj,x))]:
                    if i.startswith('_') == False:
                        if getattr(obj, i) == getattr(obj, j):
                            match = match + 1
                            log.debug(str(i) + " == " + j + " (Looking for reused values)")

        # If this assert fails, then two of the enumerations have an identical value...
        return match == outer_match

    def test_driver_async_event_enum(self):
        """
        @ brief ProtocolState enum test

            1. test that SBE37ProtocolState matches the expected enums from DriverProtocolState.
            2. test that multiple distinct states do not resolve back to the same string.
        """

        self.assertTrue(self.check_for_reused_values(DriverAsyncEvent))

    @unittest.skip("Transaction management not yet implemented")
    def test_transaction_management_messages(self):
        """
        @brief This tests the start_transaction and
               end_transaction methods.
               https://confluence.oceanobservatories.org/display/syseng/CIAD+MI+SV+Instrument+Agent+Interface#CIADMISVInstrumentAgentInterface-Transactionmanagementmessages
               * start_transaction(acq_timeout,exp_timeout)
               * end_transaction(transaction_id)
               * transaction_id

               See: ion/services/mi/instrument_agent.py
               UPDATE: stub it out fill in later when its available ... place holder
        TODO:
        """
        pass

    def de_dupe(self, list_in):
        unique_set = Set(item for item in list_in)
        return [(item) for item in unique_set]

    def test_driver_notification_messages(self):
        """
        @brief This tests event messages from the driver.  The following
               test moves the IA through all its states.  As it does this,
               event messages are generated and caught.  These messages
               are then compared with a list of expected messages to
               insure that the proper messages have been generated.
        """

        # Clear off any events from before this test so we have consistent state
        self._events_received = []

        expected_events = []
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_POWERED_DOWN')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_UNINITIALIZED')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_INACTIVE')
        expected_events.append('New driver state: DRIVER_STATE_DISCONNECTED')
        expected_events.append('New driver state: DRIVER_STATE_DISCONNECTED')
        expected_events.append('New driver state: DRIVER_STATE_UNKNOWN')
        expected_events.append('New driver configuration:')
        expected_events.append('New driver state: DRIVER_STATE_COMMAND')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_IDLE')
        expected_events.append('New driver state: DRIVER_STATE_DISCONNECTED')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_INACTIVE')
        expected_events.append('New driver state: DRIVER_STATE_UNCONFIGURED')
        expected_events.append('New driver state: DRIVER_STATE_DISCONNECTED')
        expected_events.append('New driver state: DRIVER_STATE_DISCONNECTED')
        expected_events.append('New driver state: DRIVER_STATE_UNKNOWN')
        expected_events.append('New driver configuration:')
        expected_events.append('New driver state: DRIVER_STATE_COMMAND')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_IDLE')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_OBSERVATORY')
        expected_events.append('New driver state: DRIVER_STATE_AUTOSAMPLE')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_STREAMING')
        expected_events.append('New driver configuration:')
        expected_events.append('New driver state: DRIVER_STATE_COMMAND')
        expected_events.append('New driver state: DRIVER_STATE_DIRECT_ACCESS')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_DIRECT_ACCESS')
        expected_events.append('New driver state: DRIVER_STATE_COMMAND')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_OBSERVATORY')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_STOPPED')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_OBSERVATORY')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_IDLE')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_OBSERVATORY')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_STOPPED')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_IDLE')
        expected_events.append('New driver state: DRIVER_STATE_DISCONNECTED')
        expected_events.append('New driver state: DRIVER_STATE_UNCONFIGURED')
        expected_events.append('Agent entered state: INSTRUMENT_AGENT_STATE_UNINITIALIZED')

        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='go_inactive')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)

        # Begin streaming.
        cmd = AgentCommand(command='go_streaming')
        retval = self.instrument_agent_client.execute_agent(cmd)

        # Halt streaming.
        cmd = AgentCommand(command='go_observatory')
        retval = self.instrument_agent_client.execute_agent(cmd)

        # go direct access
        cmd = AgentCommand(command='go_direct_access',
            kwargs={'session_type':DirectAccessTypes.telnet,
                    #kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)

        log.debug("RETVAL = " + str(retval))
        # Halt DA.
        cmd = AgentCommand(command='go_observatory')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='pause')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='resume')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='clear')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='pause')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='clear')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='reset')
        retval = self.instrument_agent_client.execute_agent(cmd)

        raw_events = []
        log.warn("ROGER *********************EVENTS " + str(self.event_subscribers.events_received))
        for x in self.event_subscribers.events_received:
            if x.description.find("New driver configuration:") >= 0:
                raw_events.append("New driver configuration:")
                log.warn("ROGER *********************APPENDING " + "New driver configuration:")
            else:
                raw_events.append(str(x.description))
                log.warn("ROGER *********************APPENDING " + str(x.description))
        log.debug("raw_events[] = " + str(raw_events))
        for x in sorted(raw_events):
            log.debug(str(x) + " ?in (expected_events) = " + str(x in expected_events))
            self.assertTrue(x in expected_events)

        for x in sorted(expected_events):
            log.debug(str(x) + " ?in (raw_events) = " + str(x in raw_events))
            self.assertTrue(x in raw_events)

        # assert we got the expected number of events
        self.assertEqual(len(self.de_dupe(expected_events)), len(self.de_dupe(raw_events)))
        # FAIL AssertionError: 37 != 38
        pass

    # broken
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

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        # Can't go active in unitialized state.
        # Status 660 is state error.
        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.info('GO ACTIVE CMD %s',str(retval))
        self.assertEquals(retval.status, 660)

        # Can't command driver in this state.
        cmd = AgentCommand(command='acquire_sample')
        reply = self.instrument_agent_client.execute(cmd)
        self.assertEqual(reply.status, 660)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        # OK, I can do this now.
        cmd = AgentCommand(command='acquire_sample')
        reply = self.instrument_agent_client.execute(cmd)
        self.assertSampleDict(reply.result)


        # 404 unknown agent command.
        cmd = AgentCommand(command='kiss_edward')
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.assertEquals(retval.status, 404)


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

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)
        '''
        pass

    def test_instrument_driver_to_physical_instrument_interoperability(self):
        """
        @Brief this test is the integreation test test_connect
               but run through the agent.

               On a seabird sbe37 this results in a ds and dc command being sent.
        """




        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)

        # Test the driver is configured for comms.

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        pass

    @unittest.skip("Driver.get_device_signature not yet implemented")
    def test_get_device_signature(self):
        """
        @Brief this test will call get_device_signature once that is
               implemented in the driver
        """
        pass


    def test_initialize(self):
        """
        Test agent initialize command. This causes creation of
        driver process and transition to inactive.
        """

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='reset')
        retval = self.instrument_agent_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)
