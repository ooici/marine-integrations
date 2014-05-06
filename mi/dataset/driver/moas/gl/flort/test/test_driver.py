"""
@package mi.dataset.driver.moas.gl.flort.test.test_driver
@file marine-integrations/mi/dataset/driver/moas/gl/flort/test/test_driver.py
@author Nick Almonte
@brief Test cases for glider flort data

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Nick Almonte'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from exceptions import Exception

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.idk.exceptions import SampleTimeout

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter

from mi.dataset.driver.moas.gl.flort.driver import FLORTDataSetDriver

from mi.dataset.parser.glider import FlortTelemeteredDataParticle
from pyon.agent.agent import ResourceAgentState

from interface.objects import ResourceAgentErrorEvent

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.moas.gl.flort.driver',
    driver_class="FLORTDataSetDriver",

    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = FLORTDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/florttest',
            DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_florttest',
            DataSetDriverConfigKeys.PATTERN: '*.mrg',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM = 'flort_m_glider_instrument'
    
###############################################################################
#                                UNIT TESTS                                   #
# Device specific unit tests are for                                          #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver sampling
        can be started and stopped.
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('single_glider_record.mrg', "CopyOf-single_glider_record.mrg")
        # Results file, Number of Particles (rows) expected to compare, timeout
        self.assert_data(FlortTelemeteredDataParticle, 'single_flort_record.mrg.result.yml', count=1, timeout=10)

        self.clear_async_data()
        self.create_sample_data('multiple_glider_record.mrg', "CopyOf-multiple_glider_record.mrg")
        # Results file, Number of Particles (rows) expected to compare, timeout
        self.assert_data(FlortTelemeteredDataParticle, 'multiple_flort_record.mrg.result.yml', count=4, timeout=10)

        log.debug("IntegrationTest.test_get(): Start second file ingestion")
        self.clear_async_data()
        self.create_sample_data('unit_247_2012_051_0_0-sciDataOnly.mrg', "CopyOf-unit_247_2012_051_0_0-sciDataOnly.mrg")
        self.assert_data(FlortTelemeteredDataParticle, count=115, timeout=30)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data('single_glider_record.mrg', "CopyOf-single_glider_record.mrg")
        path_2 = self.create_sample_data('multiple_glider_record.mrg', "CopyOf-multiple_glider_record.mrg")

        # Create and store the new driver state
        state = {
            'CopyOf-single_glider_record.mrg': self.get_file_state(path_1, True, 1160),
            'CopyOf-multiple_glider_record.mrg': self.get_file_state(path_2, False, 10537)
        }
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(FlortTelemeteredDataParticle, 'merged_flort_record.mrg.result.yml', count=3, timeout=10)

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data('single_glider_record.mrg', "CopyOf-single_glider_record.mrg")
        self.create_sample_data('multiple_glider_record.mrg', "xCopyOf-multiple_glider_record.mrg")
        self.assert_data(FlortTelemeteredDataParticle, 'single_flort_record.mrg.result.yml', count=1, timeout=10)
        self.assert_file_ingested("CopyOf-single_glider_record.mrg")
        self.assert_file_not_ingested("xCopyOf-multiple_glider_record.mrg")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(FlortTelemeteredDataParticle, 'multiple_flort_record.mrg.result.yml', count=4, timeout=10)
        self.assert_file_ingested("xCopyOf-multiple_glider_record.mrg")

    def test_bad_sample(self):
        """
        Test a bad sample.  To do this we set a state to the middle of a record
        """
        # create some data to parse
        self.clear_async_data()

        path = self.create_sample_data('multiple_glider_record.mrg', "CopyOf-multiple_glider_record.mrg")

        # Create and store the new driver state
        state = {
            'CopyOf-multiple_glider_record.mrg': self.get_file_state(path, False, 12167),
        }
        self.driver = self._get_driver_object(memento=state)

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(FlortTelemeteredDataParticle, 'bad_sample_flort_record.mrg.result.yml', count=1, timeout=10)
        self.assert_file_ingested("CopyOf-multiple_glider_record.mrg")

    def test_sample_exception(self):
        """
        test that a file is marked as parsed if it has a sample exception (which will happen with an empty file)
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester']['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data(filename)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    def setUp(self):
        super(QualificationTest, self).setUp()

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('single_glider_record.mrg', 'CopyOf-single_glider_record.mrg')
        self.assert_initialize()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_flort_record.mrg.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """

        self.create_sample_data('unit_247_2012_051_0_0-sciDataOnly.mrg')
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM, 115, 120)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('single_glider_record.mrg', "CopyOf-single_glider_record.mrg")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_flort_record.mrg.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('multiple_glider_record.mrg', "CopyOf-multiple_glider_record.mrg")
            # Now read the first three records of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 1)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 5 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 3)
            log.debug("got result 2 %s", result)
            self.assert_data_values(result, 'merged_flort_record.mrg.result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test the agents ability to completely stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('single_glider_record.mrg', "CopyOf-single_glider_record.mrg")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_flort_record.mrg.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('multiple_glider_record.mrg', "CopyOf-multiple_glider_record.mrg")
            # Now read the first records of the second file then stop
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
            # Restart sampling and ensure we get the last 5 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 3)
            log.debug("got result 2 %s", result)
            self.assert_data_values(result, 'merged_flort_record.mrg.result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        self.create_sample_data('unit_363_2013_245_7_7.mrg')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        self.assert_sample_queue_size(SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
