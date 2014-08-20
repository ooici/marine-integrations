"""
@package mi.dataset.driver.mflm.dosta.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/dosta/driver.py
@author Emily Hahn
@brief Test cases for mflm_dosta driver

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
import shutil
from nose.plugins.attrib import attr
from mock import Mock

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentConnectionLostErrorEvent

from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_driver import DriverEvent
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey
from mi.dataset.driver.mflm.dosta.driver import MflmDOSTADDataSetDriver, DataTypeKey
from mi.dataset.parser.dostad import DataParticleType
from mi.dataset.parser.dostad import DostadParserRecoveredDataParticle, DostadParserTelemeteredDataParticle
from mi.dataset.parser.dostad import DostadParserRecoveredMetadataDataParticle, DostadParserTelemeteredMetadataDataParticle
from mi.dataset.parser.sio_mule_common import StateKey

TELEM_DIR = '/tmp/dsatest_telem'
RECOV_DIR = '/tmp/dsatest_recov'

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.dosta.driver',
    driver_class='MflmDOSTADDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = MflmDOSTADDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER: {
            DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: 'node59p1.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            },
            DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: RECOV_DIR,
                DataSetDriverConfigKeys.PATTERN: 'DOS*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.DOSTA_ABCDJM_SIO_TELEMETERED: {},
            DataTypeKey.DOSTA_ABCDJM_SIO_RECOVERED: {},
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
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        # Start sampling
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data((DostadParserTelemeteredDataParticle, DostadParserTelemeteredMetadataDataParticle),
            'test_data_1.txt.result.yml', count=2, timeout=10)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step2.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data(DostadParserTelemeteredDataParticle, 'test_data_2.txt.result.yml',
                         count=1)

        # now 'appends' the rest of the data and just check if we get the right number
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step4.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data(DostadParserTelemeteredDataParticle, count=4)

        # Test that we can get data from files.  Verify that the driver
        # sampling can be started and stopped
        
        
    def test_get_recovered(self):
        # RECOVERED VERSIONS appear with _recovered appended
        # Start sampling
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir("DOS15908_1st7_step1.DAT", RECOV_DIR, "DOS15908.DAT",
                                        copy_metadata=False)
        self.assert_data((DostadParserRecoveredDataParticle, DostadParserRecoveredMetadataDataParticle),
            'test_data_1r.txt.result.yml', count=2, timeout=10)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.clear_async_data()
        self.create_sample_data_set_dir("DOS15908_1st7_step2.DAT", RECOV_DIR, "DOS15909.DAT",
                                        copy_metadata=False)
        self.assert_data(DostadParserRecoveredDataParticle, 'test_data_2r.txt.result.yml',
                         count=1)

        # now 'appends' the rest of the data and just check if we get the right number
        self.clear_async_data()
        self.create_sample_data_set_dir("DOS15908.DAT", RECOV_DIR, "DOS15910.DAT",
                                        copy_metadata=False)
        self.assert_data(DostadParserRecoveredDataParticle, count=4)


    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        # create the file so that it is unreadable
        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, "node59p1.dat",
                                        mode=000, copy_metadata=False)

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
        self.create_sample_data_set_dir("DOS15908_1st7_step1.DAT", RECOV_DIR, "DOS15909.DAT",
                                        mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.
     
    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
               
        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        
        # create the recovered file
        self.create_sample_data_set_dir("DOS15908_1st7_step1.DAT", RECOV_DIR, "DOS15908.DAT",
                                        copy_metadata=False)
        
        # create some data to parse
        self.clear_async_data()
 
        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(DostadParserTelemeteredDataParticle, 'test_data_1_ss1.txt.result.yml',
                         count=1, timeout=10)
        self.assert_data(DostadParserRecoveredDataParticle, 'test_data_1r_ss1.txt.result.yml',
                         count=1, timeout=10)

        self.driver.stop_sampling()

        self.driver.start_sampling()
        
        self.assert_data(DostadParserTelemeteredMetadataDataParticle, 'test_data_1_ss2.txt.result.yml',
                         count=1, timeout=10)
        self.assert_data(DostadParserRecoveredMetadataDataParticle, 'test_data_1r_ss2.txt.result.yml',
                         count=1, timeout=10)



    def test_back_fill(self):
        """
        Test new sequence flags are set correctly
        """
        self.driver.start_sampling()

        # step 2 contains 2 blocks, start with this and get both since we used them
        # separately in other tests 
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step2.dat", TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data((DostadParserTelemeteredDataParticle, DostadParserTelemeteredMetadataDataParticle),
            'test_data_1-2.txt.result.yml', count=3)

        # This file has had a section of DO data replaced with 0s
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step3.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data(DostadParserTelemeteredDataParticle, 'test_data_3.txt.result.yml',
                         count=3)

        # Now fill in the zeroed section from step3, this should just return the new
        # data
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data(DostadParserTelemeteredDataParticle, 'test_data_4.txt.result.yml',
                         count=1)

        # start over now, using step 4
        self.driver.stop_sampling()

        # Reset the driver with no memento
        self.memento = None
        self.driver = MflmDOSTADDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        self.assert_data((DostadParserTelemeteredDataParticle, DostadParserTelemeteredMetadataDataParticle),
            'test_data_1-4.txt.result.yml', count=7)



    def test_all_good(self):
        """
        Test that a set of data with no bad data, where there is no remaining
        unprocessed data in between
        """
        self.driver.start_sampling()

        self.create_sample_data_set_dir("node59p1_all_good1.dat", TELEM_DIR, "node59p1.dat")
        self.assert_data((DostadParserTelemeteredDataParticle, DostadParserTelemeteredMetadataDataParticle),
            'test_data_1-2.txt.result.yml', count=3)

        self.create_sample_data_set_dir("node59p1_all_good.dat", TELEM_DIR, "node59p1.dat")
        self.assert_data(DostadParserTelemeteredDataParticle, 'test_data_all_good.txt.result.yml',
                         count=1)

    def test_all_good_recovered(self):
        """
        Test that a set of data with no bad data, where there is no remaining
        unprocessed data in between
        """
        # Start sampling
        self.driver.start_sampling()

        self.create_sample_data_set_dir("DOS15908_1st7_step1.DAT", RECOV_DIR, "DOS15908.DAT",
                                        copy_metadata=False)
        self.assert_data((DostadParserRecoveredDataParticle, DostadParserRecoveredMetadataDataParticle),
            'test_data_1r.txt.result.yml', count=2, timeout=10)

        self.create_sample_data_set_dir("DOS15908_1st7_step2.DAT", RECOV_DIR, "DOS15909.DAT",
                                        copy_metadata=False)
        self.assert_data(DostadParserRecoveredDataParticle, 'test_data_2r.txt.result.yml',
                         count=1)



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
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat", mode=000,
                                        copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_harvester_new_file_exception_recovered(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        # need to put data in the file, not just make an empty file for this to work
        self.create_sample_data_set_dir("DOS15908_1st7_step1.DAT", RECOV_DIR, "DOS15908.DAT", mode=000,
                                        copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir("DOS15908_1st7_step1.DAT", RECOV_DIR, "DOS15908.DAT",
                                        copy_metadata=False)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)


    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.debug("======================= creating telem data")
        self.create_sample_data_set_dir('node59p1_step1.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)
        log.debug("======================= creating recov data")
        self.create_sample_data_set_dir("DOS15908_1st7_step1.DAT", RECOV_DIR, "DOS15908.DAT",
                                        copy_metadata=False)

        self.assert_initialize()

        # get the telemetered metadata particle
        result = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1)
        log.debug("*****************************************************  metadata result %s", result)
        #get the telemetered instrument particles
        result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED, 1)
        result.extend(result1)
        log.debug("RESULT: %s", result)

        # Verify values
        self.assert_data_values(result, 'test_data_1.txt.result.yml')
        
        
         # get the telemetered metadata particle
        result = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1)
        log.debug("*****************************************************  metadata result %s", result)
        #get the telemetered instrument particles
        result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 1)
        result.extend(result1)
        log.debug("RESULT: %s", result)

        # Verify values
        self.assert_data_values(result, 'test_data_1r.txt.result.yml')
       
        
    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir("node59p1.dat", TELEM_DIR)
        self.assert_initialize()
        result = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,1,60)
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED,750,400)

    def test_large_import_recovered(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir("DOS15908.DAT", RECOV_DIR)
        self.assert_initialize()
        result = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED,1,60)
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED,96,400)


    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_step2.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1)
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED, 2)
            result.extend(result1)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1-2.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_TELEMETERED, 0)

            self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                            copy_metadata=False)
            # Now read the first records of the second file then stop
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED, 2)
            log.debug("RESULT 1: %s", result1)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_TELEMETERED, 0)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED, 2)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)
            self.assert_data_values(result, 'test_data_3-4.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_TELEMETERED, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_stop_start_recovered(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('DOS15908_1st7_step1.DAT', RECOV_DIR, "DOS15908.DAT",
                                        copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1)
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 1)
            result.extend(result1)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1r.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.METADATA_RECOVERED, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_RECOVERED, 0)

            self.create_sample_data_set_dir('DOS15908_1st7_step4.DAT', RECOV_DIR, "DOS15909.DAT",
                                            copy_metadata=False)
            # Now read the first records of the second file then stop
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 2)
            log.debug("RESULT 1: %s", result1)
            self.assert_stop_sampling()
 
            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 2)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_sample_queue_size(DataParticleType.METADATA_RECOVERED, 1)
            self.assert_data_values(result, 'test_data_4r.txt.result.yml')
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")


    def test_shutdown_restart(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_step2.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1)
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED, 2)
            result.extend(result1)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1-2.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_TELEMETERED, 0)

            self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                            copy_metadata=False)
            # Now read the first records of the second file then stop
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED, 2)
            log.debug("RESULT 1: %s", result1)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_TELEMETERED, 0)

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()

            # Restart sampling and ensure we get the last 2 records of the file
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED, 2)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)
            self.assert_data_values(result, 'test_data_3-4.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_TELEMETERED, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart_recovered(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('DOS15908_1st7_step1.DAT', RECOV_DIR, "DOS15908.DAT",
                                        copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1)
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 1)
            result.extend(result1)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1r.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.METADATA_RECOVERED, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_RECOVERED, 0)

            self.create_sample_data_set_dir('DOS15908_1st7_step4.DAT', RECOV_DIR, "DOS15909.DAT",
                                            copy_metadata=False)
            # Now read the first records of the second file then stop
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 2)
            log.debug("RESULT 1: %s", result1)

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()

            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 2)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_sample_queue_size(DataParticleType.METADATA_RECOVERED, 1)
            self.assert_data_values(result, 'test_data_4r.txt.result.yml')
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")



    def test_flmb(self):
        """
        Test with data from papa flmb
        """
        self.create_sample_data_set_dir("node10p1.dat", TELEM_DIR, "node59p1.dat")
        self.assert_initialize()
        result = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,1,30)
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED,5,30)


    def test_flma(self):
        """
        Test with data from papa flma
        """
        self.create_sample_data_set_dir("node11p1.dat", TELEM_DIR, "node59p1.dat")
        self.assert_initialize()
        result = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED,1,30)
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE_TELEMETERED,5,30)
        
       
        