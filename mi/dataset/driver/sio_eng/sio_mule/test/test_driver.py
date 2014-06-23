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
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey
from mi.idk.exceptions import SampleTimeout

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.sio_eng.sio_mule.driver import SioEngSioMuleDataSetDriver, DataSourceKey 
from mi.dataset.parser.sio_eng_sio_mule import SioEngSioMuleParserDataParticle

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
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 5,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {}
        }
    }
)

#SAMPLE_STREAM = 'sio_eng_sio_mule_parsed'

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
        
      
        log.debug("test_stop_resume  ::::  First assert complete")
        #
        ## Create and store the new driver state
        #self.memento = {
        #    DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {
        #        F_NAME: {
        #            DriverStateKey.FILE_SIZE: 5000,
        #            DriverStateKey.FILE_CHECKSUM: '76749155d86be9caedba4e30b4c8b71a', # test_get = 'dd1b506100c650e70a8e0295674777d6',
        #            DriverStateKey.FILE_MOD_DATE: mod_time,
        #            DriverStateKey.PARSER_STATE: {
        #                'in_process_data': [],
        #                'unprocessed_data': [[0, 181], [4677, 4995]]
        #            }
        #        }
        #    }
        #}
        self.memento = {
            DataSourceKey.SIO_ENG_SIO_MULE_TELEMETERED: {
                F_NAME: {
                    DriverStateKey.FILE_SIZE: 4644,
                    DriverStateKey.FILE_CHECKSUM: 'dd1b506100c650e70a8e0295674777d6', #'76749155d86be9caedba4e30b4c8b71a'=test_stop_resume.dat
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE: {
                        'in_process_data': [],
                        'unprocessed_data': [[0, 181], [4677, 4995]]
                    }
                }
            }
        }
        
        self.driver = self._get_driver_object(config=driver_config)
        
        self.driver = SioEngSioMuleDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)
        
        ## create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir("test_stop_resume.dat", TELEM_DIR, F_NAME,
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
 
        # step 2 contains 2 blocks, start with this and get both since we used them
        # separately in other tests
        self.clear_async_data()
        self.create_sample_data_set_dir("node59p1_test_get.dat", TELEM_DIR, "node59p1.dat",
                                copy_metadata=False)
        self.assert_data(SioEngSioMuleParserDataParticle, 'test_get_particle.yml',
                         count=2)
        #
        ## This file has had a section of AD data replaced with 0s
        #self.create_sample_data_set_dir('node59p1_step3.dat', TELEM_DIR, "node59p1.dat",
        #                        copy_metadata=False)
        #self.assert_data(SioEngSioMuleParserDataParticle, 'test_get_particle.yml',
        #                 count=2)
        #
        #
        ## Now fill in the zeroed section from step3, this should just return the new
        ## data with a new sequence flag
        #self.create_sample_data_set_dir('node59p1_test_backfill.dat', TELEM_DIR, "node59p1.dat",
        #                        copy_metadata=False)
        #self.assert_data(SioEngSioMuleParserDataParticle, 'test_get_particle.yml',
        #                 count=1)
        #
        #
        ## start over now, using step 4
        #self.driver.shutdown()
        #self.clear_sample_data()
        #
        ## Reset the driver with no memento
        #self.memento = None
        #self.driver = self._get_driver_object()
        #
        #self.driver.start_sampling()
        #
        #self.clear_async_data()
        #self.create_sample_data_set_dir('node59p1_step4.dat', TELEM_DIR, "node59p1.dat",
        #                        copy_metadata=False)
        #self.assert_data(AdcpsParserDataParticle, 'test_data_1-4.txt.result.yml',
        #                 count=8, timeout=10)
    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        pass

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        pass
    

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
        pass

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        pass

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        pass

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        pass

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        pass

