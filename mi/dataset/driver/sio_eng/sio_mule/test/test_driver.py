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

import unittest
import os
from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from mi.idk.exceptions import SampleTimeout

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey

from interface.objects import ResourceAgentErrorEvent

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.sio_eng.sio_mule.driver import SioEngSioMuleDataSetDriver, DataSourceKey 
from mi.dataset.parser.sio_eng_sio_mule import SioEngSioMuleParserDataParticle, DataParticleType

TELEM_DIR = '/tmp/sio_eng_test'
F_NAME = 'node59p1.dat'
# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.sio_eng.sio_mule.driver',
    driver_class='SioEngSioMuleDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = SioEngSioMuleDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER: {
            DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: F_NAME,
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 2,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {}
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
        self.create_sample_data_set_dir("node59p1_test_get.dat", TELEM_DIR, F_NAME,
                                        copy_metadata=False)
        self.assert_data(SioEngSioMuleParserDataParticle,
            'test_get_particle.yml', count=2, timeout=10)

        

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        # create the file so that it is unreadable
        self.create_sample_data_set_dir("node59p1_step1.dat", TELEM_DIR, F_NAME,
                                        mode=000, copy_metadata=False)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(ValueError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.


    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        self.create_sample_data_set_dir("node59p1_test_get.dat", TELEM_DIR, F_NAME,
                                        copy_metadata=False)
        driver_config = self._driver_config()['startup_config']
        sio_eng_sio_telem_config = driver_config['harvester'][DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED]
        fullfile = os.path.join(sio_eng_sio_telem_config['directory'], sio_eng_sio_telem_config['pattern'])
        mod_time = os.path.getmtime(fullfile)
        
      
        ## Create and store the new driver state
        
        self.memento = {
            DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {
                F_NAME: {
                    DriverStateKey.FILE_SIZE: 4644,
                    DriverStateKey.FILE_CHECKSUM: 'dd1b506100c650e70a8e0295674777d6',
                    DriverStateKey.PARSER_STATE: {
                        'in_process_data': [],
                        'unprocessed_data': [[0, 181]],
                        'file_size': 4644    
                    }
                }
            }
        }
        
        self.driver = self._get_driver_object(config=driver_config)
        
        ## create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir("test_stop_resume2.dat", TELEM_DIR, F_NAME,
                                        copy_metadata=False)
        
        self.driver.start_sampling()
        
        ## verify data is produced
        self.assert_data(SioEngSioMuleParserDataParticle, 'test_stop_resume.yml',
                         count=2)

    
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
        self.create_sample_data_set_dir('node59p1_test_backfill.dat', TELEM_DIR, F_NAME,
                                copy_metadata=False)
        self.assert_data(SioEngSioMuleParserDataParticle, 'test_back_fill.yml',
                         count=1)
        
        
        # Now fill in the zeroed section, and this file also has 2 more CS SIO headers appended
        #   along with other data at the end. 
        self.create_sample_data_set_dir('test_stop_resume2.dat', TELEM_DIR, F_NAME,
                                copy_metadata=False)
        self.assert_data(SioEngSioMuleParserDataParticle, 'test_back_fill2.yml',
                         count=3)
    
    def test_bad_data(self):
        # Put bad data into the file and make sure an exemption is raised
        
        ## This file has had a section of CS data replaced with letters
        self.clear_async_data()
        self.create_sample_data_set_dir('node59p1_test_get_bad.dat', TELEM_DIR, F_NAME,
                                copy_metadata=False)
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
        self.create_sample_data_set_dir('node59p1_test_get.dat', TELEM_DIR, F_NAME,
                                        copy_metadata=False)
        
        self.assert_initialize()
        
        try:    
            # Verify we get samples
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_get_particle.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir('node59p1.dat', TELEM_DIR, F_NAME,
                                        copy_metadata=False)
        self.assert_initialize()
        
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE,30,300)
        
    def test_large_import2(self):
        """
        Test importing a large number of samples from a different file at once
        """
        self.create_sample_data_set_dir('node58p1.dat', TELEM_DIR, F_NAME,
                                        copy_metadata=False)
        self.assert_initialize()
        
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE,200,600)    
        
    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_test_get.dat', TELEM_DIR, F_NAME,
                                        copy_metadata=False)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data
            
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT: %s", result)
            # Verify values
            self.assert_data_values(result, 'test_get_particle.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            self.create_sample_data_set_dir('test_stop_resume2.dat', TELEM_DIR, F_NAME,
                                            copy_metadata=False)
            # Now read the first records of the second file then stop
            self.assert_stop_sampling()
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT 2: %s", result2)
            
            self.assert_data_values(result2, 'test_stop_resume.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout .")


    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node59p1_test_get.dat', TELEM_DIR, F_NAME,
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
            self.assert_data_values(result, 'test_get_particle.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            self.create_sample_data_set_dir('test_stop_resume2.dat', TELEM_DIR, F_NAME,
                                            copy_metadata=False)
            
            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()
            
            

            # Restart sampling and ensure we get the last 2 records of the file
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("RESULT 2: %s", result2)        
            self.assert_data_values(result2, 'test_stop_resume.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout .")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file contains invalid sample values
        self.create_sample_data_set_dir('node59p1_test_get_bad.dat', TELEM_DIR,
                                        F_NAME)
        self.event_subscribers.clear_events()
        self.assert_initialize()

        result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)



