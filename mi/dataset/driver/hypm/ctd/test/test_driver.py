"""
@package mi.dataset.driver.hypm.ctd.test.test_driver
@file marine-integrations/mi/dataset/driver/hypm/ctd/test/test_driver.py
@author Bill French
@brief Test cases for hypm/ctd driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import unittest
import gevent

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

from exceptions import Exception

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.core.exceptions import ConfigurationException
from mi.idk.exceptions import SampleTimeout

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter
from mi.dataset.driver.hypm.ctd.driver import HypmCTDPFDataSetDriver

from mi.dataset.parser.ctdpf import CtdpfParserDataParticle
from pyon.agent.agent import ResourceAgentState

from interface.objects import ResourceAgentErrorEvent

DATADIR='/tmp/dsatest'
STORAGEDIR='/tmp/stored_dsatest'
RESOURCE_ID='ctdpf'

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.hypm.ctd.driver',
    driver_class="HypmCTDPFDataSetDriver",

    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = HypmCTDPFDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: RESOURCE_ID,
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: DATADIR,
            DataSetDriverConfigKeys.STORAGE_DIRECTORY: STORAGEDIR,
            DataSetDriverConfigKeys.PATTERN: '*.txt',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM='ctdpf_parsed'
    
###############################################################################
#                                INT TESTS                                   #
# Device specific unit tests are for                                          #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver sampling
        can be started and stopped.
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('test_data_1.txt', "DATA001.txt")
        self.assert_data(CtdpfParserDataParticle, 'test_data_1.txt.result.yml', count=1, timeout=10)
        self.assert_file_ingested("DATA001.txt")

        self.clear_async_data()
        self.create_sample_data('test_data_3.txt', "DATA002.txt")
        self.assert_data(CtdpfParserDataParticle, 'test_data_3.txt.result.yml', count=8, timeout=10)
        self.assert_file_ingested("DATA002.txt")

        self.clear_async_data()
        self.create_sample_data('DATA003.txt')
        self.assert_data(CtdpfParserDataParticle, count=436, timeout=20)
        self.assert_file_ingested("DATA003.txt")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('test_data_1.txt', "DATA004.txt")
        self.assert_data(CtdpfParserDataParticle, count=1, timeout=10)
        self.assert_file_ingested("DATA004.txt")

    def test_harvester_config_exception(self):
        """
        Start the a driver with a bad configuration.  Should raise
        an exception.
        """
        with self.assertRaises(ConfigurationException):
            self.driver = HypmCTDPFDataSetDriver({},
                self.memento,
                self.data_callback,
                self.state_callback,
                self.event_callback,
                self.exception_callback)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # create some data to parse
        self.clear_async_data()
        self.create_sample_data('test_data_1.txt', "DATA001.txt")
        self.create_sample_data('test_data_3.txt', "DATA002.txt")

        state = {
            'DATA001.txt': self.get_file_state('/tmp/dsatest/DATA001.txt', True),
            'DATA002.txt': self.get_file_state('/tmp/dsatest/DATA002.txt', False, 209),
        }
        state['DATA002.txt']['parser_state']['timestamp'] = 3583861265.0

        self.driver = HypmCTDPFDataSetDriver(
            self._driver_config()['startup_config'],
            state,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(CtdpfParserDataParticle, 'test_data_3.txt.partial_results.yml', count=5, timeout=10)
        # verify we got the rest of the file
        self.assert_file_ingested("DATA002.txt")

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # create some data to parse
        self.clear_async_data()
        
        self.driver.start_sampling()
        
        self.create_sample_data('test_data_1.txt', "DATA001.txt")
        self.create_sample_data('test_data_3.txt', "DATA002.txt")
        self.assert_data(CtdpfParserDataParticle, 'test_data_1.txt.result.yml', count=1, timeout=10)
        self.assert_file_ingested("DATA001.txt")
        self.assert_file_not_ingested("DATA002.txt")
        
        self.driver.stop_sampling()
        self.driver.start_sampling()
        
        self.assert_data(CtdpfParserDataParticle, 'test_data_3.txt.result.yml', count=8, timeout=10)
        self.assert_file_ingested("DATA002.txt")

    def test_bad_sample(self):
        """
        Test a bad sample.  To do this we set a state to the middle of a record
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('bad_sample_data.txt', "DATA001.txt")
        self.assert_data(CtdpfParserDataParticle, 'bad_sample_data.txt.result.yml', count=2, timeout=10)
        gevent.sleep(5)
        self.assert_file_ingested("DATA001.txt")


###############################################################################

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    def setUp(self):
        super(QualificationTest, self).setUp()

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('test_data_1.txt', 'DATA001.txt')
        self.assert_initialize()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """
        self.create_sample_data('DATA003.txt')
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,436,120)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.error("CONFIG: %s", self._agent_config())
        self.create_sample_data('test_data_1.txt', 'DATA001.txt')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('test_data_3.txt', 'DATA003.txt')
            # Now read the first three records of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 3)
            log.debug("Time to stop sampling")
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 5 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 5)
            self.assert_data_values(result, 'test_data_3.txt.partial_results.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test the agents ability to start data flowing, stop the agent, then
        restart the agent and read at the correct spot.
        """
        log.error("CONFIG: %s", self._agent_config())
        self.create_sample_data('test_data_1.txt', 'DATA001.txt')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('test_data_3.txt', 'DATA003.txt')
            # Now read the first three records of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 3)
            log.debug("Time to stop sampling")
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
            
            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 5 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 5)
            self.assert_data_values(result, 'test_data_3.txt.partial_results.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    @unittest.skip("test failing.  Must be fixed when this driver is released")
    def test_parser_exception(self):
        """
        Test an exception raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        self.create_sample_data('test_data_2.txt', 'DATA002.txt')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(SAMPLE_STREAM, 9)
        self.assert_sample_queue_size(SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
