"""
@file coi-services/mi.idk/run_instrument.py
@author David Everett
@brief Main script class for communicating with an instrument
"""

from os.path import exists, join, isdir
from os import listdir

from mi.idk.metadata import Metadata
from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.exceptions import DriverDoesNotExist

# Pyon unittest support.
from pyon.util.int_test import IonIntegrationTestCase
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient

# Agent imports.
from pyon.util.context import LocalContextMixin
from pyon.agent.agent import ResourceAgentClient
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

# Driver imports.
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from ion.agents.instrument.driver_int_test_support import DriverIntegrationTestSupport
from ion.agents.port.logger_process import EthernetDeviceLogger
from ion.agents.instrument.driver_process import DriverProcessType
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverConnectionState
from ion.agents.instrument.taxy_factory import get_taxonomy

# Objects and clients.
from interface.objects import AgentCommand
from interface.objects import StreamQuery
from interface.objects import CapabilityType

from interface.services.icontainer_agent import ContainerAgentClient

from mi.core.log import get_logger ; log = get_logger()

from mi.idk import prompt

from prototype.sci_data.stream_defs import ctd_stream_definition
from mi.instrument.satlantic.isusv3.ooicore.driver import PACKET_CONFIG

DEV_ADDR = '67.58.40.195'
DEV_PORT = 2001
DRV_MOD = 'mi.instrument.satlantic.isusv3.ooicore.driver'
DRV_CLS = 'ooicoreInstrumentDriver'
WORK_DIR = '/tmp/'
DELIM = ['<<','>>']

DVR_CONFIG = {
    'dvr_mod' : DRV_MOD,
    'dvr_cls' : DRV_CLS,
    'workdir' : WORK_DIR,
    'process_type' : ('ZMQPyClassDriverLauncher',)
}

# Agent parameters.
IA_RESOURCE_ID = '123xyz'
IA_NAME = 'Agent007'
IA_MOD = 'ion.agents.instrument.instrument_agent'
IA_CLS = 'InstrumentAgent'


class FakeProcess(LocalContextMixin):
    """
    A fake process used because the test case is not an ion process.
    """
    name = ''
    id=''
    process_type = ''


class RunInstrument(IonIntegrationTestCase):
    """
    Main class for communicating with an instrument
    """

    def __init__(self, make=None, model=None, name=None, version=None):
        self.driver_make = make
        self.driver_model = model
        self.driver_name = name
        self.driver_version = version
        
        self._cleanups = []

    def setUp(self):
        """
        Set up driver integration support.
        Start port agent, add port agent cleanup.
        Start container.
        Start deploy services.
        Define agent config, start agent.
        Start agent client.
        """
        
        log.info('Creating driver integration test support:')
        log.info('driver module: %s', DRV_MOD)
        log.info('driver class: %s', DRV_CLS)
        log.info('device address: %s', DEV_ADDR)
        log.info('device port: %s', DEV_PORT)
        log.info('log delimiter: %s', DELIM)
        log.info('work dir: %s', WORK_DIR)
        self._support = DriverIntegrationTestSupport(DRV_MOD,
                                                     DRV_CLS,
                                                     DEV_ADDR,
                                                     DEV_PORT,
                                                     DELIM,
                                                     WORK_DIR)
        
        # Start port agent, add stop to cleanup.
        self._start_pagent()
        
        """
        DHE: Added self._cleanups
        """
        self.addCleanup(self._support.stop_pagent)    
        
        # Start container.
        log.info('Staring capability container.')
        self._start_container()
        
        # Bring up services in a deploy file (no need to message)
        log.info('Staring deploy services.')
        self.container.start_rel_from_url('res/deploy/r2deploy.yml')

        # Setup stream config.
        self._build_stream_config()
        
        # Create agent config.
        agent_config = {
            'driver_config' : DVR_CONFIG,
            'stream_config' : self._stream_config,
            'agent'         : {'resource_id': IA_RESOURCE_ID},
            'test_mode' : True
        }

        # Start instrument agent.
        self._ia_pid = None
        log.debug("TestInstrumentAgent.setup(): starting IA.")
        log.info('Agent config: %s', str(agent_config))
        container_client = ContainerAgentClient(node=self.container.node,
                                                name=self.container.name)
        self._ia_pid = container_client.spawn_process(name=IA_NAME,
                                                      module=IA_MOD, 
                                                      cls=IA_CLS, 
                                                      config=agent_config)      
        log.info('Agent pid=%s.', str(self._ia_pid))
        
        # Start a resource agent client to talk with the instrument agent.
        self._ia_client = None
        self._ia_client = ResourceAgentClient(IA_RESOURCE_ID,
                                              process=FakeProcess())
        log.info('Got ia client %s.', str(self._ia_client))        
        
    ###############################################################################
    # Port agent helpers.
    ###############################################################################

    def _start_pagent(self):
        """
        Construct and start the port agent.
        """

        port = self._support.start_pagent()
        log.info('Port agent started at port %i',port)
        
        # Configure driver to use port agent port number.
        DVR_CONFIG['comms_config'] = {
            'addr' : 'localhost',
            'port' : port
        }
        
    ###############################################################################
    # Data stream helpers.
    ###############################################################################

    def _build_stream_config(self):
        """
        """
        # Create a pubsub client to create streams.
        pubsub_client = PubsubManagementServiceClient(node=self.container.node)
                
        # Create streams and subscriptions for each stream named in driver.
        self._stream_config = {}

        for stream_name in PACKET_CONFIG:
            
            # Create stream_id from stream_name.
            stream_def = ctd_stream_definition(stream_id=None)
            stream_def_id = pubsub_client.create_stream_definition(
                                                    container=stream_def)        
            stream_id = pubsub_client.create_stream(
                        name=stream_name,
                        stream_definition_id=stream_def_id,
                        original=True,
                        encoding='ION R2')

            # Create stream config from taxonomy and id.
            taxy = get_taxonomy(stream_name)
            stream_config = dict(
                id=stream_id,
                taxonomy=taxy.dump()
            )
            self._stream_config[stream_name] = stream_config        

    def _start_data_subscribers(self, count):
        """
        """
        # Create a pubsub client to create streams.
        pubsub_client = PubsubManagementServiceClient(node=self.container.node)
                
        # Create a stream subscriber registrar to create subscribers.
        subscriber_registrar = StreamSubscriberRegistrar(process=self.container,
                                                container=self.container)

        # Create streams and subscriptions for each stream named in driver.
        self._data_subscribers = []
        self._data_greenlets = []
        self._samples_received = []
        self._async_sample_result = AsyncResult()

        # A callback for processing subscribed-to data.
        def consume_data(message, headers):
            log.info('Subscriber received data message: %s   %s.',
                     str(message), str(headers))
            self._samples_received.append(message)
            if len(self._samples_received) == count:
                self._async_sample_result.set()

        for (stream_name, stream_config) in self._stream_config.iteritems():
            
            stream_id = stream_config['id']
            
            # Create subscriptions for each stream.
            exchange_name = '%s_queue' % stream_name
            sub = subscriber_registrar.create_subscriber(
                exchange_name=exchange_name, callback=consume_data)
            self._listen_data(sub)
            self._data_subscribers.append(sub)
            query = StreamQuery(stream_ids=[stream_id])
            sub_id = pubsub_client.create_subscription(query=query,
                    exchange_name=exchange_name, exchange_point='science_data')
            pubsub_client.activate_subscription(sub_id)
 
    def _listen_data(self, sub):
        """
        Pass in a subscriber here, this will make it listen in a background greenlet.
        """
        gl = spawn(sub.listen)
        self._data_greenlets.append(gl)
        sub._ready_event.wait(timeout=5)
        return gl
                                 
    def _stop_data_subscribers(self):
        """
        Stop the data subscribers on cleanup.
        """
        for sub in self._data_subscribers:
            sub.stop()
        for gl in self._data_greenlets:
            gl.kill()


    ###############################################################################
    # Tests.
    ###############################################################################

    def test_initialize(self):
        """
        Test agent initialize command. This causes creation of
        driver process and transition to inactive.
        """
        
        # We start in uninitialized state.
        # In this state there is no driver process.
        state = self._ia_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.UNINITIALIZED)
        print "ResourceAgentState: " + str(state)
        
        # Ping the agent.
        retval = self._ia_client.ping_agent()
        log.info(retval)
        print "Ping to agent returned: " + str(retval)

        # Initialize the agent.
        # The agent is spawned with a driver config, but you can pass one in
        # optinally with the initialize command. This validates the driver
        # config, launches a driver process and connects to it via messaging.
        # If successful, we switch to the inactive state.
        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.INACTIVE)
        print "ResourceAgentState: " + str(state)

        # Ping the driver proc.
        retval = self._ia_client.ping_resource()
        log.info(retval)
        print "Ping to agent returned: " + str(retval)

        # Reset the agent. This causes the driver messaging to be stopped,
        # the driver process to end and switches us back to uninitialized.
        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.UNINITIALIZED)
        print "ResourceAgentState: " + str(state)
        
    def test_resource_states(self):
        """
        Bring the agent up, through COMMAND state, and reset to UNINITIALIZED,
        verifying the resource state at each step. Verify
        ResourceAgentResourceStateEvents are published.
        """

        """
        DHE: Don't have an event subscriber yet

        # Set up a subscriber to collect error events.
        #self._start_event_subscriber('ResourceAgentResourceStateEvent', 6)
        #self.addCleanup(self._stop_event_subscriber)
        """    

        state = self._ia_client.get_agent_state()
#        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)
        print "ResourceAgentState: " + str(state)
    
        #with self.assertRaises(Conflict):
        #res_state = self._ia_client.get_resource_state()
        #print "ResourceState: " + str(state)
    
        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.INACTIVE)
        
        res_state = self._ia_client.get_resource_state()
        #self.assertEqual(res_state, DriverConnectionState.UNCONFIGURED)
        print "DriverConnectionState: " + str(state)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.IDLE)
        print "ResourceAgentState: " + str(state)

        res_state = self._ia_client.get_resource_state()
        #self.assertEqual(res_state, DriverProtocolState.COMMAND)
        print "DriverProtocolState: " + str(state)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.COMMAND)        
        print "ResourceAgentState: " + str(state)
        
        res_state = self._ia_client.get_resource_state()
        #self.assertEqual(res_state, DriverProtocolState.COMMAND)
        print "DriverProtocolState: " + str(state)

        """
        something's not working...
        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.UNINITIALIZED)
        print "ResourceAgentState: " + str(state)
        """
        
        #with self.assertRaises(Conflict):
        #res_state = self._ia_client.get_resource_state()
        #print "ResourceState: " + str(state)
        
        """
        DHE: Don't have an event subscriber yet so we've received no events.
        self._async_event_result.get(timeout=2)
        #self.assertGreaterEqual(len(self._events_received), 6)
        print "Received: " + str(len(self._events_received)) + " events."
        """
                
        
    ###############################################################################
    # RunInstrument helpers.
    ###############################################################################
                                                
    def fetch_metadata(self):
        """
        @brief collect metadata from the user
        """
        if not (self.driver_make and self.driver_model and self.driver_name):
            self.driver_make = prompt.text( 'Driver Make', self.driver_make )
            self.driver_model = prompt.text( 'Driver Model', self.driver_model )
            self.driver_name = prompt.text( 'Driver Name', self.driver_name )

        self.metadata = Metadata(self.driver_make, self.driver_model, self.driver_name)

    def fetch_comm_config(self):
        """
        @brief collect connection information for the logger from the user
        """
        config_path = "%s/%s" % (self.metadata.driver_dir(), CommConfig.config_filename())
        self.comm_config = CommConfig.get_config_from_console(config_path)
        self.comm_config.get_from_console()

    def run(self):
        """
        @brief Run it.
        """
        print( "*** Starting RunInstrument ***" )

        self.setUp()
        #self.fetch_metadata()

        #if not exists(self.metadata.driver_dir()):
        #    raise DriverDoesNotExist( "%s/%s/$%s" % (self.metadata.driver_make,
        #                                             self.metadata.driver_model,
        #                                             self.driver_name))
        #self.fetch_comm_config()
        #self.metadata.link_current_metadata()
        
        #self.test_initialize()
        self.test_resource_states()

    @staticmethod
    def list_drivers():
        driver_dir = join(Config().get("working_repo"), 'mi', 'instrument')
        log.debug("Driver Dir: %s", driver_dir)

        drivers = SwitchDriver.get_drivers()

        for make in sorted(drivers.keys()):
            for model in sorted(drivers[make].keys()):
                for name in sorted(drivers[make][model].keys()):
                    for version in sorted(drivers[make][model][name]):
                        print "%s %s %s %s" % (make, model, name, version)


    @staticmethod
    def get_drivers():
        driver_dir = join(Config().get("working_repo"), 'mi', 'instrument')
        log.debug("Driver Dir: %s", driver_dir)

        drivers = {}

        for make in listdir(driver_dir):
            make_dir = join(driver_dir, make)
            if isdir(make_dir) and not make == 'test':
                for model in listdir(make_dir):
                    model_dir = join(make_dir, model)
                    if isdir(model_dir) and not model == 'test':
                        for name in listdir(model_dir):
                            name_dir = join(model_dir, name)
                            if isdir(name_dir) and not name == 'test':
                                log.debug("found driver: %s %s %s", make, model, name)
                                if not drivers.get(make): drivers[make] = {}
                                if not drivers[make].get(model): drivers[make][model] = {}
                                drivers[make][model][name] = SwitchDriver.get_versions(make,model,name)

        return drivers

    @staticmethod
    def get_versions(make, model, name):
        return ['master']

