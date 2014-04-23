"""
@package mi.dataset.driver.issmcnsm.dosta.test.test_driver
@file marine-integrations/mi/dataset/driver/issmcnsm/dosta/driver.py
@author Emily Hahn
@brief Test cases for issmcnsm_dosta driver

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
import gevent

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter
from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.dataset.driver.issmcnsm.dosta.driver import IssmCnsmDOSTADDataSetDriver
from mi.dataset.parser.issmcnsm_dostad import Issmcnsm_dostadParserDataParticle

RESOURCE_ID = 'dostad'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.issmcnsm.dosta.driver',
    driver_class='IssmCnsmDOSTADDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = IssmCnsmDOSTADDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: RESOURCE_ID,
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_dsatest',
            DataSetDriverConfigKeys.PATTERN: '*.dosta.log',
            DataSetDriverConfigKeys.FREQUENCY: 1,
            DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM = 'issmcnsm_dostad_parsed'

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@unittest.skip('Test files lost, entire driver needs revisiting')
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
        self.create_sample_data('test_data_1.dosta.log', "20130101.dosta.log")
        self.assert_data(Issmcnsm_dostadParserDataParticle, 'test_data_1.txt.result.yml', count=1, timeout=10)

        self.clear_async_data()
        self.create_sample_data('test_data_2.dosta.log', "20130102.dosta.log")
        self.assert_data(Issmcnsm_dostadParserDataParticle, 'test_data_2.txt.result.yml', count=4, timeout=10)

        self.clear_async_data()
        # skipping a file index 20130103 here to make sure it still finds the new file
        self.create_sample_data('test_data_3.dosta.log', "20130104.dosta.log")
        self.assert_data(Issmcnsm_dostadParserDataParticle, count=36, timeout=30)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('test_data_1.dosta.log', "20130105.dosta.log")
        self.assert_data(Issmcnsm_dostadParserDataParticle, count=1, timeout=10)

    def test_resume_file_start(self):
        """
        Test the ability to restart the process
        """
        file_path = self.create_sample_data('test_data_1.dosta.log', "20130101.dosta.log")
        self.memento = {
            '20130101.dosta.log': self.get_file_state(file_path, True, 190),
        }
        self.memento['20130101.dosta.log']['parser_state']['timestamp'] = 3590524817.862

        self.driver = IssmCnsmDOSTADDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data('test_data_2.dosta.log', "20130102.dosta.log")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(Issmcnsm_dostadParserDataParticle, 'test_data_2.txt.result.yml', count=4, timeout=10)

    def test_resume_mid_file(self):
        """
        Test the ability to restart the process in the middle of a file
        """
        path_1 = self.create_sample_data('test_data_1.dosta.log', "20130101.dosta.log")
        path_2 = self.create_sample_data('test_data_2.dosta.log', "20130102.dosta.log")

        self.memento = {
            '20130101.dosta.log': self.get_file_state(path_1, True, 190),
            '20130102.dosta.log': self.get_file_state(path_2, False, 191)
        }
        self.memento['20130101.dosta.log']['parser_state']['timestamp'] = 3590524817.862
        self.memento['20130102.dosta.log']['parser_state']['timestamp'] = 3590524819.861

        self.driver = IssmCnsmDOSTADDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(Issmcnsm_dostadParserDataParticle, 'test_data_2.txt.partial-result.yml', count=3, timeout=10)

    def test_modified(self):
        """
        Test for detection of an ingested file that has been modifed after ingestion
        """
        file_path = self.create_sample_data('test_data_1.dosta.log', "20130101.dosta.log")

        self.memento = {
            '20130101.dosta.log': self.get_file_state(file_path, True, 190),
        }
        self.memento['20130101.dosta.log']['parser_state']['timestamp'] = 3590524817.862

        self.driver = IssmCnsmDOSTADDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # overwrite the old 20130101.dosta.log file
        # NOTE: this does not make you wait until file mod time, since it copies the original file
        # modification time, not when you copy the file in running this test
        self.create_sample_data('test_data_2.dosta.log', "20130101.dosta.log")

        to = gevent.Timeout(30)
        to.start()
        done = False
        try:
            while(not done):
                if 'modified_state' in self.driver._driver_state['20130101.dosta.log']:
                    log.debug("Found modified state %s", self.driver._driver_state['20130101.dosta.log'].get('modified_state' ))
                    done = True

                if not done:
                    log.debug("modification not detected yet, sleep some more...")
                    gevent.sleep(5)
        except Timeout:
            log.error("Failed to find modified file after ingestion")
            self.fail("Failed to find modified file after ingestion")
        finally:
            to.cancel()

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@unittest.skip('Test files lost, entire driver needs revisiting')
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('test_data_1.dosta.log', "20130101.dosta.log")
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
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data('test_data_3.dosta.log', "20130103.dosta.log")
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,36,30)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.error("CONFIG: %s", self._agent_config())
        self.create_sample_data('test_data_1.dosta.log', "20130101.dosta.log")

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

            self.create_sample_data('test_data_2.dosta.log', "20130102.dosta.log")
            # Now read the first three records of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 1)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 3)
            self.assert_data_values(result, 'test_data_2.txt.partial-result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

