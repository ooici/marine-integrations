"""
@package mi.dataset.driver.mflm.flort.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/flort/driver.py
@author Emily Hahn
@brief Test cases for mflm_flort driver

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
import shutil

from nose.plugins.attrib import attr
from mock import Mock

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent

from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_driver import DriverEvent
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey

from mi.dataset.driver.mflm.flort.driver import MflmFLORTDDataSetDriver, DataSourceKey
from mi.dataset.parser.flortd import FlortdParserDataParticle, \
                                     FlortdRecoveredParserDataParticle, DataParticleType
from mi.dataset.parser.sio_mule_common import StateKey


TELEM_DIR = '/tmp/dsatest1'
RECOV_DIR = '/tmp/dsatest2'

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.flort.driver',
    driver_class='MflmFLORTDDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = MflmFLORTDDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataSourceKey.FLORT_DJ_SIO_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: 'node59p1.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            },
            DataSourceKey.FLORT_DJ_SIO_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: RECOV_DIR,
                DataSetDriverConfigKeys.PATTERN: 'FLO*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.FLORT_DJ_SIO_TELEMETERED: {},
            DataSourceKey.FLORT_DJ_SIO_RECOVERED: {}
        }
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

        # Start sampling
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_1.txt.result.yml',
                         count=1, timeout=10)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.create_sample_data_set_dir("node59p1_step2.dat", TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_2.txt.result.yml',
                         count=1, timeout=10)

        # now 'appends' the rest of the data and just check if we get the right number
        self.create_sample_data_set_dir("node59p1_step4.dat", TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, count=4, timeout=10)

        # now check recovered data
        self.create_sample_data_set_dir("FLO_short.DAT", RECOV_DIR)
        self.assert_data(FlortdRecoveredParserDataParticle, 'flo_short.result.yml', count=6)

    def test_get_dash(self):
        """
        Test that we can get a particle containing a value that doesn't exist,
        which is marked with '--'
        """
        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_dash.dat", TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_dash.txt.result.yml',
                         count=2, timeout=10)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        self.clear_sample_data()

        harvester_config = self._driver_config()['startup_config'][DataSourceConfigKey.HARVESTER]

        # Start sampling and watch for an exceptions
        self.driver.start_sampling()

        # there are multiple harvester configs, test each one
        for key in harvester_config:
            if key is DataSourceKey.FLORT_DJ_SIO_TELEMETERED:
                # need to override since filename is the whole pattern, no replace with foo
                filename = harvester_config[key][DataSetDriverConfigKeys.PATTERN]
            else:
                filename = harvester_config[key][DataSetDriverConfigKeys.PATTERN].replace('*', 'foo')
            file_dir = harvester_config[key][DataSetDriverConfigKeys.DIRECTORY]
            self.assertIsNotNone(file_dir)

            # create the file so that it is unreadable
            self.create_sample_data_set_dir(filename, file_dir, mode=000, create=True, copy_metadata=False)

            self.assert_exception(IOError)
            # clear out exceptions so we know we get a new one next key
            self.clear_async_data()

    def test_stop_resume(self):
        """
        Pick a state that the driver could have previously stopped at and restart at that point
        """
        # create the telemetered file at the point the driver stopped at
        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, "node59p1.dat")
        # create the recovered file
        self.create_sample_data_set_dir("FLO_short.DAT", RECOV_DIR)
        driver_config = self._driver_config()['startup_config']
        fullfile = os.path.join(driver_config['harvester'][DataSourceKey.FLORT_DJ_SIO_TELEMETERED]['directory'],
                            driver_config['harvester'][DataSourceKey.FLORT_DJ_SIO_TELEMETERED]['pattern'])
        mod_time = os.path.getmtime(fullfile)

        # Create and store the new driver state
        self.memento = {
            DataSourceKey.FLORT_DJ_SIO_TELEMETERED: {
                "node59p1.dat": {
                    DriverStateKey.FILE_SIZE: 300,
                    DriverStateKey.FILE_CHECKSUM: 'a640fd577c65ed07ed67f1d2e73d34e2',
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE: {StateKey.IN_PROCESS_DATA: [],
                                                  StateKey.UNPROCESSED_DATA:[[0,69], [197,300]],
                                                  StateKey.FILE_SIZE: 300
                    }
                }
            },
            DataSourceKey.FLORT_DJ_SIO_RECOVERED: {
                "FLO_short.DAT": {
                    DriverStateKey.FILE_SIZE: 486,
                    DriverStateKey.FILE_CHECKSUM: '1be7f1e42f0cee76940266e2431c28e9',
                    DriverStateKey.FILE_MOD_DATE: 1406053279.197744,
                    DriverStateKey.INGESTED: False,
                    DriverStateKey.PARSER_STATE: {StateKey.IN_PROCESS_DATA: [[243,324,1,0], [324,405,1,0], [405,486,1,0]],
                                                  StateKey.UNPROCESSED_DATA: [[243,486]],
                                                  StateKey.FILE_SIZE: 486}
                }
            }
        }

        self.driver = self._get_driver_object(memento=self.memento)
        # create some data to parse
        self.clear_async_data()
        # now change the file so the harvester finds it and starts parsing where it left off
        self.create_sample_data_set_dir("node59p1_step2.dat", TELEM_DIR, "node59p1.dat", copy_metadata=False)

        self.driver.start_sampling()

        # verify telemetered data is produced
        self.assert_data(FlortdParserDataParticle, 'test_data_2.txt.result.yml',
                         count=1, timeout=10)

        # for recovered, expect the last 3 particles in the file
        self.assert_data(FlortdRecoveredParserDataParticle, 'flo_short_last_3.result.yml',
                         count=3, timeout=10)

    def test_back_fill(self):
        """
        Test a file that has had a section zeroed out and then added back in 
        """
        self.driver.start_sampling()

        self.clear_async_data()

        # step 2 contains 2 blocks, start with this and get both since we used them
        # separately in other tests
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step2.dat", TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_1-2.txt.result.yml',
                         count=2, timeout=10)

        # This file has had a section of FL data replaced with 0s
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step3.dat', TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_3.txt.result.yml',
                         count=3, timeout=10)

        # Now fill in the zeroed section from step3
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_4.txt.result.yml',
                         count=1, timeout=10)

        # start over now, using step 4
        self.driver.stop_sampling()
        self.driver = self._get_driver_object(memento=None)
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_1-4.txt.result.yml',
                         count=6, timeout=10)

    def test_all_good(self):
        """
        Test that a set of data with no bad data, where there is no remaining
        unprocessed data in between
        """
        self.driver.start_sampling()
        self.create_sample_data_set_dir("node59p1_all_good1.dat", TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_1-2.txt.result.yml',
                         count=2, timeout=10)
        
        # make sure we can build the next parser with the empty unprocessed data
        self.create_sample_data_set_dir("node59p1_all_good.dat", TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.assert_data(FlortdParserDataParticle, 'test_data_all_good.txt.result.yml',
                         count=1, timeout=10)
        

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        harvester_config = self._driver_config()['startup_config'][DataSourceConfigKey.HARVESTER]
        for key in harvester_config:
            if key is DataSourceKey.FLORT_DJ_SIO_TELEMETERED:
                # need to override since filename is in pattern, don't replace with foo
                filename = harvester_config[key][DataSetDriverConfigKeys.PATTERN]
            else:
                filename = harvester_config[key][DataSetDriverConfigKeys.PATTERN].replace('*', 'foo')
            file_dir = harvester_config[key][DataSetDriverConfigKeys.DIRECTORY]

            self.assert_new_file_exception(filename, file_dir)
            # stop sampling so we can start again
            self.assert_stop_sampling()

            # stop and restart the agent so we can test the next key new file exception
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data_set_dir('node59p1_step1.dat', TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.create_sample_data_set_dir('FLO_short.DAT', RECOV_DIR)

        self.assert_initialize()

        try:
            # Verify we get one telemetered sample
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            log.info("result telem: %s", result)
            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')

            # Verify we get the 6 samples from the recovered file
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 6)
            self.assert_data_values(result, 'flo_short.result.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the telemetered and recovered files at once
        """
        self.create_sample_data_set_dir('node59p1_longer.dat', TELEM_DIR, "node59p1.dat", copy_metadata=False)
        self.create_sample_data_set_dir('FLO15908.DAT', RECOV_DIR)
        self.assert_initialize()

        # get the telemetered samples
        result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 12, 30)
        # get the recovered samples
        result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 96, 30)

    def test_stop_start_telem(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_step2.dat', TELEM_DIR, "node59p1.dat", copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1-2.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                            copy_metadata=False)
            # Now read the first records of the second file then stop
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT 1: %s", result1)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_RECOVERED, 0)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'test_data_3-4.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_RECOVERED, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_stop_start_recov(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('FLO_short.DAT', RECOV_DIR)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # read the first records of the file then stop
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 3)
            log.debug("RESULT 1: %s", result)
            self.assert_stop_sampling()

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 3)
            log.debug("RESULT 2: %s", result2)
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'flo_short.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_RECOVERED, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart_telem(self):
        """
        Test a full stop of the dataset agent, then restart the agent and
        confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_step2.dat', TELEM_DIR, "node59p1.dat",
                                        copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1-2.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
                                            copy_metadata=False)
            # Now read the first records of the second file then stop
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT 1: %s", result1)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_RECOVERED, 0)

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)
            # Slow down processing to 1 per second to give us time to stop again
            self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
            # Restart sampling and ensure we get the last 4 records of the file
            self.assert_start_sampling()
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'test_data_3-4.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_RECOVERED, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart_recov(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('FLO_short.DAT', RECOV_DIR)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # read the first records of the file then stop
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 3)
            log.debug("RESULT 1: %s", result)
            self.assert_stop_sampling()

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()

            # ensure we get the last 3 records of the file
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 3)
            log.debug("RESULT 2: %s", result2)
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'flo_short.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            self.assert_sample_queue_size(DataParticleType.SAMPLE_RECOVERED, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

