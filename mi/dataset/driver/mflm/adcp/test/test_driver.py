"""
@package mi.dataset.driver.mflm.adcp.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/adcp/driver.py
@author Emily Hahn
@brief Test cases for mflm_adcp driver

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
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

from mi.core.instrument.instrument_driver import DriverEvent
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey

from mi.dataset.driver.mflm.adcp.driver import MflmADCPSDataSetDriver
from mi.dataset.parser.adcps import AdcpsParserDataParticle

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent


# Fill in the blanks to initialize data set test case
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.adcp.driver',
    driver_class='MflmADCPSDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = MflmADCPSDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'adcps',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_dsatest',
            DataSetDriverConfigKeys.PATTERN: 'node59p1.dat',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM='adcps_jln_sio_mule_instrument'

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
        
    def clean_file(self):
        # remove just the file we are using
        driver_config = self._driver_config()['startup_config']
        log.debug('startup config %s', driver_config)
        fullfile = os.path.join(driver_config['harvester']['directory'],
                            driver_config['harvester']['pattern'])
        if os.path.exists(fullfile):
            os.remove(fullfile)

    def test_get(self):
        self.clean_file()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data("node59p1_step1.dat", "node59p1.dat")
        self.assert_data(AdcpsParserDataParticle, 'test_data_1.txt.result.yml',
                         count=2, timeout=10)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")
        self.assert_data(AdcpsParserDataParticle, 'test_data_2.txt.result.yml',
                         count=1, timeout=10)

        # now 'appends' the rest of the data and just check if we get the right number
        self.clear_async_data()
        self.create_sample_data("node59p1_step4.dat", "node59p1.dat")
        self.assert_data(AdcpsParserDataParticle, count=2, timeout=10)

        self.driver.stop_sampling()

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        self.clean_file()

        # create the file so that it is unreadable
        self.create_sample_data("node59p1_step1.dat", "node59p1.dat", mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(ValueError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.
        
    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        self.clean_file()
        self.create_sample_data("node59p1_step1.dat", "node59p1.dat")
        driver_config = self._driver_config()['startup_config']
        fullfile = os.path.join(driver_config['harvester']['directory'],
                            driver_config['harvester']['pattern'])
        mod_time = os.path.getmtime(fullfile)

        # Create and store the new driver state
        self.memento = {"node59p1.dat": {DriverStateKey.FILE_SIZE: 1300,
                        DriverStateKey.FILE_CHECKSUM: 'e56e28e6bd67c6b00c6702c9f9a13f93',
                        DriverStateKey.FILE_MOD_DATE: mod_time,
                        DriverStateKey.PARSER_STATE: {'in_process_data': [],
                                                     'unprocessed_data':[[0,32], [607,678], [1254,1300]],
                                                     }
                        }
        }

        self.driver = self._get_driver_object(config=driver_config)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(AdcpsParserDataParticle, 'test_data_2.txt.result.yml',
                         count=1, timeout=10)
        
    def test_sequences(self):
        """
        Test new sequence flags are set correctly.  There is only one file
        that just has data appended or inserted into it, so new sequences
        can occur in both cases, or if there is missing data in between two sequences
        """

        self.clean_file()

        self.driver.start_sampling()

        # step 2 contains 2 blocks, start with this and get both since we used them
        # separately in other tests (no new sequences)
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")
        self.assert_data(AdcpsParserDataParticle, 'test_data_1-2.txt.result.yml',
                         count=3, timeout=10)

        # This file has had a section of AD data replaced with 0s, this should start a new
        # sequence for the data following the missing AD data
        self.clear_async_data()
        self.create_sample_data('node59p1_step3.dat', "node59p1.dat")
        self.assert_data(AdcpsParserDataParticle, 'test_data_3.txt.result.yml',
                         count=4, timeout=10)

        # Now fill in the zeroed section from step3, this should just return the new
        # data with a new sequence flag
        self.clear_async_data()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")
        self.assert_data(AdcpsParserDataParticle, 'test_data_4.txt.result.yml',
                         count=1, timeout=10)

        # start over now, using step 4
        self.driver.shutdown()

        # Reset the driver with no memento
        self.memento = None
        self.driver = self._get_driver_object()

        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")
        self.assert_data(AdcpsParserDataParticle, 'test_data_1-4.txt.result.yml',
                         count=8, timeout=10)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
        
    def clean_file(self):
        # remove just the file we are using
        driver_config = self._driver_config()['startup_config']
        log.debug('startup config %s', driver_config)
        fullfile = os.path.join(driver_config['harvester']['directory'],
                            driver_config['harvester']['pattern'])
        if os.path.exists(fullfile):
            os.remove(fullfile)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        self.clean_file()
        # need to put data in the file, not just make an empty file for this to work
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat", mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clean_file()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.clean_file()

        self.create_sample_data('node59p1_step1.dat', "node59p1.dat")

        self.assert_initialize()

        try:
            # Verify we get one sample
            result = self.data_subscribers.get_samples(SAMPLE_STREAM, 2)
            log.info("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test a large import
        """
        self.create_sample_data('node59p1_shorter.dat', "node59p1.dat")
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,29,30)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.error("CONFIG: %s", self._agent_config())
        self.create_sample_data('node59p1_step2.dat', "node59p1.dat")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM, 3)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1-2.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('node59p1_step4.dat', "node59p1.dat")
            # Now read the first records of the second file then stop
            result1 = self.get_samples(SAMPLE_STREAM, 2)
            log.debug("RESULT 1: %s", result1)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result2 = self.get_samples(SAMPLE_STREAM, 3)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'test_data_3-4.txt.result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.clean_file()
        # file contains invalid sample values
        self.create_sample_data('node59p1_bad.dat', "node59p1.dat")

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(SAMPLE_STREAM, 28, 30)
        self.assert_sample_queue_size(SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

