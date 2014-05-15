"""
@package mi.dataset.driver.mflm.ctd.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/ctd/driver.py
@author Emily Hahn
@brief Test cases for mflm_ctd driver

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
import binascii
from nose.plugins.attrib import attr
from mock import Mock

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent

from mi.idk.util import remove_all_files
from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.exceptions import ConfigurationException
from mi.core.exceptions import InstrumentParameterException
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey
from mi.dataset.driver.mflm.ctd.driver import MflmCTDMODataSetDriver, DataTypeKey
from mi.dataset.parser.ctdmo import CtdmoParserDataParticle, DataParticleType


DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.ctd.driver',
    driver_class="MflmCTDMODataSetDriver",
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = MflmCTDMODataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.CTDMO_GHQR_SIO_MULE:
            {
                DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
                DataSetDriverConfigKeys.PATTERN: 'node59p1.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            }
        },
        DataSourceConfigKey.PARSER: {'inductive_id': 55}
    }
)


###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):

    def clear_sample_data(self):
        """
        Clear all the data out of the test directories
        """
        if os.path.exists('/tmp/dsatest'):
            log.debug("Clean all data from /tmp/dsatest")
            remove_all_files('/tmp/dsatest')
        else:
            os.makedirs('/tmp/dsatest')

    def test_get(self):

        self.create_sample_data_set_dir("node59p1_step1.dat", '/tmp/dsatest', "node59p1.dat")

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.assert_data(CtdmoParserDataParticle, 'test_data_1.txt.result.yml',
                         count=4, timeout=10)

        # there is only one file we read from, this example 'appends' data to
        # the end of the node59p1.dat file, and the data from the new append
        # is returned (not including the original data from _step1)
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step2.dat", '/tmp/dsatest', "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_2.txt.result.yml',
                         count=2, timeout=10)

        # now 'appends' the rest of the data and just check if we get the right number
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step4.dat", '/tmp/dsatest', "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, count=2, timeout=10)

        self.driver.stop_sampling()

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """

        # create the file so that it is unreadable
        self.create_sample_data_set_dir("node59p1_step1.dat", '/tmp/dsatest', "node59p1.dat", mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(ValueError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        self.create_sample_data_set_dir("node59p1_step1.dat", '/tmp/dsatest', "node59p1.dat")
        driver_config = self._driver_config()['startup_config']
        fullfile = os.path.join(driver_config['harvester'][DataTypeKey.CTDMO_GHQR_SIO_MULE]['directory'],
                            driver_config['harvester'][DataTypeKey.CTDMO_GHQR_SIO_MULE]['pattern'])
        mod_time = os.path.getmtime(fullfile)

        # Create and store the new driver state
        self.memento = {
            DataTypeKey.CTDMO_GHQR_SIO_MULE: {
                "node59p1.dat": {
                    DriverStateKey.FILE_SIZE: 6000,
                    DriverStateKey.FILE_CHECKSUM: 'aa1cc1aa816e99e11d8e88fc56f887e7',
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE: {
                        'in_process_data': [],
                        'unprocessed_data':[[0, 12], [336, 394], [5924,6000]],                         
                    }
                }
            }
        }
        self.driver = MflmCTDMODataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_step2.dat", '/tmp/dsatest', "node59p1.dat")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(CtdmoParserDataParticle, 'test_data_2.txt.result.yml',
                         count=2, timeout=10)

    def test_back_fill(self):
        """
        Test refilled blocks are sent correctly.  There is only one file
        that just has data appended or inserted into it, or if there is missing
        data can be added back later
        """

        self.create_sample_data_set_dir("node59p1_step1.dat", '/tmp/dsatest', "node59p1.dat")

        self.driver.start_sampling()

        # step 1 contains 4 blocks, start with this and get both since we used them
        # separately in other tests
        self.clear_async_data()
        self.assert_data(CtdmoParserDataParticle, 'test_data_1.txt.result.yml',
                         count=4, timeout=10)

        # This file has had a section of CT data replaced with 0s, this should start a new
        # sequence for the data following the missing CT data
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step3.dat', '/tmp/dsatest', "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_3.txt.result.yml',
                         count=2, timeout=10)

        # Now fill in the zeroed section from step3, this should just return the new
        # data 
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', '/tmp/dsatest', "node59p1.dat")
        self.assert_data(CtdmoParserDataParticle, 'test_data_4.txt.result.yml',
                         count=2, timeout=10)
    
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def clear_sample_data(self):
        """
        Clear all the data out of the test directories
        """
        if os.path.exists('/tmp/dsatest'):
            log.debug("Clean all data from /tmp/dsatest")
            remove_all_files('/tmp/dsatest')
        else:
            os.makedirs('/tmp/dsatest')

    def create_data_dir(self):
        """
        Verify the test data directory is created and exists.  Return the path to
        the directory.
        @return: path to data directory
        @raise: IDKConfigMissing no harvester config
        @raise: IDKException if data_dir exists, but not a directory
        """
        startup_config = self._driver_config().get('startup_config')
        if not startup_config:
            raise IDKConfigMissing("Driver config missing 'startup_config'")

        harvester_config = startup_config.get('harvester')
        if not harvester_config:
            raise IDKConfigMissing("Startup config missing 'harvester' config")

        data_dir = []

        for key in harvester_config:
            data_dir_key = harvester_config[key].get("directory")
            if not data_dir_key:
                raise IDKConfigMissing("Harvester config missing 'directory'")

            if not os.path.exists(data_dir_key):
                log.debug("Creating data dir: %s", data_dir_key)
                os.makedirs(data_dir_key)

            elif not os.path.isdir(data_dir_key):
                raise IDKException("%s is not a directory" % data_dir_key)
            data_dir.append(data_dir_key)

        return data_dir

    def remove_sample_dir(self):
        """
        Remove the sample dir and all files
        """
        data_dirs = self.create_data_dir()
        self.clear_sample_data()
        for data_dir in data_dirs:
            os.rmdir(data_dir)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """

        self.create_sample_data_set_dir('node59p1_step1.dat', '/tmp/dsatest', "node59p1.dat")

        self.assert_initialize()

        try:
            # Verify we get one sample
            result = self.data_subscribers.get_samples(DataParticleType.CT, 4)
            log.info("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test a large import
        """
        self.create_sample_data_set_dir('node59p1_step4.dat', '/tmp/dsatest', "node59p1.dat")
        self.assert_initialize()

        result = self.get_samples(DataParticleType.CT,8,30)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.error("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_step1.dat', '/tmp/dsatest', "node59p1.dat")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(DataParticleType.CT, 4)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(DataParticleType.CT, 0)

            self.create_sample_data_set_dir('node59p1_step2.dat', '/tmp/dsatest', "node59p1.dat")
            # Now read the first record of the second file then stop
            result1 = self.get_samples(DataParticleType.CT, 1)
            log.debug("RESULT 1: %s", result1)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.CT, 0)

            # Restart sampling and ensure we get the last record of the file
            self.assert_start_sampling()
            result2 = self.get_samples(DataParticleType.CT, 1)
            log.debug("RESULT 2: %s", result2)
            result = result1
            result.extend(result2)
            log.debug("RESULT: %s", result)
            self.assert_data_values(result, 'test_data_2.txt.result.yml')

            self.assert_sample_queue_size(DataParticleType.CT, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        self.create_sample_data_set_dir('node59p1_step4.dat', '/tmp/dsatest', "node59p1.dat", mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir('node59p1_step4.dat', '/tmp/dsatest', "node59p1.dat")

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

