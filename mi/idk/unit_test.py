#! /usr/bin/env python

"""
@file coi-services/ion/idk/unit_test.py
@author Bill French
@brief Base classes for instrument driver tests.  
"""

# Import pyon first for monkey patching.
from mi.core.log import get_logger ; log = get_logger()

import re
import os
import unittest
from sets import Set

import gevent
import json
from pyon.util.int_test import IonIntegrationTestCase
from ion.agents.port.port_agent_process import PortAgentProcessType

from ion.agents.instrument.driver_process import DriverProcess, DriverProcessType

from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.common import Singleton
from mi.idk.instrument_agent_client import InstrumentAgentClient
from mi.idk.instrument_agent_client import InstrumentAgentDataSubscribers
from mi.idk.instrument_agent_client import InstrumentAgentEventSubscribers


from mi.idk.exceptions import TestNotInitialized
from mi.idk.exceptions import TestNoCommConfig
from mi.core.exceptions import InstrumentException

from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.instrument_driver import DriverAsyncEvent

from interface.objects import AgentCommand

from mi.core.log import get_logger ; log = get_logger()

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from ion.agents.instrument.common import InstErrorCode
from mi.core.instrument.instrument_driver import DriverConnectionState

from ion.agents.port.port_agent_process import PortAgentProcess

from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

class InstrumentDriverTestConfig(Singleton):
    """
    Singleton driver test config object.
    """
    driver_module  = None
    driver_class   = None

    working_dir    = "/tmp/" # requires trailing / or it messes up the path. should fix.

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

    @classmethod
    def comm_config_file(cls):
        """
        @brief Return the path the the driver comm config yaml file.
        @return if comm_config.yml exists return the full path
        """
        repo_dir = Config().get('working_repo')
        driver_path = cls.test_config.driver_module
        p = re.compile('\.')
        driver_path = p.sub('/', driver_path)
        abs_path = "%s/%s/%s" % (repo_dir, os.path.dirname(driver_path), CommConfig.config_filename())
        
        log.debug(abs_path)
        return abs_path

    @classmethod
    def get_comm_config(cls):
        """
        @brief Create the comm config object by reading the comm_config.yml file.
        """
        log.info("get comm config")
        config_file = cls.comm_config_file()
        
        log.debug( " -- reading comm config from: %s" % config_file )
        if not os.path.exists(config_file):
            raise TestNoCommConfig(msg="Missing comm config.  Try running start_driver or switch_driver")
        
        return CommConfig.get_config_from_file(config_file)
        

    @classmethod
    def init_port_agent(cls):
        """
        @brief Launch the driver process and driver client.  This is used in the
        integration and qualification tests.  The port agent abstracts the physical
        interface with the instrument.
        @retval return the pid to the logger process
        """
        log.info("Startup Port Agent")

        comm_config = cls.get_comm_config()

        config = {
            'device_addr' : comm_config.device_addr,
            'device_port' : comm_config.device_port,

            'command_port': comm_config.command_port,
            'data_port': comm_config.data_port,

            'process_type': PortAgentProcessType.UNIX,
            'log_level': 5,
        }

        port_agent = PortAgentProcess.launch_process(config, timeout = 60,
            test_mode = True)

        port = port_agent.get_data_port()
        pid  = port_agent.get_pid()

        log.info('Started port agent pid %s listening at port %s' % (pid, port))

        cls.test_config.port_agent = port_agent
        return port

    @classmethod
    def stop_port_agent(cls):
        """
        Stop the port agent.
        """
        log.info("Stop port agent: cls=%s" %cls)
        if cls.test_config.port_agent:
            log.debug("found port agent, now stop it")
            cls.test_config.port_agent.stop()

    
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
        port = self.port_agent.get_data_port()
        return {
            'addr': 'localhost',
            'port': port
        }


class InstrumentDriverUnitTestCase(InstrumentDriverTestCase):
    """
    Base class for instrument driver unit tests
    """
    @classmethod
    def setUpClass(cls):
        cls.init_port_agent()

    @classmethod
    def tearDownClass(cls):
        cls.stop_port_agent()

    def compare_parsed_data_particle(self, particle_type, raw_input, happy_structure):
        """
        Compare a data particle created with the raw input string to the structure
        that should be generated.
        
        @param The data particle class to create
        @param raw_input The input string that is instrument-specific
        @param happy_structure The structure that should result from parsing the
            raw input during DataParticle creation
        """
        port_timestamp = happy_structure[DataParticleKey.PORT_TIMESTAMP]
        if DataParticleKey.INTERNAL_TIMESTAMP in happy_structure:
            internal_timestamp = happy_structure[DataParticleKey.INTERNAL_TIMESTAMP]        
            test_particle = particle_type(raw_input, port_timestamp=port_timestamp,
                                          internal_timestamp=internal_timestamp)
        else:
            test_particle = particle_type(raw_input, port_timestamp=port_timestamp)
            
        parsed_result = test_particle.generate_parsed()
        decoded_parsed = json.loads(parsed_result)
        
        driver_time = decoded_parsed[DataParticleKey.DRIVER_TIMESTAMP]
        happy_structure[DataParticleKey.DRIVER_TIMESTAMP] = driver_time
        
        # run it through json so unicode and everything lines up
        standard = json.dumps(happy_structure, sort_keys=True)

        self.assertEqual(parsed_result, standard)
    

class InstrumentDriverIntegrationTestCase(InstrumentDriverTestCase):   # Must inherit from here to get _start_container
    @classmethod
    def setUpClass(cls):
        cls.init_port_agent()

    @classmethod
    def tearDownClass(cls):
        cls.stop_port_agent()

    def setUp(self):
        """
        @brief Setup test cases.
        """
        InstrumentDriverTestCase.setUp(self)
        self.port_agent = self.test_config.port_agent

        log.debug("InstrumentDriverIntegrationTestCase setUp")
        self.init_driver_process_client()

    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverIntegrationTestCase tearDown")
        self.stop_driver_process_client()

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
        reply = self.driver_client.cmd_dvr('process_echo')
        self.assert_(reply.startswith('ping from resource ppid:'))

        reply = self.driver_client.cmd_dvr('driver_ping', 'foo')
        self.assert_(reply.startswith('driver_ping: foo'))

        # Test the driver is in state unconfigured.
        # TODO: Add this test back in after driver code is merged from coi-services
        #state = self.driver_client.cmd_dvr('get_current_state')
        #self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
                
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


class InstrumentDriverQualificationTestCase(InstrumentDriverTestCase):

    @classmethod
    def setUpClass(cls):
        cls.init_port_agent()

    @classmethod
    def tearDownClass(cls):
        cls.stop_port_agent()

    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("InstrumentDriverQualificationTestCase setUp")

        InstrumentDriverTestCase.setUp(self)

        self.port_agent = self.test_config.port_agent

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
        InstrumentDriverTestCase.tearDown(self)

    def test_common_qualification(self):
        self.assertTrue(1)

    # FIXED
    def test_instrument_agent_common_state_model_lifecycle(self):
        """
        @brief Test agent state transitions.
               This test verifies that the instrument agent can
               properly command the instrument through the following states.
        @todo  Once direct access settles down and works again, re-enable direct access.

                COMMANDS TESTED
                *ResourceAgentEvent.INITIALIZE
                *ResourceAgentEvent.RESET
                *ResourceAgentEvent.GO_ACTIVE
                *ResourceAgentEvent.RUN
                *ResourceAgentEvent.PAUSE
                *ResourceAgentEvent.RESUME
                *ResourceAgentEvent.GO_COMMAND
                *ResourceAgentEvent.GO_DIRECT_ACCESS
                *ResourceAgentEvent.GO_INACTIVE
                *ResourceAgentEvent.PING_RESOURCE
                *ResourceAgentEvent.CLEAR

                COMMANDS NOT TESTED
                * ResourceAgentEvent.GET_RESOURCE_STATE
                * ResourceAgentEvent.GET_RESOURCE
                * ResourceAgentEvent.SET_RESOURCE
                * ResourceAgentEvent.EXECUTE_RESOURCE

                STATES ACHIEVED:
                * ResourceAgentState.UNINITIALIZED
                * ResourceAgentState.INACTIVE
                * ResourceAgentState.IDLE'
                * ResourceAgentState.STOPPED
                * ResourceAgentState.COMMAND
                * ResourceAgentState.DIRECT_ACCESS

                STATES NOT ACHIEVED:
                * ResourceAgentState.STREAMING
                * ResourceAgentState.TEST
                * ResourceAgentState.CALIBRATE
                * ResourceAgentState.BUSY
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

        cmd = AgentCommand(command=ResourceAgentEvent.GO_INACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        # Works but doesnt return anything useful when i tried.
        #cmd = AgentCommand(command=ResourceAgentEvent.GET_RESOURCE_STATE)
        #retval = self.instrument_agent_client.execute_agent(cmd)
        #log.debug("======================== " + str(retval))

        # works!
        retval = self.instrument_agent_client.ping_resource()
        #log.debug("1======================== " + str(retval))
        retval = self.instrument_agent_client.ping_agent()
        #log.debug("2======================== " + str(retval))

        cmd = AgentCommand(command=ResourceAgentEvent.PING_RESOURCE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.assertTrue("ping from resource ppid" in retval.result)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
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

        cmd = AgentCommand(command=ResourceAgentEvent.PAUSE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STOPPED)

        cmd = AgentCommand(command=ResourceAgentEvent.RESUME)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.CLEAR)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            #kwargs={'session_type': DirectAccessTypes.telnet,
            kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        # assert it is as long as expected 4149CB23-AF1D-43DF-8688-DDCD2B8E435E
        self.assertTrue(36 == len(retval.result['token']))

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

    # FIXED
    def test_instrument_agent_to_instrument_driver_connectivity(self):
        """
        @brief This test verifies that the instrument agent can
               talk to the instrument driver.

               The intent of this is to be a ping to the driver
               layer.
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


        retval = self.instrument_agent_client.ping_resource()
        log.debug("RETVAL = " + str(type(retval)))
        self.assertTrue("ping from resource ppid" in retval)
        self.assertTrue("time:" in retval)

        retval = self.instrument_agent_client.ping_agent()
        log.debug("RETVAL = " + str(type(retval)))
        self.assertTrue("ping from InstrumentAgent" in retval)
        self.assertTrue("time:" in retval)


        cmd = AgentCommand(command=ResourceAgentEvent.GO_INACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)



    def test_instrument_error_code_enum(self):
        """
        @brief check InstErrorCode for consistency
        @todo did InstErrorCode become redundant in the last refactor?
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

    # FIXED
    def test_resource_agent_event_enum(self):

        self.assertTrue(self.check_for_reused_values(ResourceAgentEvent))

    # FIXED
    def test_resource_agent_state_enum(self):

        self.assertTrue(self.check_for_reused_values(ResourceAgentState))


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
        self.event_subscribers.events_received = []

        expected_events = [
            'AgentState=RESOURCE_AGENT_STATE_UNINITIALIZED',
            'AgentState=RESOURCE_AGENT_STATE_INACTIVE',
            'AgentCommand=RESOURCE_AGENT_EVENT_INITIALIZE',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNKNOWN',
            'ResourceConfig',
            'ResourceState=DRIVER_STATE_COMMAND',
            'AgentState=RESOURCE_AGENT_STATE_IDLE',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_ACTIVE',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNCONFIGURED',
            'AgentState=RESOURCE_AGENT_STATE_INACTIVE',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_INACTIVE',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNKNOWN',
            'ResourceConfig',
            'ResourceState=DRIVER_STATE_COMMAND',
            'AgentState=RESOURCE_AGENT_STATE_IDLE',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_ACTIVE',
            'AgentCommand=RESOURCE_AGENT_PING_RESOURCE',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_RUN',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNCONFIGURED',
            'AgentState=RESOURCE_AGENT_STATE_UNINITIALIZED',
            'AgentCommand=RESOURCE_AGENT_EVENT_RESET',
            'AgentState=RESOURCE_AGENT_STATE_INACTIVE',
            'AgentCommand=RESOURCE_AGENT_EVENT_INITIALIZE',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNKNOWN',
            'AgentState=RESOURCE_AGENT_STATE_IDLE',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_ACTIVE',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_RUN',
            'ResourceConfig',
            'ResourceState=DRIVER_STATE_COMMAND',
            'AgentState=RESOURCE_AGENT_STATE_STOPPED',
            'AgentCommand=RESOURCE_AGENT_EVENT_PAUSE',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_RESUME',
            'AgentState=RESOURCE_AGENT_STATE_IDLE',
            'AgentCommand=RESOURCE_AGENT_EVENT_CLEAR',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_RUN',
            'AgentState=RESOUCE_AGENT_STATE_DIRECT_ACCESS',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_DIRECT_ACCESS',
            'ResourceState=DRIVER_STATE_DIRECT_ACCESS',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_COMMAND',
            'ResourceState=DRIVER_STATE_COMMAND',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNCONFIGURED',
            'AgentState=RESOURCE_AGENT_STATE_UNINITIALIZED',
            'AgentCommand=RESOURCE_AGENT_EVENT_RESET'
        ]


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

        cmd = AgentCommand(command=ResourceAgentEvent.GO_INACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        # Works but doesnt return anything useful when i tried.
        #cmd = AgentCommand(command=ResourceAgentEvent.GET_RESOURCE_STATE)
        #retval = self.instrument_agent_client.execute_agent(cmd)
        #log.debug("======================== " + str(retval))

        # works!
        retval = self.instrument_agent_client.ping_resource()
        #log.debug("1======================== " + str(retval))
        retval = self.instrument_agent_client.ping_agent()
        #log.debug("2======================== " + str(retval))

        cmd = AgentCommand(command=ResourceAgentEvent.PING_RESOURCE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.assertTrue("ping from resource ppid" in retval.result)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
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

        cmd = AgentCommand(command=ResourceAgentEvent.PAUSE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STOPPED)

        cmd = AgentCommand(command=ResourceAgentEvent.RESUME)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.CLEAR)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            #kwargs={'session_type': DirectAccessTypes.telnet,
            kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        # assert it is as long as expected 4149CB23-AF1D-43DF-8688-DDCD2B8E435E
        self.assertTrue(36 == len(retval.result['token']))

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)


        #
        # Refactor changed it so no description is ever present.
        # go with state instead i guess...
        #
        raw_events = []
        for x in self.event_subscribers.events_received:
            if str(type(x)) == "<class 'interface.objects.ResourceAgentCommandEvent'>":
                log.warn(str(type(x)) + " ********************* " + str(x.execute_command))
                raw_events.append("AgentCommand=" + str(x.execute_command))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentResourceStateEvent'>":
                log.warn(str(type(x)) + " ********************* " + str(x.state))
                raw_events.append("ResourceState=" + str(x.state))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentStateEvent'>":
                log.warn(str(type(x)) + " ********************* " + str(x.state))
                raw_events.append("AgentState=" + str(x.state))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentResourceConfigEvent'>":
                log.warn(str(type(x)) + " ********************* ")
                raw_events.append("ResourceConfig")
            else:
                log.warn(str(type(x)) + " ********************* " + str(x))

        for x in sorted(raw_events):
            log.debug(str(x) + " ?in (expected_events) = " + str(x in expected_events))
            self.assertTrue(x in expected_events)

        for x in sorted(expected_events):
            log.debug(str(x) + " ?in (raw_events) = " + str(x in raw_events))
            self.assertTrue(x in raw_events)

        # assert we got the expected number of events
        num_expected = len(self.de_dupe(expected_events))
        num_actual = len(self.de_dupe(raw_events))
        self.assertTrue(num_actual == num_expected)

        pass


    def test_instrument_driver_to_physical_instrument_interoperability(self):
        """
        @Brief this test is the integreation test test_connect
               but run through the agent.

               On a seabird sbe37 this results in a ds and dc command being sent.
        """

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

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

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)
