"""
@file marine-integration/mi/idk/run_instrument.py
@author David Everett
@brief Main script class for communicating with an instrument
"""

import subprocess
from pyon.public import CFG
from ooi.logging import config

from os.path import exists, join, isdir
from os import listdir

from mi.idk.metadata import Metadata
from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.exceptions import DriverDoesNotExist

# Pyon pubsub and event support.
from pyon.event.event import EventSubscriber
from pyon.ion.stream import StandaloneStreamSubscriber

# Pyon unittest support.
from pyon.util.int_test import IonIntegrationTestCase

# Agent imports.
from pyon.util.context import LocalContextMixin
from pyon.agent.agent import ResourceAgentClient
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

# Driver imports.
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from ion.agents.instrument.driver_int_test_support import DriverIntegrationTestSupport
from ion.agents.port.port_agent_process import PortAgentProcess
from ion.agents.instrument.driver_process import DriverProcessType
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverConnectionState

# Parameter dicts and publishing.
from ion.agents.instrument.taxy_factory import get_taxonomy
from ion.util.parameter_yaml_IO import get_param_dict
from coverage_model.parameter import ParameterDictionary

# Objects and clients.
from interface.objects import AgentCommand
from interface.objects import CapabilityType
from interface.objects import AgentCapability
from interface.services.icontainer_agent import ContainerAgentClient
from interface.services.dm.ipubsub_management_service import PubsubManagementServiceClient

from mi.core.log import get_logger ; log = get_logger()

from mi.idk import prompt

from prototype.sci_data.stream_defs import ctd_stream_definition


WORK_DIR = '/tmp/'
DELIM = ['<<','>>']

DVR_CONFIG = {
  'workdir' : WORK_DIR,
  'process_type' : ('ZMQPyClassDriverLauncher',)
}

# Driver parameters
DRIVER_CLASS = 'InstrumentDriver'
DRIVER_MODULE_ROOT = 'mi.instrument.'
DRIVER_MODULE_LEAF = '.driver'

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

    def __init__(self, make=None, model=None, name=None, driver_class=None, 
                 ip_address=None, port=None, version=None, monitor=False):
        self.driver_make = make
        self.driver_model = model
        self.driver_name = name
        self.driver_class = driver_class
        if not self.driver_class:
            self.driver_class = DRIVER_CLASS
        self.ip_address = ip_address
        self.port = port
        self.driver_version = version
        self.monitor_window = monitor
        
        self._cleanups = []

    def _initialize(self):
        """
        Start port agent, add port agent cleanup.
        Start container.
        Start deploy services.
        Define agent config, start agent.
        Start agent client.
        """

        """
        Get the information for the driver.  This can be read from the yml
        files; the user can run switch_driver to change the current driver.
        """ 
        self.fetch_metadata()
        self.fetch_driver_class()
        self.fetch_comm_config()

        if not exists(self.metadata.driver_dir()):
            raise DriverDoesNotExist( "%s/%s/$%s" % (self.metadata.driver_make,
                                                     self.metadata.driver_model,
                                                     self.driver_name))        
        
        driver_module = DRIVER_MODULE_ROOT + self.metadata.driver_make + '.' + self.metadata.driver_model + '.' + self.metadata.driver_name + DRIVER_MODULE_LEAF
        
        log.info('driver module: %s', driver_module)
        log.info('driver class: %s', self.driver_class)
        log.info('device address: %s', self.ip_address)
        log.info('device port: %s', self.port)
        log.info('log delimiter: %s', DELIM)
        log.info('work dir: %s', WORK_DIR)

        DVR_CONFIG.update({'dvr_mod' : driver_module, 'dvr_cls' : self.driver_class})

        
        self._support = DriverIntegrationTestSupport(driver_module,
                                                     self.driver_class,
                                                     self.ip_address,
                                                     self.port,
                                                     DELIM,
                                                     WORK_DIR)
        
        # Start port agent, add stop to cleanup.
        #self._start_pagent()
        self.new_start_pagent()

        # Start a monitor window if specified.
        if self.monitor_window:
            self.monitor_file = self._pagent.port_agent.logfname
            pOpenString = "xterm -T InstrumentMonitor -e tail -f " + self.monitor_file
            
            x = subprocess.Popen(pOpenString, shell=True)        
            
        """
        DHE: Added self._cleanups to make base classes happy
        """
        #self.addCleanup(self._support.stop_pagent)    
        self.addCleanup(self.new_stop_pagent)    
        
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
        
        self._start_data_subscribers(6)

        
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
 
    def new_start_pagent(self):
        """
        Construct and start the port agent.
        @retval port Port that was used for connection to agent
        """
        # Create port agent object.
        config = { 'device_addr' : self.ip_address,
                   'device_port' : self.port,
                   'working_dir' : WORK_DIR,
                   'delimiter' : DELIM }

        self._pagent = PortAgentProcess.launch_process(config, timeout = 60, test_mode = True)
        pid = self._pagent.get_pid()
        port = self._pagent.get_data_port()

        log.info('Started port agent pid %d listening at port %d', pid, port)

        # Configure driver to use port agent port number.
        DVR_CONFIG['comms_config'] = {
            'addr' : 'localhost',
            'port' : port
        }

        return port

    def new_stop_pagent(self):
        """
        Stop the port agent.
        """
        if self._pagent:
            pid = self._pagent.get_pid()
            if pid:
                mi_logger.info('Stopping pagent pid %i', pid)
                self._pagent.stop()
            else:
                mi_logger.info('No port agent running.')


       
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

        streams = {
            'parsed' : 'ctd_parsed_param_dict',
            'raw' : 'ctd_raw_param_dict'
        }

        for (stream_name, param_dict_name) in streams.iteritems():
            stream_id, stream_route = pubsub_client.create_stream(name=stream_name,
                                                exchange_point='science_data')
            pd = get_param_dict(param_dict_name)
            stream_config = dict(stream_route=stream_route,
                                 stream_id=stream_id,
                                 parameter_dictionary=pd.dump())
            self._stream_config[stream_name] = stream_config

    def _start_data_subscribers(self, count):
        """
        """        
        # Create a pubsub client to create streams.
        pubsub_client = PubsubManagementServiceClient(node=self.container.node)
                
        # Create streams and subscriptions for each stream named in driver.
        self._data_subscribers = []
        self._samples_received = []
        #self._async_sample_result = AsyncResult()

        # A callback for processing subscribed-to data.
        def recv_data(message, stream_route, stream_id):
            print 'Received message on ' + str(stream_id) + ' (' + str(stream_route.exchange_point) + ',' + str(stream_route.routing_key) + ')'
            log.info('Received message on %s (%s,%s)', stream_id, stream_route.exchange_point, stream_route.routing_key)
            self._samples_received.append(message)
            #if len(self._samples_received) == count:
                #self._async_sample_result.set()

        for (stream_name, stream_config) in self._stream_config.iteritems():
            
            stream_id = stream_config['stream_id']
            
            # Create subscriptions for each stream.

            exchange_name = '%s_queue' % stream_name
            self._purge_queue(exchange_name)
            sub = StandaloneStreamSubscriber(exchange_name, recv_data)
            sub.start()
            self._data_subscribers.append(sub)
            print 'stream_id: %s' % stream_id
            sub_id = pubsub_client.create_subscription(name=exchange_name, stream_ids=[stream_id])
            pubsub_client.activate_subscription(sub_id)
            sub.subscription_id = sub_id # Bind the subscription to the standalone subscriber (easier cleanup, not good in real practice)

    def _purge_queue(self, queue):
        xn = self.container.ex_manager.create_xn_queue(queue)
        xn.purge()
 
    def _stop_data_subscribers(self):
        for subscriber in self._data_subscribers:
            pubsub_client = PubsubManagementServiceClient()
            if hasattr(subscriber,'subscription_id'):
                try:
                    pubsub_client.deactivate_subscription(subscriber.subscription_id)
                except:
                    pass
                pubsub_client.delete_subscription(subscriber.subscription_id)
            subscriber.stop()

    def bring_instrument_active(self):
        """
        @brief Bring the agent up to COMMAND state, 
        """

        """
        DHE: Don't have an event subscriber yet

        # Set up a subscriber to collect error events.
        #self._start_event_subscriber('ResourceAgentResourceStateEvent', 6)
        #self.addCleanup(self._stop_event_subscriber)
        """    

        state = self._ia_client.get_agent_state()
        print "ResourceAgentState: " + str(state)
    
        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        
        res_state = self._ia_client.get_resource_state()
        print "DriverConnectionState: " + str(state)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        print "ResourceAgentState: " + str(state)

        res_state = self._ia_client.get_resource_state()
        print "DriverProtocolState: " + str(state)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self._ia_client.execute_agent(cmd)
        state = self._ia_client.get_agent_state()
        print "ResourceAgentState: " + str(state)
        
        res_state = self._ia_client.get_resource_state()
        print "DriverProtocolState: " + str(state)

        """
        DHE: Don't have an event subscriber yet so we've received no events.
        self._async_event_result.get(timeout=2)
        print "Received: " + str(len(self._events_received)) + " events."
        """
                
    ###############################################################################
    # RunInstrument helpers.
    ###############################################################################
    def get_capabilities(self):
        """
        @brief Get exposed capabilities in current state.
        """
        
        retval = self._ia_client.get_capabilities()
        
        # Validate capabilities for state UNINITIALIZED.
        self.agt_cmds = [x.name for x in retval if x.cap_type==CapabilityType.AGT_CMD]
        self.agt_pars = [x.name for x in retval if x.cap_type==CapabilityType.AGT_PAR]
        self.res_cmds = [x.name for x in retval if x.cap_type==CapabilityType.RES_CMD]
        self.res_pars = [x.name for x in retval if x.cap_type==CapabilityType.RES_PAR]
        
        print "Agent Commands: " + str(self.agt_cmds)
        print "Agent Parameters: " + str(self.agt_pars)
        print "Resource Commands: " + str(self.res_cmds)
        print "Resource Parameters: " + str(self.res_pars)

    def send_command(self, command):
        """
        @brief Send a command to the instrument through the instrument agent.
        First determine whether it's a get or set, which are handled separately.
        """

        if command == DriverEvent.GET:
            self._get_param()
        elif command == DriverEvent.SET:
            self._set_param()
        else:
            print "Input command: " + str(command)
            cmd = AgentCommand(command = command)
            retval = self._ia_client.execute_resource(cmd)
            print "Results of command: " + str(retval)

    def _get_param(self):
        """
        @brief Get a single parameter from the instrument (will be updated to get 
        multiple later).
        """
        
        _all_params = self._ia_client.get_resource('DRIVER_PARAMETER_ALL')
        print "Parameters you can get are: " + str(_all_params)
        _param_valid = False
        while _param_valid is False:
            _param = prompt.text('\nEnter a single parameter')
            if _param in _all_params:
                _param_valid = True
            else:
                print 'Invalid parameter: ' + _param 
                
        reply = self._ia_client.get_resource([_param])
        print 'Reply is :' + str(reply)
                                                                    
    def _set_param(self):
        """
        @brief Set a single parameter
        """
        
        _all_params = self._ia_client.get_resource('DRIVER_PARAMETER_ALL')
        print "Parameters you can set are: " + str(_all_params)
        _param_valid = False
        while _param_valid is False:
            _param = prompt.text('\nEnter a single parameter')
            if _param in _all_params:
                _param_valid = True
            else:
                print 'Invalid parameter: ' + _param 

        _value = prompt.text('Enter value')
                
        param_dict = {_param: _value}
        reply = self._ia_client.set_resource(param_dict)
        orig_params = reply
                                                                    
    def fetch_metadata(self):
        """
        @brief collect metadata from the user
        """

        self.metadata = Metadata()
        self.driver_make = self.metadata.driver_make
        self.driver_model = self.metadata.driver_model
        self.driver_name = self.metadata.driver_name
        
        if not (self.driver_make and self.driver_model and self.driver_name):
            self.driver_make = prompt.text( 'Driver Make', self.driver_make )
            self.driver_model = prompt.text( 'Driver Model', self.driver_model )
            self.driver_name = prompt.text( 'Driver Name', self.driver_name )
            
        if not (self.driver_class):
            self.driver_class = prompt.text( 'Driver Class', self.driver_class )
            
        self.metadata = Metadata(self.driver_make, self.driver_model, self.driver_name)

    def fetch_comm_config(self):
        """
        @brief collect connection information for the logger from the user
        """

        config_path = "%s/%s" % (self.metadata.driver_dir(), CommConfig.config_filename())
        self.comm_config = CommConfig.get_config_from_console(config_path)
        self.comm_config.display_config()
        #self.comm_config.get_from_console()
        self.ip_address = self.comm_config.device_addr
        self.port = self.comm_config.device_port
        
        if not (self.ip_address):
            self.ip_address = prompt.text( 'Instrument IP Address', self.ip_address )
            
        if not (self.port):
            continuing = True
            while continuing:
                sport = prompt.text( 'Instrument Port', self.port )
                try:
                    self.port = int(sport)
                    continuing = False
                except ValueError as e:
                    print "Error converting port to number: " + str(e)
                    print "Please enter a valid port number.\n"

    def fetch_driver_class(self):
        self.driver_class = prompt.text( 'Driver Class', self.driver_class )
            
    def get_user_command(self, text='Enter command'):

        command = prompt.text(text)
        return command
            
    def run(self):
        """
        @brief Run it.
        """
        
        print( "*** Starting RunInstrument ***" )

        self._initialize()

        self.bring_instrument_active()

        PROMPT = 'Enter command (\'quit\' to exit)'
        text = PROMPT
        continuing = True
        while continuing:
            """
            Get a list of the currently available capabilities
            """
            self.get_capabilities()
            command = self.get_user_command(text)
            text = PROMPT
            if command == 'quit':
                continuing = False
            elif command in self.agt_cmds or command in self.res_cmds:
                self.send_command(command)
            else:
                text = 'Invalid Command: ' + command + PROMPT
                

