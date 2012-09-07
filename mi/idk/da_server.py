"""
@file mi/idk/da_server.py
@author Bill French
@brief Main script class for running the direct access process
"""

import os
import re
import time
import gevent

from mi.core.log import get_logger ; log = get_logger()

from mi.idk.instrument_agent_client import InstrumentAgentClient
from mi.idk.comm_config import CommConfig
from mi.idk.config import Config
from mi.idk.driver_generator import DriverGenerator
from mi.idk.metadata import Metadata
from mi.idk.unit_test import InstrumentDriverTestConfig
from mi.idk.exceptions import TestNotInitialized
from mi.idk.util import launch_data_monitor

from interface.objects import AgentCommand

from ion.agents.instrument.instrument_agent import InstrumentAgentState
from ion.agents.instrument.driver_process import DriverProcessType
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from ion.agents.port.port_agent_process import PortAgentProcess

TIMEOUT = 600

class DirectAccessServer():
    """
    Main class for running the start driver process.
    """
    port_agent = None
    instrument_agent_manager = None
    instrument_agent_client = None
    monitor_process = None

    def __init__(self, launch_monitor=False):
        """
        Setup the direct access server
        """
        # Currently we are pulling the driver config information from the driver tests.  There is a better way to do
        # this, but we are time crunched.  TODO: Fix this!

        generator = DriverGenerator(Metadata())
        __import__(generator.test_modulename())
        self.test_config = InstrumentDriverTestConfig()

        # Test to ensure we have initialized our test config
        if not self.test_config.initialized:
            raise TestNotInitialized(msg="Tests non initialized. Missing InstrumentDriverTestCase.initalize(...)?")

        self.launch_monitor = launch_monitor


    def __del__(self):
        """
        Destructor to cleanup all the processes we started to run DA
        """
        log.info("tearing down agents and containers")

        log.debug("killing the capability container")
        if self.instrument_agent_manager:
            self.instrument_agent_manager.stop_container()

        log.debug("killing the port agent")
        if self.port_agent:
            self.port_agent.stop()

        if self.monitor_process:
            log.debug("killing the monitor process")
            self.monitor_process.kill()


    def start_container(self):
        """
        Start up the capability container, port agent and the IA client
        """
        self.init_comm_config()
        self.init_port_agent()
        self.instrument_agent_manager = InstrumentAgentClient();
        self.instrument_agent_manager.start_container()
        self.init_instrument_agent_client()

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

        config = {
            'device_addr' : self.comm_config.device_addr,
            'device_port' : self.comm_config.device_port
        }

        self.port_agent = PortAgentProcess.launch_process(config, timeout = 60,
            test_mode = True)

        port = self.port_agent.get_data_port()
        pid  = self.port_agent.get_pid()

        log.info('Started port agent pid %s listening at port %s' % (pid, port))

        if self.launch_monitor:
            self.logfile = self.port_agent.port_agent.logfname
            log.info('Started port agent pid %s listening at port %s' % (pid, port))
            log.info("data log: %s" % self.logfile)
            self.monitor_process = launch_data_monitor(self.logfile)

    def stop_port_agent(self):
        """
        Stop the port agent.
        """
        if self.port_agent:
            self.port_agent.stop()

        if self.monitor_process:
            self.monitor_process.kill()

    def init_instrument_agent_client(self):
        """
        Start up the instrument agent client.
        """
        log.info("Start Instrument Agent Client")

        # Port config
        port = self.port_agent.get_data_port()
        port_config = {
            'addr': 'localhost',
            'port': port
        }

        # Driver config
        driver_config = {
            'dvr_mod' : self.test_config.driver_module,
            'dvr_cls' : self.test_config.driver_class,

            'process_type' : self.test_config.driver_process_type,

            'workdir' : self.test_config.working_dir,
            'comms_config' : port_config
        }

        # Create agent config.
        agent_config = {
            'driver_config' : driver_config,
            'stream_config' : {},
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

    def _start_da(self, type):
        """
        The actual work to start up a DA session.
        """
        self.start_container()

        log.info("--- Starting DA server ---")

        cmd = AgentCommand(command='power_down')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)

        cmd = AgentCommand(command='power_up')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)

        cmd = AgentCommand(command='initialize')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)

        cmd = AgentCommand(command='go_active')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)

        cmd = AgentCommand(command='run')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)
        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)

        cmd = AgentCommand(command='go_direct_access',
            kwargs={'session_type': type,
                    'session_timeout': TIMEOUT,
                    'inactivity_timeout': TIMEOUT})
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)

        ip_address = retval.result['ip_address']
        port= retval.result['port']
        token= retval.result['token']

        cmd = AgentCommand(command='get_resource_state')
        retval = self.instrument_agent_client.execute_agent(cmd)
        log.debug("retval: %s", retval)

        ia_state = retval.result
        log.debug("IA State: %s", ia_state)

        if ia_state == InstrumentAgentState.DIRECT_ACCESS:
            print "Direct access server started, IP: %s Port: %s" % (ip_address, port)
            if token:
                print "Token: %s" % token

            while ia_state == InstrumentAgentState.DIRECT_ACCESS:
                cmd = AgentCommand(command='get_resource_state')
                retval = self.instrument_agent_client.execute_agent(cmd)

                ia_state = retval.result
                gevent.sleep(.1)

        else:
            log.error("Failed to start DA server")


    def start_telnet_server(self):
        """
        @brief Run the telnet server
        """
        self._start_da(DirectAccessTypes.telnet)

    def start_vps_server(self):
        """
        @brief run the vps server
        """
        self._start_da(DirectAccessTypes.vsp)

