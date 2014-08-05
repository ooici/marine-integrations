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
from mi.dataset.driver.moas.gl.ctdgv.driver import DataTypeKey

from mi.dataset.parser.glider import CtdgvTelemeteredDataParticle, CtdgvRecoveredDataParticle, DataParticleType

from pyon.agent.agent import ResourceAgentState

from interface.objects import ResourceAgentErrorEvent

TELEMETERED_TEST_DIR = '/tmp/ctdgvTelemeteredTest'
RECOVERED_TEST_DIR = '/tmp/ctdgvRecoveredTest'

DataSetTestCase.initialize(

    driver_module='mi.dataset.driver.moas.gl.ctdgv.driver',
    driver_class="CTDGVDataSetDriver",
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=CTDGVDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'ctdgv',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.CTDGV_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TELEMETERED_TEST_DIR,
                DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_ctdgvTelemeteredTest',
                DataSetDriverConfigKeys.PATTERN: '*.mrg',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.CTDGV_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: RECOVERED_TEST_DIR,
                DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_ctdgvRecoveredTest',
                DataSetDriverConfigKeys.PATTERN: '*.mrg',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.CTDGV_TELEMETERED: {}, DataTypeKey.CTDGV_RECOVERED: {}
        }
    }

)

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
        self.create_sample_data_set_dir('single_ctdgv_record.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "unit_363_2013_245_6_6.mrg")
        self.assert_data(CtdgvTelemeteredDataParticle,
                         'single_ctdgv_record.mrg.result.yml',
                         count=1, timeout=10)

        self.clear_async_data()
        self.create_sample_data_set_dir('multiple_ctdgv_record.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "unit_363_2013_245_7_6.mrg")
        self.assert_data(CtdgvTelemeteredDataParticle,
                         'multiple_ctdgv_record.mrg.result.yml',
                         count=4, timeout=10)


        self.clear_async_data()
        self.create_sample_data_set_dir('single_ctdgv_record.mrg',
                                        RECOVERED_TEST_DIR,
                                        "unit_363_2013_245_6_6_rec.mrg")
        self.assert_data(CtdgvRecoveredDataParticle,
                         'single_ctdgv_record_recovered.mrg.result.yml',
                         count=1, timeout=10)

        self.clear_async_data()
        self.create_sample_data_set_dir('multiple_ctdgv_record.mrg',
                                        RECOVERED_TEST_DIR,
                                        "unit_363_2013_245_7_6.mrg")
        self.assert_data(CtdgvRecoveredDataParticle,
                         'multiple_ctdgv_record_recovered.mrg.result.yml',
                         count=4, timeout=10)


        log.debug("Start second file ingestion - Telemetered")
        # Verify sort order isn't ascii, but numeric
        self.clear_async_data()
        self.create_sample_data_set_dir('unit_363_2013_245_6_6.mrg',
                                        TELEMETERED_TEST_DIR,
                                        'unit_363_2013_245_10_6.mrg')
        self.assert_data(CtdgvTelemeteredDataParticle, count=115, timeout=30)

        log.debug("Start second file ingestion - Recovered")
        # Verify sort order isn't ascii, but numeric
        self.clear_async_data()
        self.create_sample_data_set_dir('unit_363_2013_245_6_6.mrg',
                                        RECOVERED_TEST_DIR,
                                        "unit_363_2013_245_10_6.mrg")
        self.assert_data(CtdgvRecoveredDataParticle, count=115, timeout=30)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data_set_dir('single_ctdgv_record.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_6_8.mrg")
        path_2 = self.create_sample_data_set_dir('multiple_ctdgv_record.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_6_9.mrg")
        path_3 = self.create_sample_data_set_dir('single_ctdgv_record.mrg', RECOVERED_TEST_DIR, "unit_363_2013_245_6_8.mrg")
        path_4 = self.create_sample_data_set_dir('multiple_ctdgv_record.mrg', RECOVERED_TEST_DIR, "unit_363_2013_245_6_9.mrg")

        # Create and store the new driver state
        state = {
            DataTypeKey.CTDGV_TELEMETERED: {
            'unit_363_2013_245_6_8.mrg': self.get_file_state(path_1, True, 1160),
            'unit_363_2013_245_6_9.mrg': self.get_file_state(path_2, False, 2600)
            },
            DataTypeKey.CTDGV_RECOVERED: {
            'unit_363_2013_245_6_8.mrg': self.get_file_state(path_3, True, 1160),
            'unit_363_2013_245_6_9.mrg': self.get_file_state(path_4, False, 2600)
            }
        }
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced for telemetered particle
        self.assert_data(CtdgvTelemeteredDataParticle, 'merged_ctdgv_record.mrg.result.yml', count=3, timeout=10)

        # verify data is produced for recovered particle
        self.assert_data(CtdgvRecoveredDataParticle, 'merged_ctdgv_record_recovered.mrg.result.yml', count=3, timeout=10)

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data_set_dir('single_ctdgv_record.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_6_6.mrg")
        self.create_sample_data_set_dir('multiple_ctdgv_record-1234.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_7_6.mrg")
        self.assert_data(CtdgvTelemeteredDataParticle, 'single_ctdgv_record.mrg.result.yml', count=1, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_6_6.mrg", DataTypeKey.CTDGV_TELEMETERED)
        self.assert_file_not_ingested("unit_363_2013_245_7_6.mrg")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(CtdgvTelemeteredDataParticle, 'multiple_ctdgv_record.mrg.result.yml', count=4, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_7_6.mrg", DataTypeKey.CTDGV_TELEMETERED)

        ####
        ## Repeat for Recovered Particle
        ####
        self.create_sample_data_set_dir('single_ctdgv_record.mrg', RECOVERED_TEST_DIR, "unit_363_2013_245_6_6.mrg")
        self.create_sample_data_set_dir('multiple_ctdgv_record-1234.mrg', RECOVERED_TEST_DIR, "unit_363_2013_245_7_6.mrg")
        self.assert_data(CtdgvRecoveredDataParticle, 'single_ctdgv_record_recovered.mrg.result.yml', count=1, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_6_6.mrg", DataTypeKey.CTDGV_RECOVERED)
        self.assert_file_not_ingested("unit_363_2013_245_7_6.mrg")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(CtdgvRecoveredDataParticle, 'multiple_ctdgv_record_recovered.mrg.result.yml', count=4, timeout=10)
        self.assert_file_ingested("unit_363_2013_245_7_6.mrg", DataTypeKey.CTDGV_RECOVERED)

    def test_bad_sample(self):
        """
        Test a bad sample.  To do this we set a state to the middle of a record
        """
        path_2 = self.create_sample_data_set_dir('multiple_ctdgv_record.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_6_9.mrg")
        path_4 = self.create_sample_data_set_dir('multiple_ctdgv_record.mrg', RECOVERED_TEST_DIR, "unit_363_2013_245_6_9.mrg")

        # Create and store the new driver state
        state = {
            DataTypeKey.CTDGV_TELEMETERED: {
             'unit_363_2013_245_6_9.mrg': self.get_file_state(path_2, False, 2506)
            },
            DataTypeKey.CTDGV_RECOVERED: {
            'unit_363_2013_245_6_9.mrg': self.get_file_state(path_4, False, 2506)
            }
        }
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced for telemetered particle - parser skips past the bad row and parses the next
        # three successfully
        self.assert_data(CtdgvTelemeteredDataParticle, 'merged_ctdgv_record.mrg.result.yml', count=3, timeout=10)

        # verify data is produced for recovered particle - parser skips past the bad row and parses the next
        # three successfully
        self.assert_data(CtdgvRecoveredDataParticle, 'merged_ctdgv_record_recovered.mrg.result.yml', count=3, timeout=10)

    def test_sample_exception_telemetered(self):
        """
        test that a file is marked as parsed if it has a sample exception (which will happen with an empty file)
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester'][DataTypeKey.CTDGV_TELEMETERED]['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data_set_dir(filename, TELEMETERED_TEST_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename, DataTypeKey.CTDGV_TELEMETERED)

    def test_sample_exception_recovered(self):
        """
        test that a file is marked as parsed if it has a sample exception (which will happen with an empty file)
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester'][DataTypeKey.CTDGV_RECOVERED]['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data_set_dir(filename, RECOVERED_TEST_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename, DataTypeKey.CTDGV_RECOVERED)


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
        self.create_sample_data_set_dir('single_ctdgv_record.mrg', TELEMETERED_TEST_DIR, 'unit_363_2013_245_6_9.mrg')
        self.assert_initialize()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 1)
            log.debug("Telemetered RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        # Again for the recovered particle
        self.create_sample_data_set_dir('single_ctdgv_record.mrg', RECOVERED_TEST_DIR, 'unit_363_2013_245_6_9.mrg')

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 1)
            log.debug("Recovered RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_ctdgv_record_recovered.mrg.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """
        self.create_sample_data_set_dir('unit_363_2013_245_6_6.mrg', TELEMETERED_TEST_DIR)
        self.assert_initialize()

        result1 = self.data_subscribers.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 117, 120)

        # again for recovered
        self.create_sample_data_set_dir('unit_363_2013_245_6_6.mrg', RECOVERED_TEST_DIR)
        result2 = self.data_subscribers.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 117, 120)

    def test_lost_connection_telemetered(self):
        """
        Test a parser exception and verify that the lost connection logic works
        """
        self.assert_initialize()

        path = self.create_sample_data_set_dir('single_ctdgv_record.mrg', TELEMETERED_TEST_DIR, 'unit_363_2013_245_6_9.mrg', mode=0000)

        self.assert_state_change(ResourceAgentState.LOST_CONNECTION)

        # Sleep long enough to let the first reconnect happen and fail again.
        gevent.sleep(30)

        # Resolve the issue
        os.chmod(path, 0755)

        # We should transition back to streaming and stay there.
        self.assert_state_change(ResourceAgentState.STREAMING, timeout=180)

        result = self.data_subscribers.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT)
        self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')

    def test_lost_connection_recovered(self):
        """
        Test a parser exception and verify that the lost connection logic works
        """
        self.assert_initialize()

        path = self.create_sample_data_set_dir('single_ctdgv_record.mrg', RECOVERED_TEST_DIR, 'unit_363_2013_245_6_9.mrg', mode=0000)

        self.assert_state_change(ResourceAgentState.LOST_CONNECTION)

        # Sleep long enough to let the first reconnect happen and fail again.
        gevent.sleep(30)

        # Resolve the issue
        os.chmod(path, 0755)

        # We should transition back to streaming and stay there.
        self.assert_state_change(ResourceAgentState.STREAMING, timeout=180)

        result = self.data_subscribers.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED)
        self.assert_data_values(result, 'single_ctdgv_record_recovered.mrg.result.yml')

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("## ## ## CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('single_ctdgv_record.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_6_6.mrg")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT)
            log.debug("## ## ## RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 0)


            # Stop sampling: Telemetered
            self.create_sample_data_set_dir('multiple_ctdgv_record.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_7_6.mrg")
            # Now read the first three records of the second file then stop
            result = self.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 1)
            log.debug("## ## ## Got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 0)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result = self.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 3)
            log.debug("got result 2 %s", result)
            self.assert_data_values(result, 'multiple_ctdgv_record-234.mrg.result.yml')
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 0)


            #Stop sampling: Recovered
            self.create_sample_data_set_dir('multiple_ctdgv_record.mrg', RECOVERED_TEST_DIR, "unit_363_2013_245_7_6.mrg")
            # Now read the first three records of the second file then stop
            result = self.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 1)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 0)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result = self.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 3)
            log.debug("got result 2 %s", result)
            self.assert_data_values(result, 'multiple_ctdgv_record_recovered-234.mrg.result.yml')
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test the agents ability to completely stop, then restart
        at the correct spot.
        """
        log.info("## ## ## CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('single_ctdgv_record.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_6_6.mrg")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT)
            log.debug("## ## ## RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 0)


            # Restart sampling: Telemetered
            self.create_sample_data_set_dir('multiple_ctdgv_record.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_7_6.mrg")
            # Now read the first record of the second file then stop
            result = self.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 1)
            log.debug("## ## ## Got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 0)

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Slow down processing to 1 per second to give us time to stop
            self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})

            # Restart sampling and ensure we get the next 3 records of the file
            self.assert_start_sampling()
            result = self.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 3)
            log.debug("got result 2 %s", result)
            self.assert_data_values(result, 'multiple_ctdgv_record-234.mrg.result.yml')
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 0)


            # Restart sampling: Recovered
            self.create_sample_data_set_dir('multiple_ctdgv_record-shutdown_restart.mrg', RECOVERED_TEST_DIR, "unit_363_2013_245_7_66.mrg")
            # Now read the first record of the second file then stop
            result = self.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 1)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 0)

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the next 3 records of the file
            self.assert_start_sampling()
            result = self.get_samples(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 3)
            log.debug("got result 2 %s", result)
            self.assert_data_values(result, 'multiple_ctdgv_record_recovered-234.mrg.result.yml')
            self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception raised after the driver is started during
        record parsing.
        """
       # cause the error for telemetered
        self.clear_sample_data()
        self.create_sample_data_set_dir('non-input_file.mrg', TELEMETERED_TEST_DIR, "unit_363_2013_245_7_7.mrg")

        self.assert_initialize()

        self.event_subscribers.clear_events()
        self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        # # cause the same error for recovered
        self.event_subscribers.clear_events()
        self.clear_sample_data()
        self.create_sample_data_set_dir('non-input_file.mrg', RECOVERED_TEST_DIR, "unit_363_2013_245_7_8.mrg")

        self.assert_sample_queue_size(DataParticleType.CTDGV_M_GLIDER_INSTRUMENT_RECOVERED, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)