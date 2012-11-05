#! /usr/bin/env python

"""
@file coi-services/ion/idk/unit_test.py
@author Bill French
@brief Base classes for instrument driver tests.  
"""

from mock import patch
from pyon.core.bootstrap import CFG

import re
import os
import unittest
import socket
from sets import Set

# Set testing to false because the capability container tries to clear out
# couchdb if we are testing. Since we don't care about couchdb for the most
# part we can ignore this. See initialize_ion_int_tests() for implementation.
# If you DO care about couch content make sure you do a force_clean when needed.
from pyon.core import bootstrap
bootstrap.testing = False

# Import pyon first for monkey patching.
from mi.core.log import get_logger ; log = get_logger()

import gevent
import json
from pyon.util.int_test import IonIntegrationTestCase
from ion.agents.port.port_agent_process import PortAgentProcessType
from interface.objects import AgentCapability
from interface.objects import CapabilityType

from ion.agents.instrument.driver_process import DriverProcess, DriverProcessType

from mi.idk.util import convert_enum_to_dict
from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.common import Singleton
from mi.idk.instrument_agent_client import InstrumentAgentClient
from mi.idk.instrument_agent_client import InstrumentAgentDataSubscribers
from mi.idk.instrument_agent_client import InstrumentAgentEventSubscribers
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverEvent

from mi.idk.exceptions import TestNotInitialized
from mi.idk.exceptions import TestNoCommConfig
from mi.core.exceptions import InstrumentException
from mi.core.exceptions import InstrumentTimeoutException
from pyon.core.exception import Conflict

from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.tcp_client import TcpClient
from mi.core.common import BaseEnum

from interface.objects import AgentCommand

from mi.core.log import get_logger ; log = get_logger()

from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from ion.agents.instrument.common import InstErrorCode
from mi.core.instrument.instrument_driver import DriverConnectionState

from ion.agents.port.port_agent_process import PortAgentProcess

from pyon.agent.agent import ResourceAgentState

from pyon.agent.agent import ResourceAgentEvent

# Do not remove this import.  It is for package building.
from mi.core.instrument.zmq_driver_process import ZmqDriverProcess

GO_ACTIVE_TIMEOUT=60

class AgentCapabilityType(BaseEnum):
    AGENT_COMMAND = 'agent_command'
    AGENT_PARAMETER = 'agent_parameter'
    RESOURCE_COMMAND = 'resource_command'
    RESOURCE_INTERFACE = 'resource_interface'
    RESOURCE_PARAMETER = 'resource_parameter'

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
    instrument_agent_module = 'mi.idk.instrument_agent'
    instrument_agent_class = 'InstrumentAgent'
    instrument_agent_packet_config = None
    instrument_agent_stream_encoding = 'ION R2'
    instrument_agent_stream_definition = None

    driver_startup_config = {}

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

        if kwargs.get('driver_startup_config'):
            self.driver_startup_config = kwargs.get('driver_startup_config')

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
        

    def init_port_agent(self):
        """
        @brief Launch the driver process and driver client.  This is used in the
        integration and qualification tests.  The port agent abstracts the physical
        interface with the instrument.
        @retval return the pid to the logger process
        """
        if(self.port_agent):
            log.error("Port agent already initialized")
            return

        log.debug("Startup Port Agent")

        comm_config = self.get_comm_config()

        config = {
            'device_addr' : comm_config.device_addr,
            'device_port' : comm_config.device_port,

            'command_port': comm_config.command_port,
            'data_port': comm_config.data_port,

            'process_type': PortAgentProcessType.UNIX,
            'log_level': 5,
        }

        port_agent = PortAgentProcess.launch_process(config, timeout = 60, test_mode = True)

        port = port_agent.get_data_port()
        pid  = port_agent.get_pid()

        log.info('Started port agent pid %s listening at port %s' % (pid, port))

        self.addCleanup(self.stop_port_agent)
        self.port_agent = port_agent
        return port


    def stop_port_agent(self):
        """
        Stop the port agent.
        """
        log.info("Stop port agent")
        if self.port_agent:
            log.debug("found port agent, now stop it")
            self.port_agent.stop()

        self.port_agent = None

    
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
            'startup_config' : self.test_config.driver_startup_config
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
            log.debug("before 'process_echo'")
            retval = driver_client.cmd_dvr('process_echo', 'Test.') # data=? RU
            log.debug("after 'process_echo'")

            startup_config = driver_config.get('startup_config')
            retval = driver_client.cmd_dvr('set_init_params', startup_config)

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

    #####
    # Custom assert methods
    #####

    def assert_set_complete(self, subset, superset):
        """
        Assert that every item in subset is in superset
        """

        # use assertTrue here intentionally because it's easier to unit test
        # this method.
        if len(superset):
            self.assertTrue(len(subset) > 0)

        for item in subset:
            self.assertTrue(item in superset)

        # This added so the unit test can set a true flag.  If we have made it
        # this far we should pass the test.
        #self.assertTrue(True)

    def assert_enum_has_no_duplicates(self, obj):
        dic = convert_enum_to_dict(obj)
        occurances  = {}
        for k, v in dic.items():
            #v = tuple(v)
            occurances[v] = occurances.get(v,0) + 1

        for k in occurances:
            if occurances[k] > 1:
                log.error(str(obj) + " has ambigous duplicate values for '" + str(k) + "'")
                self.assertEqual(1, occurances[k])

    def assert_chunker_sample(self, chunker, sample):
        '''
        Verify the chunker can parse a sample that comes in a single string
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        chunker.add_chunk(sample)
        result = chunker.get_next_data()
        self.assertEqual(result, sample)

        result = chunker.get_next_data()
        self.assertEqual(result, None)


    def assert_chunker_fragmented_sample(self, chunker, sample):
        '''
        Verify the chunker can parse a sample that comes in fragmented
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        for c in sample:
            chunker.add_chunk(c)
            result = chunker.get_next_data()
            if(result): break

        self.assertEqual(result, sample)

        result = chunker.get_next_data()
        self.assertEqual(result, None)

    def assert_chunker_combined_sample(self, chunker, sample):
        '''
        Verify the chunker can parse a sample that comes in combined
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        chunker.add_chunk(sample + sample)

        result = chunker.get_next_data()
        self.assertEqual(result, sample)

        result = chunker.get_next_data()
        self.assertEqual(result, sample)

        result = chunker.get_next_data()
        self.assertEqual(result, None)

    def assert_chunker_sample_with_noise(self, chunker, sample):
        '''
        Verify the chunker can parse a sample with noise on the
        front or back of sample data
        @param chunker: Chunker to use to do the parsing
        @param sample: raw sample
        '''
        noise = "this is a bunch of noise to add to the sample\r\n"

        # Try a sample with noise in the front
        chunker.add_chunk(noise + sample)

        result = chunker.get_next_data()
        self.assertEqual(result, sample)

        result = chunker.get_next_data()
        self.assertEqual(result, None)

        # Now some noise in the back
        chunker.add_chunk(sample + noise)

        result = chunker.get_next_data()
        self.assertEqual(result, sample)

        result = chunker.get_next_data()
        self.assertEqual(result, None)

        # There should still be some noise in the buffer, make sure
        # we can still take a sample.
        chunker.add_chunk(sample + noise)

        result = chunker.get_next_data()
        self.assertEqual(result, sample)

        result = chunker.get_next_data()
        self.assertEqual(result, None)

class InstrumentDriverUnitTestCase(InstrumentDriverTestCase):
    """
    Base class for instrument driver unit tests
    """
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
    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("InstrumentDriverIntegrationTestCase.setUp")
        self.init_port_agent()
        InstrumentDriverTestCase.setUp(self)

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
        log.debug("before 'process_echo'")
        reply = self.driver_client.cmd_dvr('process_echo')
        log.debug("after 'process_echo'")
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
    def setUp(self):
        """
        @brief Setup test cases.
        """
        InstrumentDriverTestCase.setUp(self)
        self.init_port_agent()
        self.instrument_agent_manager = InstrumentAgentClient();
        self.instrument_agent_manager.start_container(deploy_file=self.test_config.container_deploy_file)

        self.container = self.instrument_agent_manager.container

        self.data_subscribers = InstrumentAgentDataSubscribers(
            packet_config=self.test_config.instrument_agent_packet_config,
        )
        self.event_subscribers = InstrumentAgentEventSubscribers(instrument_agent_resource_id=self.test_config.instrument_agent_resource_id)

        self.init_instrument_agent_client()

        self.event_subscribers.events_received = []


    def tearDown(self):
        """
        @brief Test teardown
        """
        log.debug("InstrumentDriverQualificationTestCase tearDown")
        self.instrument_agent_manager.stop_container()
        self.event_subscribers.stop()
        InstrumentDriverTestCase.tearDown(self)


    def init_instrument_agent_client(self):
        log.info("Start Instrument Agent Client")

        # Driver config
        driver_config = {
            'dvr_mod' : self.test_config.driver_module,
            'dvr_cls' : self.test_config.driver_class,
            'workdir' : self.test_config.working_dir,
            'process_type' : self.test_config.driver_process_type,

            'comms_config' : self.port_agent_comm_config(),

            'startup_config' : self.test_config.driver_startup_config
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



    def assert_capabilities(self, capabilities):
        '''
        Verify that all capabilities are available for a give state

        @todo: Currently resource interface not implemented because it requires
               a submodule update and some of the submodules are in release
               states.  So for now, no resource interfaces

        @param: dictionary of all the different capability types. i.e.
        {
          agent_command = ['DO_MY_COMMAND'],
          agent_parameter = ['foo'],
          resource_command = None,
          resource_interface = None,
          resource_parameter = None,
        }
        '''
        def sort_capabilities(caps_list):
            '''
            sort a return value into capability buckets.
            @retur agt_cmds, agt_pars, res_cmds, res_iface, res_pars
            '''
            agt_cmds = []
            agt_pars = []
            res_cmds = []
            res_iface = []
            res_pars = []

            if(not capabilities.get(AgentCapabilityType.AGENT_COMMAND)):
                capabilities[AgentCapabilityType.AGENT_COMMAND] = []
            if(not capabilities.get(AgentCapabilityType.AGENT_PARAMETER)):
                capabilities[AgentCapabilityType.AGENT_PARAMETER] = []
            if(not capabilities.get(AgentCapabilityType.RESOURCE_COMMAND)):
                capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
            if(not capabilities.get(AgentCapabilityType.RESOURCE_INTERFACE)):
                capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
            if(not capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER)):
                capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

            if len(caps_list)>0 and isinstance(caps_list[0], AgentCapability):
                agt_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.AGT_CMD]
                agt_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.AGT_PAR]
                res_cmds = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_CMD]
                #res_iface = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_IFACE]
                res_pars = [x.name for x in caps_list if x.cap_type==CapabilityType.RES_PAR]

            elif len(caps_list)>0 and isinstance(caps_list[0], dict):
                agt_cmds = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.AGT_CMD]
                agt_pars = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.AGT_PAR]
                res_cmds = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_CMD]
                #res_iface = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_IFACE]
                res_pars = [x['name'] for x in caps_list if x['cap_type']==CapabilityType.RES_PAR]

            return agt_cmds, agt_pars, res_cmds, res_iface, res_pars

        retval = self.instrument_agent_client.get_capabilities()
        agt_cmds, agt_pars, res_cmds, res_iface, res_pars = sort_capabilities(retval)

        log.debug("Agent Commands: %s " % str(agt_cmds))
        log.debug("Agent Parameters: %s " % str(agt_pars))
        log.debug("Resource Commands: %s " % str(res_cmds))
        log.debug("Resource Interface: %s " % str(res_iface))
        log.debug("Resource Parameter: %s " % str(res_pars))

        self.assertEqual(capabilities.get(AgentCapabilityType.AGENT_COMMAND), agt_cmds)
        self.assertEqual(capabilities.get(AgentCapabilityType.AGENT_PARAMETER), agt_pars)
        self.assertEqual(capabilities.get(AgentCapabilityType.RESOURCE_COMMAND), res_cmds)
        self.assertEqual(capabilities.get(AgentCapabilityType.RESOURCE_INTERFACE), res_iface)
        self.assertEqual(capabilities.get(AgentCapabilityType.RESOURCE_PARAMETER), res_pars)

    def assert_sample_polled(self, sampleDataAssert, sampleQueue, timeout = 10):
        """
        Test observatory polling function.

        Verifies the acquire_status command.
        """
        # Set up all data subscriptions.  Stream names are defined
        # in the driver PACKET_CONFIG dictionary
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        ###
        # Poll for a few samples
        ###

        # make sure there aren't any junk samples in the parsed
        # data queue.
        log.debug("Acqire Sample")
        self.data_subscribers.clear_sample_queue(sampleQueue)

        cmd = AgentCommand(command=DriverEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        log.debug("Acqire Sample")
        cmd = AgentCommand(command=DriverEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        log.debug("Acqire Sample")
        cmd = AgentCommand(command=DriverEvent.ACQUIRE_SAMPLE)
        reply = self.instrument_agent_client.execute_resource(cmd)

        # Watch the parsed data queue and return once three samples
        # have been read or the default timeout has been reached.
        samples = self.data_subscribers.get_samples(sampleQueue, 3, timeout = timeout)
        self.assertGreaterEqual(len(samples), 3)
        log.error("SAMPLE: %s" % samples)

        # Verify
        sampleDataAssert(samples.pop())
        sampleDataAssert(samples.pop())
        sampleDataAssert(samples.pop())

        self.assert_reset()

        self.doCleanups()

    def assert_sample_autosample(self, sampleDataAssert, sampleQueue, timeout = 10):
        """
        Test instrument driver execute interface to start and stop streaming
        mode.

        This command is only useful for testing one stream produced in
        streaming mode at a time.  If your driver has multiple streams
        then you will need to call this method more than once or use a
        different test.
        """
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)

        self.assert_enter_command_mode()

        self.data_subscribers.clear_sample_queue(sampleQueue)

        # Begin streaming.
        self.assert_start_autosample()

        # Assert we got 3 samples.
        samples = self.data_subscribers.get_samples(sampleQueue, 3, timeout = timeout)
        self.assertGreaterEqual(len(samples), 3)

        s = samples.pop()
        log.debug("SAMPLE: %s" % s)
        sampleDataAssert(s)

        s = samples.pop()
        log.debug("SAMPLE: %s" % s)
        sampleDataAssert(s)

        s = samples.pop()
        log.debug("SAMPLE: %s" % s)
        sampleDataAssert(s)

        # Halt streaming.
        self.assert_stop_autosample()

        self.assert_reset()

        self.doCleanups()

    def assert_reset(self):
        '''
        Exist active state
        '''
        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

    def assert_get_parameter(self, name, value):
        '''
        verify that parameters are got correctly.  Assumes we are in command mode.
        '''
        getParams = [ name ]

        result = self.instrument_agent_client.get_resource(getParams)

        self.assertEqual(result[name], value)

    def assert_set_parameter(self, name, value):
        '''
        verify that parameters are set correctly.  Assumes we are in command mode.
        '''
        setParams = { name : value }
        getParams = [ name ]

        self.instrument_agent_client.set_resource(setParams)
        result = self.instrument_agent_client.get_resource(getParams)

        self.assertEqual(result[name], value)

    def assert_read_only_parameter(self, name, value):
        '''
        verify that parameters are read only.  Ensure an exception is thrown
        when set is called and that the value returned is the same as the
        passed in value.
        '''
        setParams = { name : value }
        getParams = [ name ]

        # Call set, but verify the command failed.
        #self.instrument_agent_client.set_resource(setParams)

        # Call get and verify the value is correct.
        #result = self.instrument_agent_client.get_resource(getParams)
        #self.assertEqual(result[name], value)

    def assert_stop_autosample(self, timeout=GO_ACTIVE_TIMEOUT):
        '''
        Enter autosample mode from command
        '''
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        # Stop streaming.
        cmd = AgentCommand(command=DriverEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)


    def assert_start_autosample(self, timeout=GO_ACTIVE_TIMEOUT):
        '''
        Enter autosample mode from command
        '''
        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverProtocolState.COMMAND)

        # Begin streaming.
        cmd = AgentCommand(command=DriverEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=timeout)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)


    def assert_enter_command_mode(self):
        '''
        Walk through IA states to get to command mode from uninitialized
        '''
        state = self.instrument_agent_client.get_agent_state()
        if state == ResourceAgentState.UNINITIALIZED:

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

        state = self.instrument_agent_client.get_agent_state()
        if state == ResourceAgentState.STREAMING:
            self.assert_stop_autosample()

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, DriverProtocolState.COMMAND)

    def assert_direct_access_start_telnet(self, timeout = 600):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()

        # go direct access
        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            kwargs={'session_type': DirectAccessTypes.telnet,
                    'session_timeout':timeout,
                    'inactivity_timeout':timeout})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.warn("go_direct_access retval=" + str(retval.result))

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        # start 'telnet' client with returned address and port
        self.tcp_client = TcpClient(retval.result['ip_address'], retval.result['port'])

        self.assertTrue(self.tcp_client.expect("Username: " ))
        self.tcp_client.send_data("bob\r\n")

        self.assertTrue(self.tcp_client.expect("token: "))
        self.tcp_client.send_data(retval.result['token'] + "\r\n",)

        self.assertTrue(self.tcp_client.telnet_handshake())

        self.assertTrue(self.tcp_client.expect("connected\r\n"))
        
    def assert_direct_access_stop_telnet(self):
        '''
        Exit out of direct access mode.  We do this by simply changing
        state to command mode.
        @return:
        '''
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_COMMAND)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)


    def assert_switch_driver_state(self, command, result_state):
        '''
        Transition to a new driver state using command passed.
        @param command: protocol event used to transition state
        @param result_state: final protocol state
        '''
        cmd = AgentCommand(command=command)
        retval = self.instrument_agent_client.execute_resource(cmd)

        res_state = self.instrument_agent_client.get_resource_state()
        self.assertEqual(res_state, result_state)



    @unittest.skip("testing")
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
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_INACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        # Works but doesnt return anything useful when i tried.
        #cmd = AgentCommand(command=ResourceAgentEvent.GET_RESOURCE_STATE)
        #retval = self.instrument_agent_client.execute_agent(cmd)

        # works!
        retval = self.instrument_agent_client.ping_resource()
        retval = self.instrument_agent_client.ping_agent()

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
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)
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


    @unittest.skip("testing")
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
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)
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



    @unittest.skip("not an integration tests, should be in unit tests")
    def test_instrument_error_code_enum(self):
        """
        @brief check InstErrorCode for consistency
        @todo did InstErrorCode become redundant in the last refactor?
        """
        self.assertTrue(self.check_for_reused_values(InstErrorCode))
        pass


    @unittest.skip("not an integration tests, should be in unit tests")
    def test_driver_connection_state_enum(self):
        """
        @brief check DriverConnectionState for consistency
        @todo this check should also be a device specific for drivers like Trhph
        """

        # self.assertEqual(TrhphDriverState.UNCONFIGURED, DriverConnectionState.UNCONFIGURED)
        # self.assertEqual(TrhphDriverState.DISCONNECTED, DriverConnectionState.DISCONNECTED)
        # self.assertEqual(TrhphDriverState.CONNECTED, DriverConnectionState.CONNECTED)

        self.assertTrue(self.check_for_reused_values(DriverConnectionState))

    @unittest.skip("not an integration tests, should be in unit tests")
    def test_resource_agent_event_enum(self):

        self.assertTrue(self.check_for_reused_values(ResourceAgentEvent))


    @unittest.skip("not an integration tests, should be in unit tests")
    def test_resource_agent_state_enum(self):

        self.assertTrue(self.check_for_reused_values(ResourceAgentState))


    @unittest.skip("not an integration tests, should be in unit tests")
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


    @unittest.skip("not an integration tests, should be in unit tests")
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

    @unittest.skip("testing")
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
            'AgentState=RESOURCE_AGENT_STATE_INACTIVE',
            'AgentCommand=RESOURCE_AGENT_EVENT_INITIALIZE',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNKNOWN',
            'ResourceConfig',
            'ResourceState=DRIVER_STATE_COMMAND',
            'AgentState=RESOURCE_AGENT_STATE_IDLE',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_ACTIVE',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_RUN',
            'AgentCommand=RESOURCE_AGENT_PING_RESOURCE',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNCONFIGURED',
            'AgentState=RESOURCE_AGENT_STATE_UNINITIALIZED',
            'AgentCommand=RESOURCE_AGENT_EVENT_RESET',
            'AgentState=RESOURCE_AGENT_STATE_INACTIVE',
            'AgentCommand=RESOURCE_AGENT_EVENT_INITIALIZE',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_DISCONNECTED',
            'ResourceState=DRIVER_STATE_UNKNOWN',
            'ResourceConfig',
            'ResourceState=DRIVER_STATE_COMMAND',
            'AgentState=RESOURCE_AGENT_STATE_IDLE',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_ACTIVE',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_RUN',
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
            'ResourceState=DRIVER_STATE_COMMAND',
            'AgentState=RESOURCE_AGENT_STATE_COMMAND',
            'AgentCommand=RESOURCE_AGENT_EVENT_GO_COMMAND',
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
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        retval = self.instrument_agent_client.ping_resource()

        retval = self.instrument_agent_client.ping_agent()

        cmd = AgentCommand(command=ResourceAgentEvent.PING_RESOURCE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.assertTrue("ping from resource ppid" in retval.result)


        #cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        #retval = self.instrument_agent_client.execute_agent(cmd)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.IDLE)

        #cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        #retval = self.instrument_agent_client.execute_agent(cmd)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)
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

        log.debug("ROGERROGER got to the end!")
        raw_events = []
        for x in self.event_subscribers.events_received:
            if str(type(x)) == "<class 'interface.objects.ResourceAgentCommandEvent'>":
                log.debug(str(type(x)) + " ++********************* AgentCommand=" + str(x.execute_command))
                raw_events.append("AgentCommand=" + str(x.execute_command))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentResourceStateEvent'>":
                log.debug(str(type(x)) + " ++********************* ResourceState=" + str(x.state))
                raw_events.append("ResourceState=" + str(x.state))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentStateEvent'>":
                log.debug(str(type(x)) + " ++********************* AgentState=" + str(x.state))
                raw_events.append("AgentState=" + str(x.state))
            elif str(type(x)) == "<class 'interface.objects.ResourceAgentResourceConfigEvent'>":
                log.debug(str(type(x)) + " ++********************* ResourceConfig")
                raw_events.append("ResourceConfig")
            else:
                log.debug(str(type(x)) + " ++********************* " + str(x))

        for x in sorted(raw_events):
            log.debug(str(x) + " ?in (expected_events) = " + str(x in expected_events))
            self.assertTrue(x in expected_events)

        for x in sorted(expected_events):
            log.debug(str(x) + " ?in (raw_events) = " + str(x in raw_events))
            self.assertTrue(x in raw_events)

        # assert we got the expected number of events
        num_expected = len(self.de_dupe(expected_events))
        num_actual = len(self.de_dupe(raw_events))
        log.debug("num_expected = " + str(num_expected) + " num_actual = " + str(num_actual))
        self.assertTrue(num_actual == num_expected)

        pass

    @unittest.skip("redundant test")
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
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=GO_ACTIVE_TIMEOUT)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

    @unittest.skip("Driver.get_device_signature not yet implemented")
    def test_get_device_signature(self):
        """
        @Brief this test will call get_device_signature once that is
               implemented in the driver
        """
        pass

    @unittest.skip("redundant test")
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

