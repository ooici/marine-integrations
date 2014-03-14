"""
@package mi.dataset.driver.MOPAK.STC.test.test_driver
@file marine-integrations/mi/dataset/driver/MOPAK/STC/driver.py
@author Emily Hahn
@brief Test cases for MOPAK__STC driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Emily Hahn'
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

from mi.dataset.driver.MOPAK.STC.driver import MOPAK__STC_DataSetDriver
from mi.dataset.parser.mopak__stc import Mopak__stcAccelParserDataParticle, Mopak__stcRateParserDataParticle, DataParticleType
from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.MOPAK.STC.driver',
    driver_class='MOPAK__STC_DataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = MOPAK__STC_DataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'mopak__stc',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: '*.mopak.log',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)


###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
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
        self.create_sample_data('first.mopak.log', "20140120_140004.mopak.log")
        self.assert_data_multiple_class('first.result.yml', count=5, timeout=10)

        self.clear_async_data()
        self.create_sample_data('second.mopak.log', "20140120_150004.mopak.log")
        self.assert_data_multiple_class('second.result.yml', count=2, timeout=10)

    def test_get_rate(self):
        """
        Make a second test_get which uses a files having both accel and rate particles
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('first_rate.mopak.log', "20140313_191853.mopak.log")
        self.assert_data_multiple_class('first_rate.result.yml', count=6, timeout=10)

        self.clear_async_data()
        self.create_sample_data('second_rate.mopak.log', "20140313_201853.mopak.log")
        self.assert_data_multiple_class('second_rate.result.yml', count=3, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data('first.mopak.log', "20140120_140004.mopak.log")
        path_2 = self.create_sample_data('second.mopak.log', "20140120_150004.mopak.log")

        # Create and store the new driver state
        state = {
            "20140120_140004.mopak.log": self.get_file_state(path_1, False, 172),
            "20140120_150004.mopak.log": self.get_file_state(path_2, False, 0)
        }
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data_multiple_class('partial_first_second.result.yml', count=3, timeout=10)

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data('first.mopak.log', "20140120_140004.mopak.log")
        self.create_sample_data('second.mopak.log', "20140120_150004.mopak.log")
        self.assert_data_multiple_class('first.result.yml', count=5, timeout=10)
        self.assert_file_ingested("20140120_140004.mopak.log")
        self.assert_file_not_ingested("20140120_150004.mopak.log")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data_multiple_class('second.result.yml', count=2, timeout=10)
        self.assert_file_ingested("20140120_150004.mopak.log")

    def test_sample_exception(self):
        """
        test that a file is marked as parsed if it has a sample exception, which will
        happen if we have noise in the file
        """
        self.clear_async_data()

        self.create_sample_data('noise.mopak.log', "20140120_140004.mopak.log")

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested("20140120_140004.mopak.log")

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('first.mopak.log', "20140120_140004.mopak.log")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # NOTE: If the processing is not slowed down here, the samples are returned
        # in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.ACCEL, 5)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_publish_path_rate(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('first_rate.mopak.log', "20140313_191853.mopak.log")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # NOTE: If the processing is not slowed down here, the samples are returned
        # in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.ACCEL, 2)
            result2 = self.data_subscribers.get_samples(DataParticleType.RATE, 4)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_rate.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        config = self._driver_config()['startup_config']['harvester']['pattern']
        # need to override this from base unit test class to not use 'foo' text,
        # which produces an error since the name is needed to parse the file
        filename = config.replace("*", "20140313_191853")

        self.assert_new_file_exception(filename)

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data("20140120_140004.mopak.log")
        self.assert_initialize()

        # get results for each of the data particle streams
        result = self.get_samples(DataParticleType.ACCEL,11964,480)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('first_qual.mopak.log', "20140120_140004.mopak.log")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(DataParticleType.ACCEL, 3)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_qual.result.yml')
            self.assert_sample_queue_size(DataParticleType.ACCEL, 0)

            self.create_sample_data('second_qual.mopak.log', "20140120_150004.mopak.log")
            # Now read the first three records of the second file then stop
            result = self.get_samples(DataParticleType.ACCEL, 2)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.ACCEL, 0)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result2 = self.get_samples(DataParticleType.ACCEL, 2)
            log.debug("got result 2 %s", result2)
            result.extend(result2)
            self.assert_data_values(result, 'second_qual.result.yml')

            self.assert_sample_queue_size(DataParticleType.ACCEL, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('first_rate.mopak.log', "20140313_191853.mopak.log")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(DataParticleType.ACCEL, 2)
            result2 = self.data_subscribers.get_samples(DataParticleType.RATE, 4)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_rate.result.yml')
            self.assert_sample_queue_size(DataParticleType.ACCEL, 0)
            self.assert_sample_queue_size(DataParticleType.RATE, 0)

            self.create_sample_data('second_rate.mopak.log', "20140313_201853.mopak.log")
            # Now read the first three records of the second file then stop
            result = self.get_samples(DataParticleType.RATE, 1)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.ACCEL, 0)
            self.assert_sample_queue_size(DataParticleType.RATE, 0)
            
            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result2 = self.get_samples(DataParticleType.RATE, 2)
            log.debug("got result 2 %s", result2)
            result.extend(result2)
            self.assert_data_values(result, 'second_rate.result.yml')

            self.assert_sample_queue_size(DataParticleType.ACCEL, 0)
            self.assert_sample_queue_size(DataParticleType.RATE, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        # file contains invalid sample values
        self.create_sample_data('noise.mopak.log', "20140120_140004.mopak.log")

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(DataParticleType.ACCEL, 5)
        self.assert_sample_queue_size(DataParticleType.ACCEL, 0)
        
        self.assert_data_values(result, 'first.result.yml')

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

