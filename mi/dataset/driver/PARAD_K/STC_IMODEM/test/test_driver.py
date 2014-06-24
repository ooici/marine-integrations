"""
@package mi.dataset.driver.PARAD_K.STC_IMODEM.test.test_driver
@file marine-integrations/mi/dataset/driver/PARAD_K/STC_IMODEM/driver.py
@author Mike Nicoletti
@brief Test cases for PARAD_K_STC_IMODEM driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Mike Nicoletti, Steve Myerson (recovered)'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys

from mi.dataset.driver.PARAD_K.STC_IMODEM.driver import \
    PARAD_K_STC_IMODEM_DataSetDriver, \
    DataTypeKey

from mi.dataset.parser.parad_k_stc_imodem import \
    Parad_k_stc_imodemDataParticle, \
    Parad_k_stc_imodemRecoveredDataParticle

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.dataset.dataset_driver import DriverParameter

DIR_REC = '/tmp/dsatest_rec'
DIR_TEL = '/tmp/dsatest_tel'
FILE1_TEL = 'E0000001.DAT'
FILE2_TEL = 'E0000002.DAT'
FILE3_TEL = 'E0000003.DAT'
FILE1_REC = 'E0000011.DAT'
FILE2_REC = 'E0000012.DAT'
FILE3_REC = 'E0000013.DAT'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.PARAD_K.STC_IMODEM.driver',
    driver_class='PARAD_K_STC_IMODEM_DataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = PARAD_K_STC_IMODEM_DataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'parad_k_stc_imodem',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.PARAD_K_STC:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_TEL,
                DataSetDriverConfigKeys.PATTERN: 'E*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.PARAD_K_STC_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_REC,
                DataSetDriverConfigKeys.PATTERN: 'E*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER:
        {
            DataTypeKey.PARAD_K_STC: {},
            DataTypeKey.PARAD_K_STC_RECOVERED: {}
        }
    }
)

REC_SAMPLE_STREAM = 'parad_k__stc_imodem_instrument_recovered'
TEL_SAMPLE_STREAM = 'parad_k__stc_imodem_instrument'

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
        log.info("================ START INTEG TEST GET =====================")

        key_rec = DataTypeKey.PARAD_K_STC_RECOVERED
        key_tel = DataTypeKey.PARAD_K_STC

        particle_rec = Parad_k_stc_imodemRecoveredDataParticle
        particle_tel = Parad_k_stc_imodemDataParticle

        # Start sampling
        self.clear_async_data()
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir('first.DAT', DIR_TEL, FILE1_TEL)
        self.assert_data(particle_tel, 'first.result.yml', count=1, timeout=10)
        self.assert_file_ingested(FILE1_TEL, key_tel)

        self.create_sample_data_set_dir('first.DAT', DIR_REC, FILE1_REC)
        self.assert_data(particle_rec, 'rec_first.result.yml', count=1, timeout=10)
        self.assert_file_ingested(FILE1_REC, key_rec)

        self.create_sample_data_set_dir('second.DAT', DIR_REC, FILE2_REC)
        self.assert_data(particle_rec, 'rec_second.result.yml', count=4, timeout=10)

        self.create_sample_data_set_dir('second.DAT', DIR_TEL, FILE2_TEL)
        self.assert_data(particle_tel, 'second.result.yml', count=4, timeout=10)

        self.create_sample_data_set_dir('E0000303.DAT', DIR_TEL, FILE3_TEL)
        self.assert_data(particle_tel, count=32, timeout=10)

        log.info("================ END INTEG TEST GET =====================")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data_set_dir('first.DAT', DIR_TEL, FILE1_TEL)
        path_2 = self.create_sample_data_set_dir('second.DAT', DIR_TEL, FILE2_TEL)
        rec_path_1 = self.create_sample_data_set_dir('first.DAT', DIR_REC, FILE1_REC)
        rec_path_2 = self.create_sample_data_set_dir('second.DAT', DIR_REC, FILE2_REC)

        # Create and store the new driver state
        state = {
            DataTypeKey.PARAD_K_STC:
                {FILE1_TEL: self.get_file_state(path_1, True, 50),
                 FILE2_TEL: self.get_file_state(path_2, False, 76)},
            DataTypeKey.PARAD_K_STC_RECOVERED:
                {FILE1_REC: self.get_file_state(rec_path_1, True, 50),
                 FILE2_REC: self.get_file_state(rec_path_2, False, 76)}
        }
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()
        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(Parad_k_stc_imodemRecoveredDataParticle,
                         'rec_partial_second.result.yml', count=2, timeout=10)
        self.assert_data(Parad_k_stc_imodemDataParticle,
                         'partial_second.result.yml', count=2, timeout=10)

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        log.info("========= START INTEG TEST STOP START INGEST ==============")

        key_rec = DataTypeKey.PARAD_K_STC_RECOVERED
        key_tel = DataTypeKey.PARAD_K_STC

        particle_rec = Parad_k_stc_imodemRecoveredDataParticle
        particle_tel = Parad_k_stc_imodemDataParticle

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data_set_dir('first.DAT', DIR_REC, FILE1_REC)
        self.create_sample_data_set_dir('second.DAT', DIR_REC, FILE2_REC)
        self.create_sample_data_set_dir('first.DAT', DIR_TEL, FILE1_TEL)
        self.create_sample_data_set_dir('second.DAT', DIR_TEL, FILE2_TEL)

        log.info("========= READ TELEMETERED FILE 1 ==============")
        self.assert_data(particle_tel, 'first.result.yml', count=1, timeout=10)
        self.assert_file_ingested(FILE1_TEL, key_tel)
        self.assert_file_not_ingested(FILE2_TEL, key_tel)

        log.info("========= READ RECOVERED FILE 1 ==============")
        self.assert_data(particle_rec, 'rec_first.result.yml', count=1, timeout=10)
        self.assert_file_ingested(FILE1_REC, key_rec)
        self.assert_file_not_ingested(FILE2_REC, key_rec)

        log.info("========= STOP AND RESTART SAMPLING ==============")
        self.driver.stop_sampling()
        self.driver.start_sampling()

        log.info("========= READ RECOVERED FILE 2 ==============")
        self.assert_data(particle_rec, 'rec_second.result.yml', count=4, timeout=10)
        self.assert_file_ingested(FILE2_REC, key_rec)

        log.info("========= READ TELEMETERED FILE 2 ==============")
        self.assert_data(particle_tel, 'second.result.yml', count=4, timeout=10)
        self.assert_file_ingested(FILE2_TEL, key_tel)

        log.info("========= END INTEG TEST STOP START INGEST ==============")

    def test_sample_exception(self):
        """
        test that an empty file generates a sample exception
        """
        self.clear_async_data()

        filename = 'FOO'
        self.create_sample_data_set_dir(filename, DIR_TEL, 'E1234567.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()

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
        self.create_sample_data_set_dir('second.DAT', DIR_TEL, FILE1_TEL)
        self.create_sample_data_set_dir('second.DAT', DIR_REC, FILE1_REC)
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # NOTE: If the processing is not slowed down here, the engineering samples are
        # returned in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get 4 samples from each file
        try:
            result = self.data_subscribers.get_samples(TEL_SAMPLE_STREAM, 4)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'second.result.yml')

            result = self.data_subscribers.get_samples(REC_SAMPLE_STREAM, 4)
            log.debug("RECOVERED RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'rec_second.result.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir('E0000303.DAT', DIR_TEL, 'E0000303.DAT')
        self.create_sample_data_set_dir('E0000427.DAT', DIR_TEL, 'E0000427.DAT')
        self.create_sample_data_set_dir('E0000303.DAT', DIR_REC, 'E0001303.DAT')
        self.create_sample_data_set_dir('E0000427.DAT', DIR_REC, 'E0001427.DAT')
        
        self.assert_initialize()

        # get results for each of the data particle streams
        self.get_samples(TEL_SAMPLE_STREAM,64,40)
        self.get_samples(REC_SAMPLE_STREAM,64,40)

    def test_for_nan(self):
        """
        Test to verify that a Sample Exception occurs if the input file contains
        a NaN value for the parad data.
        """
        log.info("========== START QUAL TEST NAN INPUT TELEMETERED ==========")

        self.event_subscribers.clear_events()
        self.assert_initialize()
        self.create_sample_data_set_dir('NaN.DAT', DIR_TEL, FILE3_TEL)

        log.info("========== CHECK FOR EXCEPTION TELEMETERED ==========")
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        log.info("========== END QUAL TEST NAN INPUT TELEMETERED ==========")

    def test_for_nan_recovered(self):
        """
        Test to verify that a Sample Exception occurs if the input file contains
        a NaN value for the parad data.
        """
        log.info("========== START QUAL TEST NAN INPUT RECOVERED ==========")

        self.event_subscribers.clear_events()
        self.assert_initialize()
        self.create_sample_data_set_dir('NaN.DAT', DIR_REC, FILE2_REC)

        log.info("========== CHECK FOR EXCEPTION RECOVERED ==========")
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        log.info("========== END QUAL TEST NAN INPUT RECOVERED ==========")

    def test_status_in_middle(self):
        """
        This file has status particles in the middle and at the end
        """
        self.create_sample_data_set_dir('E0000039.DAT', DIR_TEL,'E0000039.DAT' )
        self.create_sample_data_set_dir('E0000039.DAT', DIR_REC,'E0000139.DAT' )
        self.assert_initialize()

        # get results for each of the data particle streams
        result2 = self.get_samples(TEL_SAMPLE_STREAM,53,40)
        result = self.get_samples(REC_SAMPLE_STREAM,53,40)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first.DAT', DIR_TEL, FILE1_TEL)
        self.create_sample_data_set_dir('first.DAT', DIR_REC, FILE1_REC)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(TEL_SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
            self.assert_sample_queue_size(TEL_SAMPLE_STREAM, 0)

            # Read the first recovered file and verify the data
            rec_result = self.get_samples(REC_SAMPLE_STREAM)
            log.debug("REC RESULT: %s", rec_result)

            # Verify values for recovered data
            self.assert_data_values(rec_result, 'rec_first.result.yml')
            self.assert_sample_queue_size(REC_SAMPLE_STREAM, 0)

            self.create_sample_data_set_dir('second.DAT', DIR_TEL, FILE2_TEL)
            self.create_sample_data_set_dir('second.DAT', DIR_REC, FILE2_REC)

            # Now read the first two records of the second file
            result = self.get_samples(TEL_SAMPLE_STREAM, 2)
            log.debug("got result 1 %s", result)

            # Now read the first two records of the second recovered file then stop
            rec_result = self.get_samples(REC_SAMPLE_STREAM, 2)
            log.debug("got rec result 1 %s", rec_result)

            self.assert_stop_sampling()
            self.assert_sample_queue_size(TEL_SAMPLE_STREAM, 0)
            self.assert_sample_queue_size(REC_SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 5 records of the file
            self.assert_start_sampling()
            result2 = self.get_samples(TEL_SAMPLE_STREAM, 2)
            log.debug("got result 2 %s", result2)
            result.extend(result2)
            self.assert_data_values(result, 'second.result.yml')
            self.assert_sample_queue_size(TEL_SAMPLE_STREAM, 0)

            # Ensure we get the last 5 records of the recovered file
            rec_result2 = self.get_samples(REC_SAMPLE_STREAM, 2)
            log.debug("got rec result 2 %s", rec_result2)
            rec_result.extend(rec_result2)
            self.assert_data_values(rec_result, 'rec_second.result.yml')
            self.assert_sample_queue_size(REC_SAMPLE_STREAM, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test the agents ability to start, completely shutdown, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first.DAT', DIR_TEL, FILE1_TEL)
        self.create_sample_data_set_dir('first.DAT', DIR_REC, FILE1_REC)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(TEL_SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
            self.assert_sample_queue_size(TEL_SAMPLE_STREAM, 0)

            # Read the first recovered file and verify the data
            rec_result = self.get_samples(REC_SAMPLE_STREAM)
            log.debug("REC RESULT: %s", rec_result)

            # Verify values
            self.assert_data_values(rec_result, 'rec_first.result.yml')
            self.assert_sample_queue_size(REC_SAMPLE_STREAM, 0)

            self.create_sample_data_set_dir('second.DAT', DIR_TEL, FILE2_TEL)
            self.create_sample_data_set_dir('second.DAT', DIR_REC, FILE2_REC)

            # Now read the first two records of the second file
            result = self.get_samples(TEL_SAMPLE_STREAM, 2)
            log.debug("got result 1 %s", result)

            # Now read the first two records of the second recovered file then stop
            rec_result = self.get_samples(REC_SAMPLE_STREAM, 2)
            log.debug("got rec result 1 %s", rec_result)

            self.assert_stop_sampling()
            self.assert_sample_queue_size(TEL_SAMPLE_STREAM, 0)
            self.assert_sample_queue_size(REC_SAMPLE_STREAM, 0)

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 2 records of the files
            self.assert_start_sampling()
            
            result2 = self.get_samples(TEL_SAMPLE_STREAM, 2)
            log.debug("got result 2 %s", result2)
            result.extend(result2)
            self.assert_data_values(result, 'second.result.yml')
            self.assert_sample_queue_size(TEL_SAMPLE_STREAM, 0)

            rec_result2 = self.get_samples(REC_SAMPLE_STREAM, 2)
            log.debug("got rec result 2 %s", result2)
            rec_result.extend(rec_result2)
            self.assert_data_values(rec_result, 'rec_second.result.yml')
            self.assert_sample_queue_size(REC_SAMPLE_STREAM, 0)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.create_sample_data_set_dir('bad.DAT', DIR_TEL, FILE1_TEL)
        self.create_sample_data_set_dir('first.DAT', DIR_TEL, FILE2_TEL)

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(TEL_SAMPLE_STREAM, 1)
        self.assert_data_values(result, 'first.result.yml')
        self.assert_sample_queue_size(TEL_SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def test_parser_exception_recovered(self):
        """
        Test an exception is raised after the driver is started during
        record parsing for recovered data.
        """
        self.create_sample_data_set_dir('bad.DAT', DIR_REC, FILE1_REC)
        self.create_sample_data_set_dir('first.DAT', DIR_REC, FILE2_REC)

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(REC_SAMPLE_STREAM, 1)
        self.assert_data_values(result, 'rec_first.result.yml')
        self.assert_sample_queue_size(TEL_SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)