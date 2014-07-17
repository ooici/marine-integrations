"""
@package mi.dataset.driver.vel3d_a.mmp_cds.test.test_driver
@file marine-integrations/mi/dataset/driver/vel3d_a/mmp_cds/driver.py
@author Jeremy Amundson
@brief Test cases for vel3d_a_mmp_cds driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DriverParameter, DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.vel3d_a.mmp_cds.driver import Vel3dAMmpCdsDataSetDriver

from mi.dataset.parser.vel3d_a_mmp_cds import Vel3dAMmpCdsParserDataParticle, DataParticleType

from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.vel3d_a.mmp_cds.driver',
    driver_class='Vel3dAMmpCdsDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = Vel3dAMmpCdsDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'vel3d_a_mmp_cds',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: '*.mpk',
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
        Test that we can get data from files. Verify that the driver
        sampling can be started and stopped
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.create_sample_data('first_data.mpk', "test_get.mpk")

        self.assert_data(Vel3dAMmpCdsParserDataParticle, 'first_data.yml', count=193, timeout=30)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.create_sample_data('first_data.mpk', "test_stop_resume.mpk")
        self.assert_data(Vel3dAMmpCdsParserDataParticle, 'first_four.yml', count=4, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        self.assert_data(Vel3dAMmpCdsParserDataParticle, 'second.yml', count=4, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.create_sample_data('second_data.mpk', "test_stop_start_resume_001.mpk")
        self.assert_data(Vel3dAMmpCdsParserDataParticle, 'second_data.yml', count=20, timeout=20)

        self.create_sample_data('first_data.mpk', "test_stop_start_resume_000.mpk")
        self.assert_data(Vel3dAMmpCdsParserDataParticle, 'first_four.yml', count=4, timeout=10)

        # Retrieve all remaining samples
        self.get_samples(Vel3dAMmpCdsParserDataParticle, count=189, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Clear the sample file data
        self.clear_sample_data()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        self.create_sample_data('second_data.mpk', "test_stop_start_resume_010.mpk")
        self.create_sample_data('first_data.mpk', "test_stop_start_resume_009.mpk")
        self.assert_data(Vel3dAMmpCdsParserDataParticle, 'first_data.yml', count=193, timeout=10)
        self.assert_data(Vel3dAMmpCdsParserDataParticle, 'second_data.yml', count=20, timeout=20)

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        self.create_sample_data('not-msg-pack.mpk', "test_sample_exception_001.mpk")

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.assert_event('ResourceAgentErrorEvent')

        # Notify the driver to stop sampling
        self.driver.stop_sampling()

        # Clear the sample file data
        self.clear_sample_data()

        self.create_sample_data('acm_1_20131124T005004_BAD.mpk', "test_sample_exception_002.mpk")

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.assert_event('ResourceAgentErrorEvent')


###############################################################################
# QUALIFICATION TESTS #
# Device specific qualification tests are for #
# testing device specific capabilities #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('first_data.mpk', 'test_publish_path.mpk')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second otherwise samples come in the wrong order
        #self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get four samples
        try:
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 2, 100)
            result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 2, 100)
            result.extend(result2)
            log.info("RESULT: %s", result)
            #
            # # Verify values
            self.assert_data_values(result, 'first_four.yml')
        except Exception as e:

            log.error("Exception trapped: %s", e)
            self.fail("Unexpected Exception trapped.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data('first_data.mpk', 'test_large_import.mpk')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Speed up processing to 10 per second
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 10})
        self.assert_start_sampling()

        # Verify we can retrieve 1000 samples
        try:
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 193, 100)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_data.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Unexpected Exception trapped.")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())

        self.create_sample_data('first_data.mpk', 'stop_start1.mpk')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 2})

        self.assert_start_sampling()

        # Verify we first get 193 samples and then 20 samples
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 4, 200)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_four.yml')

            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 189, 200)

            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

            self.create_sample_data('second_data.mpk', 'stop_start2.mpk')

            # Now read the first ten records of the second file then stop
            result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 10, 110)
            log.debug("got result %s", result2)

            # Stop sampling
            self.assert_stop_sampling()

            # Make sure there are no samples in the queue
            #self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

            # Restart sampling and ensure we get the last ten records of the file
            self.assert_start_sampling()

            result3 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 10, 100)
            log.debug("got result 3 %s", result3)
            result2.extend(result3)
            self.assert_data_values(result2, 'second_data.yml')

            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

        except Exception as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Unexpected Exception trapped.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())

        self.create_sample_data('first_data.mpk', 'stop_start1.mpk')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 2})

        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 4, 200)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_four.yml')

            # dump extra data
            self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 189, 200)

            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

            self.create_sample_data('second_data.mpk', 'stop_start2.mpk')

            # Now read the first ten records of the second file then stop
            result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 10, 200)
            log.debug("got result %s", result2)

            # Stop sampling
            self.assert_stop_sampling()

            # stop the agent
            self.stop_dataset_agent_client()

            # re-start the agent
            self.init_dataset_agent_client()

            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last ten records of the file
            self.assert_start_sampling()

            result3 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 10, 100)
            log.debug("got result 3 %s", result3)
            result2.extend(result3)
            self.assert_data_values(result2, 'second_data.yml')

            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

        except Exception as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Unexpected Exception trapped.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.assert_initialize()

        # Clear any prior events
        self.event_subscribers.clear_events()

        filename = 'not-msg-pack.mpk'
        self.create_sample_data(filename)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

