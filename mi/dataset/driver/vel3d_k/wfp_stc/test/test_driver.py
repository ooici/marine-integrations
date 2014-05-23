"""
@package mi.dataset.driver.vel3d_k.wfp_stc.test.test_driver
@file marine-integrations/mi/dataset/driver/vel3d_k/wfp_stc/driver.py
@author Steve Myerson (Raytheon)
@brief Test cases for vel3d_k_wfp_stc driver

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
from mi.core.exceptions import SampleException, DatasetParserException
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import \
  DataSourceConfigKey, \
  DataSetDriverConfigKeys, \
  DriverParameter

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent


from mi.dataset.driver.vel3d_k.wfp_stc.driver import \
  Vel3dKWfpStcDataSetDriver

from mi.dataset.parser.vel3d_k_wfp_stc import \
  DataParticleType, \
  StateKey, \
  Vel3dKWfpStcTimeDataParticle, \
  Vel3dKWfpStcVelocityDataParticle


# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.vel3d_k.wfp_stc.driver',
    driver_class='Vel3dKWfpStcDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = Vel3dKWfpStcDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'vel3d_k_wfp_stc',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: 'A*.DEC',
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
        Test that we can get data from multiple files.
        """
        log.info("START INTEG TEST GET")

        # Start sampling.
        self.clear_sample_data()
        self.driver.start_sampling()
        self.clear_async_data()

        # From sample file A0000010.DEC:
        # Flag record, first and last velocity record, time record.
        log.info("FIRST FILE A0000002 INTEG TEST GET")
        self.create_sample_data('valid_A0000002.DEC', "A0000002.DEC")
        self.assert_data(None, 'valid_A0000002.yml', 
          count=3, timeout=10)

        # From sample file A0000010.DEC:
        # Flag record, first and last velocity records twice, time record.
        log.info("SECOND FILE A0000004 INTEG TEST GET")
        self.clear_async_data()
        self.create_sample_data('valid_A0000004.DEC', "A0000004.DEC")
        self.assert_data(None, 'valid_A0000004.yml', 
          count=5, timeout=10)

        # Made-up data with all flags set to True.
        # Field values may not be realistic.
        log.info("THIRD FILE A0000003 INTEG TEST GET")
        self.clear_async_data()
        self.create_sample_data('all_A0000003.DEC', "A0000003.DEC")
        self.assert_data(None, 'all_A0000003.yml', 
          count=4, timeout=10)
        log.info("END INTEG TEST GET")

    def test_incomplete_file(self):
        """
        Test that we can handle a file missing the end of Velocity records.
        Should generate a SampleException.
        """
        log.info("START INTEG TEST INCOMPLETE")

        self.clear_sample_data()
        self.clear_async_data()

        # From sample file A0000010.DEC:
        # Flag record, first and last velocity record, time record,
        # but the end of Velocity record (all zeroes) is missing.
        filename = "A1000002.DEC"
        self.create_sample_data('incomplete_A0000002.DEC', filename)

        # Start sampling.
        self.driver.start_sampling()

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

        # Verify that the entire file has been read.
        self.assert_file_ingested(filename)

        log.info("END INTEG TEST INCOMPLETE")

    def test_invalid_flag_record(self):
        """
        Test that we can handle a file with an invalid Flag record.
        Should generate a SampleException.
        """
        log.info("START INTEG TEST INVALID")

        self.clear_sample_data()
        self.clear_async_data()

        # Made-up data with all flags except the first set to True.
        # First flag is not a zero or one.
        filename = "A1000003.DEC"
        self.create_sample_data('invalid_A0000003.DEC', filename)

        # Start sampling.
        self.driver.start_sampling()

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

        # Verify that the entire file has been read.
        self.assert_file_ingested(filename)
        log.info("END INTEG TEST INVALID")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("START INTEG TEST STOP RESUME")
        filename_1 = "A0000002.DEC"
        filename_2 = "A0000004.DEC"

        path_1 = self.create_sample_data('valid_A0000002.DEC', filename_1)
        path_2 = self.create_sample_data('valid_A0000004.DEC', filename_2)

        # Create and store the new driver state
        # Set status of file 1 to completely read.
        # Set status of file 2 to start reading at record 3 of a 4 record file.
        state = {
            filename_1 : self.get_file_state(path_1, True, 50),
            filename_2 : self.get_file_state(path_2, False, 74)
        }
        state[filename_1]['parser_state'][StateKey.FIRST_RECORD] = False
        state[filename_1]['parser_state'][StateKey.VELOCITY_END] = True
        state[filename_2]['parser_state'][StateKey.FIRST_RECORD] = False
        state[filename_2]['parser_state'][StateKey.VELOCITY_END] = False
        self.driver = self._get_driver_object(memento=state)

        self.clear_async_data()
        self.driver.start_sampling()

        # Verify that data is produced 
        # (last 2 velocity records plus time record).
        self.assert_data(None, 'valid_partial_A0000004.yml', 
          count=3, timeout=10)
        log.info("END INTEG TEST STOP RESUME")

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_incomplete_file(self):
        """
        Test that we can handle a file missing the end of Velocity records,
        which means we'll run off the end of the file reading Velocity records.
        Should generate a SampleException.
        """
        log.info("START QUAL TEST INCOMPLETE FILE")

        # From sample file A0000010.DEC:
        # Flag record, first and last velocity record, time record,
        # but the end of Velocity record (all zeroes) is missing.
        self.clear_sample_data()
        self.event_subscribers.clear_events()
        self.assert_initialize()
        self.create_sample_data('incomplete_A0000002.DEC', "A1000002.DEC")

        # Verify an event was raised and we are in our retry state.
        self.verify_queue_empty()
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        log.info("END QUAL TEST INCOMPLETE FILE")

    def test_invalid_flag_record(self):
        """
        Test that we can handle a file with an invalid Flag record.
        Should generate a SampleException.
        """
        log.info("START QUAL TEST INVALID FLAG RECORD")

        # Made-up data with all flags except the first set to True.
        # First flag is not a zero or one.
        self.clear_sample_data()
        self.event_subscribers.clear_events()
        self.assert_initialize()
        self.create_sample_data('invalid_A0000003.DEC', "A1000003.DEC")

        # Verify an event was raised and we are in our retry state.
        self.verify_queue_empty()
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        log.info("END QUAL TEST INVALID FLAG RECORD")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once.
        """
        log.info("START QUAL TEST LARGE IMPORT")

        # The sample file referenced in the IDD.
        # Contains 522 velocity data records.
        self.create_sample_data('idd_A0000010.DEC', 'A0000010.DEC')
        filesize = 522
        records_per_second = 4
        max_time = 2 * (filesize / records_per_second)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
          {DriverParameter.RECORDS_PER_SECOND: records_per_second})
        self.assert_start_sampling()

        try:
            self.get_samples(DataParticleType.VELOCITY_PARTICLE,
              filesize, max_time)
            self.get_samples(DataParticleType.TIME_PARTICLE, 1)
            self.verify_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("END QUAL TEST LARGE IMPORT")

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent.
        """
        log.info("START QUAL TEST PUBLISH PATH")
        self.create_sample_data('valid_A0000004.DEC', "A0000004.DEC")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
          {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Verify that we get 4 velocity samples with the correct values.
            result = self.data_subscribers.get_samples(
              DataParticleType.VELOCITY_PARTICLE, 4)
            self.assert_data_values(result, 'valid_no_time_A0000004.yml')

            # Verify that we get the Time sample.
            time_result = self.data_subscribers.get_samples(
              DataParticleType.TIME_PARTICLE, 1)

            # Combine the velocity and time samples and verify results.
            result.extend(time_result)
            self.assert_data_values(result, 'valid_A0000004.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        log.info("END QUAL TEST PUBLISH PATH")

    def test_shutdown_restart(self):
        """
        Test the agents ability to start data flowing, shutdown, then restart
        at the correct spot.
        """
        log.info("START QUAL TEST SHUTDOWN RESTART")
        self.create_sample_data('all_A0000003.DEC', "A0000003.DEC")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
          {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file (3 velocity records) and verify the data.
            result = self.get_samples(DataParticleType.VELOCITY_PARTICLE, 3)
            time_result = self.get_samples(DataParticleType.TIME_PARTICLE, 1)
            result.extend(time_result)

            # Verify values
            self.assert_data_values(result, 'all_A0000003.yml')
            self.verify_queue_empty()

            # Read the first 2 velocity records of the second file then stop.
            self.create_sample_data('valid_A0000004.DEC', "A0000004.DEC")
            result = self.get_samples(DataParticleType.VELOCITY_PARTICLE, 2)
            self.assert_stop_sampling()
            self.verify_queue_empty()

            # Stop the agent
            self.stop_dataset_agent_client()
            # Re-start the agent
            self.init_dataset_agent_client()
            # Re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and get the last 2 records of the file
            # and combine with the previous ones we read.
            self.assert_start_sampling()
            result2 = self.get_samples(DataParticleType.VELOCITY_PARTICLE, 2)
            result.extend(result2)

            # Get the time record and combine with previous records.
            time_result = self.data_subscribers.get_samples(
              DataParticleType.TIME_PARTICLE, 1)
            result.extend(time_result)
            self.assert_data_values(result, 'valid_A0000004.yml')

            self.verify_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("END QUAL TEST SHUTDOWN RESTART")

    def test_stop_resume_at_time_record(self):
        """
        Test the agents ability to start data flowing, stop after having
        read all the velocity records, then restart at the correct spot.
        """
        log.info("START QUAL TEST STOP RESUME AT TIME RECORD")

        # Read the velocity records of a 4 velocity record file.
        self.create_sample_data('valid_A0000004.DEC', "A0000004.DEC")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
          {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()
        result = self.get_samples(DataParticleType.VELOCITY_PARTICLE, 4)

        self.assert_stop_sampling()
        self.verify_queue_empty()

        # Get the time record and combine with previous records.
        self.assert_start_sampling()
        time_result = self.data_subscribers.get_samples(
          DataParticleType.TIME_PARTICLE, 1)
        result.extend(time_result)
        self.assert_data_values(result, 'valid_A0000004.yml')
        self.verify_queue_empty()

        log.info("END QUAL TEST STOP RESUME AT TIME RECORD")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("START QUAL TEST STOP START")
        self.create_sample_data('all_A0000003.DEC', "A0000003.DEC")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
          {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file (3 velocity records) and verify the data.
            result = self.get_samples(DataParticleType.VELOCITY_PARTICLE, 3)
            time_result = self.get_samples(DataParticleType.TIME_PARTICLE, 1)
            result.extend(time_result)

            # Verify values
            self.assert_data_values(result, 'all_A0000003.yml')
            self.verify_queue_empty()

            # Read the first 2 velocity records of the second file then stop.
            self.create_sample_data('valid_A0000004.DEC', "A0000004.DEC")
            result = self.get_samples(DataParticleType.VELOCITY_PARTICLE, 2)
            self.assert_stop_sampling()
            self.verify_queue_empty()

            # Restart sampling and get the last 2 records of the file
            # and combine with the previous ones we read.
            self.assert_start_sampling()
            result2 = self.get_samples(DataParticleType.VELOCITY_PARTICLE, 2)
            result.extend(result2)

            # Get the time record and combine with previous records.
            time_result = self.data_subscribers.get_samples(
              DataParticleType.TIME_PARTICLE, 1)
            result.extend(time_result)
            self.assert_data_values(result, 'valid_A0000004.yml')

            self.verify_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.info("END QUAL TEST STOP START")

    def verify_queue_empty(self):
        """
        Assert the sample queue for all data streams is empty.
        """
        self.assert_sample_queue_size(DataParticleType.VELOCITY_PARTICLE, 0)
        self.assert_sample_queue_size(DataParticleType.TIME_PARTICLE, 0)

