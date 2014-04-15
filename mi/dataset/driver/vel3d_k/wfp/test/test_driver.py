"""
@package mi.dataset.driver.vel3d_k.wfp.test.test_driver
@file marine-integrations/mi/dataset/driver/vel3d_k/wfp/driver.py
@author Steve Myerson (Raytheon)
@brief Test cases for vel3d_k_wfp driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout
from mi.core.exceptions import \
    DatasetParserException, \
    RecoverableSampleException, \
    SampleException, \
    UnexpectedDataException

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import \
  DataSourceConfigKey, \
  DataSetDriverConfigKeys, \
  DriverParameter

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.dataset.driver.vel3d_k.wfp.driver import Vel3dKWfp

from mi.dataset.parser.vel3d_k_wfp import \
    DataParticleType, \
    StateKey, \
    Vel3dKWfpInstrumentParticle, \
    Vel3dKWfpMetadataParticle, \
    Vel3dKWfpStringParticle


# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.vel3d_k.wfp.driver',
    driver_class='Vel3dKWfp',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = Vel3dKWfp.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'vel3d_k_wfp',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: 'A*.DAT',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

FILE_HEADER_RECORD_SIZE = 4  # bytes
DATA_RECORD_SIZE = 90
TIME_RECORD_SIZE = 8
TIME_ON = 1393266602.0  # time_on from the data file
SAMPLE_RATE = .5        # data records sample rate
PARSER_STATE = 'parser_state'
SAMPLE_STREAM = 'vel3d_k_wfp_parsed'

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
 
    def test_get(self):
        """
        Test that we can get data from multiple files.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.clear_sample_data()
        self.driver.start_sampling()
        self.clear_async_data()

        # From sample file A0000010_10.DAT (10 data records, 1 time record),
        # get records 1-3.
        # Remaining records will be ignored.
        log.info("========== FIRST FILE A0000010_10 INTEG TEST GET ============")
        self.create_sample_data('A0000010_10.DAT', "A0000010.DAT")
        self.assert_data(None, 'A0000010_10_1_3.yml', count=3, timeout=10)
        self.assert_data(None, None, count=8, timeout=30)

        # Read the entire file.  10 data records.  Verify the time record.
        log.info("========= SECOND FILE A0000010_10 INTEG TEST GET ============")
        self.clear_sample_data()
        self.clear_async_data()
        self.create_sample_data('A0000010_10.DAT', "A0000011.DAT")
        self.assert_data(None, None, count=10, timeout=30)
        self.assert_data(None, 'A0000010_time.yml', count=1, timeout=10)

        log.info("================ END INTEG TEST GET ======================")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("=========== START INTEG TEST STOP RESUME  ================")
        filename_1 = "A0000005.DAT"
        filename_2 = "A0000010.DAT"
        path_1 = self.create_sample_data('A0000010_5.DAT', filename_1)
        path_2 = self.create_sample_data('A0000010_10.DAT', filename_2)

        # Create and store the new driver state
        # Set status of file 1 to completely read.
        # Set status of file 2 to start reading at record 7 of a 10 record file.
        file1_position = FILE_HEADER_RECORD_SIZE + (5 * DATA_RECORD_SIZE) + \
            TIME_RECORD_SIZE
        file2_position = FILE_HEADER_RECORD_SIZE + (6 * DATA_RECORD_SIZE)
        state = {
            filename_1 : self.get_file_state(path_1, True, file1_position),
            filename_2 : self.get_file_state(path_2, False, file2_position)
        }
        state[filename_1][PARSER_STATE][StateKey.POSITION] = file1_position
        state[filename_1][PARSER_STATE][StateKey.RECORD_NUMBER] = 5
        state[filename_1][PARSER_STATE][StateKey.TIMESTAMP] = TIME_ON + \
            (5 * SAMPLE_RATE)
        state[filename_2][PARSER_STATE][StateKey.POSITION] = file2_position
        state[filename_2][PARSER_STATE][StateKey.RECORD_NUMBER] = 6
        state[filename_2][PARSER_STATE][StateKey.TIMESTAMP] = TIME_ON + \
            (6 * SAMPLE_RATE)
        self.driver = self._get_driver_object(memento=state)

        self.clear_async_data()
        self.driver.start_sampling()

        log.info("====== SECOND FILE A0000010_10 INTEG TEST STOP RESUME =========")
        # Verify that data is produced (last 4 data records plus time record).
        self.assert_data(None, 'A0000010_10_7_10.yml', count=5, timeout=10)

        log.info("============== END INTEG TEST STOP RESUME  ================")

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        log.info("========== START INTEG TEST STOP START RESUME  ===============")
        filename_1 = "A0000005.DAT"
        filename_2 = "A0000010.DAT"
        path_1 = self.create_sample_data('A0000010_5.DAT', filename_1)
        path_2 = self.create_sample_data('A0000010_10.DAT', filename_2)

        # Create and store the new driver state
        state = {
            filename_1 : self.get_file_state(path_1, False, 0),
            filename_2 : self.get_file_state(path_2, False, 0)
        }
        state[filename_1][PARSER_STATE][StateKey.RECORD_NUMBER] = 0
        state[filename_2][PARSER_STATE][StateKey.RECORD_NUMBER] = 0
        self.driver = self._get_driver_object(memento=state)

        log.info("========== READ FIRST FILE A0000010_5 ============")
        self.clear_async_data()
        self.driver.start_sampling()
        self.assert_data(None, 'A0000010_5_1_5.yml', count=6, timeout=10)

        log.info("========== VERIFY FIRST FILE AT EOF ============")
        # Verify that the entire file has been read.
        self.assert_file_ingested(filename_1)

        log.info("========== READ SECOND FILE A0000010_10 Rec 1-3 ============")
        self.assert_data(None, 'A0000010_10_1_3.yml', count=3, timeout=10)
        self.driver.stop_sampling()
        log.info("========== READ SECOND FILE A0000010_10 Rec 4-6 ============")
        self.driver.start_sampling()
        self.assert_data(None, None, count=3, timeout=10)
        log.info("========== READ SECOND FILE A0000010_10 Rec 7-10 ============")
        self.assert_data(None, 'A0000010_10_7_10.yml', count=5, timeout=10)

        log.info("========== VERIFY SECOND FILE AT EOF ============")
        # Verify that the entire file has been read.
        self.assert_file_ingested(filename_2)

        log.info("=========== END INTEG TEST STOP START RESUME  ================")

    def test_sample_exception_family(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs.  Error = invalid Family.
        """
        log.info("======== START INTEG TEST SAMPLE EXCEPTION FAMILY ==========")

        self.clear_sample_data()
        self.clear_async_data()
        self.create_sample_data('A0000010_5_Family.DAT', "A0000010.DAT")
        self.driver.start_sampling()

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

        log.info("======== END INTEG TEST SAMPLE EXCEPTION FAMILY ==========")

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        log.info("=========== START QUAL TEST LARGE IMPORT =================")

        # The sample file referenced in the IDD.
        # Contains 656 data records.
        self.create_sample_data('A0000010.DAT', 'A0000010.DAT')
        records_per_second = 4

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: records_per_second})
        self.assert_start_sampling()

        log.info("========== READING SAMPLES QUAL TEST LARGE IMPORT ==============")
        try:
            samples = 100
            log.info("===== READ %d SAMPLES =====", samples)
            self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, samples, samples)
            samples = 200
            log.info("===== READ %d SAMPLES =====", samples)
            self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, samples, samples)
            samples = 300
            log.info("===== READ %d SAMPLES =====", samples)
            self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, samples, samples)
            samples = 56
            log.info("===== READ %d SAMPLES =====", samples)
            self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, samples, samples)

            log.info("===== READ METADATA SAMPLE =====")
            self.get_samples(DataParticleType.METADATA_PARTICLE, 1)
            self.verify_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("=========== END QUAL TEST LARGE IMPORT =================")

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.info("=========== START QUAL TEST PUBLISH PATH =================")
        self.create_sample_data('A0000010_5.DAT', "A0000005.DAT")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Verify that we get 5 instrument data particles.
            result = self.data_subscribers.get_samples(
                DataParticleType.INSTRUMENT_PARTICLE, 5)

            # Verify that we get the Metadata particle.
            time_result = self.data_subscribers.get_samples(
                DataParticleType.METADATA_PARTICLE, 1)

            # Combine the instrument and metadata particles and verify results.
            result.extend(time_result)
            self.assert_data_values(result, 'A0000010_5_1_5.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        log.info("=========== END QUAL TEST PUBLISH PATH =================")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent
        and confirm it restarts at the correct spot.
        """
        log.info("========== START QUAL TEST SHUTDOWN RESTART ===============")
        self.create_sample_data('A0000010_10.DAT', "A0000010.DAT")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file (3 instrument data records) and verify the data.
            log.info("====== FIRST FILE READ AND VERIFY RECORDS 1-3 =========")
            result = self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 3)
            self.assert_data_values(result, 'A0000010_10_1_3.yml')

            # Read the first file (7 instrument data records plus 1 time record).
            # Data is not verified.
            log.info("======== FIRST FILE READ LAST 7 RECORDS =============")
            result = self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 7)
            time_result = self.get_samples(DataParticleType.METADATA_PARTICLE, 1)
            self.verify_queue_empty()

            # Read the first 2 data records of the second file then stop.
            log.info("======== SECOND FILE READ RECORDS 1-2 =============")
            self.create_sample_data('A0000010_5.DAT', "A0000005.DAT")
            result = self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 2)
            self.assert_stop_sampling()

            # Stop the agent
            self.stop_dataset_agent_client()
            # Re-start the agent
            self.init_dataset_agent_client()
            # Re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and get the last 3 records of the file
            # and combine with the previous ones we read.
            log.info("======== SECOND FILE READ LAST 3 RECORDS =============")
            self.assert_start_sampling()
            result2 = self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 3)
            result.extend(result2)

            # Get the time record of the file
            # and combine with the previous ones we read.
            log.info("======== SECOND FILE READ TIME RECORD =============")
            time_result = self.get_samples(DataParticleType.METADATA_PARTICLE, 1)
            result.extend(time_result)

            self.assert_data_values(result, 'A0000010_5_1_5.yml')
            self.verify_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("========== END QUAL TEST SHUTDOWN RESTART =================")

    def test_small_import(self):
        """
        Test importing a small number of samples from the file at once
        """
        log.info("=========== START QUAL TEST SMALL IMPORT =================")

        self.create_sample_data('A0000010_10.DAT', 'A0000010.DAT')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.assert_start_sampling()

        log.info("========== READING SAMPLES QUAL TEST SMALL IMPORT ==============")
        try:
            self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 10, 10)
            self.get_samples(DataParticleType.METADATA_PARTICLE, 1)
            self.verify_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("=========== END QUAL TEST SMALL IMPORT =================")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("========== START QUAL TEST STOP START ===============")
        self.create_sample_data('A0000010_5.DAT', "A0000005.DAT")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
          {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file (5 data particles) and verify the data.
            result = self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 5)
            time_result = self.get_samples(DataParticleType.METADATA_PARTICLE, 1)
            result.extend(time_result)

            # Verify values
            self.assert_data_values(result, 'A0000010_5_1_5.yml')
            self.verify_queue_empty()

            # Read the first 3 data particles of the second file then stop.
            self.create_sample_data('A0000010_10.DAT', "A0000010.DAT")
            result = self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 3)

            # Verify values
            self.assert_data_values(result, 'A0000010_10_1_3.yml')
            self.assert_stop_sampling()
            self.verify_queue_empty()

            # Restart sampling and get the next 3 particles (4-6) of the file.
            # These particles are ignored.
            self.assert_start_sampling()
            result = self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 3)
            self.assert_stop_sampling()
            self.verify_queue_empty()

            # Read the last 4 particles (7-10).
            self.assert_start_sampling()
            result = self.get_samples(DataParticleType.INSTRUMENT_PARTICLE, 4)

            # Get the metadata particle and combine with previous particles.
            time_result = self.get_samples(DataParticleType.METADATA_PARTICLE, 1)
            result.extend(time_result)
            self.assert_data_values(result, 'A0000010_10_7_10.yml')

            self.verify_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("========== END QUAL TEST STOP START ===============")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        pass

    def verify_queue_empty(self):
        """
        Assert the sample queue for all data streams is empty.
        """
        self.assert_sample_queue_size(DataParticleType.INSTRUMENT_PARTICLE, 0)
        self.assert_sample_queue_size(DataParticleType.METADATA_PARTICLE, 0)

