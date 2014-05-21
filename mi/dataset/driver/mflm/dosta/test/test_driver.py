"""
@package mi.dataset.driver.mflm.dosta.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/dosta/driver.py
@author Emily Hahn
@brief Test cases for mflm_dosta driver

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
from interface.objects import ResourceAgentConnectionLostErrorEvent

from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_driver import DriverEvent
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey
from mi.dataset.driver.mflm.dosta.driver import MflmDOSTADDataSetDriver
from mi.dataset.parser.dostad import DostadParserDataParticle, DataParticleType


DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.dosta.driver',
    driver_class='MflmDOSTADDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = MflmDOSTADDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: 'node59p1.dat',
            DataSetDriverConfigKeys.FREQUENCY: 1,
            DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM = 'dosta_ln_wfp_instrument'

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

    def create_sample_data(self, filename, dest_filename=None, mode=0644, create=True):
        """
        Search for a data file in the driver resource directory and if the file
        is not found there then search using the filename directly.  Then copy
        the file to the test data directory.

        If a dest_filename is supplied it will be renamed in the destination
        directory.
        @param: filename - filename or path to a data file to copy
        @param: dest_filename - name of the file when copied. default to filename
        @param: file mode
        @param: create an empty file in the destination if the source is not found
        @return: path to file created
        """
        data_dir = self.create_data_dir()
        source_path = None

        try:
            source_path = self._get_source_data_file(filename)
        except IDKException:
            if not create:
                raise

        log.debug("DIR: %s", data_dir)
        if dest_filename is None and source_path is not None:
            dest_path = os.path.join(data_dir, os.path.basename(source_path))
        elif dest_filename is None and source_path is None:
            dest_path = os.path.join(data_dir, filename)
        else:
            dest_path = os.path.join(data_dir, dest_filename)

        log.debug("Creating data file src: %s, dest: %s", source_path, dest_path)

        if source_path == None:
            file = open(dest_path, 'w')
            file.close()
        else:
            # need to override this copy to make the time the file is modified change
            shutil.copy(source_path, dest_path)

        os.chmod(dest_path, mode)

        return dest_path

    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        self.clean_file()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data("node59p1_step1.dat", "node59p1.dat")
        self.assert_data(DostadParserDataParticle, 'test_data_1.txt.result.yml',
                         count=1, timeout=10)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")
        self.assert_data(DostadParserDataParticle, 'test_data_2.txt.result.yml',
                         count=1, timeout=10)

        # now 'appends' the rest of the data and just check if we get the right number
        self.clear_async_data()
        self.create_sample_data("node59p1_step4.dat", "node59p1.dat")
        self.assert_data(DostadParserDataParticle, count=4, timeout=10)

        self.driver.stop_sampling()
        
        # Reset the driver with no memento
        self.memento = None
        self.driver = MflmDOSTADDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        self.driver.start_sampling()

        self.clear_async_data()
        
        self.create_sample_data("node59p1_step1.dat", "node59p1.dat")
        self.assert_data(DostadParserDataParticle, count=1, timeout=10)

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
        self.memento = {"node59p1.dat":
                            {DriverStateKey.FILE_SIZE: 314,
                            DriverStateKey.FILE_CHECKSUM: '515e5da08a6b4bb0d197e62c410da532',
                            DriverStateKey.FILE_MOD_DATE: mod_time,
                            DriverStateKey.PARSER_STATE: {'in_process_data': [],
                                                          'unprocessed_data':[[0,69]]}
                            }
                        }

        self.driver = MflmDOSTADDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(DostadParserDataParticle, 'test_data_2.txt.result.yml',
                         count=1, timeout=10)

    def test_sequences(self):
        """
        Test new sequence flags are set correctly
        """
        self.clean_file()

        self.driver.start_sampling()

        self.clear_async_data()

        # step 2 contains 2 blocks, start with this and get both since we used them
        # separately in other tests (no new sequences)
        self.clear_async_data()
        self.create_sample_data("node59p1_step2.dat", "node59p1.dat")
        self.assert_data(DostadParserDataParticle, 'test_data_1-2.txt.result.yml',
                         count=2, timeout=40)

        # This file has had a section of DO data replaced with 0s, this should start a new
        # sequence for the data following the missing DO data
        self.clear_async_data()
        self.create_sample_data('node59p1_step3.dat', "node59p1.dat")
        self.assert_data(DostadParserDataParticle, 'test_data_3.txt.result.yml',
                         count=3, timeout=40)

        # Now fill in the zeroed section from step3, this should just return the new
        # data
        self.clear_async_data()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")
        self.assert_data(DostadParserDataParticle, 'test_data_4.txt.result.yml',
                         count=1, timeout=40)

        # start over now, using step 4
        self.driver.stop_sampling()

        # Reset the driver with no memento
        self.memento = None
        self.driver = MflmDOSTADDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('node59p1_step4.dat', "node59p1.dat")
        self.assert_data(DostadParserDataParticle, 'test_data_1-4.txt.result.yml',
                         count=6, timeout=40)

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

    def create_sample_data(self, filename, dest_filename=None, mode=0644, create=True):
        """
        Search for a data file in the driver resource directory and if the file
        is not found there then search using the filename directly.  Then copy
        the file to the test data directory.

        If a dest_filename is supplied it will be renamed in the destination
        directory.
        @param: filename - filename or path to a data file to copy
        @param: dest_filename - name of the file when copied. default to filename
        @param: file mode
        @param: create an empty file in the destination if the source is not found
        @return: path to file created
        """
        data_dir = self.create_data_dir()
        source_path = None

        try:
            source_path = self._get_source_data_file(filename)
        except IDKException:
            if not create:
                raise

        log.debug("DIR: %s", data_dir)
        if dest_filename is None and source_path is not None:
            dest_path = os.path.join(data_dir, os.path.basename(source_path))
        elif dest_filename is None and source_path is None:
            dest_path = os.path.join(data_dir, filename)
        else:
            dest_path = os.path.join(data_dir, dest_filename)

        log.debug("Creating data file src: %s, dest: %s", source_path, dest_path)

        if source_path == None:
            file = open(dest_path, 'w')
            file.close()
        else:
            # need to override this copy to make the time the file is modified change
            shutil.copy(source_path, dest_path)

        os.chmod(dest_path, mode)

        return dest_path

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
            result = self.data_subscribers.get_samples(SAMPLE_STREAM, 1)
            log.info("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data('node59p1_longer.dat', "node59p1.dat")
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,11,30)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('node59p1_step2.dat', "node59p1.dat")

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
            result2 = self.get_samples(SAMPLE_STREAM, 2)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'test_data_3-4.txt.result.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")


