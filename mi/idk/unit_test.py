#! /usr/bin/env python

"""
@file coi-services/ion/idk/unit_test.py
@author Bill French
@brief Base classes for instrument driver tests.  
"""

# Import pyon first for monkey patching.
from pyon.public import log

import re
import os
import time

from os.path import basename

import gevent
from gevent import spawn
from gevent.event import AsyncResult
import subprocess

from pyon.container.cc import Container
from pyon.util.int_test import IonIntegrationTestCase
from pyon.util.context import LocalContextMixin

from mi.core.instrument.zmq_driver_client import ZmqDriverClient
from mi.core.instrument.zmq_driver_process import ZmqDriverProcess
from ion.agents.port.logger_process import EthernetDeviceLogger

from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.common import Singleton

from mi.idk.exceptions import TestNotInitialized
from mi.idk.exceptions import TestNoCommConfig
from mi.idk.exceptions import TestNoDeployFile
from mi.idk.exceptions import PortAgentTimeout
from mi.idk.exceptions import MissingConfig
from mi.idk.exceptions import MissingExecutable
from mi.idk.exceptions import FailedToLaunch
from mi.core.exceptions import InstrumentException

from mi.core.instrument.instrument_driver import DriverAsyncEvent

from interface.objects import AgentCommand
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient
from pyon.public import StreamSubscriberRegistrar
from pyon.event.event import EventSubscriber, EventPublisher

from mi.core.logger import Log




class InstrumentDriverTestConfig(Singleton):
    """
    Singleton driver test config object.
    """
    driver_module  = None
    driver_class   = None
    working_dir    = "/tmp"
    delimeter      = ['<<','>>']
    logger_timeout = 15

    instrument_agent_resource_id = None
    instrument_agent_name = None
    instrument_agent_module = 'ion.agents.instrument.instrument_agent'
    instrument_agent_class = 'InstrumentAgent'
    instrument_agent_packet_config = None
    instrument_agent_stream_encoding = 'ION R2'
    instrument_agent_stream_definition = None
    
    container_deploy_file = 'res/deploy/r2lca.yml'
    
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
        
        self.initialized = True
    

class InstrumentDriverTestCase(IonIntegrationTestCase):
    """
    Base class for instrument driver tests
    """
    
    # configuration singleton
    _test_config = InstrumentDriverTestConfig()
    
    @classmethod
    def initialize(cls, *args, **kwargs):
        """
        Initialize the test_configuration singleton
        """
        cls._test_config.initialize(*args,**kwargs)
    
    # Port agent process object.
    port_agent = None
    
    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("InstrumentDriverTestCase setUp")
        
        # Test to ensure we have initialized our test config
        if not self._test_config.initialized:
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
        driver_path = self._test_config.driver_module
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
                                                              self._test_config.working_dir,
                                                              self._test_config.delimeter,
                                                              this_pid)


        log.debug( " Port agent object created" )

        start_time = time.time()
        expire_time = start_time + int(self._test_config.logger_timeout)
        pid = self.port_agent.get_pid()
        while not pid:
            gevent.sleep(.1)
            pid = self.port_agent.get_pid()
            if time.time() > expire_time:
                log.error("!!!! Failed to start Port Agent !!!!")
                raise PortAgentTimeout()

        port = self.port_agent.get_port()

        start_time = time.time()
        expire_time = start_time + int(self._test_config.logger_timeout)
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
        
        this_pid = os.getpid()
        (dvr_proc, cmd_port, evt_port) = ZmqDriverProcess.launch_process(self._test_config.driver_module,
                                                                         self._test_config.driver_class,
                                                                         self._test_config.working_dir,
                                                                         this_pid)
        self.driver_process = dvr_proc
        log.info('Started driver process for %d %d %s %s' %
                 (cmd_port, evt_port, self._test_config.driver_module, self._test_config.driver_class))
        log.info('Driver process pid %d' % self.driver_process.pid)

        # Create driver client.
        self.driver_client = ZmqDriverClient('localhost', cmd_port, evt_port)
        log.info('Created driver client for %d %d %s %s' % (cmd_port,
            evt_port, self._test_config.driver_module, self._test_config.driver_class))

        # Start client messaging.
        self.driver_client.start_messaging(self.event_received)
        log.info('Driver messaging started.')
        gevent.sleep(.5)
    
    def stop_driver_process_client(self):
        """
        Stop the driver_process.
        """
        if self.driver_process:
            log.info('Stopping driver process pid %d' % self.driver_process.pid)
            if self.driver_client:
                self.driver_client.done()
                self.driver_process.wait()
                self.driver_client = None

            else:
                try:
                    log.info('Killing driver process.')
                    self.driver_process.kill()
                except OSError:
                    pass
            self.driver_process = None

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
        drv_pid = self.driver_process.pid
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
    class FakeProcess(LocalContextMixin):
        """
        A fake process used because the test case is not an ion process.
        """
        name = ''
        id=''
        process_type = ''


    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("InstrumentDriverQualificationTestCase setUp")
        
        self.container = Container.instance
        self.instrument_agent_client = self.container.instrument_agent_client

        InstrumentDriverTestCase.setUp(self)

        self.init_event_subscribers()
        self.init_data_subscribers()
        self.init_port_agent()

    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverQualificationTestCase tearDown")
        self.stop_port_agent()
        self.stop_data_subscribers()
        self.stop_event_subscribers()
        
        InstrumentDriverTestCase.tearDown(self)
        
    @classmethod
    def setupClass(cls):
        """
        @brief One time setup class
        """
        log.debug("InstrumentDriverQualificationTestCase setupClass")
        cls.init_rabbitmq_server()
        cls.init_couchdb()
        cls.init_instrument_agent()
        
        
    @classmethod
    def tearDownClass(cls):
        """
        @brief One time teardown class
        """
        
        log.debug("InstrumentDriverQualificationTestCase tear down class")
        #cls.stop_instrument_agent()
        #cls.stop_couchdb()
        #cls.stop_rabbitmq_server()

    @classmethod
    def init_instrument_agent(cls):
        """
        @brief Launch the instrument agent
        """
        log.info("Startup Instrument Agent")

        if not os.path.exists(cls._test_config.container_deploy_file):
            raise TestNoDeployFile(cls._test_config.container_deploy_file)
            
        # Derive a special test case so we can instantiate a testcase object.
        # then we can run start_container which initiallized the capability container
        class _StartContainer(InstrumentDriverTestCase):
            def runTest(self): pass
            
        testcase = _StartContainer()

        # Start container.
        testcase._start_container()
        container = testcase.container

        log.debug( "Capability container id: %s" % testcase.container.id )

        # Bring up services in a deploy file (no need to message)
        container.start_rel_from_url(testcase._test_config.container_deploy_file)
        return

        # Driver config
        driver_config = {
            'dvr_mod' : cls._test_config.driver_module,
            'dvr_cls' : cls._test_config.driver_class,
            'workdir' : cls._test_config.working_dir
        }
        
        # Create agent config.
        agent_config = {
            'driver_config' : driver_config,
            'stream_config' : testcase.stream_config,
            'agent'         : {'resource_id': testcase._test_config.instrument_agent_resource_id},
            'test_mode' : True  ## Enable a poison pill. If the spawning process dies
                                ## shutdown the daemon process.
        }

        # Start instrument agent.
        log.debug("TestInstrumentAgent.setup(): starting IA.")
        container_client = ContainerAgentClient(node=container.node,
                                                name=container.name)

        instrument_agent_pid = container_client.spawn_process(
                                                 name=cls._test_config.instrument_agent_name,
                                                 module=cls._test_config.instrument_agent_module,
                                                 cls=cls._test_config.instrument_agent_class,
                                                 config=agent_config)      
        log.info('Agent pid=%s.', instrument_agent_pid)
        
        ia_client = ResourceAgentClient(
            cls._test_config.instrument_agent_resource_id, process=FakeProcess())

        log.info('Got ia client %s.', str(ia_client))

        container.instrument_agent_client = ia_client
        
    @classmethod
    def stop_instrument_agent(cls):
        """
        @brief Stop the instrument agent
        """
        log.info("Stop the instrument agent")
        
        # Derive a special test case so we can instantiate a testcase object.
        # then we can run start_container which initiallized the capability container
        class _StartContainer(InstrumentDriverTestCase):
            def runTest(self): pass
            
        testcase = _StartContainer()
        testcase.container = Container.instance
        testcase._stop_container()

    def init_data_subscribers(self):
        """
        Data subscribers
        """
        # Create a pubsub client to create streams.
        pubsub_client = PubsubManagementServiceClient(node=self.container.node)

        # A callback for processing subscribed-to data.
        def consume_data(message, headers):
            log.info('Subscriber received data message: %s.', str(message))
            self.samples_received.append(message)
            if self.no_samples and self.no_samples == len(self.samples_received):
                self.async_data_result.set()

        # Create a stream subscriber registrar to create subscribers.
        subscriber_registrar = StreamSubscriberRegistrar(process=self.container,
            node=self.container.node)

        # Create streams and subscriptions for each stream named in driver.

        self.stream_config = {}
        self.data_subscribers = []
        for (stream_name, val) in self._test_config.instrument_agent_packet_config.iteritems():
            stream_def_id = pubsub_client.create_stream_definition(
                container=self._test_config.instrument_agent_stream_definition)
            stream_id = pubsub_client.create_stream(
                name=stream_name,
                stream_definition_id=stream_def_id,
                original=True,
                encoding=self._test_config.instrument_agent_stream_encoding)
            self.stream_config[stream_name] = stream_id

            # Create subscriptions for each stream.
            exchange_name = '%s_queue' % stream_name
            sub = subscriber_registrar.create_subscriber(exchange_name=exchange_name,
                callback=consume_data)
            self._listen(sub)
            self.data_subscribers.append(sub)
            query = StreamQuery(stream_ids=[stream_id])
            sub_id = pubsub_client.create_subscription(\
                query=query, exchange_name=exchange_name)
            pubsub_client.activate_subscription(sub_id)

    def stop_data_subscribers(self):
        """
        Stop the data subscribers on cleanup.
        """
        for sub in self.data_subscribers:
            sub.stop()
        for gl in self.data_greenlets:
            gl.kill()

    def init_event_subscribers(self):
        """
        Create subscribers for agent and driver events.
        """
        def consume_event(*args, **kwargs):
            log.info('Test recieved ION event: args=%s, kwargs=%s, event=%s.',
                str(args), str(kwargs), str(args[0]))
            self.events_received.append(args[0])
            if self.no_events and self.no_events == len(self.event_received):
                self.async_event_result.set()

        event_sub = EventSubscriber(event_type="DeviceEvent", callback=consume_event)
        event_sub.activate()
        self.event_subscribers.append(event_sub)

    def stop_event_subscribers(self):
        """
        Stop event subscribers on cleanup.
        """
        for sub in self.event_subscribers:
            sub.deactivate()

    @classmethod
    def init_couchdb(cls):
        """
        @brief Start the instrument agent
        """
        cmd = Config().get("couchdb")
        if not cmd:
            raise MissingConfig("couchdb")

        cls._run_process(cmd, '-b', cls._pid_filename("couchdb"), False)

    @classmethod
    def stop_couchdb(cls):
        """
        @brief Stop the instrument agent
        """
        pid = cls._read_pidfile(cls._pid_filename("couchdb"))

        if not pid:
            return

        cmd = Config().get("couchdb")
        if not cmd:
            raise MissingConfig("couchdb")

        cls._run_process(cmd, '-k')

        os.remove(cls._pid_filename("couchdb"))

    @classmethod
    def init_rabbitmq_server(cls):
        """
        @brief Start the instrument agent
        """
        cmd = Config().get("rabbitmq")
        if not cmd:
            raise MissingConfig("rabbitmq")

        cls._run_process(cmd, '', cls._pid_filename("rabbitmq"), False)

    @classmethod
    def stop_rabbitmq_server(cls):
        """
        @brief Stop the instrument agent
        """
        pid = cls._read_pidfile(cls._pid_filename("rabbitmq"))

        if not pid:
            return

        os.remove(cls._pid_filename("rabbitmq"))

    @classmethod
    def _run_process(cls, cmd, args = None, pidfile = None, raise_error = True):
        """
        @brief Start an external process and store the PID
        """
        if not args: args = ''
        name = basename(cmd)
        log.info("Start process: %s" % name)
        log.debug( "cmd: %s %s" % (cmd, args))

        if not os.path.exists(cmd):
            raise MissingExecutable(cmd)

        command_line = "%s %s" % (cmd, args);

        process = subprocess.Popen( command_line, shell=True)
        time.sleep(2)

        log.debug("Process pid: %d" % process.pid )
        if process.pid > 0:
            if pidfile:
                cls._write_pidfile(process.pid, pidfile)
        else:
            log.error( "Failed to launch application: %s " % command_line)
            if(raise_error):
                raise FailedToLaunch(command_line)


    @classmethod
    def _write_pidfile(cls, pid, pidfile):
        log.debug("write pid %d to file %s" % (pid, pidfile))
        outfile = open(pidfile, "w")
        outfile.write("%s" % pid)
        outfile.close()

    @classmethod
    def _read_pidfile(cls, pidfile):
        log.debug( "read pidfile %s" % pidfile)
        try:
            infile = open(pidfile, "r")
            pid = infile.read()
            infile.close()
        except IOError, e:
            return None

        return pid

    @classmethod
    def _pid_filename(cls, name):
        return "%s/%s_%d.pid" % (Config().get('tmp_dir'), name, os.getpid())


    def _listen(self, sub):
        """
        Pass in a subscriber here, this will make it listen in a background greenlet.
        """
        gl = spawn(sub.listen)
        self.data_greenlets.append(gl)
        sub.ready_event.wait(timeout=5)
        return gl


    def test_common_qualification(self):
        self.assertTrue(1)

    def test_instrument_agent_common_state_model_lifecycle(self):
        """
        @brief Test agent state transitions.
               This test verifies that the instrument agent can
               properly command the instrument through the following states.

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

        self._ia_client = self.instrument_agent_client
        cmd = AgentCommand(command='power_down')
        retval = self._ia_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.POWERED_DOWN)

        cmd = AgentCommand(command='power_up')
        retval = self._ia_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)

        cmd = AgentCommand(command='initialize')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        cmd = AgentCommand(command='go_active')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='go_inactive')
        retval = self._ia_client.execute_agent(cmd)

        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.INACTIVE)

        # ...and put it back to where it should be...
        cmd = AgentCommand(command='go_active')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)


        cmd = AgentCommand(command='run')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        # Begin streaming.
        cmd = AgentCommand(command='go_streaming')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.STREAMING)

        # Halt streaming.
        cmd = AgentCommand(command='go_observatory')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        # go direct access
        cmd = AgentCommand(command='go_direct_access')
        retval = self._ia_client.execute_agent(cmd)
        log.debug("5***** go_direct_access retval=" + str(retval.result))
        # 5***** go_direct_access retval={'token': '3AE880EF-27FE-4DE8-BFFF-C078640A3090', 'ip_address': 'REDACTED.local', 'port': 8000}

        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.DIRECT_ACCESS)

        # Halt DA.
        cmd = AgentCommand(command='go_observatory')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        cmd = AgentCommand(command='pause')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.STOPPED)

        cmd = AgentCommand(command='resume')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        cmd = AgentCommand(command='clear')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='run')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.OBSERVATORY)

        cmd = AgentCommand(command='pause')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.STOPPED)

        cmd = AgentCommand(command='clear')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.IDLE)

        cmd = AgentCommand(command='reset')
        retval = self._ia_client.execute_agent(cmd)
        cmd = AgentCommand(command='get_current_state')
        retval = self._ia_client.execute_agent(cmd)
        state = retval.result
        self.assertEqual(state, InstrumentAgentState.UNINITIALIZED)
