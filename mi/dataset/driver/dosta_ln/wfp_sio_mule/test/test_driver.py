"""
@package mi.dataset.driver.dosta_ln.wfp_sio_mule.test.test_driver
@file marine-integrations/mi/dataset/driver/dosta_ln/wfp_sio_mule/driver.py
@author Christopher Fortin
@brief Test cases for dosta_ln_wfp_sio_mule driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Christopher Fortin'
__license__ = 'Apache 2.0'

import unittest
import os
import gevent

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
from mi.dataset.dataset_driver import DriverParameter, DriverStateKey

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.dosta_ln.wfp_sio_mule.driver import DostaLnWfpSioMuleDataSetDriver, \
                                                        DataSourceKey
from mi.dataset.parser.dosta_ln_wfp_sio_mule import DostaLnWfpSioMuleParser, \
                                                    DostaLnWfpSioMuleParserDataParticle, \
                                                    DataParticleType
from mi.dataset.parser.dosta_ln_wfp import DostaLnWfpInstrumentParserDataParticle, \
                                           DataParticleType as DostaLnWfpParticleType, \
                                           HEADER_BYTES, \
                                           WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_BYTES
from mi.dataset.parser.sio_mule_common import StateKey

TELEM_DIR = '/tmp/dsatest_telem'
RECOV_DIR = '/tmp/dsatest_recov'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.dosta_ln.wfp_sio_mule.driver',
    driver_class='DostaLnWfpSioMuleDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = DostaLnWfpSioMuleDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'dosta_ln_wfp_sio_mule',
        DataSourceConfigKey.HARVESTER:
        {
            DataSourceKey.DOSTA_LN_WFP_SIO_MULE: {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: 'node58p1.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataSourceKey.DOSTA_LN_WFP: {
                DataSetDriverConfigKeys.DIRECTORY: RECOV_DIR,
                DataSetDriverConfigKeys.PATTERN: 'E*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.DOSTA_LN_WFP_SIO_MULE: {},
            DataSourceKey.DOSTA_LN_WFP: {}
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
        
        log.debug("                        ************************************************   test_get")
        # Start sampling and watch for an exception. node58p1_1st2WE.dat contains the first 2 WE blocks in node58p1.dat
        
        # Clear the asynchronous callback results
        self.clear_async_data()
        
        # Notify the driver to start sampling
        self.driver.start_sampling()
        
        self.create_sample_data_set_dir('node58p1_1stWE.dat', TELEM_DIR, 'node58p1.dat')
        self.assert_data(DostaLnWfpSioMuleParserDataParticle, 'first.result.yml', count=3, timeout=30)
            
        self.create_sample_data_set_dir('node58p1_1st2WE.dat', TELEM_DIR, 'node58p1.dat')
        self.assert_data(DostaLnWfpSioMuleParserDataParticle, 'second.result.yml', count=1, timeout=30)

    def test_get_recov(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """

        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir('E0000001.DAT', RECOV_DIR, "E0000001.DAT")
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, 'first.yml', count=1, timeout=10)

        # Read the remaining values in first.DAT
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, None, count=682, timeout=100)

        self.clear_async_data()
        self.create_sample_data_set_dir('E0000002.DAT', RECOV_DIR, "E0000002.DAT")
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, 'six_samples.yml', count=6, timeout=10)

        # Read the remaining values in second.DAT
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, None, count=677, timeout=100)

        self.clear_async_data()
        self.create_sample_data_set_dir('E0000001.DAT', RECOV_DIR, "E0000003.DAT")
        # start is the same particle here, just use the same results
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, count=30, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """

        self.create_sample_data_set_dir("node58p1_1st2WE.dat", TELEM_DIR, "node58p1.dat")
        
        driver_config = self._driver_config()['startup_config']
        fullfile = os.path.join(driver_config['harvester'][DataSourceKey.DOSTA_LN_WFP_SIO_MULE]['directory'],
                            driver_config['harvester'][DataSourceKey.DOSTA_LN_WFP_SIO_MULE]['pattern'])
        mod_time = os.path.getmtime(fullfile)

        # Create and store the new driver state
        # note that these values for size, checksum and mod_time are purposely incorrect,
        # to cause the harvester to decide that the target file has changed.
        self.memento = {
            DataSourceKey.DOSTA_LN_WFP_SIO_MULE: {
                "node58p1.dat": {
                    DriverStateKey.FILE_SIZE: 300,
                    DriverStateKey.FILE_CHECKSUM: 'b9605fd76ed3aff469fe7a874c5e1681',
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE: {
                        StateKey.IN_PROCESS_DATA: [],
                        StateKey.UNPROCESSED_DATA:[],
                        StateKey.FILE_SIZE: 300
                    }
                }
            },
            DataSourceKey.DOSTA_LN_WFP: {}
        }

        self.driver = self._get_driver_object(memento=self.memento)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir("node58p1_1st2WE.dat", TELEM_DIR, "node58p1.dat")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(DostaLnWfpSioMuleParserDataParticle, 'test_data_2.txt.result.yml',
                         count=1, timeout=10)

    def test_stop_resume_recov(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data_set_dir('E0000001.DAT', RECOV_DIR, "E0000001.DAT")
        path_2 = self.create_sample_data_set_dir('E0000002.DAT', RECOV_DIR, "E0000002.DAT")

        # Create and store the new driver state
        # The first file will be fully ingested
        # The second file will have had 4 samples read from it already
        state = {
            DataSourceKey.DOSTA_LN_WFP: {
                'E0000001.DAT': self.get_file_state(path_1, True, None),
                'E0000002.DAT': self.get_file_state(path_2, False,
                                                    HEADER_BYTES+(WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_BYTES*4))
            },
            DataSourceKey.DOSTA_LN_WFP_SIO_MULE: {}
        }
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, 'two_samples.yml', count=2, timeout=10)

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """

        # create the file so that it is unreadable
        self.create_sample_data_set_dir("node58p1_step1.dat", TELEM_DIR, "node58p1.dat", mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(ValueError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_stop_start_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data_set_dir('node58p1_1st3k.dat', TELEM_DIR, "node58p1.dat")
        self.assert_data(None, 'first_ssr_result.yml', count=3, timeout=10)
 
        self.driver.stop_sampling()
        self.create_sample_data_set_dir('node58p1_1st6k.dat', TELEM_DIR, "node58p1.dat")
        self.driver.start_sampling()

        self.assert_data(None, 'second_ssr_result.yml', count=12, timeout=10)

    def test_stop_start_resume_recov(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data_set_dir('E0000001.DAT', RECOV_DIR, "E0000001.DAT")
        self.create_sample_data_set_dir('E0000002.DAT', RECOV_DIR, "E0000002.DAT")

        # Read the first record and compare it
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, 'first.yml', count=1, timeout=10)

        # Read the the remaining 682 records from E0000001.DAT, plus 4 additional from E0000002.DAT
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, None, count=686, timeout=100)

        # Ensure it is true that E0000001.DAT was fully ingested
        self.assert_file_ingested("E0000001.DAT", DataSourceKey.DOSTA_LN_WFP)

        # Ensure it is true that E0000002.DAT was NOT fully ingested
        self.assert_file_not_ingested("E0000002.DAT", DataSourceKey.DOSTA_LN_WFP)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        # Read 2 records and compare them
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, 'two_samples.yml', count=2, timeout=10)

        # Read the remaining 677 records from E0000002.DAT
        self.assert_data(DostaLnWfpInstrumentParserDataParticle, None, count=677, timeout=100)

        # Ensure it is true that E0000002.DAT was fully ingested
        self.assert_file_ingested("E0000002.DAT", DataSourceKey.DOSTA_LN_WFP)

    def test_bad_e_header(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs. bad_e_header.dat contains the first two WE
        SIO mule headers from node58p1.dat, the first wrapping a bad e header.
        Should throw exception, skip the bad data and continue parsing the 2nd WE.
        """
        self.create_sample_data_set_dir('bad_e_header5.dat', TELEM_DIR, 'node58p1.dat')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(DostaLnWfpSioMuleParserDataParticle, 'second.result.yml', count=1, timeout=30)

    def test_bad_e_file_data(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs. bad_e_file data.dat contains the first two
        WE SIO mule headers from node58p1.dat, the first wrapping bad e file
        data. Should throw exception, skip the bad data and continue parsing
        the 2nd WE.
        """
        # bad_e_file data.dat contains the first two WE SIO mule headers from node58p1.dat, the first 
        # wrapping bad e file data. Should throw exception, skip the bad data and continue parsing the 2nd WE.
        self.create_sample_data_set_dir('bad_e_data3.dat', TELEM_DIR, 'node58p1.dat')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_data(DostaLnWfpSioMuleParserDataParticle, 'second.result.yml', count=1, timeout=30)

    def test_sample_exception_recov(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        self.clear_async_data()
        filename = "Efoo.DAT"
        self.create_sample_data_set_dir(filename, RECOV_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename, DataSourceKey.DOSTA_LN_WFP)


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
        self.create_sample_data_set_dir('node58p1_1stWE.dat', TELEM_DIR, 'node58p1.dat')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second otherwise samples come in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_publish_path_recov(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.info("CONFIG: %s", self._agent_config())

        # Create a sample input file using a small input test file that contains 6 samples.
        self.create_sample_data_set_dir('small.DAT', RECOV_DIR, 'E0000001.DAT')

        # Put the agent into SAMPLING mode and ensure the agent is initialized
        self.assert_initialize()

        # Verify we get one sample
        try:

            # Try to get 6 records
            result = self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 6)
            log.debug("First RESULT: %s", result)

            # Verify the 6 retrieved records against the expected results
            self.assert_data_values(result, 'six_samples.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node58p1_1stWE.dat', TELEM_DIR, 'node58p1.dat')
        
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()
    
        try:
            # Read the first file, get 2 samples, and verify data
            result1 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug("      ********************     RESULT 1: %s", result1)
            self.assert_data_values(result1, 'firstA.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            
            # Read the second file, get the next sample, then stop
            self.create_sample_data_set_dir('node58p1_1st2WE.dat', TELEM_DIR, 'node58p1.dat')
            
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            log.debug("      ********************     RESULT 2: %s", result2)
            self.assert_stop_sampling()
            self.assert_data_values(result2, 'firstB.result.yml')
            
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

            # Restart sampling and ensure we get the next record, first record
            # of the 2nd WE sio mule header.
            self.assert_start_sampling()
            
            result3 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            self.assert_data_values(result3, 'second.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            log.debug("      ********************     RESULT 3: %s", result3)
            
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_stop_start_recov(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())

        # Create a sample input file using a test file that contains one sample
        self.create_sample_data_set_dir('one.DAT', RECOV_DIR, "E0000001.DAT")

        # Put the agent into SAMPLING mode and ensure the agent is initialized
        self.assert_initialize()

        # Verify we get one sample
        try:
            # Read the first file containing one record and verify the data
            result = self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 1)
            log.debug("RESULT 1: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.yml')

            # Make sure the queue is now emtpy
            self.assert_sample_queue_size(DostaLnWfpParticleType.INSTRUMENT, 0)

            self.create_sample_data_set_dir('small.DAT', RECOV_DIR, "E0000002.DAT")
            # Now read the first four records of the second file then stop
            result2 = self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 4)
            log.debug("RESULT 2: %s", result2)

            # Stop the agent from doing sampling
            self.assert_stop_sampling()

            # There should be 2 items remaining on the queue
            self.assert_sample_queue_size(DostaLnWfpParticleType.INSTRUMENT, 2)

            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()

            result3 = self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 2)
            log.debug("RESULT 3: %s", result3)

            # Make sure the two samples match the expected results
            self.assert_data_values(result3, 'two_samples.yml')

            # There should be 0 elements in the queue
            self.assert_sample_queue_size(DostaLnWfpParticleType.INSTRUMENT, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('node58p1_1stWE.dat', TELEM_DIR, 'node58p1.dat')
        
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file, get 2 samples, and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
            log.debug(" *********##*****************        RESULT: %s", result)
            # verify the data
            self.assert_data_values(result, 'firstA.result.yml')
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            
            # Read the second file, get the next record, then stop
            #gevent.sleep(5)
            
            self.create_sample_data_set_dir('node58p1_1st2WE.dat', TELEM_DIR, 'node58p1.dat')
            
            result2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            log.debug(" *******#####*****************        RESULT 2: %s", result2)
            self.assert_stop_sampling()
            self.assert_data_values(result2, 'firstB.result.yml')
 
            self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)
            
            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize()

            # Restart sampling and ensure we get the next record
            result3 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 1)
            self.assert_data_values(result3, 'second.result.yml')
            log.debug("      ********************     RESULT 3: %s", result3)
            
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart_recov(self):
        """
        Test a full stop of the dataset agent, then restart the agent
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())

        self.create_sample_data_set_dir('one.DAT', RECOV_DIR, "E0000001.DAT")

        # Put the agent into SAMPLING mode and ensure the agent is initialized
        self.assert_initialize()

        # Verify we get one sample
        try:
            # Read the first file containing one record and verify the data
            result = self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 1)
            log.debug("RESULT 1: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.yml')

            # Make sure the queue is now emtpy
            self.assert_sample_queue_size(DostaLnWfpParticleType.INSTRUMENT, 0)

            self.create_sample_data_set_dir('small.DAT', RECOV_DIR, "E0000002.DAT")
            # Now read the first four records of the second file then stop
            result2 = self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 4)
            log.debug("RESULT 2: %s", result2)
            self.assert_stop_sampling()

            # There should be 2 items remaining on the queue
            self.assert_sample_queue_size(DostaLnWfpParticleType.INSTRUMENT, 2)

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)
            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()

            # Attempt to retrieve 2 samples
            result3 = self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 2)
            log.debug("RESULT 3: %s", result3)

            self.assert_data_values(result3, 'two_samples.yml')

            # There should be 0 elements in the queue
            self.assert_sample_queue_size(DostaLnWfpParticleType.INSTRUMENT, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir("node58p1_10kBytes.dat", TELEM_DIR, "node58p1.dat")
        self.assert_initialize()
   
        # get results for each of the data particle streams
        result = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 30, timeout=60)

    def test_large_import_recov(self):
        """
        Test importing a large number of samples from the file at once
        """
        log.info("CONFIG: %s", self._agent_config())

        # Create a sample input file using a test input file that includes an OffloadProcessorData record that
        # includes a decimation factor
        self.create_sample_data_set_dir('E0000002.DAT', RECOV_DIR, 'E0000002.DAT')

        # Put the agent into SAMPLING mode and ensure the agent is initialized
        self.assert_initialize()

        try:
            # Attempt to retrieve 400 samples and use a 500 second timeout
            self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 400, 500)

            # Attempt to retrieve the remaining 283 samples using a 500 second timeout
            self.data_subscribers.get_samples(DostaLnWfpParticleType.INSTRUMENT, 283, 500)

            # There should be 0 elements remaining in the queue
            self.assert_sample_queue_size(DostaLnWfpParticleType.INSTRUMENT, 0)

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        # need to put data in the file, not just make an empty file for this to work
        self.create_sample_data_set_dir('node58p1_1st6k.dat', TELEM_DIR, "node58p1.dat", mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir('node58p1_1st6k.dat', TELEM_DIR, "node58p1.dat")

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # file contains invalid sample values
        self.create_sample_data_set_dir('bad_e_data3.dat', TELEM_DIR, "node58p1.dat")

        self.assert_initialize()
        self.event_subscribers.clear_events()
        result = self.get_samples(DataParticleType.SAMPLE, 18, 30) 
        self.assert_sample_queue_size(DataParticleType.SAMPLE, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def test_parser_exception_recov(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """

        # Create a sample input file that should result in a SampleException
        self.create_sample_data_set_dir('E0000001-BAD-DATA.DAT', RECOV_DIR, 'E0000001.DAT')

        # Create a sample input file that has one sample
        self.create_sample_data_set_dir('one.DAT', RECOV_DIR, 'E0000002.DAT')

        # Put the agent into SAMPLING mode and ensure the agent is initialized
        self.assert_initialize()

        # Clear any prior events
        self.event_subscribers.clear_events()

        # Attempt to retrieve one sample
        result = self.get_samples(DostaLnWfpParticleType.INSTRUMENT, 1)

        # Check to make sure the one sample matches the expected results
        self.assert_data_values(result, 'first.yml')

        # There should be 0 elements in the queue now
        self.assert_sample_queue_size(DostaLnWfpParticleType.INSTRUMENT, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
