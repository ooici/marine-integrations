"""
@package mi.dataset.driver.optaa_ac.mmp_cds.test.test_driver
@file marine-integrations/mi/dataset/driver/optaa_ac/mmp_cds/driver.py
@author Mark Worden
@brief Test cases for optaa_ac_mmp_cds driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DriverParameter, DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.optaa_ac.mmp_cds.driver import OptaaAcMmpCdsDataSetDriver
from mi.dataset.parser.optaa_ac_mmp_cds import OptaaAcMmpCdsParserDataParticle, DataParticleType

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

# Driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.optaa_ac.mmp_cds.driver',
    driver_class='OptaaAcMmpCdsDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=OptaaAcMmpCdsDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'optaa_ac_mmp_cds',
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
        Test that we can get data from files.
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.create_sample_data('acs_archive.mpk', "test_get.mpk")

        self.assert_data(OptaaAcMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)

        self.get_samples(OptaaAcMmpCdsParserDataParticle, count=39, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.create_sample_data('stop_resume.mpk')
        self.assert_data(OptaaAcMmpCdsParserDataParticle, 'stop_resume_1.yml', count=1, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        self.assert_data(OptaaAcMmpCdsParserDataParticle, 'stop_resume_2.yml', count=1, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        self.create_sample_data("stop_start_resume_2.mpk")
        self.assert_data(OptaaAcMmpCdsParserDataParticle, 'stop_start_resume_2.yml', count=1, timeout=10)

        self.create_sample_data("stop_start_resume_1.mpk")
        self.assert_data(OptaaAcMmpCdsParserDataParticle, 'stop_start_resume_1.yml', count=1, timeout=10)

        # Retrieve all remaining samples
        self.get_samples(OptaaAcMmpCdsParserDataParticle, count=9, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Clear the sample file data
        self.clear_sample_data()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        self.create_sample_data('stop_start_resume_2.mpk', "stop_start_resume_4.mpk")
        self.create_sample_data('stop_start_resume_1.mpk', "stop_start_resume_3.mpk")
        self.assert_data(OptaaAcMmpCdsParserDataParticle, 'stop_start_resume_1.yml', count=1, timeout=10)

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

        self.create_sample_data('acs_archive_BAD.mpk', "test_sample_exception_002.mpk")

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
        self.create_sample_data('test_publish_path.mpk')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 1)
            result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 2)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_publish_path.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Unexpected Exception trapped.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data('large_import.mpk')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second otherwise samples come in the wrong order
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

        self.create_sample_data('qual_stop_start_1.mpk')

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
            self.assert_data_values(result, 'qual_stop_start_1.yml')

            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

            self.create_sample_data('qual_stop_start_2.mpk')

            # Now read the first three records of the second file then stop
            result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 3, 10)
            log.debug("got result %s", result2)

            # Stop sampling
            self.assert_stop_sampling()

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()

            result3 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT, 3, 10)
            log.debug("got result 3 %s", result3)
            result2.extend(result3)
            self.assert_data_values(result2, 'qual_stop_start_2.yml')

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

        self.create_sample_data('qual_stop_start_1.mpk')

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
            self.assert_data_values(result, 'qual_stop_start_1.yml')

            self.assert_sample_queue_size(DataParticleType.INSTRUMENT, 0)

            self.create_sample_data('qual_stop_start_2.mpk')

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
            self.assert_data_values(result2, 'qual_stop_start_2.yml')

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