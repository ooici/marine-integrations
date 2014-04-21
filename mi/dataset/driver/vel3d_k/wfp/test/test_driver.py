"""
@package mi.dataset.driver.vel3d_k.wfp.test.test_driver
@file marine-integrations/mi/dataset/driver/vel3d_k/wfp/driver.py
@author Steve Myerson (Raytheon)
@brief Test cases for vel3d_k_wfp driver (for both telemetered and recovered data)

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

from mi.core.log import get_logger; log = get_logger()
import os

from mi.core.exceptions import \
    DatasetParserException, \
    RecoverableSampleException, \
    SampleException, \
    UnexpectedDataException

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.idk.exceptions import IDKConfigMissing, IDKException, SampleTimeout
from mi.idk.util import remove_all_files

from mi.dataset.dataset_driver import \
    DataSourceConfigKey, \
    DataSetDriverConfigKeys, \
    DriverParameter

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.dataset.driver.vel3d_k.wfp.driver import \
    Vel3dKWfp, \
    DataTypeKey

from mi.dataset.parser.vel3d_k_wfp import \
    Vel3dKWfpDataParticleType, \
    Vel3dKWfpStateKey, \
    Vel3dKWfpInstrumentParticle, \
    Vel3dKWfpMetadataParticle, \
    Vel3dKWfpStringParticle

from mi.dataset.parser.vel3d_k_wfp_stc import \
  Vel3dKWfpStcDataParticleType, \
  Vel3dKWfpStcStateKey, \
  Vel3dKWfpStcTimeDataParticle, \
  Vel3dKWfpStcVelocityDataParticle

DIR_WFP = '/tmp/dsatest1'
DIR_WFP_STC = '/tmp/dsatest2'

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
            DataTypeKey.VEL3D_K_WFP:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_WFP,
                DataSetDriverConfigKeys.PATTERN: 'A*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.VEL3D_K_WFP_STC:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_WFP_STC,
                DataSetDriverConfigKeys.PATTERN: 'A*.DEC',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {}
    }
)

# Recovered data parameters
FILE_HEADER_RECORD_SIZE = 4  # bytes
DATA_RECORD_SIZE = 90
TIME_RECORD_SIZE = 8

# Telemetered data parameters
FLAG_RECORD_SIZE = 26
VELOCITY_RECORD_SIZE = 24

SAMPLE_RATE = .5        # data records sample rate
PARSER_STATE = 'parser_state'

WFP_PARTICLES = (Vel3dKWfpInstrumentParticle, Vel3dKWfpMetadataParticle,
    Vel3dKWfpStringParticle)
WFP_STC_PARTICLES = (Vel3dKWfpStcTimeDataParticle, Vel3dKWfpStcVelocityDataParticle)

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

    def clear_sample_data(self):
        log.debug("Driver Config: %s", self._driver_config())
        if os.path.exists(DIR_WFP):
            log.debug("Clean all data from %s", DIR_WFP)
            remove_all_files(DIR_WFP)
        else:
            log.debug("Create directory %s", DIR_WFP)
            os.makedirs(DIR_WFP)

        if os.path.exists(DIR_WFP_STC):
            log.debug("Clean all data from %s", DIR_WFP_STC)
            remove_all_files(DIR_WFP_STC)
        else:
            log.debug("Create directory %s", DIR_WFP_STC)
            os.makedirs(DIR_WFP_STC)
 
    def test_get(self):
        """
        Test that we can get data from multiple files.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.clear_sample_data()
        self.driver.start_sampling()

        # From sample file A0000010.DEC (telemetered):
        # Flag record, first and last velocity record, time record.
        log.info("FILE A0000002 (WFP_STC) INTEG TEST GET")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'valid_A0000002.DEC', DIR_WFP_STC, 'A0000002.DEC')
        self.assert_data(WFP_STC_PARTICLES, 'valid_A0000002.yml',
            count=3, timeout=10)

        # From sample file A0000010.DEC (telemetered):
        # Flag record, first and last velocity records twice, time record.
        log.info("FILE A0000004 (WFP_STC) INTEG TEST GET")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'valid_A0000004.DEC', DIR_WFP_STC, 'A0000004.DEC')
        self.assert_data(WFP_STC_PARTICLES, 'valid_A0000004.yml',
            count=5, timeout=10)

        # Made-up data with all flags set to True.
        # Field values may not be realistic.
        log.info("FILE A0000003 (WFP_STC) INTEG TEST GET")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'all_A0000003.DEC', DIR_WFP_STC, 'A0000003.DEC')
        self.assert_data(None, 'all_A0000003.yml', count=4, timeout=10)

        # From sample file A0000010_10.DAT (recovered):
        # 10 data records, 1 time record,
        # Get records 1-3. Remaining records will be ignored.
        log.info("========== FILE A0000010_10 (WFP) INTEG TEST GET ============")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'A0000010_10.DAT', DIR_WFP, 'A0000010.DAT')
        self.assert_data(WFP_PARTICLES, 'A0000010_10_1_3.yml', count=3, timeout=10)
        self.assert_data(None, None, count=8, timeout=30)

        # Read the entire file.  10 data records.  Verify the time record.
        log.info("========= FILE A0000010_10 (WFP) INTEG TEST GET ============")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'A0000010_10.DAT', DIR_WFP, 'A0000011.DAT')
        self.assert_data(None, None, count=10, timeout=30)
        self.assert_data(None, 'A0000010_time.yml', count=1, timeout=10)

        log.info("================ END INTEG TEST GET ======================")

    def test_get_any_order(self):
        """
        Test that we can get data from files for all harvesters / parsers.
        """
        log.info("=========== START INTEG TEST GET ANY ORDER  ================")

        # Start sampling.
        self.clear_sample_data()
        self.driver.start_sampling()

        # Set up the test files.
        log.info("=========== CREATE DATA FILES  ================")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'valid_A0000004.DEC', DIR_WFP_STC, 'A0000004.DEC')
        self.create_sample_data_set_dir(
            'valid_A0000002.DEC',  DIR_WFP_STC, 'A0000002.DEC')

        self.create_sample_data_set_dir(
            'A0000010_5.DAT', DIR_WFP, 'A0000005.DAT')
        self.create_sample_data_set_dir(
            'A0000010_10.DAT', DIR_WFP, 'A0000010.DAT')

        # Read files in the following order:
        # Entire recovered data file #1.
        # Records 1-3 from recovered data file #2.
        # Entire telemetered data file #1.
        # Records 4-6 from recovered data file #2 (contents not verified).
        # Entire telemetered data file #2.
        # Records 7-10 from recovered data file #2.
        log.info("=========== READ DATA FILES  ================")
        self.assert_data(WFP_PARTICLES, 'A0000010_5_1_5.yml', count=6, timeout=10)
        self.assert_data(WFP_PARTICLES, 'A0000010_10_1_3.yml', count=3, timeout=10)
        self.assert_data(WFP_STC_PARTICLES, 'valid_A0000002.yml',count=3, timeout=10)
        self.assert_data(WFP_PARTICLES, None, count=3, timeout=10)
        self.assert_data(WFP_STC_PARTICLES, 'valid_A0000004.yml',count=5, timeout=10)
        self.assert_data(WFP_PARTICLES, 'A0000010_10_7_10.yml', count=5, timeout=10)

        log.info("=========== END INTEG TEST GET ANY ORDER  ================")

    def test_incomplete_file(self):
        """
        Test that we can handle a file missing the end of Velocity records.
        Should generate a SampleException.
        This test applies to telemetered data only.
        """
        log.info("========== START INTEG TEST INCOMPLETE ==========")

        self.clear_sample_data()
        self.clear_async_data()

        # From sample file A0000010.DEC:
        # Flag record, first and last velocity record, time record,
        # but the end of Velocity record (all zeroes) is missing.
        filename = 'A1000002.DEC'
        self.create_sample_data_set_dir(
            'incomplete_A0000002.DEC', DIR_WFP_STC, filename)

        # Start sampling.
        self.driver.start_sampling()

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

        # Verify that the entire file has been read.
        self.assert_file_ingested(filename)

        log.info("========== END INTEG TEST INCOMPLETE ==========")

    def test_invalid_flag_record(self):
        """
        Test that we can handle a file with an invalid Flag record.
        Should generate a SampleException.
        This test applies to telemetered data only.
        """
        log.info("========== START INTEG TEST INVALID FLAG ==========")

        self.clear_sample_data()
        self.clear_async_data()

        # Made-up data with all flags except the first set to True.
        # First flag is not a zero or one.
        filename = 'A1000003.DEC'
        self.create_sample_data_set_dir('invalid_A0000003.DEC', DIR_WFP_STC, filename)

        # Start sampling.
        self.driver.start_sampling()

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

        # Verify that the entire file has been read.
        self.assert_file_ingested(filename)

        log.info("========== END INTEG TEST INVALID FLAG ==========")

    def test_sample_exception_family(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs.  Error = invalid Family.
        """
        log.info("======== START INTEG TEST SAMPLE EXCEPTION FAMILY ==========")

        self.clear_sample_data()
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'A0000010_5_Family.DAT', DIR_WFP, 'A0000010.DAT')
        self.driver.start_sampling()

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

        log.info("======== END INTEG TEST SAMPLE EXCEPTION FAMILY ==========")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("=========== START INTEG TEST STOP RESUME  ================")

        self.clear_async_data()
        filename_1 = 'A0000005.DAT'
        filename_2 = 'A0000010.DAT'
        filename_3 = 'A0000002.DEC'
        filename_4 = 'A0000004.DEC'
        path_1 = self.create_sample_data_set_dir(
            'A0000010_5.DAT', DIR_WFP, filename_1)
        path_2 = self.create_sample_data_set_dir(
            'A0000010_10.DAT', DIR_WFP, filename_2)
        path_3 = self.create_sample_data_set_dir(
            'valid_A0000002.DEC', DIR_WFP_STC, filename_3)
        path_4 = self.create_sample_data_set_dir(
            'valid_A0000004.DEC', DIR_WFP_STC, filename_4)

        # Create and store the new driver state.
        # Set status of file 1 to completely read.
        # Set status of file 2 to start reading at record 7 of a 10 record file.
        # Set status of file 3 to completely read.
        # Set status of file 4 to start reading at record 3 of a 4 record file.
        file1_position = FILE_HEADER_RECORD_SIZE + (5 * DATA_RECORD_SIZE) + \
            TIME_RECORD_SIZE
        file2_position = FILE_HEADER_RECORD_SIZE + (6 * DATA_RECORD_SIZE)
        file3_position = FLAG_RECORD_SIZE + (2 *VELOCITY_RECORD_SIZE) + \
            TIME_RECORD_SIZE
        file4_position = FLAG_RECORD_SIZE + (2 *VELOCITY_RECORD_SIZE)

        state = {
            filename_1 : self.get_file_state(path_1, True, file1_position),
            filename_2 : self.get_file_state(path_2, False, file2_position),
            filename_3 : self.get_file_state(path_3, True, file3_position),
            filename_4 : self.get_file_state(path_4, False, file4_position)
        }
        state[filename_1][PARSER_STATE][Vel3dKWfpStateKey.POSITION] = file1_position
        state[filename_1][PARSER_STATE][Vel3dKWfpStateKey.RECORD_NUMBER] = 5

        state[filename_2][PARSER_STATE][Vel3dKWfpStateKey.POSITION] = file2_position
        state[filename_2][PARSER_STATE][Vel3dKWfpStateKey.RECORD_NUMBER] = 6

        state[filename_3][PARSER_STATE][Vel3dKWfpStcStateKey.FIRST_RECORD] = False
        state[filename_3][PARSER_STATE][Vel3dKWfpStcStateKey.VELOCITY_END] = True
        state[filename_4][PARSER_STATE][Vel3dKWfpStcStateKey.FIRST_RECORD] = False
        state[filename_4][PARSER_STATE][Vel3dKWfpStcStateKey.VELOCITY_END] = False
        self.driver = self._get_driver_object(memento=state)

        self.driver.start_sampling()

        # File 2: Verify that data is produced (last 4 data records plus time record).
        # File 4: Verify that data is produced (last 2 data records plus time record
        self.assert_data(WFP_STC_PARTICLES, 'valid_partial_A0000004.yml',
            count=3, timeout=10)
        self.assert_data(WFP_PARTICLES, 'A0000010_10_7_10.yml', count=5, timeout=10)

        log.info("============== END INTEG TEST STOP RESUME  ================")

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        log.info("========== START INTEG TEST STOP START RESUME  ===============")
        self.clear_async_data()
        self.driver.start_sampling()

        filename_1 = 'A0000005.DAT'
        filename_2 = 'A0000010.DAT'
        filename_3 = 'A0000002.DEC'
        filename_4 = 'A0000004.DEC'
        self.create_sample_data_set_dir(
            'A0000010_5.DAT', DIR_WFP, filename_1)
        self.create_sample_data_set_dir(
            'A0000010_10.DAT', DIR_WFP, filename_2)
        self.create_sample_data_set_dir(
            'valid_A0000002.DEC', DIR_WFP_STC, filename_3)
        self.create_sample_data_set_dir(
            'valid_A0000004.DEC', DIR_WFP_STC, filename_4)

        # Read the first telemetered data file (A0000002.DEC)
        # Verify that the entire file has been read.
        log.info("========== READ FILE A0000002.DEC ============")
        self.assert_data(WFP_STC_PARTICLES, 'valid_A0000002.yml',count=3, timeout=10)
        self.assert_file_ingested(filename_3)

        # Read the first recovered data file (A0000005.DAT)
        # Verify that the entire file has been read.
        log.info("========== READ FILE A0000005.DAT ============")
        self.assert_data(WFP_PARTICLES, 'A0000010_5_1_5.yml', count=6, timeout=10)
        self.assert_file_ingested(filename_1)

        # Read records 1-3 of the second recovered data file (A0000010.DAT)
        log.info("========== READ FILE A0000010.DAT RECORDS 1-3 ============")
        self.assert_data(WFP_PARTICLES, 'A0000010_10_1_3.yml', count=3, timeout=10)

        # Stop and then start sampling, resuming from where we left off.
        self.driver.stop_sampling()
        self.driver.start_sampling()

        # Read records 4-6 of the second recovered data file (A0000010.DAT)
        # without verifying results.
        self.assert_data(WFP_PARTICLES, None, count=3, timeout=10)

        # Read the second telemetered data file (A0000004.DEC)
        self.assert_data(WFP_STC_PARTICLES, 'valid_A0000004.yml',count=5, timeout=10)
        self.assert_file_ingested(filename_4)

        # Read records 7-10 of the second recovered data file (A0000010.DAT)
        self.assert_data(WFP_PARTICLES, 'A0000010_10_7_10.yml', count=5, timeout=10)
        self.assert_file_ingested(filename_2)

        log.info("=========== END INTEG TEST STOP START RESUME  ================")

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def clear_sample_data(self):
        """
        Need to override this from base class to clean all directories
        """
        data_dirs = self.create_data_dir()
        log.debug("Startup Config: %s", self._driver_config().get('startup_config'))
        for data_dir in data_dirs:
            log.debug("Clean all data from %s", data_dir)
            remove_all_files(data_dir)

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

        data_dir = []

        for key in harvester_config:
            data_dir_key = harvester_config[key].get("directory")
            if not data_dir_key:
                raise IDKConfigMissing("Harvester config missing 'directory'")

            if not os.path.exists(data_dir_key):
                log.debug("Creating data dir: %s", data_dir_key)
                os.makedirs(data_dir_key)

            elif not os.path.isdir(data_dir_key):
                raise IDKException("%s is not a directory" % data_dir_key)
            data_dir.append(data_dir_key)

        return data_dir

    def test_large_import(self):
        """
        Test importing a large number of samples from the files at once
        """
        log.info("=========== START QUAL TEST LARGE IMPORT =================")

        # The recovered data file referenced in the IDD contains 656 data records.
        # The telemetered data file referenced in the IDD contains 522 data records.
        self.create_sample_data_set_dir('A0000010.DAT', DIR_WFP, 'A0000010.DAT')
        self.create_sample_data_set_dir('idd_A0000010.DEC', DIR_WFP_STC, 'A0000010.DEC')
        records_per_second = 4

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: records_per_second})
        self.assert_start_sampling()

        log.info("========== READING SAMPLES QUAL TEST LARGE IMPORT ==============")
        try:
            wfp_samples = 256
            log.info("===== READ RECOVERED %d SAMPLES =====", wfp_samples)
            self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE,
                wfp_samples, wfp_samples)

            wfp_stc_samples = 522
            log.info("===== READ TELEMETERED %d SAMPLES =====", wfp_stc_samples)
            self.get_samples(Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE,
                wfp_stc_samples, wfp_stc_samples)

            wfp_samples = 400
            log.info("===== READ RECOVERED %d SAMPLES =====", wfp_samples)
            self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE,
                wfp_samples, wfp_samples)

            log.info("===== READ RECOVERED METADATA SAMPLE =====")
            self.get_samples(Vel3dKWfpDataParticleType.METADATA_PARTICLE, 1)
            self.verify_wfp_queue_empty()

            log.info("===== READ TELEMETERED METADATA SAMPLE =====")
            self.get_samples(Vel3dKWfpStcDataParticleType.TIME_PARTICLE, 1)
            self.verify_wfp_stc_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("=========== END QUAL TEST LARGE IMPORT =================")

    def test_parser_exception_invalid_family(self):
        """
        Test an exception is raised after the driver is started during
        record parsing. Should generate a SampleException.
        """
        log.info("========== START QUAL TEST INVALID FAMILY ==========")

        self.clear_sample_data()
        self.event_subscribers.clear_events()
        self.assert_initialize()
        self.create_sample_data_set_dir(
            'A0000010_5_Family.DAT', DIR_WFP, 'A0000010.DAT')

        # Verify an event was raised and we are in our retry state.
        self.verify_wfp_queue_empty()
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        log.info("========== END QUAL TEST INVALID FAMILY ==========")

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.info("=========== START QUAL TEST PUBLISH PATH =================")
        self.create_sample_data_set_dir('A0000010_5.DAT', DIR_WFP, 'A0000005.DAT')
        self.create_sample_data_set_dir('valid_A0000004.DEC', DIR_WFP_STC, 'A0000004.DEC')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Verify that we get 5 instrument data particles from the recovered data file.
            result = self.data_subscribers.get_samples(
                Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 5)

            # Verify that we get the Metadata particle from the recovered data file.
            time_result = self.data_subscribers.get_samples(
                Vel3dKWfpDataParticleType.METADATA_PARTICLE, 1)

            # Combine the instrument and metadata particles and verify results.
            result.extend(time_result)
            self.assert_data_values(result, 'A0000010_5_1_5.yml')

            # Verify that we get 4 velocity samples from the telemetered data file.
            result = self.data_subscribers.get_samples(
                Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE, 4)

            # Verify that we get the Time sample from the telemetered data file.
            time_result = self.data_subscribers.get_samples(
                Vel3dKWfpStcDataParticleType.TIME_PARTICLE, 1)

            # Combine the velocity and time samples and verify results.
            result.extend(time_result)
            self.assert_data_values(result, 'valid_A0000004.yml')

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
        self.create_sample_data_set_dir('A0000010_10.DAT', DIR_WFP, 'A0000010.DAT')
        self.create_sample_data_set_dir('all_A0000003.DEC', DIR_WFP_STC, 'A0000003.DEC')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read file A0000010_10 (3 instrument data records) and verify the data.
            log.info("====== READ FILE A0000010_10 AND VERIFY RECORDS 1-3 =========")
            result = self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 3)
            self.assert_data_values(result, 'A0000010_10_1_3.yml')

            # Read file all_A0000003 (3 velocity records) and verify the data.
            log.info("====== READ FILE all_A0000003 AND VERIFY RECORDS 1-3 =========")
            result = self.get_samples(Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE, 3)
            time_result = self.get_samples(Vel3dKWfpStcDataParticleType.TIME_PARTICLE, 1)
            result.extend(time_result)
            self.assert_data_values(result, 'all_A0000003.yml')
            self.verify_wfp_stc_queue_empty()

            # Read file A0000010_10 (7 instrument data records plus 1 time record).
            # Data is not verified.
            log.info("======== READ FILE A0000010_10 LAST 7 RECORDS =============")
            result = self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 7)
            time_result = self.get_samples(Vel3dKWfpDataParticleType.METADATA_PARTICLE, 1)
            self.verify_wfp_queue_empty()

            # Read the first 2 data records of file A0000010_5.
            log.info("======== READ FILE A0000010_5 RECORDS 1-2 =============")
            self.create_sample_data_set_dir('A0000010_5.DAT', DIR_WFP, 'A0000005.DAT')
            wfp_result = self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 2)

            # Read the first 2 data records of file valid_A0000004.
            log.info("======== READ FILE valid_A0000004 RECORDS 1-2 =============")
            self.create_sample_data_set_dir('valid_A0000004.DEC', DIR_WFP_STC, 'A0000004.DEC')
            wfp_stc_result = self.get_samples(Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE, 2)

            # Stop sampling.
            log.info("========== QUAL TEST SHUTDOWN RESTART STOP SAMPLING ===============")
            self.assert_stop_sampling()

            # Stop the agent
            self.stop_dataset_agent_client()
            # Re-start the agent
            self.init_dataset_agent_client()
            # Re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and get the last 3 records of file A0000010_5
            # and combine with the previous ones we read.
            log.info("======== READ FILE A0000010_5 LAST 3 RECORDS =============")
            self.assert_start_sampling()
            result2 = self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 3)
            wfp_result.extend(result2)

            # Get the time record of file A0000010_5 and combine with the previous ones we read.
            log.info("======== READ FILE A0000010_5 TIME RECORD =============")
            time_result = self.get_samples(Vel3dKWfpDataParticleType.METADATA_PARTICLE, 1)
            wfp_result.extend(time_result)

            # Verify the results for file A0000010_5 and that the queue is empty.
            self.assert_data_values(wfp_result, 'A0000010_5_1_5.yml')
            self.verify_wfp_queue_empty()

            # Get the last 2 velocity records of file valid_A0000004
            # and combine with the previous ones we read.
            result2 = self.get_samples(Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE, 2)
            wfp_stc_result.extend(result2)

            # Get the time record and combine with previous records.
            # Verify the results and that the queue is empty.
            time_result = self.get_samples(Vel3dKWfpStcDataParticleType.TIME_PARTICLE, 1)
            wfp_stc_result.extend(time_result)
            self.assert_data_values(wfp_stc_result, 'valid_A0000004.yml')
            self.verify_wfp_stc_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("========== END QUAL TEST SHUTDOWN RESTART =================")

    def test_small_import(self):
        """
        Test importing a small number of samples from the file at once
        """
        log.info("=========== START QUAL TEST SMALL IMPORT =================")

        self.create_sample_data_set_dir('A0000010_10.DAT', DIR_WFP, 'A0000010.DAT')
        self.create_sample_data_set_dir('all_A0000003.DEC', DIR_WFP_STC, 'A0000003.DEC')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.assert_start_sampling()

        try:
            log.info("========== READ FILE A0000010_10 ==============")
            self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 10, 10)
            self.get_samples(Vel3dKWfpDataParticleType.METADATA_PARTICLE, 1)
            self.verify_wfp_queue_empty()

            log.info("====== READ FILE all_A0000003 AND VERIFY RECORDS 1-3 =========")
            result = self.get_samples(Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE, 3)
            time_result = self.get_samples(Vel3dKWfpStcDataParticleType.TIME_PARTICLE, 1)
            result.extend(time_result)
            self.assert_data_values(result, 'all_A0000003.yml')
            self.verify_wfp_stc_queue_empty()

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
        self.create_sample_data_set_dir('A0000010_5.DAT', DIR_WFP, 'A0000005.DAT')
        self.create_sample_data_set_dir('valid_A0000004.DEC', DIR_WFP_STC, 'A0000004.DEC')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
          {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read file A0000010_5 (5 data particles) and verify the data.
            result = self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 5)
            time_result = self.get_samples(Vel3dKWfpDataParticleType.METADATA_PARTICLE, 1)
            result.extend(time_result)

            # Verify values
            self.assert_data_values(result, 'A0000010_5_1_5.yml')
            self.verify_wfp_queue_empty()

            # Read the first 2 velocity records of file valid_A0000004.
            wfp_stc_result = self.get_samples(Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE, 2)

            # Read the first 3 data particles of file A0000010_10 then stop.
            self.create_sample_data_set_dir('A0000010_10.DAT', DIR_WFP, 'A0000010.DAT')
            result = self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 3)

            # Verify values from file A0000010_10.
            self.assert_data_values(result, 'A0000010_10_1_3.yml')

            self.assert_stop_sampling()
            self.verify_wfp_queue_empty()

            # Restart sampling and get the last 2 records of file valid_A0000004
            # and combine with the previous ones we read.
            self.assert_start_sampling()
            result = self.get_samples(Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE, 2)
            wfp_stc_result.extend(result)

            # Get the next 3 particles (4-6) of file A0000010_10.
            # These particles are ignored.
            result = self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 3)

            self.assert_stop_sampling()
            self.verify_wfp_queue_empty()

            # Restart sampling. Read the last 4 particles (7-10) from file A0000010_10.
            self.assert_start_sampling()
            result = self.get_samples(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 4)

            # Get the metadata particle and combine with previous particles.
            time_result = self.get_samples(Vel3dKWfpDataParticleType.METADATA_PARTICLE, 1)
            result.extend(time_result)
            self.assert_data_values(result, 'A0000010_10_7_10.yml')
            self.verify_wfp_queue_empty()

            # Get the time record for file valid_A0000004 and combine with previous records.
            time_result = self.get_samples(Vel3dKWfpStcDataParticleType.TIME_PARTICLE, 1)
            wfp_stc_result.extend(time_result)
            self.assert_data_values(wfp_stc_result, 'valid_A0000004.yml')
            self.verify_wfp_stc_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("========== END QUAL TEST STOP START ===============")

    def verify_wfp_queue_empty(self):
        """
        Assert the sample queue for all WFP data streams is empty.
        """
        self.assert_sample_queue_size(Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE, 0)
        self.assert_sample_queue_size(Vel3dKWfpDataParticleType.METADATA_PARTICLE, 0)
        self.assert_sample_queue_size(Vel3dKWfpDataParticleType.STRING_PARTICLE, 0)

    def verify_wfp_stc_queue_empty(self):
        """
        Assert the sample queue for all WFP_STC data streams is empty.
        """
        self.assert_sample_queue_size(Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE, 0)
        self.assert_sample_queue_size(Vel3dKWfpStcDataParticleType.TIME_PARTICLE, 0)
