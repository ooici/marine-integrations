"""
@package mi.dataset.driver.flort_dj.cspp.test.test_driver
@file marine-integrations/mi/dataset/driver/flort_dj/cspp/driver.py
@author Jeremy Amundson
@brief Test cases for flort_dj_cspp driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr

import hashlib

import gevent
from mi.core.log import get_logger
log = get_logger()
import os
from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.parser.cspp_base import StateKey
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter

from mi.dataset.driver.flort_dj.cspp.driver import \
    FlortDjCsppDataSetDriver, DataTypeKey
from mi.dataset.parser.flort_dj_cspp import DataParticleType, \
    FlortDjCsppMetadataRecoveredDataParticle, FlortDjCsppMetadataTelemeteredDataParticle, \
    FlortDjCsppInstrumentRecoveredDataParticle, FlortDjCsppInstrumentTelemeteredDataParticle

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

TELEMETERED_DIR = 'tmp/flort_dj/telemetered'
RECOVERED_DIR = 'tmp/flort_dj/recovered'

TEST_FILE_ONE = 'first_data.txt'
TEST_ALL_EXPECTED_RESULTS_RECOVERED = 'first_data_recovered.yml'
TEST_ALL_EXPECTED_RESULTS_TELEMETERED = 'first_data_telemetered.yml'

TEST_FOUR_EXPECTED_RESULTS_RECOVERED = 'first_four_recovered.yml'
TEST_FOUR_EXPECTED_RESULTS_TELEMETERED = 'first_four_telemetered.yml'

BAD_DATA = 'BAD.txt'
BAD_EXPECTED_RESULTS_RECOVERED = 'BAD_recovered.yml'
BAD_EXPECTED_RESULTS_TELEMETERED = 'BAD_telemetered.yml'

RECOVERED_PARTICLES = (FlortDjCsppMetadataRecoveredDataParticle, FlortDjCsppInstrumentRecoveredDataParticle)
TELEMETERED_PARTICLES = (FlortDjCsppMetadataTelemeteredDataParticle, FlortDjCsppInstrumentTelemeteredDataParticle)

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.flort_dj.cspp.driver',
    driver_class='FlortDjCsppDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = FlortDjCsppDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'flort_dj_cspp',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.FLORT_DJ_CSPP_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TELEMETERED_DIR,
                DataSetDriverConfigKeys.PATTERN: '*.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.FLORT_DJ_CSPP_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: RECOVERED_DIR,
                DataSetDriverConfigKeys.PATTERN: '*.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.FLORT_DJ_CSPP_TELEMETERED: {},
            DataTypeKey.FLORT_DJ_CSPP_RECOVERED: {}
        }
    }
)

# The integration and qualification tests generated here are suggested tests,
# but may not be enough to fully test your driver. Additional tests should be
# written as needed.

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):

    def get_file_state(self, path, ingested=False, position=None, metadata_extracted=False):
        """
        Create a state object for a file. If a position is passed then add a parser state as well.
        """
        mod_time = os.path.getmtime(path)
        file_size = os.path.getsize(path)
        with open(path) as filehandle:
            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()

        parser_state = {
            StateKey.POSITION: position,
            StateKey.METADATA_EXTRACTED: metadata_extracted
        }

        return {
            'ingested': ingested,
            'file_mod_date': mod_time,
            'file_checksum': md5_checksum,
            'file_size': file_size,
            'parser_state': parser_state
        }

    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """

        self.driver.start_sampling()

        self.create_sample_data_set_dir(TEST_FILE_ONE, TELEMETERED_DIR, TEST_FILE_ONE)
        self.create_sample_data_set_dir(TEST_FILE_ONE, RECOVERED_DIR, TEST_FILE_ONE)

        self.assert_data(TELEMETERED_PARTICLES, TEST_FOUR_EXPECTED_RESULTS_TELEMETERED, count=4)
        self.assert_data(RECOVERED_PARTICLES, TEST_FOUR_EXPECTED_RESULTS_RECOVERED, count=4)

        self.get_samples(TELEMETERED_PARTICLES, count=189)
        self.get_samples(RECOVERED_PARTICLES, count=189)

        self.create_sample_data_set_dir('second_data.txt', RECOVERED_DIR, 'test_file_two.txt')
        self.create_sample_data_set_dir('second_data.txt', TELEMETERED_DIR, 'test_file_two.txt')

        self.assert_data(TELEMETERED_PARTICLES, 'second_data_telemetered.yml', count=150)
        self.assert_data(RECOVERED_PARTICLES, 'second_data_recovered.yml', count=150)

    def test_mid_state_start(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("================ START INTEG TEST MID STATE START =====================")

        # Clear any existing sampling
        self.clear_sample_data()

        recovered_path_1 = self.create_sample_data_set_dir(TEST_FILE_ONE, RECOVERED_DIR)
        telemetered_path_1 = self.create_sample_data_set_dir(TEST_FILE_ONE, TELEMETERED_DIR)

        state = {
            DataTypeKey.FLORT_DJ_CSPP_RECOVERED: {
                TEST_FILE_ONE: self.get_file_state(recovered_path_1,
                                                        ingested=False,
                                                        position=8173,
                                                        metadata_extracted=True),
            },
            DataTypeKey.FLORT_DJ_CSPP_TELEMETERED: {
                TEST_FILE_ONE: self.get_file_state(telemetered_path_1,
                                                          ingested=False,
                                                          position=2730,
                                                          metadata_extracted=True),
            }
        }

        driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        driver.start_sampling()

        # verify data is produced
        self.assert_data(RECOVERED_PARTICLES, 'mid_state_recovered.yml', count=4, timeout=10)

        self.assert_data(TELEMETERED_PARTICLES, 'mid_state_telemetered.yml', count=4, timeout=10)

    def test_start_stop_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """

        self.create_sample_data_set_dir(TEST_FILE_ONE, TELEMETERED_DIR, TEST_FILE_ONE)
        self.create_sample_data_set_dir(TEST_FILE_ONE, RECOVERED_DIR, TEST_FILE_ONE)

        self.driver.start_sampling()

        # wait for the test to receive 50 or more samples and stop sampling
        while len(self.data_callback_result) < 50:
            gevent.sleep(0)

        # ensure that the queues are not full
        assert len(self.data_callback_result) < 382

        self.driver.stop_sampling()

        #restart sampling
        self.driver.start_sampling()

        #verify results
        self.assert_data(TELEMETERED_PARTICLES, TEST_ALL_EXPECTED_RESULTS_TELEMETERED, count=193)
        self.assert_data(RECOVERED_PARTICLES, TEST_ALL_EXPECTED_RESULTS_RECOVERED, count=193)

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        # file contains invalid chunks
        self.create_sample_data_set_dir(BAD_DATA, TELEMETERED_DIR)

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

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

        self.create_sample_data_set_dir(TEST_FILE_ONE, TELEMETERED_DIR, TEST_FILE_ONE)
        self.create_sample_data_set_dir(TEST_FILE_ONE, RECOVERED_DIR, TEST_FILE_ONE)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            result_telemetered = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, sample_count=1,
                                                                   timeout=20)
            second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, sample_count=3,
                                                            timeout=10)
            result_telemetered.extend(second_part)

            result_recovered = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, sample_count=1,
                                                                 timeout=20)
            second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, sample_count=3,
                                                            timeout=10)
            result_recovered.extend(second_part)

            # Verify values
            self.assert_data_values(result_telemetered, TEST_FOUR_EXPECTED_RESULTS_TELEMETERED)
            self.assert_data_values(result_recovered, TEST_FOUR_EXPECTED_RESULTS_RECOVERED)

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):

        self.create_sample_data_set_dir(TEST_FILE_ONE, TELEMETERED_DIR, TEST_FILE_ONE)
        self.create_sample_data_set_dir(TEST_FILE_ONE, RECOVERED_DIR, TEST_FILE_ONE)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 3})
        self.assert_start_sampling()

        try:
            result_telemetered = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,
                                                                   sample_count=1, timeout=20)
            second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, sample_count=192,
                                                            timeout=100)
            result_telemetered.extend(second_part)

            result_recovered = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, sample_count=1,
                                                                 timeout=20)
            second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 192, timeout=100)

            result_recovered.extend(second_part)

            # Verify values
            self.assert_data_values(result_telemetered, TEST_ALL_EXPECTED_RESULTS_TELEMETERED)
            self.assert_data_values(result_recovered, TEST_ALL_EXPECTED_RESULTS_RECOVERED)

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        self.create_sample_data_set_dir(TEST_FILE_ONE, TELEMETERED_DIR, TEST_FILE_ONE)
        self.create_sample_data_set_dir(TEST_FILE_ONE, RECOVERED_DIR, TEST_FILE_ONE)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:

            result_telemetered = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,
                                                                   sample_count=1, timeout=20)

            result_recovered = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, sample_count=1,
                                                                 timeout=20)
            self.assert_stop_sampling()

            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, size=0)
            self.assert_sample_queue_size(DataParticleType.INSTRUMENT_TELEMETERED, size=0)
            self.assert_sample_queue_size(DataParticleType.METADATA_RECOVERED, size=0)
            self.assert_sample_queue_size(DataParticleType.INSTRUMENT_RECOVERED, size=0)

            self.assert_start_sampling()

            second_telemetered = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED,
                                                                   sample_count=3, timeout=10)
            second_recovered = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, sample_count=3,
                                                                 timeout=10)
            result_recovered.extend(second_recovered)
            result_telemetered.extend(second_telemetered)

            self.assert_data_values(result_telemetered, 'first_four_telemetered.yml')
            self.assert_data_values(result_recovered, 'first_four_recovered.yml')

        except Exception as e:
            log.error('Exception trapped: %s', e)

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent
        and confirm it restarts at the correct spot.
        """
        self.create_sample_data_set_dir(TEST_FILE_ONE, TELEMETERED_DIR, TEST_FILE_ONE)
        self.create_sample_data_set_dir(TEST_FILE_ONE, RECOVERED_DIR, TEST_FILE_ONE)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:

            result_telemetered = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,
                                                                   sample_count=1, timeout=20)
            result_recovered = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, sample_count=1,
                                                                 timeout=20)
            self.assert_stop_sampling()

            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, size=0)
            self.assert_sample_queue_size(DataParticleType.INSTRUMENT_TELEMETERED, size=0)
            self.assert_sample_queue_size(DataParticleType.METADATA_RECOVERED, size=0)
            self.assert_sample_queue_size(DataParticleType.INSTRUMENT_RECOVERED, size=0)

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)
            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()

            second_telemetered = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED,
                                                                   sample_count=3, timeout=10)
            second_recovered = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, sample_count=3,
                                                                 timeout=10)
            result_recovered.extend(second_recovered)
            result_telemetered.extend(second_telemetered)

            self.assert_data_values(result_telemetered, TEST_FOUR_EXPECTED_RESULTS_TELEMETERED)
            self.assert_data_values(result_recovered, TEST_FOUR_EXPECTED_RESULTS_RECOVERED)

        except Exception as e:
            log.error('Exception trapped: %s', e)

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.create_sample_data_set_dir(BAD_DATA, TELEMETERED_DIR, TEST_FILE_ONE)
        self.create_sample_data_set_dir(BAD_DATA, RECOVERED_DIR, TEST_FILE_ONE)

        self.assert_initialize()

        self.event_subscribers.clear_events()

        result_telemetered = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,
                                                               sample_count=1, timeout=20)
        second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, sample_count=3,
                                                        timeout=100)
        result_telemetered.extend(second_part)

        result_recovered = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, sample_count=1,
                                                             timeout=20)
        second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, sample_count=3,
                                                        timeout=100)

        result_recovered.extend(second_part)

        # Verify values
        self.assert_data_values(result_telemetered, BAD_EXPECTED_RESULTS_TELEMETERED)
        self.assert_data_values(result_recovered, BAD_EXPECTED_RESULTS_RECOVERED)

        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)