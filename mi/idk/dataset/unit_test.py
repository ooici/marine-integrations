#! /usr/bin/env python

"""
@file coi-services/ion/idk/data_set_agent/unit_test.py
@author Bill French
@brief Base classes for data set agent tests.
"""
import os
import shutil
from mi.core.log import get_logger ; log = get_logger()

from mi.core.unit_test import MiIntTestCase
from mi.core.unit_test import ParticleTestMixin

from mi.idk.util import remove_all_files
from mi.idk.unit_test import InstrumentDriverTestConfig
from mi.idk.exceptions import TestNotInitialized
from mi.idk.exceptions import IDKConfigMissing
from mi.idk.exceptions import IDKException

from mi.idk.dataset.metadata import Metadata
from mi.idk.instrument_agent_client import InstrumentAgentClient
from mi.idk.instrument_agent_client import InstrumentAgentDataSubscribers
from mi.idk.instrument_agent_client import InstrumentAgentEventSubscribers

from mi.core.instrument.instrument_driver import DriverEvent

from pyon.core.exception import Conflict
from pyon.core.exception import ResourceError, BadRequest, Timeout, ServerError
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from interface.objects import AgentCommandResult
from interface.objects import AgentCommand

class DataSetTestConfig(InstrumentDriverTestConfig):
    """
    Singleton driver test config object.
    """
    agent_module = 'mi.idk.instrument_agent'
    agent_class = 'DatasetAgent'

    container_deploy_file = 'deploy/r2qual.yml'
    publisher_deploy_file = 'deploy/r2pub.yml'

    def initialize(self, *args, **kwargs):
        super(DataSetTestConfig, self).initialize(*args, **kwargs)

        log.debug("Dataset Agent Test Config:")
        for property, value in vars(self).iteritems():
            log.debug("key: %s, value: %s", property, value)


class DataSetTestCase(MiIntTestCase):
    """
    Base class for instrument driver tests
    """
    # configuration singleton
    test_config = DataSetTestConfig()

    @classmethod
    def initialize(cls, *args, **kwargs):
        """
        Initialize the test_configuration singleton
        """
        cls.test_config.initialize(*args,**kwargs)

    def setUp(self):
        """
        @brief Setup test cases.
        """
        log.debug("*********************************************************************")
        log.debug("Starting Dataset Test %s", self._testMethodName)
        log.debug("*********************************************************************")
        log.debug("ID: %s", self.id())
        log.debug("DataSetTestCase setUp")

        # Test to ensure we have initialized our test config
        if not self.test_config.initialized:
            return TestNotInitialized(msg="Tests non initialized. Missing DataSetTestCase.initialize(...)?")

        self.clear_sample_data()

    def _driver_config(self):
        """
        Build the driver configuration and return it
        """
        config = {
            'dvr_mod' : self.test_config.driver_module,
            'dvr_cls' : self.test_config.driver_class,
            'startup_config' : self.test_config.driver_startup_config
        }
        return config

    def _agent_config(self):
        """
        Build the agent configuration and return it
        """
        config = {
            'driver_config': self._driver_config(),
            'stream_config' : self.data_subscribers.stream_config,
            'agent': {'resource_id': self.test_config.agent_resource_id}
        }
        return config

    def _get_source_data_file(self, filename):
        """
        Search for a sample data file, first check the driver resource directory
        then just use the filename as a path.  If the file doesn't exists
        raise an exception
        @param filename name or path of the file to search for
        @return full path to the found data file
        @raise IDKException if the file isn't found
        """
        resource_dir = Metadata().resource_dir()

        source_path = os.path.join(resource_dir, filename)

        log.debug("Search for resource file (%s) in %s", filename, resource_dir)
        if os.path.isfile(source_path):
            log.debug("Found %s in resource directory", filename)
            return source_path

        log.debug("Search for resource file (%s) in current directory", filename)
        if os.path.isfile(filename):
            log.debug("Found %s in the current directory", filename)
            return filename

        raise IDKException("Data file %s does not exist", filename)

    def create_data_dir(self):
        """
        Verify the test data directory is created and exists.  Return the path to
        the directory.
        @return: path to data directory
        @raise: IDKConfigMissing no harvester config
        @raise: IDKException if data_dir exists, but not a directory
        """
        startup_config = self._driver_config().get('startup_config')
        if not startup_config:
            raise IDKConfigMissing("Driver config missing 'startup_config'")

        harvester_config = startup_config.get('harvester')
        if not harvester_config:
            raise IDKConfigMissing("Startup config missing 'harvester' config")

        data_dir = harvester_config.get("directory")
        if not data_dir:
            raise IDKConfigMissing("Harvester config missing 'directory'")

        if not os.path.exists(data_dir):
            log.debug("Creating data dir: %s", data_dir)
            os.makedirs(data_dir)

        elif not os.path.isdir(data_dir):
            raise IDKException("'data_dir' is not a directory")

        return data_dir

    def clear_sample_data(self):
        """
        Remove all files from the sample data directory
        """
        data_dir = self.create_data_dir()

        log.debug("Clean all data from %s", data_dir)
        remove_all_files(data_dir)

    def create_sample_data(self, filename, dest_filename=None):
        """
        Search for a data file in the driver resource directory and if the file
        is not found there then search using the filename directly.  Then copy
        the file to the test data directory.

        If a dest_filename is supplied it will be renamed in the destination
        directory.
        @param: filename - filename or path to a data file to copy
        @param: dest_filename - name of the file when copied. default to filename
        """
        data_dir = self.create_data_dir()
        source_path = self._get_source_data_file(filename)

        log.debug("DIR: %s", data_dir)
        if dest_filename is None:
            dest_path = os.path.join(data_dir, os.path.basename(source_path))
        else:
            dest_path = os.path.join(data_dir, dest_filename)

        log.debug("Creating data file src: %s, dest: %s", source_path, dest_path)
        shutil.copy2(source_path, dest_path)

class DataSetUnitTestCase(DataSetTestCase):
    """
    Base class for instrument driver unit tests
    """
    def setUp(self):
        """
        Startup the container and start the agent.
        """
        super(DataSetUnitTestCase, self).setUp()

#class DataSetIntegrationTestCase(DataSetTestCase, ParticleTestMixin):
class DataSetIntegrationTestCase(DataSetTestCase):
    """
    Base class for instrument driver unit tests
    """
    def setUp(self):
        """
        Startup the container and start the agent.
        """
        super(DataSetIntegrationTestCase, self).setUp()

class DataSetQualificationTestCase(DataSetTestCase):
    """
    Base class for instrument driver unit tests
    """
    def setUp(self):
        """
        Startup the container and start the agent.
        """
        super(DataSetQualificationTestCase, self).setUp()

        self.instrument_agent_manager = InstrumentAgentClient()
        self.instrument_agent_manager.start_container(deploy_file=self.test_config.container_deploy_file)

        self.container = self.instrument_agent_manager.container

        log.debug("Packet Config: %s", self.test_config.agent_packet_config)
        self.data_subscribers = InstrumentAgentDataSubscribers(
            packet_config=self.test_config.agent_packet_config,
        )
        self.event_subscribers = InstrumentAgentEventSubscribers(instrument_agent_resource_id=self.test_config.agent_resource_id)

        self.init_dataset_agent_client()

        self.event_subscribers.events_received = []
        self.data_subscribers.start_data_subscribers()

        log.debug("********* setUp complete.  Begin Testing *********")

    def init_dataset_agent_client(self):
        log.info("Start Instrument Agent Client")

        # Start instrument agent client.
        self.instrument_agent_manager.start_client(
            name=self.test_config.agent_name,
            module=self.test_config.agent_module,
            cls=self.test_config.agent_class,
            config=self._agent_config(),
            resource_id=self.test_config.agent_resource_id,
            deploy_file=self.test_config.container_deploy_file
        )

        self.instrument_agent_client = self.instrument_agent_manager.instrument_agent_client

    def assert_initialize(self, final_state = ResourceAgentState.STREAMING):
        '''
        Walk through DSA states to get to streaming mode from uninitialized
        '''
        state = self.instrument_agent_client.get_agent_state()

        with self.assertRaises(Conflict):
            res_state = self.instrument_agent_client.get_resource_state()

        log.debug("Initialize DataSet agent")
        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)
        log.info("Sent INITIALIZE; DSA state = %s", state)

        log.debug("DataSet agent go active")
        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        log.info("Sent GO_ACTIVE; DSA state = %s", state)
        self.assertEqual(state, ResourceAgentState.IDLE)

        log.debug("DataSet agent run")
        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        log.info("Sent RUN; DSA state = %s", state)
        self.assertEqual(state, ResourceAgentState.COMMAND)

        if final_state == ResourceAgentState.STREAMING:
            self.assert_start_sampling()

    def assert_stop_sampling(self):
        '''
        transition to command.  Must be called from streaming
        '''
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.STREAMING)

        log.debug("DataSet agent start sampling")
        cmd = AgentCommand(command=DriverEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)
        state = self.instrument_agent_client.get_agent_state()
        log.info("Sent START SAMPLING; DSA state = %s", state)
        self.assertEqual(state, ResourceAgentState.COMMAND)

    def assert_start_sampling(self):
        '''
        transition to sampling.  Must be called from command
        '''
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        log.debug("DataSet agent start sampling")
        cmd = AgentCommand(command=DriverEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)
        state = self.instrument_agent_client.get_agent_state()
        log.info("Sent START SAMPLING; DSA state = %s", state)
        self.assertEqual(state, ResourceAgentState.STREAMING)

    def assert_reset(self):
        '''
        Put the instrument back in uninitialized
        '''
        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)


