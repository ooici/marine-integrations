"""
@package mi.dataset.driver.flord_l_wfp.sio_mule.test.test_driver
@file marine-integrations/mi/dataset/driver/flord_l_wfp/sio_mule/driver.py
@author Maria Lutz
@brief Test cases for flord_l_wfp_sio_mule driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Maria Lutz, Joe Padula'
__license__ = 'Apache 2.0'

import os

from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent
from mi.core.log import get_logger
log = get_logger()
from mi.idk.config import Config
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey
from mi.core.instrument.instrument_driver import DriverEvent

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.flord_l_wfp.sio_mule.driver import DataSourceKey, FlordLWfpSioMuleDataSetDriver
from mi.dataset.parser.flord_l_wfp import FlordLWfpInstrumentParserDataParticle
from mi.dataset.parser.flord_l_wfp import DataParticleType as RecoveredDataParticleType
from mi.dataset.parser.flord_l_wfp_sio_mule import FlordLWfpSioMuleParserDataParticle, DataParticleType

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'flord_l_wfp', 'sio_mule', 'resource')

TELEM_DIR = '/tmp/flord/telem/test'
RECOV_DIR = '/tmp/flord/recov/test'

RECOVERED_SAMPLE_DATA = 'E0000001.DAT'

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.flord_l_wfp.sio_mule.driver',
    driver_class='FlordLWfpSioMuleDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=FlordLWfpSioMuleDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'flord_l_wfp_sio_mule',
        DataSourceConfigKey.HARVESTER:
        {
            DataSourceKey.FLORD_L_WFP_SIO_MULE: {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: 'TestData.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataSourceKey.FLORD_L_WFP: {
                DataSetDriverConfigKeys.DIRECTORY: RECOV_DIR,
                DataSetDriverConfigKeys.PATTERN: 'E*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.FLORD_L_WFP_SIO_MULE: {},
            DataSourceKey.FLORD_L_WFP: {}
        }
    }
)

SAMPLE_STREAM = 'flord_l_wfp_instrument'

REC_PARTICLE = FlordLWfpInstrumentParserDataParticle


###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
            
    def test_get(self):
        """
        Test that we can get data from files.
        Assert that the particles are correct.
        """
        # Start sampling and watch for an exception. node58p1_1st2WE.dat
        # contains the first 2 WE blocks in node58p1.dat
        self.clear_async_data()
        self.driver.start_sampling()
        self.create_sample_data_set_dir('node58p1_1stWE.dat', TELEM_DIR, 'TestData.dat')
        self.assert_data(FlordLWfpSioMuleParserDataParticle, 'first.result.yml',
                         count=3, timeout=30)       
        self.create_sample_data_set_dir('node58p1_1st2WE.dat', TELEM_DIR, 'TestData.dat')
        self.assert_data(FlordLWfpSioMuleParserDataParticle, 'second.result.yml',
                         count=1, timeout=30)

    def test_get_recov(self):
        """
        Test that we can get data from files.
        Assert that the particles are correct.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        self.create_sample_data_set_dir('E0000001.DAT', RECOV_DIR)
        log.debug('### Sample file created in dir = %s ', TELEM_DIR)

        # check the first 3 instrument particles
        self.assert_data(REC_PARTICLE,
                         'E0000001_recov.yml',
                         count=3, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        self.create_sample_data_set_dir("node58p1_1st2WE.dat", TELEM_DIR, "TestData.dat")
        
        driver_config = self._driver_config()['startup_config']
        fullfile = os.path.join(driver_config['harvester'][DataSourceKey.FLORD_L_WFP_SIO_MULE]['directory'],
                                driver_config['harvester'][DataSourceKey.FLORD_L_WFP_SIO_MULE]['pattern'])
        mod_time = os.path.getmtime(fullfile)

        # Create and store the new driver state
        # note that these values for size, checksum and mod_time are purposely incorrect,
        # to cause the harvester to decide that the target file has changed.
        self.memento = {
            DataSourceKey.FLORD_L_WFP_SIO_MULE: {
                "TestData.dat": {
                    DriverStateKey.FILE_SIZE: 300,
                    DriverStateKey.FILE_CHECKSUM: 'b9605fd76ed3aff469fe7a874c5e1681',
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE: {'in_process_data': [],
                                                  'unprocessed_data': [[0, 300]],
                                                  'file_size': 300}
                }
            },
            DataSourceKey.FLORD_L_WFP: {}
        }

        self.driver = self._get_driver_object(memento=self.memento)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir("node58p1_1st2WE.dat", TELEM_DIR, "TestData.dat")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(FlordLWfpSioMuleParserDataParticle, 'first.result.yml',
                         count=3, timeout=10)

    def test_mid_state_start_recov(self):
        """
        Test the ability to start the driver with a saved state
        """
        log.info("================ START INTEG TEST MID STATE START RECOV =====================")

        recovered_file_one = RECOVERED_SAMPLE_DATA

        recovered_path_1 = self.create_sample_data_set_dir(recovered_file_one, RECOV_DIR)

        # For recovered, we will assume first 2 records have been processed and put position to 84
        # which is the beginning of the third data record
        state = {
            DataSourceKey.FLORD_L_WFP: {
                recovered_file_one: self.get_file_state(recovered_path_1,
                                                        ingested=False,
                                                        position=84),
            },
            DataSourceKey.FLORD_L_WFP_SIO_MULE: {}
        }

        driver = self._get_driver_object(memento=state)

        self.clear_async_data()

        driver.start_sampling()

        # verify data is produced for the 3rd data record
        self.assert_data(REC_PARTICLE, 'test_recovered_midstate_start.yml', count=1, timeout=60)
           
    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """

        # create the file so that it is unreadable
        self.create_sample_data_set_dir("node58p1_step1.dat", TELEM_DIR, "TestData.dat", mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        self.assert_exception(ValueError)
        
    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order.
        """
        self.clear_async_data()
        self.driver.start_sampling()
        self.create_sample_data_set_dir('node58p1_1st2WE.dat', TELEM_DIR, 'TestData.dat')
        self.assert_data(FlordLWfpSioMuleParserDataParticle, 'first.result.yml',
                         count=3, timeout=30)    
        self.driver.stop_sampling()
        self.create_sample_data_set_dir('node58p1_1st6k.dat', TELEM_DIR, "TestData.dat")
        self.driver.start_sampling()
        self.assert_data(FlordLWfpSioMuleParserDataParticle, 'second.result.yml',
                         count=1, timeout=30)

    def test_start_stop_resume_recov(self):
        """
        Test the ability to stop and restart sampling.
        """
        log.info("================ START INTEG TEST START STOP RESUME RECOV =====================")

        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, RECOV_DIR)

        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(REC_PARTICLE, 'test_recovered_start_stop_resume_one.yml', count=1, timeout=10)

        self.driver.stop_sampling()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(REC_PARTICLE, 'test_recovered_start_stop_resume_two.yml', count=2, timeout=60)

        self.driver.stop_sampling()

    def test_bad_e_header(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs. bad_e_header5.dat contains the first two WE
        SIO mule headers from node58p1.dat, the first wrapping a bad e header.
        Should throw exception, skip the bad data and continue parsing the 2nd WE.
        """
        self.create_sample_data_set_dir('bad_e_header5.dat', TELEM_DIR, 'TestData.dat')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(FlordLWfpSioMuleParserDataParticle, 'second.result.yml',
                         count=1, timeout=30)
        
    def test_bad_e_file_data(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs. bad_e_file data.dat contains the first two
        WE SIO mule headers from node58p1.dat, the first wrapping bad e file
        data. Should throw exception, skip the bad data and continue parsing
        the 2nd WE.
        """
        self.create_sample_data_set_dir('bad_e_data3.dat', TELEM_DIR, 'TestData.dat')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(FlordLWfpSioMuleParserDataParticle, 'second.result.yml',
                         count=1, timeout=30)

    def test_bad_header_recov(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        log.info("================ START INTEG TEST BAD HEADER RECOV =====================")

        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        # Handle a file that does not exist
        self.create_sample_data_set_dir("E0000001-BAD-HEADER1.DAT", RECOV_DIR)

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

    def test_bad_data_recov(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        log.info("================ START INTEG TEST BAD DATA RECOV =====================")

        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        # Handle a file that does not exist
        self.create_sample_data_set_dir("E0000001-BAD-DATA.DAT", RECOV_DIR)

        # an event catches the sample exception
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
        self.create_sample_data_set_dir('node58p1_1stWE.dat', TELEM_DIR, 'TestData.dat')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second, otherwise samples come in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get three samples
        try:
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
            self.assert_data_values(result, 'first.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_publish_path_recov(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.info("=========== START QUAL TEST PUBLISH PATH RECOV =================")

        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, RECOV_DIR)

        self.assert_initialize()

        # get the recovered instrument particles
        result = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 3, 10)

        # check the results
        self.assert_data_values(result, 'E0000001_recov.yml')

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir("node58p1_10kBytes.dat", TELEM_DIR, "TestData.dat")
        self.assert_initialize()
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE,
                                                   30, timeout=60)

    def test_large_import_recov(self):
        """
        Test importing a large number of samples from the file at once
        Assert that we get the correct number of particles
        """
        log.info("=========== START QUAL TEST LARGE IMPORT RECOV =================")

        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, RECOV_DIR)

        self.assert_initialize()

        # get the recovered instrument particle
        self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 200, 500)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node58p1_1st2WE.dat', TELEM_DIR, 'TestData.dat')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        
        self.assert_start_sampling()
    
        try:
            # Read the first file, get 2 samples, and verify data
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            self.assert_data_values(result, 'firstA.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            # Read the second file, get the next sample, then stop
            self.create_sample_data_set_dir('node58p1_10kBytes.dat', TELEM_DIR, 'TestData.dat')
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            self.assert_data_values(result2, 'firstB.result.yml')
            self.assert_stop_sampling()

            # Restart sampling and ensure we get the next record, first record
            # of the 2nd WE sio mule header.
            self.assert_start_sampling()
            result3 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            self.assert_data_values(result3, 'second.result.yml')
            
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_stop_start_recov(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("=========== START QUAL TEST STOP START RECOV =================")

        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, RECOV_DIR)

        # Put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # get the first 2 recovered instrument particle
        result1 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 2, 40)

        # check the results
        self.assert_data_values(result1, 'test_recovered_stop_start_one.yml')

        # stop sampling
        self.assert_stop_sampling()

        # restart sampling
        self.assert_start_sampling()

        # get the next 1 recovered instrument particle
        result2 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 1, 40)

        # check the results
        self.assert_data_values(result2, 'test_recovered_stop_start_two.yml')

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node58p1_1st2WE.dat', TELEM_DIR, 'TestData.dat')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file, get 2 samples, and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            self.assert_data_values(result, 'firstA.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            
            # Read the second file, get the next record, then stop
            self.create_sample_data_set_dir('node58p1_10kBytes.dat', TELEM_DIR, 'TestData.dat')
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            self.assert_stop_sampling()
            
            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the next record
            self.assert_start_sampling()
            result3 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            self.assert_data_values(result3, 'second.result.yml')
            
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart_recov(self):
        """
        Test a full stop of the dataset agent, then restart the agent
        and confirm it restarts at the correct spot.
        """
        log.info("=========== START QUAL TEST SHUTDOWN RECOV RESTART =================")

        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, RECOV_DIR)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # get the first 2 recovered instrument particle
        result1 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 2, 40)

        # check the results
        self.assert_data_values(result1, 'test_recovered_stop_start_one.yml')

        # stop sampling
        self.assert_stop_sampling()

        self.stop_dataset_agent_client()
        # Re-start the agent
        self.init_dataset_agent_client()
        # Re-initialize and enter streaming state
        self.assert_initialize()

        # get the next 1 recovered instrument particle
        result2 = self.data_subscribers.get_samples(RecoveredDataParticleType.INSTRUMENT, 1, 40)

        # check the results
        self.assert_data_values(result2, 'test_recovered_stop_start_two.yml')

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.
        """
        # need to put data in the file, not just make an empty file for this to work
        self.create_sample_data_set_dir('node58p1_1st6k.dat', TELEM_DIR, 'TestData.dat', mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir('node58p1_1st6k.dat', TELEM_DIR, 'TestData.dat')

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_parser_exception(self):
        """
        Test an exception is raised after the parser is started during
        record parsing.
        """
        # file contains invalid sample values
        self.create_sample_data_set_dir('bad_e_data3.dat', TELEM_DIR, "TestData.dat")

        self.event_subscribers.clear_events()
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM, 18, 30)
        self.assert_sample_queue_size(SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 60)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def test_parser_exception_recov(self):
        """
        Test an exception is raised after the parser is started during
        record parsing.
        """
        log.info("=========== START QUAL TEST PARSER EXCEPTION RECOV =================")

        self.create_sample_data_set_dir('E0000001-BAD-DATA.DAT', RECOV_DIR)

        self.assert_initialize()

        self.assert_event_received(ResourceAgentErrorEvent, 10)
