"""
@package mi.dataset.driver.moas.gl.ctdgv.test.test_driver
@file marine-integrations/mi/dataset/driver/moas/gl/ctdgv/test/test_driver.py
@author Bill French
@brief Test cases for glider ctd data

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import gevent
import unittest
import os

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from exceptions import Exception

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.idk.exceptions import SampleTimeout

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter

from mi.dataset.driver.moas.gl.ctdgv.driver import CTDGVDataSetDriver

from mi.dataset.parser.glider import CtdgvDataParticle
from pyon.agent.agent import ResourceAgentState

from interface.objects import ResourceAgentErrorEvent

DATADIR='/tmp/dsatest'
STORAGEDIR='/tmp/stored_dsatest'
RESOURCE_ID='ctdgv'

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.moas.gl.ctdgv.driver',
    driver_class="CTDGVDataSetDriver",

    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = CTDGVDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: RESOURCE_ID,
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: DATADIR,
            DataSetDriverConfigKeys.STORAGE_DIRECTORY: STORAGEDIR,
            DataSetDriverConfigKeys.PATTERN: '*.mrg',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM='ctdgv_m_glider_instrument'
    
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
        self.create_sample_data('single_ctdgv_record.mrg', "unit_363_2013_245_6_6.mrg")
        self.assert_data(CtdgvDataParticle, 'single_ctdgv_record.mrg.result.yml', count=1, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_6_6.mrg")

        self.clear_async_data()
        self.create_sample_data('multiple_ctdgv_record.mrg', "unit_363_2013_245_7_6.mrg")
        self.assert_data(CtdgvDataParticle, 'multiple_ctdgv_record.mrg.result.yml', count=4, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_7_6.mrg")

        log.debug("Start second file ingestion")
        # Verify sort order isn't ascii, but numeric
        self.clear_async_data()
        self.create_sample_data('unit_363_2013_245_6_6.mrg', "CopyOf-unit_363_2013_245_6_6.mrg")
        self.assert_data(CtdgvDataParticle, count=240, timeout=30)
        self.assert_file_ingested("CopyOf-unit_363_2013_245_6_6.mrg")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data('single_ctdgv_record.mrg', "unit_363_2013_245_6_8.mrg")
        path_2 = self.create_sample_data('multiple_ctdgv_record.mrg', "unit_363_2013_245_6_9.mrg")

        # Create and store the new driver state
        state = {
            'unit_363_2013_245_6_8.mrg': self.get_file_state(path_1, True, 1160),
            'unit_363_2013_245_6_9.mrg': self.get_file_state(path_2, False, 2600)
        }
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(CtdgvDataParticle, 'merged_ctdgv_record.mrg.result.yml', count=3, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_6_9.mrg")

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data('single_ctdgv_record.mrg', "unit_363_2013_245_6_6.mrg")
        self.create_sample_data('multiple_ctdgv_record.mrg', "unit_363_2013_245_7_6.mrg")
        self.assert_data(CtdgvDataParticle, 'single_ctdgv_record.mrg.result.yml', count=1, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_6_6.mrg")
        self.assert_file_not_ingested("unit_363_2013_245_7_6.mrg")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(CtdgvDataParticle, 'multiple_ctdgv_record.mrg.result.yml', count=4, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_7_6.mrg")

    def test_bad_sample(self):
        """
        Test a bad sample.  To do this we set a state to the middle of a record
        """
        # create some data to parse
        self.clear_async_data()

        path = self.create_sample_data('multiple_ctdgv_record.mrg', "unit_363_2013_245_6_9.mrg")

        # Create and store the new driver state - middle of a row
        state = {
            'unit_363_2013_245_6_9.mrg': self.get_file_state(path, False, 2506),
        }
        self.driver = self._get_driver_object(memento=state)

        self.driver.start_sampling()

        # verify data is produced - parser skips past the bad row and parses the next three successfully
        self.assert_data(CtdgvDataParticle, 'bad_sample_ctdgv_record.mrg.result.yml', count=3, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_6_9.mrg")

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

    @unittest.skip('skip until this feature is implemented')
    def test_missing_storage(self):
        """
        Verify that we can work when the storage directory doesn't exists
        """
        ###
        # Directory doesn't exist, but we have write permissions
        ###
        log.debug("Test ingest if storage directory doesn't exist")
        self.clear_async_data()
        if os.path.isdir(STORAGEDIR):
            os.rmdir(STORAGEDIR)

        storage_dir = os.path.join(STORAGEDIR, DATADIR.lstrip('/'))

        source_file = "multiple_ctdgv_record.mrg"
        dest_file_1 ="unit_363_2013_245_6_9.mrg"
        dest_file_2 ="unit_363_2013_245_6_10.mrg"
        dest_file_3 ="unit_363_2013_245_6_11.mrg"
        dest_file_4 ="unit_363_2013_245_6_12.mrg"
        result_file = "multiple_ctdgv_record.mrg.result.yml"

        path = self.create_sample_data(source_file, dest_file_1)
        self.driver = self._get_driver_object()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(CtdgvDataParticle, result_file, count=4, timeout=10)

        dest_path_1 = os.path.join(storage_dir, "%s.%s" % (dest_file_1, RESOURCE_ID))
        log.debug("Dest Path 1: %s", dest_path_1)

        # verify the file was staged properly
        self.assertTrue(os.path.exists(dest_path_1))

        ###
        # Directory doesn't exist and we have no write permission in the directory
        ###
        log.debug("Test ingest if storage directory with bad permissions")
        self.clear_async_data()
        self.clear_sample_data()
        path = self.create_sample_data(source_file, dest_file_2)
        new_storagedir = os.path.join(STORAGEDIR, 'newdir')

        if os.path.isdir(STORAGEDIR):
            os.rmdir(STORAGEDIR)

        def cleandir():
            try:
                os.rmdir(STORAGEDIR)
            except:
                pass

            try:
                os.unlink(STORAGEDIR)
            except:
                pass

        self.addCleanup(cleandir)
        self.addCleanup(self.clear_sample_data)

        os.makedirs(STORAGEDIR, mode=0000)

        config = self._driver_config()['startup_config']
        config[DataSourceConfigKey.HARVESTER][DataSetDriverConfigKeys.STORAGE_DIRECTORY] = new_storagedir
        self._get_driver_object(config=config)
        self.driver.start_sampling()

        self.assert_data(CtdgvDataParticle, result_file, count=4, timeout=10)

        self.assertFalse(os.path.exists(new_storagedir))
        os.rmdir(STORAGEDIR)

        ###
        # Path exists, but it is a file not a directory
        ###
        log.debug("Test ingest if storage directory exists, but is a file")
        self.clear_async_data()
        self.clear_sample_data()
        path = self.create_sample_data(source_file, dest_file_3)
        if os.path.isdir(STORAGEDIR):
            os.rmdir(STORAGEDIR)

        with file(STORAGEDIR, 'a'):
            os.utime(STORAGEDIR, None)

        self._get_driver_object()
        self.driver.start_sampling()

        self.assert_data(CtdgvDataParticle, result_file, count=4, timeout=10)

        self.assertTrue(os.path.isfile(STORAGEDIR))

        ###
        # Destination file already exists.  Make sure it isn't overwritten
        ###
        log.debug("Test ingest ensure file isn't overwritten")
        self.clear_async_data()
        self.clear_sample_data()

        dest_path_4 = os.path.join(storage_dir, "%s.%s" % (dest_file_4, RESOURCE_ID))
        os.unlink(STORAGEDIR)
        self.assertFalse(os.path.exists(STORAGEDIR))

        log.debug("Making directories: %s", storage_dir)
        os.makedirs(storage_dir)

        # Write a file.
        with open(dest_path_4, 'a') as outfile:
            outfile.write("Hello")

        self.assertTrue(os.path.isfile(dest_path_4))

        path = self.create_sample_data(source_file, dest_file_4)
        self.driver = self._get_driver_object()

        self.driver.start_sampling()

        self.assert_data(CtdgvDataParticle, count=4, timeout=10)

        # verify the file was staged properly
        self.assertTrue(os.path.exists(dest_path_4))

        content = None
        with open(dest_path_4) as infile:
            content = infile.readlines()
        self.assertEqual(["Hello"], content)

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
        self.create_sample_data('single_ctdgv_record.mrg', 'unit_363_2013_245_6_9.mrg')
        self.assert_initialize()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """
        self.create_sample_data('unit_363_2013_245_6_6.mrg')
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,171,120)

    def test_lost_connection(self):
        """
        Test a parser exception and verify that the lost connection logic works
        """
        self.assert_initialize()

        path = self.create_sample_data('single_ctdgv_record.mrg', 'unit_363_2013_245_6_9.mrg', mode=0000)

        self.assert_state_change(ResourceAgentState.LOST_CONNECTION)

        # Sleep long enough to let the first reconnect happen and fail again.
        gevent.sleep(30)

        # Resolve the issue
        os.chmod(path, 0755)

        # We should transition back to streaming and stay there.
        self.assert_state_change(ResourceAgentState.STREAMING, timeout=180)

        result = self.data_subscribers.get_samples(SAMPLE_STREAM)
        self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('single_ctdgv_record.mrg', "unit_363_2013_245_6_6.mrg")

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
            self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('multiple_ctdgv_record.mrg', "unit_363_2013_245_7_6.mrg")
            # Now read the first three records of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 1)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 5 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 4)
            log.debug("got result 2 %s", result)
            #self.assert_data_values(result, 'merged_ctdgv_record.mrg.result.yml')
            self.assert_data_values(result, 'multiple_ctdgv_record.mrg.stopstartresult.yml')

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
        self.create_sample_data('single_ctdgv_record.mrg', "unit_363_2013_245_6_6.mrg")

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
            self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('multiple_ctdgv_record-shutdownrestart.mrg', "unit_363_2013_245_7_6.mrg")
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
            result = self.get_samples(SAMPLE_STREAM, 4)
            log.debug("got result 2 %s", result)
            #self.assert_data_values(result, 'multiple_ctdgv_record.mrg.shutdownrestartresult.yml')
            self.assert_data_values(result, 'multiple_ctdgv_record.mrg.stopstartresult.yml')

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
