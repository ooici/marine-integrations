"""
@package mi.dataset.driver.wfp_eng.wfp_sio_mule.test.test_driver
@file marine-integrations/mi/dataset/driver/wfp_eng/wfp_sio_mule/driver.py
@author Mark Worden
@brief Test cases for wfp_eng_wfp_sio_mule driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import os

from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent

from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.log import get_logger
log = get_logger()
from mi.idk.config import Config

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys, DriverStateKey, DriverParameter
from mi.dataset.driver.WFP_ENG.wfp.driver import WfpEngWfp, DataTypeKey
from mi.dataset.parser.wfp_eng_wfp_sio_mule import WfpEngWfpSioMuleParserDataStartTimeParticle, \
    WfpEngWfpSioMuleParserDataStatusParticle, \
    WfpEngWfpSioMuleParserDataEngineeringParticle
from mi.dataset.parser.wfp_eng_wfp_sio_mule import DataParticleType as WfpEngWfpSioMuleDataParticleType
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStatusRecoveredDataParticle, \
    WfpEngStcImodemStartRecoveredDataParticle, WfpEngStcImodemEngineeringRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import DataParticleType as WfpEngStcImodemDataParticleType
from mi.dataset.parser.sio_mule_common import StateKey

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'WFP_ENG', 'wfp', 'resource')

DIR_REC = '/tmp/dsatest_rec'
DIR_TEL = '/tmp/dsatest_tel'
FILE_REC1 = 'E00000001.DAT'
FILE_REC2 = 'E00000002.DAT'
FILE_TEL = 'node58p1.dat'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.WFP_ENG.wfp.driver',
    driver_class='WfpEngWfp',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=WfpEngWfp.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'wfp_eng_wfp',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.WFP_ENG_STC_IMODEM:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_REC,
                DataSetDriverConfigKeys.PATTERN: 'E*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.WFP_ENG_WFP_SIO_MULE:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_TEL,
                DataSetDriverConfigKeys.PATTERN: FILE_TEL,
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.WFP_ENG_STC_IMODEM: {},
            DataTypeKey.WFP_ENG_WFP_SIO_MULE: {},
        }
    }
)


PARSER_STATE = 'parser_state'

REC_PARTICLES = (WfpEngStcImodemStatusRecoveredDataParticle,
                 WfpEngStcImodemStartRecoveredDataParticle,
                 WfpEngStcImodemEngineeringRecoveredDataParticle)
TEL_PARTICLES = (WfpEngWfpSioMuleParserDataStartTimeParticle,
                 WfpEngWfpSioMuleParserDataStatusParticle,
                 WfpEngWfpSioMuleParserDataEngineeringParticle)


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
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        # Test simple telemetered data handling
        self.create_sample_data_set_dir('node58p3.dat', DIR_TEL, FILE_TEL)
        self.assert_data(TEL_PARTICLES, 'first_five.yml', count=5, timeout=10)

        # Test simple recovered data handling
        self.create_sample_data_set_dir('recovered_one.DAT', DIR_REC, FILE_REC1)
        self.assert_data(REC_PARTICLES, 'recovered.one.yml', count=2, timeout=10)

    def test_new_and_changed_files(self):
        """
        Test the ability to process new recovered and changed telemetered data files.
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        # Deploy a recovered data file to process
        self.create_sample_data_set_dir('recovered_one.DAT', DIR_REC, FILE_REC1)

        # Deploy an initial telemeter data file into the telemetered data file deployment directory
        telem_file1 = 'node58p1-part1.dat'
        self.create_sample_data_set_dir(telem_file1, DIR_TEL, FILE_TEL)

        # Make sure we receive the correct recovered particle
        self.assert_data(WfpEngStcImodemStartRecoveredDataParticle, 'recovered.part1.yml',
                         count=1, timeout=10)

        # Make sure we receive the correct telemetered particles
        self.assert_data(WfpEngWfpSioMuleParserDataStartTimeParticle, 'telem_one.yml', count=1, timeout=10)
        self.assert_data(WfpEngWfpSioMuleParserDataStatusParticle, 'telem_two.yml', count=1, timeout=10)
        self.assert_data(WfpEngWfpSioMuleParserDataEngineeringParticle, 'telem_three.yml', count=3, timeout=10)

        # Add a new recovered data file to process
        self.create_sample_data_set_dir('recovered_two.DAT', DIR_REC, FILE_REC2)

        # Update the telemetered data file with additional contents
        telem_file2 = 'node58p1-part2.dat'
        self.create_sample_data_set_dir(telem_file2, DIR_TEL, FILE_TEL)

        # Make sure we receive the correct recovered particle
        self.assert_data(WfpEngStcImodemEngineeringRecoveredDataParticle, 'recovered.part2.yml',
                         count=1, timeout=10)

        # Make sure we receive the correct telemetered particle
        self.assert_data(WfpEngWfpSioMuleParserDataStartTimeParticle, 'telem_four.yml',
                         count=1, timeout=10)

    def test_start_stop_restart(self):
        """
        Test the ability to start, stop and restart the driver
        """
        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        # Deploy two recovered data files to process
        self.create_sample_data_set_dir('recovered_one.DAT', DIR_REC, FILE_REC1)
        self.create_sample_data_set_dir('recovered_two.DAT', DIR_REC, FILE_REC2)

        # Deploy an initial telemeter data file into the telemetered data file deployment directory
        telem_file1 = 'node58p1-part1.dat'
        self.create_sample_data_set_dir(telem_file1, DIR_TEL, FILE_TEL)

        # Make sure we receive the correct recovered particle
        self.assert_data(WfpEngStcImodemStartRecoveredDataParticle, 'recovered.part1.yml',
                         count=1, timeout=10)

        # Make sure we receive the correct telemetered particles
        self.assert_data(WfpEngWfpSioMuleParserDataStartTimeParticle, 'telem_one.yml', count=1, timeout=10)
        self.assert_data(WfpEngWfpSioMuleParserDataStatusParticle, 'telem_two.yml', count=1, timeout=10)
        self.assert_data(WfpEngWfpSioMuleParserDataEngineeringParticle, 'telem_three.yml', count=3, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Get the modification time and file statistics information for the telemetered data file in the
        # telemetered data file deployment directory
        driver_config = self._driver_config()['startup_config']

        telem_prod_file_path = os.path.join(driver_config['harvester'][DataTypeKey.WFP_ENG_WFP_SIO_MULE]['directory'],
                                            driver_config['harvester'][DataTypeKey.WFP_ENG_WFP_SIO_MULE]['pattern'])
        mod_time = os.path.getmtime(telem_prod_file_path)
        stat_info = os.stat(os.path.join(telem_prod_file_path))

        # Clear any existing sampling
        self.clear_sample_data()

        # Clear the asynchronous callback results
        self.clear_async_data()

        # Re-deploy the two recovered data files
        rec_file_path1 = self.create_sample_data_set_dir('recovered_one.DAT', DIR_REC, FILE_REC1)
        rec_file_path2 = self.create_sample_data_set_dir('recovered_two.DAT', DIR_REC, FILE_REC2)

        # Update the telemetered data file with additional contents
        telem_file2 = 'node58p1-part2.dat'
        self.create_sample_data_set_dir(telem_file2, DIR_TEL, FILE_TEL)

        key_rec = DataTypeKey.WFP_ENG_STC_IMODEM
        key_tel = DataTypeKey.WFP_ENG_WFP_SIO_MULE

        # Set the state of the driver to the prior state altered to have ingested the first recovered
        # data file fully, not ingested the second recovered data file, and to have not returned the fifth
        # telemetered data particle in the original version of the telemetered data file
        new_state = {
            key_rec: {
                # The following recovered file state will be fully read
                FILE_REC1: self.get_file_state(rec_file_path1, True, position=50),
                # The following recovered file state will start at byte 76
                FILE_REC2: self.get_file_state(rec_file_path2, False, position=76)
            },
            key_tel: {
                FILE_TEL: {
                    DriverStateKey.FILE_SIZE: stat_info.st_size,
                    DriverStateKey.FILE_CHECKSUM: '81ed5234fa0b6c76cf5b9f6cf76030a2',
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE: {
                        StateKey.UNPROCESSED_DATA:
                            [[2818, 2982]],
                        StateKey.IN_PROCESS_DATA: [[2818, 2982, 5, 4]],
                        StateKey.FILE_SIZE: stat_info.st_size
                    }
                }
            }
        }

        # Reset the state of the driver
        self.driver = self._get_driver_object(memento=new_state)

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        # Check to make sure we received the correct recovered particles
        self.assert_data(WfpEngStcImodemEngineeringRecoveredDataParticle, 'recovered.stop_resume.yml',
                         count=2, timeout=10)

        # Check to make sure we received a correct telemetered data particle
        self.assert_data(WfpEngWfpSioMuleParserDataEngineeringParticle, 'telemetered.stop_resume1.yml',
                         count=1, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        # Check to make sure we received a correct telemetered data particle
        self.assert_data(WfpEngWfpSioMuleParserDataStartTimeParticle, 'telemetered.stop_resume2.yml',
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
        Need to override common test since there is no '*' to replace with foo
        in the pattern for the single file (telemetered), and need to use a
        shorter file to assert the state change before timing out.
        """
        # need to put data in the file, not just make an empty file for this to work
        self.create_sample_data_set_dir('node58p3.dat', DIR_TEL, FILE_TEL,
                                        mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir('node58p3.dat', DIR_TEL, FILE_TEL)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

        # stop sampling so we can start again
        self.assert_stop_sampling()

        # stop and restart the agent so we can test the next new file exception
        self.stop_dataset_agent_client()
        self.init_dataset_agent_client()

        self.assert_new_file_exception(FILE_REC1, DIR_REC)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.info("CONFIG: %s", self._agent_config())

        # Deploy the recovered and telemetered data files
        self.create_sample_data_set_dir('recovered_one.DAT', DIR_REC, FILE_REC1)
        self.create_sample_data_set_dir('node58p3.dat', DIR_TEL, FILE_TEL)

        self.assert_initialize()

        try:
            # Retrieve one wfp eng imodem start time particle
            imodem_start_particles = \
                self.data_subscribers.get_samples(WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 1)
            log.info("WfpEngStcImodemDataParticleType.START_TIME_RECOVERED particles: %s",
                     imodem_start_particles)

            # Retrieve one wfp eng imodem engineering particle
            imodem_engineering_particles = \
                self.data_subscribers.get_samples(WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 1)
            log.info("WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED particles: %s",
                     imodem_engineering_particles)

            # Concatenate the two wfp eng imodem particle lists
            imodem_particles = imodem_start_particles + imodem_engineering_particles

            # Compare the wfp eng imodem particles to the expected results
            self.assert_data_values(imodem_particles, 'recovered.one.yml')

            # Retrieve one wfp eng sio mule start time particle
            sio_mule_start_time_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.START_TIME, 1)
            log.info("WfpEngWfpSioMuleDataParticleType.START_TIME particles: %s", sio_mule_start_time_particles)

            # Retrieve one wfp eng sio mule status particle
            sio_mule_status_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.STATUS, 1)
            log.info("WfpEngWfpSioMuleDataParticleType.STATUS particles: %s", sio_mule_status_particles)

            # Retrieve three wfp eng sio mule engineering particles
            sio_mule_engineering_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.ENGINEERING, 3)
            log.info("WfpEngWfpSioMuleDataParticleType.ENGINEERING particles: %s", sio_mule_engineering_particles)

            # Concatenate the three wfp eng sio mule particle lists
            sio_mule_particles = sio_mule_start_time_particles + sio_mule_status_particles + \
                                 sio_mule_engineering_particles

            # Compare the wfp eng sio mule particles to the expected results
            self.assert_data_values(sio_mule_particles, 'first_five.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Exception caught.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        log.info("CONFIG: %s", self._agent_config())

        # Deploy large wfp eng imodem and wfp eng sio mule data files to their deployment locations
        self.create_sample_data_set_dir('IModem.dat', DIR_REC, FILE_REC1)
        self.create_sample_data_set_dir('node58p1.dat', DIR_TEL, FILE_TEL)

        # Put the agent into SAMPLING mode and ensure the agent is initialized
        self.assert_initialize()

        try:

            log.info("About to retrieve 1000 WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED samples.")

            # Attempt to retrieve 1000 wfp eng imodem engineering particles
            particles = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 1000, 5000)

            log.info("Checking number of returned WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED samples.")

            # Verify we retrieved 1000 wfp eng imodem engineering particles
            self.assertTrue(len(particles) == 1000)

            log.info("About to retrieve 300 WfpEngWfpSioMuleDataParticleType.ENGINEERING samples.")

            # Attempt to retrieve 300 wfp eng sio mule engineering particles
            particles = self.data_subscribers.get_samples(WfpEngWfpSioMuleDataParticleType.ENGINEERING, 300, 5000)

            log.info("Checking number of returned WfpEngWfpSioMuleDataParticleType.ENGINEERING samples.")

            # Verify we retrieved 300 wfp eng sio mule engineering particles
            self.assertTrue(len(particles) == 300)

            log.info("About to retrieve 100 WfpEngWfpSioMuleDataParticleType.STATUS samples.")

            # Attempt to retrieve 100 wfp eng sio mule status particles
            particles = self.data_subscribers.get_samples(WfpEngWfpSioMuleDataParticleType.STATUS, 100, 5000)

            log.info("Checking number of returned WfpEngWfpSioMuleDataParticleType.STATUS samples.")

            # Verify we retrieved 100 wfp eng sio mule status particles
            self.assertTrue(len(particles) == 100)

            log.info("About to retrieve 100 WfpEngWfpSioMuleDataParticleType.START_TIME samples.")

            # Attempt to retrieve 100 wfp eng sio mule start time particles
            particles = self.data_subscribers.get_samples(WfpEngWfpSioMuleDataParticleType.START_TIME, 100, 5000)

            log.info("Checking number of returned WfpEngWfpSioMuleDataParticleType.STATUS samples.")

            # Verify we retrieved 100 wfp eng sio mule start time particles
            self.assertTrue(len(particles) == 100)

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Exception caught.")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.error("CONFIG: %s", self._agent_config())

        # Deploy initial wfp eng imodem and wfp eng sio mule data files to their deployment locations
        self.create_sample_data_set_dir('node58p1-part1.dat', DIR_TEL, FILE_TEL)
        self.create_sample_data_set_dir('recovered_one.DAT', DIR_REC, FILE_REC1)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:

            # Attempt to retrieve one wfp eng sio mule start time particle
            sio_mule_start_time_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.START_TIME, 1, 100)
            log.info("WfpEngWfpSioMuleDataParticleType.START_TIME particles: %s", sio_mule_start_time_particles)

            # Attempt to retrieve one wfp eng sio mule status particle
            sio_mule_status_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.STATUS, 1, 100)
            log.debug("WfpEngWfpSioMuleDataParticleType.STATUS particles: %s", sio_mule_status_particles)

            # Attempt to retrieve one wfp eng sio mule engineering particle
            sio_mule_eng_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.ENGINEERING, 3, 100)
            log.debug("WfpEngWfpSioMuleDataParticleType.ENGINEERING particles: %s", sio_mule_eng_particles)

            # Attempt to retrieve one wfp eng imodem start time particle
            imodem_start_time_particles = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 1, 100)
            log.debug("WfpEngStcImodemDataParticleType.START_TIME particles: %s", imodem_start_time_particles)

            # Attempt to retrieve one wfp eng imodem engineering particle
            imodem_eng_particles = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 1, 100)
            log.debug("WfpEngStcImodemDataParticleType.ENGINEERING particles: %s", imodem_eng_particles)

            # Concatenate the two wfp eng imodem particle lists
            imodem_particles = imodem_start_time_particles + imodem_eng_particles

            # Verify that we retrieved the expected wfp eng imodem particles
            self.assert_data_values(imodem_particles, 'recovered.one.yml')

            # Verify that we retrieved the expected wfp eng sio mule particles
            self.assert_data_values(sio_mule_start_time_particles, 'telem_one.yml')
            self.assert_data_values(sio_mule_status_particles, 'telem_two.yml')
            self.assert_data_values(sio_mule_eng_particles, 'telem_three.yml')

            # Verify that the sample queue sizes are 0
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.START_TIME, 0)
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.STATUS, 0)
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.ENGINEERING, 0)
            self.assert_sample_queue_size(WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 0)
            self.assert_sample_queue_size(WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 0)

            # Deploy updated wfp eng imodem and wfp eng sio mule data
            self.create_sample_data_set_dir('node58p1-part3.dat', DIR_TEL, FILE_TEL)
            self.create_sample_data_set_dir('recovered_two.DAT', DIR_REC, FILE_REC2)

            # Attempt to retrieve one wfp eng sio mule start time particle
            sio_mule_start_time_particles2 = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.START_TIME, 1, 100)
            log.debug("WfpEngWfpSioMuleDataParticleType.START_TIME particles 2nd query: %s",
                      sio_mule_start_time_particles2)

            # Verify that we retrieved the expected wfp eng sio mule start time particle
            self.assert_data_values(sio_mule_start_time_particles2, 'telem_four.yml')

            # Attempt to retrieve one imodem start time particle
            imodem_start_time_particles2 = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 1, 100)

            # Attempt to retrieve two imodem engineering particles
            imodem_eng_particles2 = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 2, 100)

            log.debug("Stopping sampling")

            # Stop the sampling
            self.assert_stop_sampling()

            # Verify that the sio mule start time sample queue size is 0
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.START_TIME, 0)

            log.debug("Restarting sampling")

            # Restart the sampling
            self.assert_start_sampling()

            # Attempt to retrieve one wfp eng sio mule start time particle
            sio_mule_start_time_particles3 = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.START_TIME, 1, 200)
            log.debug("WfpEngWfpSioMuleDataParticleType.START_TIME particles 3rd query: %s",
                      sio_mule_start_time_particles3)

            # Verify that we retrieved the expected wfp eng sio mule start time particle
            self.assert_data_values(sio_mule_start_time_particles3, 'telem_five.yml')

            # Attempt to retrieve two wfp eng sio mule engineering particles
            imodem_eng_particles3 = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 2, 100)
            log.debug("WfpEngStcImodemDataParticleType.ENGINEERING particles 3rd query: %s",
                      imodem_eng_particles3)

            # Concatenate the wfp eng imodem start time and engineering particles retrieved before the stop with the
            # wfp eng imodem engineering particles retrieved after the restart
            imodem_particles = imodem_start_time_particles2 + imodem_eng_particles2 + imodem_eng_particles3

            # Verify that we retrieved the expected wfp eng imodem particles
            self.assert_data_values(imodem_particles, 'recovered.two.yml')

            # Verify that the sample queue sizes are 0
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.START_TIME, 0)
            self.assert_sample_queue_size(WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 0)

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Exception caught.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())

        # Deploy initial wfp eng imodem and wfp eng sio mule data files to their deployment locations
        self.create_sample_data_set_dir('node58p1-part1.dat', DIR_TEL, FILE_TEL)
        self.create_sample_data_set_dir('recovered_one.DAT', DIR_REC, FILE_REC1)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:

            # Attempt to retrieve one wfp eng sio mule start time particle
            sio_mule_start_time_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.START_TIME, 1, 100)
            log.debug("WfpEngWfpSioMuleDataParticleType.START_TIME particles: %s", sio_mule_start_time_particles)

            # Attempt to retrieve one wfp eng sio mule status particle
            sio_mule_status_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.STATUS, 1, 100)
            log.debug("WfpEngWfpSioMuleDataParticleType.STATUS particles: %s", sio_mule_status_particles)

            # Attempt to retrieve three wfp eng sio mule engineering particles
            sio_mule_eng_particles = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.ENGINEERING, 3, 100)
            log.debug("WfpEngWfpSioMuleDataParticleType.ENGINEERING particles: %s", sio_mule_eng_particles)

            # Attempt to retrieve one wfp eng imodem start time particle
            imodem_start_time_particles = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 1, 100)
            log.debug("WfpEngStcImodemDataParticleType.START_TIME_RECOVERED particles: %s", imodem_start_time_particles)

            # Attempt to retrieve one wfp eng sio mule start time particle
            imodem_eng_particles = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 1, 100)
            log.debug("WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED particles: %s", imodem_eng_particles)

            # Concatenate the wfp eng imodem start time and engineering particles into a single list
            imodem_particles = imodem_start_time_particles + imodem_eng_particles

            # Verify that we retrieved the expected wfp eng sio mule particles
            self.assert_data_values(sio_mule_start_time_particles, 'telem_one.yml')
            self.assert_data_values(sio_mule_status_particles, 'telem_two.yml')
            self.assert_data_values(sio_mule_eng_particles, 'telem_three.yml')

            # Verify that we retrieved the expected wfp eng imodem particles
            self.assert_data_values(imodem_particles, 'recovered.one.yml')

            # Verify that the sample queue sizes are 0
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.START_TIME, 0)
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.STATUS, 0)
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.ENGINEERING, 0)
            self.assert_sample_queue_size(WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 0)
            self.assert_sample_queue_size(WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 0)

            # Deploy updated wfp eng imodem and wfp eng sio mule data
            self.create_sample_data_set_dir('node58p1-part3.dat', DIR_TEL, FILE_TEL)
            self.create_sample_data_set_dir('recovered_two.DAT', DIR_REC, FILE_REC2)

            # Attempt to retrieve one wfp eng sio mule start time particle
            sio_mule_start_time_particles2 = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.START_TIME, 1, 100)
            log.debug("WfpEngWfpSioMuleDataParticleType.START_TIME particles 2nd query: %s",
                      sio_mule_start_time_particles2)

            # Verify that we retrieved the expected wfp eng sio mule particle
            self.assert_data_values(sio_mule_start_time_particles2, 'telem_four.yml')

            # Attempt to retrieve one wfp eng imodem start time particle
            imodem_start_time_particles2 = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 1, 100)

            # Attempt to retrieve two wfp eng imodem engineering particles
            imodem_eng_particles2 = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 2, 100)

            # Stop the sampling
            self.assert_stop_sampling()

            # Stop the agent
            self.stop_dataset_agent_client()

            # Re-start the agent
            self.init_dataset_agent_client()

            # Re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart the sampling
            self.assert_start_sampling()

            # Attempt to retrieve one wfp eng sio mule start time particle
            sio_mule_start_time_particles3 = self.data_subscribers.get_samples(
                WfpEngWfpSioMuleDataParticleType.START_TIME, 1, 300)
            log.debug("WfpEngWfpSioMuleDataParticleType.START_TIME particles 3rd query: %s",
                      sio_mule_start_time_particles3)

            # Verify that we retrieved the expected wfp eng sio mule particle
            self.assert_data_values(sio_mule_start_time_particles3, 'telem_five.yml')

            # Attempt to retrieve two wfp eng imodem engineering particles
            imodem_eng_particles3 = self.data_subscribers.get_samples(
                WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 2, 200)
            imodem_particles2 = imodem_start_time_particles2 + imodem_eng_particles2 + imodem_eng_particles3

            # Verify that we retrieved the expected wfp eng imodem particles
            self.assert_data_values(imodem_particles2, 'recovered.two.yml')

            # Verify that the sample queue sizes are 0
            self.assert_sample_queue_size(WfpEngWfpSioMuleDataParticleType.START_TIME, 0)

            self.assert_sample_queue_size(WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 0)

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Exception caught.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.assert_initialize()

        # Clear any prior events
        self.event_subscribers.clear_events()

        # Deploy a good and bad wfp eng imodem data files
        self.create_sample_data_set_dir('recovered_bad.DAT', DIR_REC, FILE_REC1)
        self.create_sample_data_set_dir('recovered_one.DAT', DIR_REC, FILE_REC2)

        # Attempt to retrieve one wfp eng imodem start time particle
        imodem_start_time_particles = self.data_subscribers.get_samples(
            WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 1)
        log.debug("WfpEngStcImodemDataParticleType.START_TIME_RECOVERED particles: %s", imodem_start_time_particles)

        # Attempt to retrieve one wfp eng imodem engineering particle
        imodem_eng_particles = self.data_subscribers.get_samples(
            WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 1)
        log.debug("WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED particles: %s", imodem_eng_particles)

        # Concatenate the wfp eng imodem start time and engineering particles into a single list
        imodem_particles = imodem_start_time_particles + imodem_eng_particles

        # Verify that the expected wfp eng imodem particles were retrieved
        self.assert_data_values(imodem_particles, 'recovered.one.yml')

        # Verify that the sample queues are empty
        self.assert_sample_queue_size(WfpEngStcImodemDataParticleType.START_TIME_RECOVERED, 0)
        self.assert_sample_queue_size(WfpEngStcImodemDataParticleType.ENGINEERING_RECOVERED, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        self.clear_sample_data()

        # Clear any prior received events
        self.event_subscribers.clear_events()

        # Deploy a good and bad wfp eng sio mule data files
        self.create_sample_data_set_dir('telemetered_bad.dat', DIR_TEL, 'telemetered_bad.dat')
        self.create_sample_data_set_dir('node58p1-part1.dat', DIR_TEL, FILE_TEL)

        # Attempt to retrieve one wfp eng sio mule start time particle
        sio_mule_start_time_particles = self.get_samples(WfpEngWfpSioMuleDataParticleType.START_TIME, 1)
        log.debug("sio mule start time particles: %s", sio_mule_start_time_particles)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
