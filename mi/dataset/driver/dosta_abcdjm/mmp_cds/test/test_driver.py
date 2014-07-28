"""
@package mi.dataset.driver.dosta_abcdjm.mmp_cds.test.test_driver
@file marine-integrations/mi/dataset/driver/dosta_abcdjm/mmp_cds/driver.py
@author Mark Worden
@brief Test cases for dosta_abcdjm_mmp_cds driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

from mi.core.log import get_logger
log = get_logger()

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DriverParameter, DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.dosta_abcdjm.mmp_cds.driver import DostaAbcdjmMmpCdsDataSetDriver

from mi.dataset.parser.dosta_abcdjm_mmp_cds import DostaAbcdjmMmpCdsParserDataParticle, DataParticleType

from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.dosta_abcdjm.mmp_cds.driver',
    driver_class='DostaAbcdjmMmpCdsDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=DostaAbcdjmMmpCdsDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'dosta_abcdjm_mmp_cds',
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
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.create_sample_data('optode_1_20131124T005004_458.mpk', "test_get.mpk")

        self.assert_data(DostaAbcdjmMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)

        self.get_samples(DostaAbcdjmMmpCdsParserDataParticle, count=85, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.create_sample_data('optode_1_20131124T005004_458.mpk', "test_stop_resume.mpk")
        self.assert_data(DostaAbcdjmMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        self.assert_data(DostaAbcdjmMmpCdsParserDataParticle, 'second.yml', count=1, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.create_sample_data('optode_1_20131124T005004_459.mpk', "test_stop_start_resume_001.mpk")
        self.assert_data(DostaAbcdjmMmpCdsParserDataParticle, 'first2.yml', count=1, timeout=10)

        self.create_sample_data('optode_1_20131124T005004_458.mpk', "test_stop_start_resume_000.mpk")
        self.assert_data(DostaAbcdjmMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)

        # Retrieve all remaining samples
        self.get_samples(DostaAbcdjmMmpCdsParserDataParticle, count=93, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Clear the sample file data
        self.clear_sample_data()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        self.create_sample_data('optode_1_20131124T005004_459.mpk', "test_stop_start_resume_010.mpk")
        self.create_sample_data('optode_1_20131124T005004_458.mpk', "test_stop_start_resume_009.mpk")
        self.assert_data(DostaAbcdjmMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)

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

        self.create_sample_data('optode_1_20131124T005004_BAD.mpk', "test_sample_exception_002.mpk")

        # Notify the driver to start sampling
        self.driver.start_sampling()

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
        self.create_sample_data('optode_1_20131124T005004_458.mpk', 'test_publish_path.mpk')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 1)
            result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 2)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first_three.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Unexpected Exception trapped.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data('large_import.mpk', 'test_large_import.mpk')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Speed up to 10 records per second
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 10})
        self.assert_start_sampling()

        # Verify we can retrieve 1000 samples
        try:
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 1000, 1000)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'large_import.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Unexpected Exception trapped.")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())

        self.create_sample_data('stop_start1.mpk', 'stop_start1.mpk')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})

        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 3, 10)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'stop_start1.yml')

            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

            self.create_sample_data('stop_start2.mpk', 'stop_start2.mpk')

            # Now read the first three records of the second file then stop
            result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 3, 10)
            log.debug("got result %s", result2)

            # Stop sampling
            self.assert_stop_sampling()

            # Make sure there are no samples in the queue
            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()

            result3 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 3, 10)
            log.debug("got result 3 %s", result3)
            result2.extend(result3)
            self.assert_data_values(result2, 'stop_start2.yml')

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

        self.create_sample_data('stop_start1.mpk', 'stop_start1.mpk')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})

        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 3, 10)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'stop_start1.yml')

            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

            self.create_sample_data('stop_start2.mpk', 'stop_start2.mpk')

            # Now read the first three records of the second file then stop
            result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 3, 10)
            log.debug("got result %s", result2)

            # Stop sampling
            self.assert_stop_sampling()

            # stop the agent
            self.stop_dataset_agent_client()

            # re-start the agent
            self.init_dataset_agent_client()

            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()

            result3 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 3, 10)
            log.debug("got result 3 %s", result3)
            result2.extend(result3)
            self.assert_data_values(result2, 'stop_start2.yml')

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


