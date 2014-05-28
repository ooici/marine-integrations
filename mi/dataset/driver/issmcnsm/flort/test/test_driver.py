"""
@package mi.dataset.driver.issmcnsm.flort.test.test_driver
@file marine-integrations/mi/dataset/driver/issmcnsm/flort/driver.py
@author Emily Hahn
@brief Test cases for issmcnsm_flort driver

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
import hashlib
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

from mi.dataset.driver.issmcnsm.flort.driver import IssmCnsmFLORTDDataSetDriver
from mi.dataset.parser.issmcnsm_flortd import Issmcnsm_flortdParserDataParticle

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.issmcnsm.flort.driver',
    driver_class='IssmCnsmFLORTDDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = IssmCnsmFLORTDDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_dsatest',
            DataSetDriverConfigKeys.PATTERN: '*.flort.log',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM = 'issmcnsm_flortd_parsed'

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@unittest.skip('Test files were lost, driver needs revisiting')
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
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")
        self.assert_data(Issmcnsm_flortdParserDataParticle, 'test_data_1.txt.result.yml', count=2, timeout=10)

        self.clear_async_data()
        self.create_sample_data('test_data_2.flort.log', "20130102.flort.log")
        self.assert_data(Issmcnsm_flortdParserDataParticle, 'test_data_2.txt.result.yml', count=4, timeout=10)

        self.clear_async_data()
        # skipping a file index 20130103 here to make sure it still finds the new file
        self.create_sample_data('test_data_3.flort.log', "20130104.flort.log")
        self.assert_data(Issmcnsm_flortdParserDataParticle, count=15, timeout=30)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('test_data_1.flort.log', "20130105.flort.log")
        self.assert_data(Issmcnsm_flortdParserDataParticle, count=2, timeout=10)

    def test_resume_file_start(self):
        """
        Test the ability to restart the process
        """
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")
        startup_config = self._driver_config()['startup_config']
        file_path = os.path.join(startup_config[DataSourceConfigKey.HARVESTER].get(DataSetDriverConfigKeys.DIRECTORY),
                                 "20130101.flort.log")
        # need to reset file mod time since file is created again
        mod_time = os.path.getmtime(file_path)
        file_size = os.path.getsize(file_path)
        with open(file_path) as filehandle:
            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()
        # Create and store the new driver state, after completed reading 20130101.flort.log
        # Note, since file is ingested, parser state is not looked at, in a real run there would be a state in there
        memento = {'20130101.flort.log':{'ingested': True,
                                        'file_mod_date': mod_time,
                                        'file_checksum': md5_checksum,
                                        'file_size': file_size,
                                        'parser_state': {}
                                      }
        }
        self.driver = self._get_driver_object(memento=memento)

        # create some data to parse
        self.clear_async_data()

        self.create_sample_data('test_data_2.flort.log', "20130102.flort.log")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(Issmcnsm_flortdParserDataParticle, 'test_data_2.txt.result.yml', count=4, timeout=10)

    def test_resume_mid_file(self):
        """
        Test the ability to restart the process in the middle of a file
        """
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")
        self.create_sample_data('test_data_2.flort.log', "20130102.flort.log")

        startup_config = self._driver_config()['startup_config']
        file_path_1 = os.path.join(startup_config[DataSourceConfigKey.HARVESTER].get(DataSetDriverConfigKeys.DIRECTORY),
                                 "20130101.flort.log")
        # need to reset file mod time since file is created again
        mod_time_1 = os.path.getmtime(file_path_1)
        file_size_1 = os.path.getsize(file_path_1)
        with open(file_path_1) as filehandle:
            md5_checksum_1 = hashlib.md5(filehandle.read()).hexdigest()
        file_path_2 = os.path.join(startup_config[DataSourceConfigKey.HARVESTER].get(DataSetDriverConfigKeys.DIRECTORY),
                                 "20130102.flort.log")
        # need to reset file mod time since file is created again
        mod_time_2 = os.path.getmtime(file_path_2)
        file_size_2 = os.path.getsize(file_path_2)
        with open(file_path_2) as filehandle:
            md5_checksum_2 = hashlib.md5(filehandle.read()).hexdigest()
        # Create and store the new driver state, after completed reading 20130101.flort.log
        # Note, since file 20130101 is ingested, parser state is not looked at, in a real run there would be a state in there
        memento = {'20130101.flort.log':{'ingested': True,
                                        'file_mod_date': mod_time_1,
                                        'file_checksum': md5_checksum_1,
                                        'file_size': file_size_1,
                                        'parser_state': {}
                                      },
                  '20130102.flort.log':{'ingested': False,
                                        'file_mod_date': mod_time_2,
                                        'file_checksum': md5_checksum_2,
                                        'file_size': file_size_2,
                                        'parser_state': {'position': 146, 'timestamp': 3592854648.401}
                  }
        }
        # Create and store the new driver state, after completed reading  20130101.dosta.log
        self.driver = self._get_driver_object(memento=memento)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(Issmcnsm_flortdParserDataParticle, 'test_data_2.txt.partial-result.yml', count=2, timeout=10)

    def test_modified(self):
        """
        Test for detection of an ingested file that has been modifed after ingestion
        """
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")

        startup_config = self._driver_config()['startup_config']
        directory = startup_config[DataSourceConfigKey.HARVESTER].get(DataSetDriverConfigKeys.DIRECTORY)
        file_path = os.path.join(directory, "20130101.flort.log")
        # need to reset file mod time since file is created again
        mod_time = os.path.getmtime(file_path)
        file_size = os.path.getsize(file_path)
        with open(file_path) as filehandle:
            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()
        # Create and store the new driver state, after completed reading  20130101.flort.log
        memento = {'20130101.flort.log':{'ingested': True,
                                         'file_mod_date': mod_time,
                                         'file_checksum': md5_checksum,
                                         'file_size': file_size,
                                         'parser_state': {}
                                        }
        }

	self.driver = self._get_driver_object(memento=memento)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # overwrite the old 20130101.flort.log file
        # NOTE: this does not make you wait until file mod time, since it copies the original file
        # modification time, not when you copy the file in running this test
        self.create_sample_data('test_data_2.flort.log', "20130101.flort.log")

        to = gevent.Timeout(30)
        to.start()
        done = False
        try:
            while(not done):
                if 'modified_state' in self.driver._driver_state['20130101.flort.log']:
                    log.debug("Found modified state %s", self.driver._driver_state['20130101.flort.log'].get('modified_state' ))
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
@unittest.skip('Test files were lost, driver needs revisiting')
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Right now, there is an issue with keeping records in order,
        # which has to do with the sleep time in get_samples in
        # instrument_agent_client.  By setting this delay more than the
        # delay in get_samples, the records are returned in the expected
        # otherwise they are returned out of order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(SAMPLE_STREAM, 2)
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
        self.create_sample_data('test_data_3.flort.log', "20130103.flort.log")
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,15,30)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('test_data_1.flort.log', "20130101.flort.log")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM, 2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('test_data_2.flort.log', "20130102.flort.log")
            # Now read the first records of the second file then stop
            result = self.get_samples(SAMPLE_STREAM, 2)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 2)
            self.assert_data_values(result, 'test_data_2.txt.partial-result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")


