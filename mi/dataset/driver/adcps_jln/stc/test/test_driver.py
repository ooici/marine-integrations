"""
@package mi.dataset.driver.adcps_jln.stc.test.test_driver
@file marine-integrations/mi/dataset/driver/adcps_jln/stc/driver.py
@author Maria Lutz
@brief Test cases for adcps_jln_stc driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Maria Lutz'
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
from mi.dataset.driver.adcps_jln.stc.driver import AdcpsJlnStcDataSetDriver
from mi.dataset.parser.adcps_jln_stc import AdcpsJlnStcInstrumentParserDataParticle, DataParticleType
from mi.dataset.parser.adcps_jln_stc import AdcpsJlnStcMetadataParserDataParticle

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.adcps_jln.stc.driver',
    driver_class='AdcpsJlnStcDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = AdcpsJlnStcDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'adcps_jln_stc',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: 'adcp[st]_*.DAT',
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
        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.create_sample_data('first.DAT', 'adcpt_20130929_061817.DAT')
        self.assert_data(None, 'first.result.yml', count=3, timeout=10)
        
        self.create_sample_data('adcpt_20130929_091817.DAT')
        self.assert_data(None, 'second.result.yml', count=6, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data('first.DAT', 'adcpt_20130929_061817.DAT')
        path_2 = self.create_sample_data('adcpt_20130929_091817.DAT')

        # Create and store the new driver state
        state = {
            'adcpt_20130929_061817.DAT': self.get_file_state(path_1, True, 880),
            'adcpt_20130929_091817.DAT': self.get_file_state(path_2, False, 880)
        }
        self.driver = self._get_driver_object(memento=state)

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(None, 'partial_second.result.yml', count=3, timeout=10)

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        self.driver.start_sampling()

        self.create_sample_data('first.DAT', 'adcpt_20130929_061817.DAT')
        self.create_sample_data('adcpt_20130929_091817.DAT')
        self.assert_data(None, 'first.result.yml', count=3, timeout=10)
        self.assert_file_ingested('adcpt_20130929_061817.DAT')
        self.assert_file_not_ingested('adcpt_20130929_091817.DAT')

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(None, 'second.result.yml', count=6, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT')

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        self.clear_sample_data()
        # need to override this because of or in configuration pattern '[st]' matches s or t
        filename = 'adcpt_foo.DAT'

        # create the file so that it is unreadable
        self.create_sample_data(filename, create=True, mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        filename = 'adcpt_foo.DAT'
        self.create_sample_data(filename)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename)

    def test_no_footer(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        self.create_sample_data('no_footer.DAT', 'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('adcpt_20130929_091817.DAT')

    def test_no_header(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        self.create_sample_data('no_header.DAT', 'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('adcpt_20130929_091817.DAT')

    def test_bad_id(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        self.create_sample_data('bad_id.DAT', 'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(None, 'partial_first.result.yml', count=2, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT')

    def test_bad_num_bytes(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        self.create_sample_data('missing_bytes.DAT', 'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(None, 'partial_first.result.yml', count=2, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT')
        
    def test_extra_bytes_between_records(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs. extra_bytes.DAT contains an extra byte just before the ID of record 1768.
        """
        self.create_sample_data('extra_bytes.DAT', 'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(None, 'second.result.yml', count=6, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT')

    def test_receive_fail(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        # no error for receiveFailure marked samples
        self.create_sample_data('recv_fail.DAT', 'adcpt_20130929_091817.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
    
        self.assert_data(None, 'first_fail.result.yml', count=3, timeout=10)
        self.assert_file_ingested('adcpt_20130929_091817.DAT')

    def test_unpack_err(self):
        self.create_sample_data('adcpt_20131113_002307.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('adcpt_20131113_002307.DAT')

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
        self.create_sample_data('first.DAT', 'adcpt_20130929_061817.DAT')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second otherwise samples come in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.ADCPS_JLN_META, 1)
            result2 = self.data_subscribers.get_samples(DataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data("adcpt_20130926_010110.DAT")
        self.assert_initialize()

        # get results for each of the data particle streams
        result = self.data_subscribers.get_samples(DataParticleType.ADCPS_JLN_META, 1)
        result2 = self.data_subscribers.get_samples(DataParticleType.ADCPS_JLN_INS, 36, timeout=60)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('first.DAT', 'adcpt_20130929_061817.DAT')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.ADCPS_JLN_META, 1)
            result2 = self.data_subscribers.get_samples(DataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_INS, 0)

            self.create_sample_data('adcpt_20130929_091817.DAT')
            # Now read the first three records of the second file then stop
            result = self.get_samples(DataParticleType.ADCPS_JLN_META, 1)
            result2 = self.get_samples(DataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("got result %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_INS, 0)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result3 = self.get_samples(DataParticleType.ADCPS_JLN_INS, 3)
            log.debug("got result 3 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'second.result.yml')

            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_INS, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('first.DAT', 'adcpt_20130929_061817.DAT')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.ADCPS_JLN_META, 1)
            result2 = self.data_subscribers.get_samples(DataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_INS, 0)

            self.create_sample_data('adcpt_20130929_091817.DAT')
            # Now read the first three records of the second file then stop
            result = self.get_samples(DataParticleType.ADCPS_JLN_META, 1)
            result2 = self.get_samples(DataParticleType.ADCPS_JLN_INS, 2)
            result.extend(result2)
            log.debug("got result %s", result)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_INS, 0)
            
            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result3 = self.get_samples(DataParticleType.ADCPS_JLN_INS, 3)
            log.debug("got result 3 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'second.result.yml')

            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_META, 0)
            self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_INS, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file is empty, no samples
        filename = 'adcpt_foo.DAT'
        self.create_sample_data(filename)

        self.assert_initialize()

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def test_missing_bytes(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file contains invalid sample values
        self.create_sample_data('missing_bytes.DAT', 'adcpt_20130929_091817.DAT')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(DataParticleType.ADCPS_JLN_META, 1)
        result2 = self.get_samples(DataParticleType.ADCPS_JLN_INS, 1)
        result.extend(result2)
        
        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
        
        self.assert_data_values(result, 'partial_first.result.yml')
        self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_META, 0)
        self.assert_sample_queue_size(DataParticleType.ADCPS_JLN_INS, 0)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        filename = 'adcpt_foo.DAT'

        self.assert_new_file_exception(filename)
    

