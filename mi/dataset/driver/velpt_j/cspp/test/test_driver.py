"""
@package mi.dataset.driver.velpt_j.cspp.test.test_driver
@file marine-integrations/mi/dataset/driver/velpt_j/cspp/driver.py
@author Jeremy Amundson
@brief Test cases for velpt_j_cspp driver

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

from mi.dataset.driver.velpt_j.cspp.driver import \
    VelptJCsppDataSetDriver, DataTypeKey
from mi.dataset.parser.velpt_j_cspp import DataParticleType, \
    VelptJCsppMetadataRecoveredDataParticle, VelptJCsppMetadataTelemeteredDataParticle, \
    VelptJCsppInstrumentRecoveredDataParticle, VelptJCsppInstrumentTelemeteredDataParticle

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

TELEMETERED_DIR = 'tmp/velpt_j/telemetered'
RECOVERED_DIR = 'tmp/velpt_j/recovered'

FIRST_TEXT = '11079364_PPB_ADCP.txt'
SECOND_TEXT = '11079364_PPD_ADCP.txt'
BAD_TEXT = 'BAD_PPB_ADCP.txt'

FIRST_RESULTS_TELEMETERED = 'tel_11079364_PPB_ADCP.yml'
FIRST_RESULTS_RECOVERED = '11079364_PPB_ADCP.yml'
FIRST_FOUR_RESULTS_TELEMETERED = 'tel_first_four_PPB_ADCP.yml'
FIRST_FOUR_RESULTS_RECOVERED = 'first_four_PPB_ADCP.yml'

SECOND_RESULTS_RECOVERED = 'rec_11079364_PPD_ADCP.yml'
SECOND_RESULTS_TELEMETERED = '11079364_PPD_ADCP.yml'
FIRST_FOUR_RESULTS_SECOND_RECOVERED = 'rec_first_four_PPD_ADCP.yml'
FIRST_FOUR_RESULTS_SECOND_TELEMETERED = 'first_four_PPD_ADCP.yml'

BAD_RESULTS_RECOVERED = 'rec_BAD_ADCP.yml'
BAD_RESULTS_TELEMETERED = 'tel_BAD_ADCP.yml'


RECOVERED_PARTICLES = (VelptJCsppMetadataRecoveredDataParticle, VelptJCsppInstrumentRecoveredDataParticle)
TELEMETERED_PARTICLES = (VelptJCsppMetadataTelemeteredDataParticle, VelptJCsppInstrumentTelemeteredDataParticle)

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.velpt_j.cspp.driver',
    driver_class='VelptJCsppDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = VelptJCsppDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'velpt_j_cspp',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.VELPT_J_CSPP_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TELEMETERED_DIR,
                DataSetDriverConfigKeys.PATTERN: '*.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.VELPT_J_CSPP_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: RECOVERED_DIR,
                DataSetDriverConfigKeys.PATTERN: '*.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.VELPT_J_CSPP_TELEMETERED: {},
            DataTypeKey.VELPT_J_CSPP_RECOVERED: {}
        }
    }
)


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

        self.create_sample_data_set_dir(SECOND_TEXT, TELEMETERED_DIR)
        self.create_sample_data_set_dir(FIRST_TEXT, RECOVERED_DIR)

        self.assert_data(TELEMETERED_PARTICLES, FIRST_FOUR_RESULTS_SECOND_TELEMETERED, count=4)
        self.assert_data(RECOVERED_PARTICLES, FIRST_FOUR_RESULTS_RECOVERED, count=4)

        self.get_samples(TELEMETERED_PARTICLES, count=20)
        self.get_samples(RECOVERED_PARTICLES, count=227)

        self.create_sample_data_set_dir(FIRST_TEXT, TELEMETERED_DIR)
        self.create_sample_data_set_dir(SECOND_TEXT, RECOVERED_DIR)

        self.assert_data(RECOVERED_PARTICLES, FIRST_FOUR_RESULTS_SECOND_RECOVERED, count=4)
        self.assert_data(TELEMETERED_PARTICLES, FIRST_FOUR_RESULTS_TELEMETERED, count=4)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("================ START INTEG TEST MID STATE START =====================")

        recovered_path_1 = self.create_sample_data_set_dir(FIRST_TEXT, RECOVERED_DIR)
        telemetered_path_1 = self.create_sample_data_set_dir(SECOND_TEXT, TELEMETERED_DIR)

        state = {
            DataTypeKey.VELPT_J_CSPP_RECOVERED: {
                FIRST_TEXT: self.get_file_state(recovered_path_1,
                                                        ingested=False,
                                                        position=1353,
                                                        metadata_extracted=True),
            },
            DataTypeKey.VELPT_J_CSPP_TELEMETERED: {
                SECOND_TEXT: self.get_file_state(telemetered_path_1,
                                                          ingested=False,
                                                          position=1453,
                                                          metadata_extracted=True),
            }
        }

        driver = self._get_driver_object(memento=state)

        self.clear_async_data()

        driver.start_sampling()

        # verify data is produced
        self.assert_data(RECOVERED_PARTICLES, 'mid_11079364_PPB_ADCP.yml', count=4, timeout=10)

        self.assert_data(TELEMETERED_PARTICLES, 'mid_11079364_PPD_ADCP.yml', count=4, timeout=10)

    def test_start_stop_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """

        self.create_sample_data_set_dir(FIRST_TEXT, TELEMETERED_DIR)
        self.create_sample_data_set_dir(FIRST_TEXT, RECOVERED_DIR)

        self.driver.start_sampling()

        # wait for the test to receive 50 or more samples and stop sampling
        while len(self.data_callback_result) < 50:
            gevent.sleep(0)

        # ensure that the queues are not full
        assert len(self.data_callback_result) < 458

        self.driver.stop_sampling()

        #restart sampling
        self.driver.start_sampling()

        #verify results
        self.assert_data(TELEMETERED_PARTICLES, FIRST_RESULTS_TELEMETERED, count=231)
        self.assert_data(RECOVERED_PARTICLES, FIRST_RESULTS_RECOVERED, count=231)

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        # file contains invalid chunks
        self.create_sample_data_set_dir(BAD_TEXT, TELEMETERED_DIR)

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

        self.create_sample_data_set_dir(FIRST_TEXT, TELEMETERED_DIR)
        self.create_sample_data_set_dir(FIRST_TEXT, RECOVERED_DIR)

        self.assert_initialize()

        try:
            result_telemetered = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,
                                                                   sample_count=1, timeout=20)
            second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, sample_count=3,
                                                            timeout=10)
            result_telemetered.extend(second_part)

            result_recovered = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, sample_count=1,
                                                                 timeout=20)
            second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, sample_count=3,
                                                            timeout=10)
            result_recovered.extend(second_part)

            # Verify values
            self.assert_data_values(result_telemetered, FIRST_FOUR_RESULTS_TELEMETERED)
            self.assert_data_values(result_recovered, FIRST_FOUR_RESULTS_RECOVERED)

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):

        self.create_sample_data_set_dir(FIRST_TEXT, TELEMETERED_DIR)
        self.create_sample_data_set_dir(FIRST_TEXT, RECOVERED_DIR)

        self.assert_initialize()

        try:
            result_telemetered = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,
                                                                   sample_count=1, timeout=20)
            second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, sample_count=230,
                                                            timeout=100)
            result_telemetered.extend(second_part)

            result_recovered = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, sample_count=1,
                                                                 timeout=20)
            second_part = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 230, timeout=100)

            result_recovered.extend(second_part)

            # Verify values
            self.assert_data_values(result_telemetered, FIRST_RESULTS_TELEMETERED)
            self.assert_data_values(result_recovered, FIRST_RESULTS_RECOVERED)

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        self.create_sample_data_set_dir(FIRST_TEXT, TELEMETERED_DIR)
        self.create_sample_data_set_dir(FIRST_TEXT, RECOVERED_DIR)

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

            self.assert_data_values(result_telemetered, FIRST_FOUR_RESULTS_TELEMETERED)
            self.assert_data_values(result_recovered, FIRST_FOUR_RESULTS_RECOVERED)

        except Exception as e:
            log.error('Exception trapped: %s', e)

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent
        and confirm it restarts at the correct spot.
        """
        self.create_sample_data_set_dir(FIRST_TEXT, TELEMETERED_DIR)
        self.create_sample_data_set_dir(FIRST_TEXT, RECOVERED_DIR)

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

            self.assert_data_values(result_telemetered, FIRST_FOUR_RESULTS_RECOVERED)
            self.assert_data_values(result_recovered, FIRST_FOUR_RESULTS_TELEMETERED)

        except Exception as e:
            log.error('Exception trapped: %s', e)

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.create_sample_data_set_dir(BAD_TEXT, TELEMETERED_DIR)
        self.create_sample_data_set_dir(BAD_TEXT, RECOVERED_DIR)

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
        self.assert_data_values(result_telemetered, BAD_RESULTS_TELEMETERED)
        self.assert_data_values(result_recovered, BAD_RESULTS_RECOVERED)

        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)