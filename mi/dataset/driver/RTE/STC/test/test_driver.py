"""
@package mi.dataset.driver.RTE.STC.test.test_driver
@file marine-integrations/mi/dataset/driver/RTE/STC/driver.py
@author Jeff Roy
@brief Test cases for rte_o_stc driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.dataset.driver.RTE.STC.driver import RteOStcDataSetDriver
from mi.dataset.parser.rte_o_stc import RteOStcParserDataParticle


# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.RTE.STC.driver',
    driver_class='RteOStcDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = RteOStcDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'rte_o_stc',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: '*.rte.log',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM = 'rte_xx__stc_instrument'

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@unittest.skip('In process of merging with MOPAK')
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
 
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('first_test.data', "RTE0000001.rte.log") 
        self.assert_data(RteOStcParserDataParticle, 'first_test_data.txt.result.yml', count=2, timeout=10)

        self.clear_async_data()
        self.create_sample_data('second_test.data', "RTE0000002.rte.log")
        self.assert_data(RteOStcParserDataParticle, 'second_test_data.txt.result.yml', count=2, timeout=10)

        self.driver.stop_sampling()
        self.driver.start_sampling()


        self.clear_async_data()
        self.create_sample_data('third_test.data', "RTE0000303.rte.log")
        self.assert_data(RteOStcParserDataParticle, count=1, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """

        path_1 = self.create_sample_data('first_test.data', "RTE0000001.rte.log")
        path_2 = self.create_sample_data('second_resume_test.data', "RTE0000002.rte.log")
        
        state = {
            "RTE0000001.rte.log" : self.get_file_state(path_1, True, 546),
            "RTE0000002.rte.log" : self.get_file_state(path_2, False, 152)
        }
        
        self.driver = self._get_driver_object(memento=state)
       
         # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.assert_data(RteOStcParserDataParticle, 'second_resume_test_data.txt.result.yml', count=2, timeout=10)
       

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data('first_test.data', "RTE0000001.rte.log")
        self.create_sample_data('second_test.data', "RTE0000002.rte.log")
        self.assert_data(RteOStcParserDataParticle, 'first_test_data.txt.result.yml', count=2, timeout=10)
        self.assert_file_ingested("RTE0000001.rte.log")
        self.assert_file_not_ingested("RTE0000002.rte.log")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(RteOStcParserDataParticle, 'second_test_data.txt.result.yml', count=2, timeout=10)
        self.assert_file_ingested("RTE0000002.rte.log")


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@unittest.skip('In process of merging with MOPAK')
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    def setUp(self):
        super(QualificationTest, self).setUp()

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        
        self.create_sample_data('full_test.data', "RTE0000001.rte.log")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # slow down processing for tests
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(SAMPLE_STREAM, 5)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, "full_test_data.txt.result.yml")
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data("lots_of_data_test1.data", "RTE0000001.rte.log")
        self.create_sample_data("lots_of_data_test1.data", "RTE0000002.rte.log")
        self.assert_initialize()

        # get results for each of the data particle streams
        result2 = self.get_samples(SAMPLE_STREAM,100,10)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('first_test.data', "RTE0000001.rte.log")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM,2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_test_data.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('second_resume_test.data', "RTE0000002.rte.log")
            # Now read the first record of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 1)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result2 = self.get_samples(SAMPLE_STREAM, 2)
            log.debug("got result 2 %s", result2)
            result.extend(result2)
            self.assert_data_values(result, 'second_restart_test_data.txt.result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")


    def test_shutdown_restart(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('first_test.data', "RTE0000001.rte.log")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM,2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_test_data.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('second_resume_test.data', "RTE0000002.rte.log")
            # Now read the first record of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 1)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
            
            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            
            result2 = self.get_samples(SAMPLE_STREAM, 2)
            log.debug("got result 2 %s", result2)
            result.extend(result2)
            self.assert_data_values(result, 'second_restart_test_data.txt.result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")


