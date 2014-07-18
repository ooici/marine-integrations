"""
@package mi.dataset.driver.mflm.phsen.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/phsen/driver.py
@author Emily Hahn
@brief Test cases for mflm_phsen driver

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
import os
from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent

from mi.core.log import get_logger
log = get_logger()
from mi.core.instrument.instrument_driver import DriverEvent
from mi.idk.exceptions import SampleTimeout
from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey

from mi.dataset.driver.mflm.phsen.driver import MflmPHSENDataSetDriver, DataSourceKey
from mi.dataset.parser.phsen import PhsenParserDataParticle, PhsenControlDataParticle
from mi.dataset.parser.phsen import DataParticleType
from mi.dataset.parser.phsen_abcdef import PhsenRecoveredInstrumentDataParticle, \
    PhsenRecoveredMetadataDataParticle, StateKey
from mi.dataset.parser.phsen_abcdef import DataParticleType as RecoveredDataParticleType
from mi.dataset.parser.sio_mule_common import StateKey as SioMuleStateKey


TELEM_DIR = '/tmp/dsatest'
RECOVERED_DIR = '/tmp/recoveredtest'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.phsen.driver',
    driver_class='MflmPHSENDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=MflmPHSENDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.HARVESTER:
        {
            DataSourceKey.PHSEN_ABCDEF_SIO_MULE: {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: 'node59p1.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            },
            DataSourceKey.PHSEN_ABCDEF: {
                DataSetDriverConfigKeys.DIRECTORY: RECOVERED_DIR,
                DataSetDriverConfigKeys.PATTERN: 'SAMI_*.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.PHSEN_ABCDEF_SIO_MULE: {},
            DataSourceKey.PHSEN_ABCDEF: {}
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

    def test_get(self):
        """
        Test that we can get data from files.
        """
        # Start sampling
        self.driver.start_sampling()

        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data((PhsenParserDataParticle, PhsenControlDataParticle),
                         'test_data_1.txt.result.yml', count=2)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.create_sample_data_set_dir("node59p1_step2.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data(PhsenParserDataParticle, 'test_data_2.txt.result.yml',
                         count=2)

        # now 'appends' the rest of the data and just check if we get the right number
        self.create_sample_data_set_dir("node59p1_step4.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data(PhsenParserDataParticle, count=6)

        # RECOVERED DATA
        # Test that we can get data from files reading one record at a time and reading multiple records at a time.
        self.create_sample_data_set_dir("SAMI_P0080_180713_small.txt", RECOVERED_DIR,
                                        "SAMI_A.txt")
        self.create_sample_data_set_dir("SAMI_P0080_180713_simple.txt", RECOVERED_DIR)

        # small file should generate two metadata and one instrument
        self.assert_data(PhsenRecoveredMetadataDataParticle,
                         'SAMI_P0080_180713_4.yml', count=2)

        self.assert_data(PhsenRecoveredInstrumentDataParticle,
                         'SAMI_P0080_180713_5.yml', count=1)

        # # Begin processing of second "simple" file
        self.assert_data(PhsenRecoveredMetadataDataParticle,
                         'SAMI_P0080_180713.yml', count=1)

        self.assert_data(PhsenRecoveredMetadataDataParticle,
                         'SAMI_P0080_180713_2.yml', count=1)

        self.assert_data(PhsenRecoveredMetadataDataParticle,
                         'SAMI_P0080_180713_3.yml', count=3)

        self.assert_data(PhsenRecoveredMetadataDataParticle,
                         'SAMI_P0080_180713_4.yml', count=2)

        # We are not going to compare the next 10 records
        self.assert_data(PhsenRecoveredMetadataDataParticle,
                         None, count=10)

        self.assert_data(PhsenRecoveredInstrumentDataParticle,
                         'SAMI_P0080_180713_5.yml', count=1)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """

        # create the file so that it is unreadable
        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, "node59p1.dat",
                                        mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(ValueError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_harvester_new_file_exception_recovered(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """

        # create the file so that it is unreadable
        self.create_sample_data_set_dir("SAMI_P0080_180713_simple.txt", RECOVERED_DIR, "SAMI_P0080_180713_simple.txt",
                                        mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_mid_state_start(self):
        """
        Test the ability to start processing in mid-state
        """

        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)

        phsen_abcdef_file = "SAMI_P0080_180713_integration.txt"
        self.create_sample_data_set_dir(phsen_abcdef_file, RECOVERED_DIR)

        driver_config = self._driver_config()['startup_config']

        sio_mule_config = driver_config['harvester'][DataSourceKey.PHSEN_ABCDEF_SIO_MULE]
        phsen_abcdef_sio_mule_file = os.path.join(sio_mule_config['directory'], sio_mule_config['pattern'])

        phsen_abcdef_sio_mule_stat = os.stat(phsen_abcdef_sio_mule_file)

        phsen_abcdef_config = driver_config['harvester'][DataSourceKey.PHSEN_ABCDEF]
        phsen_abcdef_fullfile = os.path.join(phsen_abcdef_config['directory'], phsen_abcdef_file)

        phsen_abcdef_stat = os.stat(phsen_abcdef_fullfile)

        # start in mid-state

        # Create and store the new driver state
        memento = {
            DataSourceKey.PHSEN_ABCDEF_SIO_MULE: {
                "node59p1.dat": {
                    DriverStateKey.FILE_SIZE: phsen_abcdef_sio_mule_stat.st_size,
                    DriverStateKey.FILE_CHECKSUM: '8b7cf73895eded0198b3f3621f962abc',
                    DriverStateKey.FILE_MOD_DATE: phsen_abcdef_sio_mule_stat.st_mtime,
                    DriverStateKey.PARSER_STATE: {
                        SioMuleStateKey.IN_PROCESS_DATA: [],
                        SioMuleStateKey.UNPROCESSED_DATA: [[0, 172]],
                        SioMuleStateKey.FILE_SIZE: phsen_abcdef_sio_mule_stat.st_size
                    }
                }
            },
            DataSourceKey.PHSEN_ABCDEF: {
                "SAMI_P0080_180713_integration.txt": {
                    DriverStateKey.INGESTED: False,
                    DriverStateKey.PARSER_STATE: {
                        StateKey.POSITION: 1313,
                        StateKey.START_OF_DATA: True,
                    },
                    DriverStateKey.FILE_SIZE: phsen_abcdef_stat.st_size,
                    DriverStateKey.FILE_MOD_DATE: phsen_abcdef_stat.st_mtime
                }
            }
        }

        driver = self._get_driver_object(memento=memento)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step2.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        driver.start_sampling()

        # # verify data is produced
        self.assert_data(PhsenParserDataParticle, 'test_data_2.txt.result.yml',
                         count=2, timeout=10)

        # Test Recovered
        # verify recovered data is produced
        self.assert_data(PhsenRecoveredMetadataDataParticle, 'SAMI_test_mid_state_start.yml',
                         count=1, timeout=10)

    def test_back_fill(self):
        """
        Test that a file with a zeroed block of data is read, skipping the zeroed block, then
        when that block is replaced with data, that record is returned
        """
        self.driver.start_sampling()

        # step 2 contains 3 blocks (4 records), start with this and get both since we used them
        # separately in other tests
        self.create_sample_data_set_dir("node59p1_step2.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data((PhsenParserDataParticle, PhsenControlDataParticle),
                         'test_data_1-2.txt.result.yml', count=4)

        # This file has had a section of data replaced with 0s (14171-14675),
        # replacing PH1236501_01D6u51F11341_5D_E538
        self.create_sample_data_set_dir('node59p1_step3.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data(PhsenParserDataParticle, 'test_data_3.txt.result.yml',
                         count=5)

        # Now fill in the zeroed section from step3, this should just return the new
        # data 
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data(PhsenParserDataParticle, 'test_data_4.txt.result.yml',
                         count=1)

        # start over now using step 4
        self.driver.stop_sampling()
        # Reset the driver with no memento
        self.driver = self._get_driver_object(memento=None)
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data((PhsenParserDataParticle, PhsenControlDataParticle),
                         'test_data_1-4.txt.result.yml', count=10)

    # The remaining integration tests only apply to the recovered
    # data parsed by the phsen_abcdef parser

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        log.info("======== START INTEG TEST SAMPLE EXCEPTION FAMILY ==========")

        self.clear_async_data()
        self.create_sample_data_set_dir('SAMI_P0080_180713_invalid_control.txt', RECOVERED_DIR)
        self.driver.start_sampling()

        # an event catches the sample exception - excess data at end of record
        self.assert_event('ResourceAgentErrorEvent')

        log.info("======== END INTEG TEST SAMPLE EXCEPTION FAMILY ==========")

    def test_start_stop_resume(self):
        """
        Test the ability to start, stop and resume the driver, ingesting files in the
        correct order
        """
        log.info("### START INTEG TEST START STOP RESUME RECOVERED ###")

        # Clear the asynchronous callback results
        self.clear_async_data()
        self.driver.start_sampling()

        # create some recovered data to parse
        self.create_sample_data_set_dir("SAMI_P0080_180713_integration_1.txt", RECOVERED_DIR)
        self.create_sample_data_set_dir("SAMI_P0080_180713_integration_2.txt", RECOVERED_DIR)
        self.create_sample_data_set_dir("SAMI_P0080_180713_integration_3.txt", RECOVERED_DIR)
        self.create_sample_data_set_dir("SAMI_P0080_180713_integration_4.txt", RECOVERED_DIR)

        # verify data is produced
        self.assert_data(PhsenRecoveredMetadataDataParticle, 'SAMI_test_stop_resume_recovered_step_1.yml',
                         count=2, timeout=10)
        self.assert_file_ingested('SAMI_P0080_180713_integration_1.txt', DataSourceKey.PHSEN_ABCDEF)

        # verify data is produced
        self.assert_data(PhsenRecoveredMetadataDataParticle, 'SAMI_test_stop_resume_recovered_step_2.yml',
                         count=2, timeout=10)
        self.assert_file_ingested('SAMI_P0080_180713_integration_2.txt', DataSourceKey.PHSEN_ABCDEF)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Resume
        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(PhsenRecoveredMetadataDataParticle, 'SAMI_test_stop_resume_recovered_step_1.yml',
                         count=2, timeout=10)
        self.assert_file_ingested('SAMI_P0080_180713_integration_3.txt', DataSourceKey.PHSEN_ABCDEF)

        # verify data is produced
        self.assert_data(PhsenRecoveredInstrumentDataParticle,
                         'SAMI_test_stop_resume_recovered_step_4.yml',
                         count=1, timeout=10)
        self.assert_file_ingested('SAMI_P0080_180713_integration_4.txt', DataSourceKey.PHSEN_ABCDEF)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        # need to put data in the file, not just make an empty file for this to work
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                        mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat")

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_harvester_new_recov_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        # need to put data in the file, not just make an empty file for this to work
        self.create_sample_data_set_dir('SAMI_P0080_180713_integration.txt', RECOVERED_DIR, mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir('SAMI_P0080_180713_integration.txt', RECOVERED_DIR)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """

        self.create_sample_data_set_dir('node59p1_step1.dat', TELEM_DIR, "node59p1.dat")
        self.create_sample_data_set_dir('SAMI_P0080_180713_integration_1.txt', RECOVERED_DIR)
        self.create_sample_data_set_dir('SAMI_P0080_180713_integration_ph_10.txt', RECOVERED_DIR)

        self.assert_initialize()

        try:
            # Verify we get one sample
            result = self.data_subscribers.get_samples(DataParticleType.CONTROL, 1)
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            result.extend(result1)
            log.info("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')

            # Test the Recovered Path

            # Verify that we get 2 control samples and 10 ph samples
            result = self.data_subscribers.get_samples(
                RecoveredDataParticleType.METADATA, 2, 100)
            result1 = self.data_subscribers.get_samples(
                RecoveredDataParticleType.INSTRUMENT, 10, 100)
            result.extend(result1)
            self.assert_data_values(result, 'SAMI_P0080_180713_control_ph.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        # the original file (from the IDD) is a previous version of the file from
        # the data server for the gp03flmb platform
        self.create_sample_data_set_dir('node59p1_orig.dat', TELEM_DIR, 'node59p1.dat')
        # For Recovered, using the original sample input file from the IDD
        self.create_sample_data_set_dir('SAMI_P0080_180713_orig.txt', RECOVERED_DIR)
        self.assert_initialize()
        # one bad sample in here:
        # PH1236501_01D5u51F361E0_EC_162E has non ascii bytes at the end and is missing \r
        result = self.data_subscribers.get_samples(DataParticleType.CONTROL, 1, 60)
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 49, 100)

        # this file is the more recent file off the data server for gp03flmb/d00001
        # this file appends more data to that in node59p1_orig
        self.create_sample_data_set_dir('node59p1.dat', TELEM_DIR)
        # several bad samples in here:
        # PH1236501_01D5u521208B4_A1_D274 doesn't have enough bytes (469 not 470)
        # PH1236501_01D5u52461BDC_CF_55BD doesn't have enough bytes (469 not 470)
        # PH1236501_01D5u5266BCF1_DA_6466 doesn't have enough bytes (469 not 470)
        # PH1236501_01DAu5288AF85_C9_7365, PH1236501_01DAu529E1BDF_42_4835
        # have extra bytes after the sample, not an error anymore
        # PH1236501_01D5u52B090DA_BA_8CC1 doesn't have enough bytes (469 not 470)
        # PH1236501_01DAu52B38839_BB_4134, PH1236501_01DAu52C8F493_34_3FC2
        # PH1236501_01DAu52ECE16B_79_F727, PH1236501_01DAu53024DC6_F2_7EC9 
        # have extra bytes after sample, not an error anymore
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 751, 430)

        # Test Recovered
        self.data_subscribers.get_samples(RecoveredDataParticleType.METADATA, 4, 60)
        self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 24, 60)
        self.data_subscribers.get_samples(RecoveredDataParticleType.METADATA, 1, 20)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_step2.dat', TELEM_DIR, "node59p1.dat")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.CONTROL, 1)
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
            result.extend(result1)

            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1-2.txt.result.yml')

            # Setup for Recovered
            self.create_sample_data_set_dir('SAMI_P0080_180713_integration_control_ph.txt', RECOVERED_DIR)
            # Read the first recovered file
            result = self.data_subscribers.get_samples(RecoveredDataParticleType.METADATA, 2)
            # Note - increase default timeout for Instrument particles
            result1 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 10, 20)
            result.extend(result1)

            # Verify Recovered values
            self.assert_data_values(result, 'SAMI_P0080_180713_control_ph.yml')

            self.assert_sample_queue_size(DataParticleType.CONTROL, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            self.assert_sample_queue_size(RecoveredDataParticleType.METADATA, 0)
            self.assert_sample_queue_size(RecoveredDataParticleType.INSTRUMENT, 0)

            # Second part of test

            self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat")
            # Now read the first record of the second file then stop
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
            log.debug("RESULT 1: %s", result)

            # Stop sampling
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.CONTROL, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            # Restart sampling and ensure we get the last records of the file
            self.assert_start_sampling()
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
            log.debug("RESULT 2: %s", result2)
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'test_data_3-4.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.CONTROL, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            # Test recovered file
            self.create_sample_data_set_dir('SAMI_P0080_180713_integration_control_ph_2.txt', RECOVERED_DIR)
            # Now read the first three records of the second recovered file then stop
            result = self.data_subscribers.get_samples(RecoveredDataParticleType.METADATA, 2)
            result1 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 1)
            result.extend(result1)

            # Stop sampling
            self.assert_stop_sampling()

            # Restart sampling and ensure we get the last records of the file
            self.assert_start_sampling()
            result2 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 5)
            result.extend(result2)
            self.assert_data_values(result, 'SAMI_P0080_180713_control_ph_2.yml')
            self.assert_sample_queue_size(RecoveredDataParticleType.METADATA, 0)
            self.assert_sample_queue_size(RecoveredDataParticleType.INSTRUMENT, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent and
        confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_step2.dat', TELEM_DIR, "node59p1.dat")
        self.create_sample_data_set_dir('SAMI_P0080_180713_integration_control_ph.txt', RECOVERED_DIR)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.CONTROL, 1)
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
            result.extend(result1)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1-2.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.CONTROL, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            # Now sample the recovered data - read all records in file
            result = self.data_subscribers.get_samples(RecoveredDataParticleType.METADATA, 2)
            result1 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 10, 20)
            result.extend(result1)

            # Verify values
            self.assert_data_values(result, 'SAMI_P0080_180713_control_ph.yml')
            self.assert_sample_queue_size(RecoveredDataParticleType.METADATA, 0)
            self.assert_sample_queue_size(RecoveredDataParticleType.INSTRUMENT, 0)

            self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat")

            # Now read the first record of the second file then stop
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
            log.debug("RESULT 1: %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.CONTROL, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()

            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
            log.debug("RESULT 2: %s", result2)
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'test_data_3-4.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.CONTROL, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            # Test Recovered, continue sampling

            self.create_sample_data_set_dir('SAMI_P0080_180713_integration_ph_10.txt', RECOVERED_DIR)
            # # Now read first 3 records from recovered file, then stop
            result = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 3)
            self.assert_stop_sampling()

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # # re-initialize
            self.assert_initialize()
            # Read remaining records from second recovered file
            # Note - increase from default timeout
            result2 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 7, 30)
            result.extend(result2)
            self.assert_data_values(result, 'SAMI_P0080_180713_ph.yml')
            self.assert_sample_queue_size(RecoveredDataParticleType.INSTRUMENT, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started on a
        file which contains a bad sample
        """
        # file contains 1 invalid sample values, 17 PH records total
        self.create_sample_data_set_dir('node59p1_bad.dat', TELEM_DIR, "node59p1.dat")

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(DataParticleType.CONTROL, 1)
        result = self.get_samples(DataParticleType.SAMPLE, 16, 30)
        self.assert_sample_queue_size(DataParticleType.CONTROL, 0)
        self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)