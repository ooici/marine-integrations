#! /usr/bin/env python

"""
@file coi-services/ion/idk/data_set_agent/unit_test.py
@author Bill French
@brief Base classes for data set agent tests.
"""
import os
from mi.core.log import get_logger ; log = get_logger()

from mi.core.unit_test import MiIntTestCase

from mi.idk.unit_test import InstrumentDriverTestConfig
from mi.idk.exceptions import TestNotInitialized

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
    agent_module = 'ion.agents.data.dataset_agent'
    agent_class = 'DataSetAgent'

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

    TEST_DATA_1 = """
* Sea-Bird SBE52 MP Data File *

*** Starting profile number 3 ***
07/26/2013 21:01:03
GPS1: 
GPS2: 
 10.5914,  4.1870,  161.06,   2693.0
 11.5912,  4.1875,  161.06,   2709.0
 12.5912,  4.1870,  161.08,   2716.1
 13.5913,  4.1872,  161.09,   2723.5
 14.5912,  4.1869,  161.10,   2727.3
 15.5912,  4.1867,  161.10,   2731.8
 16.5914,  4.1870,  161.09,   2733.4
 17.5913,  4.1866,  161.08,   2738.1
 18.5914,  4.1863,  161.08,   2739.1
 19.5912,  4.1862,  161.06,   2740.1
"""

    TEST_DATA_2 = """
* Sea-Bird SBE52 MP Data File *

*** Starting profile number 3 ***
07/26/2013 21:01:03
GPS1: 
GPS2: 
 20.5914,  4.1870,  161.06,   2693.0
 21.5912,  4.1875,  161.06,   2709.0
 22.5912,  4.1870,  161.08,   2716.1
 23.5913,  4.1872,  161.09,   2723.5
 24.5912,  4.1869,  161.10,   2727.3
 25.5912,  4.1867,  161.10,   2731.8
 26.5914,  4.1870,  161.09,   2733.4
 27.5913,  4.1866,  161.08,   2738.1
"""

    TEST_DATA_LONG = """
* Sea-Bird SBE52 MP Data File *

*** Starting profile number 3 ***
07/26/2013 21:01:03
GPS1: 
GPS2: 
 300.5914,  4.1870,  161.06,   2693.0
 301.5912,  4.1875,  161.06,   2709.0
 302.5912,  4.1870,  161.08,   2716.1
 303.5913,  4.1872,  161.09,   2723.5
 304.5912,  4.1869,  161.10,   2727.3
 305.5912,  4.1867,  161.10,   2731.8
 306.5914,  4.1870,  161.09,   2733.4
 307.5913,  4.1866,  161.08,   2738.1
 308.5914,  4.1870,  161.06,   2693.0
 309.5912,  4.1875,  161.06,   2709.0
 310.5912,  4.1870,  161.08,   2716.1
 311.5913,  4.1872,  161.09,   2723.5
 312.5912,  4.1869,  161.10,   2727.3
 313.5912,  4.1867,  161.10,   2731.8
 314.5914,  4.1870,  161.09,   2733.4
 315.5913,  4.1866,  161.08,   2738.1
 316.5914,  4.1870,  161.06,   2693.0
 317.5912,  4.1875,  161.06,   2709.0
 318.5912,  4.1870,  161.08,   2716.1
 319.5913,  4.1872,  161.09,   2723.5
 320.5912,  4.1869,  161.10,   2727.3
 321.5912,  4.1867,  161.10,   2731.8
 322.5914,  4.1870,  161.09,   2733.4
 323.5913,  4.1866,  161.08,   2738.1
 324.5912,  4.1867,  161.10,   2731.8
 325.5914,  4.1870,  161.09,   2733.4
 326.5913,  4.1866,  161.08,   2738.1
 327.5912,  4.1867,  161.10,   2731.8
 328.5914,  4.1870,  161.09,   2733.4
 329.5913,  4.1866,  161.08,   2738.1
 330.5912,  4.1867,  161.10,   2731.8
 331.5914,  4.1870,  161.09,   2733.4
 332.5913,  4.1866,  161.08,   2738.1
 333.5912,  4.1867,  161.10,   2731.8
 334.5914,  4.1870,  161.09,   2733.4
 335.5913,  4.1866,  161.08,   2738.1
"""

    TESTDIR = '/tmp/dsatest'


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
            'agent': {'resource_id': self.test_config.agent_resource_id}
        }
        return config
    
    def create_sample_data(self):
        """
        Create some test data: Some files with some lines in them. Leave room
        for individual test cases to insert files at the beginning of the sequence
        """
        log.debug("Creating test file directory: %s", self.TESTDIR)
        if(not os.path.exists(self.TESTDIR)):
            os.makedirs(self.TESTDIR)
    
        log.debug("Creating test file: %s/DAT0003.txt", self.TESTDIR)
        fh = open(os.path.join(self.TESTDIR, "DAT0003.txt"), 'a')
        fh.write(self.TEST_DATA_1)
        fh.close()
        
        log.debug("Creating test file: %s/DAT0004.txt", self.TESTDIR)
        fh = open(os.path.join(self.TESTDIR, "DAT0004.txt"), 'a')
        fh.write(self.TEST_DATA_2)
        fh.close()
        
        log.debug("Creating test file: %s/DAT0005.txt", self.TESTDIR)
        fh = open(os.path.join(self.TESTDIR, "DAT0005.txt"), 'a')
        fh.write(self.TEST_DATA_LONG)
        fh.close()


class DataSetUnitTestCase(DataSetTestCase):
    """
    Base class for instrument driver unit tests
    """
    def setUp(self):
        """
        Startup the container and start the agent.
        """
        super(DataSetUnitTestCase, self).setUp()

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

        #log.debug("Packet Config: %s", self.test_config.agent_packet_config)
        #self.data_subscribers = InstrumentAgentDataSubscribers(
        #    packet_config=self.test_config.agent_packet_config,
        #)

        self.init_dataset_agent_client()

        #self.event_subscribers.events_received = []
        #self.data_subscribers.start_data_subscribers()

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


