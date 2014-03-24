"""
@package mi.dataset.driver.dofst_k.wfp.test.test_driver
@file marine-integrations/mi/dataset/driver/dofst_k/wfp/driver.py
@author Emily Hahn
@brief Test cases for dofst_k_wfp driver

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

from nose.plugins.attrib import attr
from mock import Mock

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout
from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DriverParameter
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.dofst_k.wfp.driver import DofstKWfpDataSetDriver
from mi.dataset.parser.dofst_k_wfp import DofstKWfpParserDataParticle, DataParticleType
from mi.dataset.parser.wfp_c_file_common import StateKey

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.dofst_k.wfp.driver',
    driver_class='DofstKWfpDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = DofstKWfpDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'dofst_k_wfp',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: 'C*.DAT',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
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

    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('first.DAT', "C0000001.DAT")
        self.assert_data_multiple_class('first.result.yml', count=4, timeout=10)

        self.clear_async_data()
        self.create_sample_data('second.DAT', "C0000002.DAT")
        self.assert_data_multiple_class('second.result.yml', count=7, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data('first.DAT', "C0000001.DAT")
        path_2 = self.create_sample_data('second.DAT', "C0000002.DAT")

        # Create and store the new driver state
        state = {
            'C0000001.DAT': self.get_file_state(path_1, True, 33),
            'C0000002.DAT': self.get_file_state(path_2, False, 33)
        }
        # only the position field in the parser state is initialized in get_file_state, need to add the other state fields
        state['C0000001.DAT']['parser_state'][StateKey.TIMESTAMP] = 3589862588.666667
        state['C0000001.DAT']['parser_state'][StateKey.RECORDS_READ] = 3
        state['C0000001.DAT']['parser_state'][StateKey.METADATA_SENT] = True
        state['C0000002.DAT']['parser_state'][StateKey.TIMESTAMP] = 3589862495.333333
        state['C0000002.DAT']['parser_state'][StateKey.RECORDS_READ] = 3
        state['C0000002.DAT']['parser_state'][StateKey.METADATA_SENT] = True

        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data_multiple_class('partial_second.result.yml', count=3, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data('first.DAT', "C0000001.DAT")
        self.create_sample_data('second.DAT', "C0000002.DAT")
        self.assert_data_multiple_class('first.result.yml', count=4, timeout=10)
        self.assert_file_ingested("C0000001.DAT")
        self.assert_file_not_ingested("C0000002.DAT")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data_multiple_class('second.result.yml', count=7, timeout=10)
        self.assert_file_ingested("C0000002.DAT")

    def test_sample_exception_empty(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs.  In this case an empty file will produce a sample exception.
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester']['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data(filename)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename)

    def test_sample_exception_num_samples(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs.  In this case an empty file will produce a sample exception.
        """
        self.clear_async_data()
        self.create_sample_data('bad_num_samples.DAT', 'C0000001.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('C0000001.DAT')

    def test_timestamp_only(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs.  In this case an empty file will produce a sample exception.
        """
        self.clear_async_data()
        self.create_sample_data('ts_only.DAT', 'C0000001.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        self.assert_data_multiple_class('ts_only.result.yml', count=1, timeout=10)
        self.assert_file_ingested('C0000001.DAT')

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def assert_all_queue_empty(self):
        """
        Assert the sample queue for all 3 data streams is empty
        """
        self.assert_sample_queue_size(DataParticleType.METADATA, 0)
        self.assert_sample_queue_size(DataParticleType.DATA, 0)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('first.DAT', 'C0000001.DAT')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # NOTE: If the processing is not slowed down here, the engineering samples are
        # returned in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.METADATA, 1)
            log.debug("First RESULT: %s", result)

            result_2 = self.data_subscribers.get_samples(DataParticleType.DATA, 3)
            log.debug("Second RESULT: %s", result_2)

            result.extend(result_2)
            log.debug("Extended RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data('C0000038.DAT')
        self.assert_initialize()

        # get results for each of the data particle streams
        result1 = self.get_samples(DataParticleType.METADATA,1,10)
        result2 = self.get_samples(DataParticleType.DATA,270,40)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('first.DAT', "C0000001.DAT")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data
            result = self.get_samples(DataParticleType.METADATA)
            result2 = self.get_samples(DataParticleType.DATA, 3)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
            self.assert_all_queue_empty()

            self.create_sample_data('second.DAT', "C0000002.DAT")
            # Now read the first three records (1 metadata, 2 data) of the second file then stop
            result = self.get_samples(DataParticleType.METADATA)
            result2 = self.get_samples(DataParticleType.DATA, 2)
            result.extend(result2)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # Restart sampling and ensure we get the last 4 records of the file
            self.assert_start_sampling()
            result3 = self.get_samples(DataParticleType.DATA, 4)
            log.debug("got result 2 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'second.result.yml')

            self.assert_all_queue_empty()
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('first.DAT', "C0000001.DAT")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data
            result = self.get_samples(DataParticleType.METADATA)
            result2 = self.get_samples(DataParticleType.DATA, 3)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
            self.assert_all_queue_empty()

            self.create_sample_data('second.DAT', "C0000002.DAT")
            # Now read the first three records (1 metadata, 2 data) of the second file then stop
            result = self.get_samples(DataParticleType.METADATA)
            result2 = self.get_samples(DataParticleType.DATA, 2)
            result.extend(result2)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 4 records of the file
            self.assert_start_sampling()
            result3 = self.get_samples(DataParticleType.DATA, 4)
            log.debug("got result 2 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'second.result.yml')

            self.assert_all_queue_empty()
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        self.create_sample_data('bad_num_samples.DAT', 'C0000001.DAT')
        self.create_sample_data('first.DAT', 'C0000002.DAT')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(DataParticleType.METADATA)
        result1 = self.get_samples(DataParticleType.DATA, 3)
        result.extend(result1)
        self.assert_data_values(result, 'first.result.yml')
        self.assert_all_queue_empty();

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

