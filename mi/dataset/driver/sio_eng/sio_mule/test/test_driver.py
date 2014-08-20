"""
@package mi.dataset.driver.sio_eng.sio_mule.test.test_driver
@file marine-integrations/mi/dataset/driver/sio_eng/sio_mule/driver.py
@author Mike Nicoletti
@brief Test cases for sio_eng_sio_mule driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Mike Nicoletti'
__license__ = 'Apache 2.0'

import os
from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from mi.idk.exceptions import SampleTimeout

from mi.core.log import get_logger
log = get_logger()

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import \
    DriverParameter, \
    DriverStateKey, \
    DataSourceConfigKey, \
    DataSetDriverConfigKeys

from interface.objects import ResourceAgentErrorEvent

from mi.dataset.parser.sio_mule_common import StateKey

from mi.dataset.driver.sio_eng.sio_mule.driver import \
    SioEngSioMuleDataSetDriver, \
    DataSourceKey
from mi.dataset.parser.sio_eng_sio_mule import \
    SioEngSioMuleDataParticle, \
    SioEngSioRecoveredDataParticle, \
    DataParticleType

TELEM_DIR = '/tmp/sio_eng_test/telem'
RECOV_DIR = '/tmp/sio_eng_test/recov'

MULE_FILE_NAME = 'node59p1.dat'
RECOV_FILE_NAME = 'STA15908.DAT'
SIO_ENG_PATTERN = 'STA*.DAT'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.sio_eng.sio_mule.driver',
    driver_class='SioEngSioMuleDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=SioEngSioMuleDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.HARVESTER: {
            DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: MULE_FILE_NAME,
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            },
            DataSourceKey.SIO_ENG_SIO_MULE_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: RECOV_DIR,
                DataSetDriverConfigKeys.PATTERN: SIO_ENG_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {},
            DataSourceKey.SIO_ENG_SIO_MULE_RECOVERED: {}
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
        # Start Sampling
        self.driver.start_sampling()

        self.clear_async_data()

        self.create_sample_data_set_dir("node59p1_test_get.dat", TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)

        self.create_sample_data_set_dir(RECOV_FILE_NAME, RECOV_DIR)

        self.assert_data(SioEngSioMuleDataParticle,
                         'test_get_particle.yml', count=2, timeout=10)

        self.assert_data(SioEngSioRecoveredDataParticle,
                         'test_get_recov.yml', count=2, timeout=10)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        # create the file so that it is unreadable
        self.clear_sample_data()

        harvester_config = self._driver_config()['startup_config'][DataSourceConfigKey.HARVESTER]

        # Start sampling and watch for an exceptions
        self.driver.start_sampling()

        # there are multiple harvester configs, test each one
        for key in harvester_config:

            if key is DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED:
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
        Test the ability to stop and restart the process
        """

        mule_path = self.create_sample_data_set_dir("node59p1_test_get.dat", TELEM_DIR, MULE_FILE_NAME,
                                                    copy_metadata=False)

        recov_path = self.create_sample_data_set_dir(RECOV_FILE_NAME, RECOV_DIR)
        recov_mod_time = os.path.getmtime(recov_path)

        mod_time = os.path.getmtime(mule_path)

        ## Create and store the new driver state

        memento = {
            DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {
                MULE_FILE_NAME: {
                    DriverStateKey.FILE_SIZE: 4644,
                    DriverStateKey.FILE_CHECKSUM: 'dd1b506100c650e70a8e0295674777d6',
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE: {
                        StateKey.IN_PROCESS_DATA: [],
                        StateKey.UNPROCESSED_DATA: [[0, 181]],
                        StateKey.FILE_SIZE: 4644
                    }
                }
            },
            DataSourceKey.SIO_ENG_SIO_MULE_RECOVERED: {
                RECOV_FILE_NAME: {
                    DriverStateKey.FILE_SIZE: 1392,
                    DriverStateKey.FILE_CHECKSUM: '32c9021cdb5091db28524fe551095bcd',
                    DriverStateKey.FILE_MOD_DATE: recov_mod_time,
                    DriverStateKey.INGESTED: False,
                    DriverStateKey.PARSER_STATE: {
                        StateKey.IN_PROCESS_DATA: [],
                        StateKey.UNPROCESSED_DATA: [[290, 638]],
                        StateKey.FILE_SIZE: 1392
                    }
                }
            }
        }

        driver = self._get_driver_object(memento=memento)

        ## create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir("test_stop_resume2.dat", TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)

        driver.start_sampling()

        ## verify data is produced
        self.assert_data(SioEngSioMuleDataParticle, 'test_stop_resume.yml',
                         count=2)
        self.assert_data(SioEngSioRecoveredDataParticle,
                         'test_stop_resume_recov.yml', count=6, timeout=20)

    def test_back_fill(self):
        """
        There that a file that has had a section fill with zeros is skipped, then
        when data is filled in that data is read. 
        """
        self.driver.start_sampling()

        # Using 2 files, one with a block of sio header and data filled with
        #   zeros (node59p1_test_backfill.dat)
        #   
        self.clear_async_data()
        ## This file has had a section of CS data replaced with 0s
        self.create_sample_data_set_dir('node59p1_test_backfill.dat', TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)
        self.assert_data(SioEngSioMuleDataParticle, 'test_back_fill.yml',
                         count=1)

        # Now fill in the zeroed section, and this file also has 2 more CS SIO headers appended
        #   along with other data at the end. 
        self.create_sample_data_set_dir('test_stop_resume2.dat', TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)
        self.assert_data(SioEngSioMuleDataParticle, 'test_back_fill2.yml',
                         count=3)

    def test_bad_data(self):
        # Put bad data into the file and make sure an exemption is raised

        ## This file has had a section of CS data replaced with letters
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_test_get_bad.dat', TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)
        self.driver.start_sampling()

        self.assert_event('ResourceAgentErrorEvent')

    def test_bad_data_recov(self):
        # Put bad data into the file and make sure an exemption is raised

        ## This file has had a section of CS data replaced with letters
        self.clear_async_data()
        self.create_sample_data_set_dir('STA15908_BAD.DAT', RECOV_DIR)
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
        self.create_sample_data_set_dir('node59p1_test_get.dat', TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)

        self.create_sample_data_set_dir(RECOV_FILE_NAME, RECOV_DIR)

        self.assert_initialize()

        try:
            # Verify we get samples
            result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED, 2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_get_particle.yml')

            result = self.data_subscribers.get_samples(DataParticleType.RECOVERED, 2)

            self.assert_data_values(result, 'test_get_recov.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir('node59p1.dat', TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)
        self.assert_initialize()

        self.data_subscribers.get_samples(DataParticleType.TELEMETERED, 30, 300)

    def test_large_import2(self):
        """
        Test importing a large number of samples from a different file at once
        """
        self.create_sample_data_set_dir('node58p1.dat', TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)
        self.assert_initialize()

        self.data_subscribers.get_samples(DataParticleType.TELEMETERED, 200, 600)

    def test_large_import_recov(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir(RECOV_FILE_NAME, RECOV_DIR)

        self.assert_initialize()

        self.data_subscribers.get_samples(DataParticleType.RECOVERED, 24, 120)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """

        self.create_sample_data_set_dir('node59p1_test_get.dat', TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)

        self.create_sample_data_set_dir(RECOV_FILE_NAME, RECOV_DIR)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data

            result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED, 2)
            log.debug("RESULT: %s", result)

            # Verify Telemetered values
            self.assert_data_values(result, 'test_get_particle.yml')
            self.assert_sample_queue_size(DataParticleType.TELEMETERED, 0)

            # Verify Recovered values
            result = self.data_subscribers.get_samples(DataParticleType.RECOVERED, 5, 60)
            self.assert_data_values(result, 'test_stop_start1_recov.yml')

            self.create_sample_data_set_dir('test_stop_resume2.dat', TELEM_DIR, MULE_FILE_NAME,
                                            copy_metadata=False)

            # Now read the first records of the second file then stop
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.TELEMETERED, 0)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()

            result2 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED, 2)
            log.debug("RESULT 2: %s", result2)

            # Verify Telemetered values
            self.assert_data_values(result2, 'test_stop_resume.yml')
            self.assert_sample_queue_size(DataParticleType.TELEMETERED, 0)

            # Verify Recovered values
            result = self.data_subscribers.get_samples(DataParticleType.RECOVERED, 6, 60)
            self.assert_data_values(result, 'test_stop_resume_recov.yml')

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout .")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """

        self.create_sample_data_set_dir('node59p1_test_get.dat', TELEM_DIR, MULE_FILE_NAME,
                                        copy_metadata=False)

        self.create_sample_data_set_dir(RECOV_FILE_NAME, RECOV_DIR)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data

            result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED, 2)
            log.debug("RESULT: %s", result)

            # Verify Telemetered values
            self.assert_data_values(result, 'test_get_particle.yml')
            self.assert_sample_queue_size(DataParticleType.TELEMETERED, 0)

            # Verify Recovered values
            result = self.data_subscribers.get_samples(DataParticleType.RECOVERED, 5, 60)
            self.assert_data_values(result, 'test_stop_start1_recov.yml')

            self.create_sample_data_set_dir('test_stop_resume2.dat', TELEM_DIR, MULE_FILE_NAME,
                                            copy_metadata=False)

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()

            # Restart sampling and ensure we get the last 2 records of the file
            # Verify Telemetered values
            result2 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED, 2)
            log.debug("RESULT 2: %s", result2)
            self.assert_data_values(result2, 'test_stop_resume.yml')
            self.assert_sample_queue_size(DataParticleType.TELEMETERED, 0)
            # Verify Recovered values
            result = self.data_subscribers.get_samples(DataParticleType.RECOVERED, 6, 60)
            self.assert_data_values(result, 'test_stop_resume_recov.yml')

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout .")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """

        # Test telemetered parser
        # file contains invalid sample values
        self.create_sample_data_set_dir('node59p1_test_get_bad.dat', TELEM_DIR,
                                        MULE_FILE_NAME)
        self.event_subscribers.clear_events()
        self.assert_initialize()

        self.data_subscribers.get_samples(DataParticleType.TELEMETERED, 1)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        # clear the event queue to make sure we log a new event
        self.event_subscribers.clear_events()

        # Test telemetered parser
        self.create_sample_data_set_dir('STA15908_BAD.DAT', RECOV_DIR)

        self.data_subscribers.get_samples(DataParticleType.RECOVERED, 20)

        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)




