"""
@package mi.dataset.driver.ctdpf_ckl.wfp.test.test_driver
@file marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp/driver.py
@author cgoodrich
@brief Test cases for ctdpf_ckl_wfp driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

import os
from mi.idk.config import Config

from nose.plugins.attrib import attr
from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.core.log import get_logger
log = get_logger()
from mi.idk.exceptions import SampleTimeout
from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DriverParameter
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.ctdpf_ckl.wfp.driver import DataTypeKey, CtdpfCklWfpDataSetDriver
from mi.dataset.parser.ctdpf_ckl_wfp import CtdpfCklWfpParser
from mi.dataset.parser.ctdpf_ckl_wfp_particles import\
    DataParticleType,\
    CtdpfCklWfpRecoveredDataParticle,\
    CtdpfCklWfpRecoveredMetadataParticle,\
    CtdpfCklWfpTelemeteredDataParticle,\
    CtdpfCklWfpTelemeteredMetadataParticle
from mi.dataset.parser.wfp_c_file_common import StateKey


RESOURCE_PATH = os.path.join(Config().base_dir(),
                             'mi', 'dataset', 'driver',
                             'ctdpf_ckl', 'wfp', 'resource')


REC_DIR = '/tmp/dsatest_rec'
TEL_DIR = '/tmp/dsatest_tel'
REC_FILE = 'C0000034.DAT'
TEL_FILE = 'C0000038.DAT'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.ctdpf_ckl.wfp.driver',
    driver_class='CtdpfCklWfpDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = CtdpfCklWfpDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'ctdpf_ckl_wfp',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.CTDPF_CKL_WFP_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: REC_DIR,
                DataSetDriverConfigKeys.PATTERN: 'C*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.CTDPF_CKL_WFP_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TEL_DIR,
                DataSetDriverConfigKeys.PATTERN: 'C*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.CTDPF_CKL_WFP_RECOVERED: {},
            DataTypeKey.CTDPF_CKL_WFP_TELEMETERED: {}
        }
    }
)

PARSER_STATE = 'parser_state'

REC_PARTICLES = (CtdpfCklWfpRecoveredDataParticle, CtdpfCklWfpRecoveredMetadataParticle)
TEL_PARTICLES = (CtdpfCklWfpTelemeteredDataParticle, CtdpfCklWfpTelemeteredMetadataParticle)

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

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        # Read from the recovered data
        self.clear_async_data()
        self.create_sample_data_set_dir('first.DAT', REC_DIR, 'C0000001.DAT')
        self.assert_data(REC_PARTICLES, 'first.result.yml', count=4, timeout=10)

        # Read from the telemetered data
        self.clear_async_data()
        self.create_sample_data_set_dir('second.DAT', TEL_DIR, 'C0000002.DAT')
        self.assert_data(TEL_PARTICLES, 'second.result.yml', count=7, timeout=10)

    def test_mid_state(self):
        """
        Test the ability to stop and restart the process
        """

        path_R1 = self.create_sample_data_set_dir('first.DAT', REC_DIR, 'C0000001.DAT')
        path_R2 = self.create_sample_data_set_dir('second.DAT', REC_DIR, 'C0000002.DAT')

        path_T1 = self.create_sample_data_set_dir('first.DAT', TEL_DIR, 'C0000001.DAT')
        path_T2 = self.create_sample_data_set_dir('second.DAT', TEL_DIR, 'C0000002.DAT')

        # Create and store the new driver state
        state = {
            DataTypeKey.CTDPF_CKL_WFP_RECOVERED: {
                'C0000001.DAT': self.get_file_state(path_R1, True, 33),
                'C0000002.DAT': self.get_file_state(path_R2, False, 33)
            },
            DataTypeKey.CTDPF_CKL_WFP_TELEMETERED: {
                'C0000001.DAT': self.get_file_state(path_T1, True, 33),
                'C0000002.DAT': self.get_file_state(path_T2, False, 33)
            }
        }
        # only the position field in the parser state is initialized in get_file_state,
        # need to add the other state fields
        state[DataTypeKey.CTDPF_CKL_WFP_RECOVERED]['C0000001.DAT'][PARSER_STATE][StateKey.METADATA_SENT] = True
        state[DataTypeKey.CTDPF_CKL_WFP_RECOVERED]['C0000002.DAT'][PARSER_STATE][StateKey.RECORDS_READ] = 3
        state[DataTypeKey.CTDPF_CKL_WFP_RECOVERED]['C0000002.DAT'][PARSER_STATE][StateKey.METADATA_SENT] = True

        state[DataTypeKey.CTDPF_CKL_WFP_TELEMETERED]['C0000001.DAT'][PARSER_STATE][StateKey.METADATA_SENT] = True
        state[DataTypeKey.CTDPF_CKL_WFP_TELEMETERED]['C0000002.DAT'][PARSER_STATE][StateKey.RECORDS_READ] = 3
        state[DataTypeKey.CTDPF_CKL_WFP_TELEMETERED]['C0000002.DAT'][PARSER_STATE][StateKey.METADATA_SENT] = True

        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(TEL_PARTICLES, 'tel_partial_second.result.yml', count=3, timeout=10)

        # the starting state for recovered is the same as telemetered, so do the same compare
        # again for recovered
        self.assert_data(REC_PARTICLES,'rec_partial_second.result.yml', count=3, timeout=10)

    def test_ingest_order(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data_set_dir('first.DAT', TEL_DIR, "C0000001.DAT")
        self.create_sample_data_set_dir('second.DAT', TEL_DIR, "C0000002.DAT")
        self.assert_data(TEL_PARTICLES, 'tel_first.result.yml', count=4, timeout=10)
        self.assert_file_ingested("C0000001.DAT", DataTypeKey.CTDPF_CKL_WFP_TELEMETERED)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(TEL_PARTICLES, 'tel_second.result.yml', count=7, timeout=10)
        self.assert_file_ingested("C0000002.DAT",DataTypeKey.CTDPF_CKL_WFP_TELEMETERED)

        # now check the same thing for recovered (all the files are not created at the
        # start because there is no guarantee what order telemetered or recovered
        # particles will be found because they are on the same stream)
        self.create_sample_data_set_dir('first.DAT', REC_DIR, "C0000001.DAT")
        self.create_sample_data_set_dir('second.DAT', REC_DIR, "C0000002.DAT")
        
        self.assert_data(REC_PARTICLES, 'rec_first.result.yml', count=4, timeout=10)
        self.assert_file_ingested("C0000001.DAT", DataTypeKey.CTDPF_CKL_WFP_RECOVERED)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(REC_PARTICLES, 'rec_second.result.yml', count=7, timeout=10)
        self.assert_file_ingested("C0000002.DAT", DataTypeKey.CTDPF_CKL_WFP_RECOVERED)

    def test_sample_exception_empty_telem(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs.  In this case an empty file will produce a sample exception.
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester'][DataTypeKey.CTDPF_CKL_WFP_TELEMETERED]['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data_set_dir(filename, TEL_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename, DataTypeKey.CTDPF_CKL_WFP_TELEMETERED)

    def test_sample_exception_empty_recov(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs.  In this case an empty file will produce a sample exception.
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester'][DataTypeKey.CTDPF_CKL_WFP_RECOVERED]['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data_set_dir(filename, REC_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename, DataTypeKey.CTDPF_CKL_WFP_RECOVERED)

    def test_sample_exception_num_samples(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs.  In this case an empty file will produce a sample exception.
        """
        self.clear_async_data()
        self.create_sample_data_set_dir('bad_num_samples.DAT', TEL_DIR, 'C0000001.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('C0000001.DAT', DataTypeKey.CTDPF_CKL_WFP_TELEMETERED)
        
        # same test for recovered
        self.clear_async_data()
        self.create_sample_data_set_dir('bad_num_samples.DAT', REC_DIR, 'C0000001.DAT')
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested('C0000001.DAT', DataTypeKey.CTDPF_CKL_WFP_RECOVERED)

    def test_timestamp_only(self):
        """
        Test a case where the only thing present are the timestamps.
        assert_file_ingested with indicate a failure condition in the test.
        """
        self.clear_async_data()
        self.create_sample_data_set_dir('ts_only.DAT', TEL_DIR, 'C0000001.DAT')

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        self.assert_data(TEL_PARTICLES, 'tel_ts_only.result.yml', count=1, timeout=10)
        self.assert_file_ingested('C0000001.DAT', DataTypeKey.CTDPF_CKL_WFP_TELEMETERED)
        
        # same test for recovered
        self.create_sample_data_set_dir('ts_only.DAT', REC_DIR, 'C0000001.DAT')
        self.assert_data(REC_PARTICLES,'rec_ts_only.result.yml', count=1, timeout=10)
        self.assert_file_ingested('C0000001.DAT', DataTypeKey.CTDPF_CKL_WFP_RECOVERED)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def assert_all_queue_empty(self):
        """
        Assert the sample queue for all 4 data streams are empty
        """
        self.assert_sample_queue_size(DataParticleType.TELEMETERED_METADATA, 0)
        self.assert_sample_queue_size(DataParticleType.TELEMETERED_DATA, 0)
        self.assert_sample_queue_size(DataParticleType.RECOVERED_METADATA, 0)
        self.assert_sample_queue_size(DataParticleType.RECOVERED_DATA, 0)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data_set_dir('first.DAT', TEL_DIR, 'C0000001.DAT')
        self.assert_initialize()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_METADATA, 1)
            log.debug("First RESULT: %s", result)

            result_2 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA, 3)
            log.debug("Second RESULT: %s", result_2)

            result.extend(result_2)
            log.debug("Extended RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        # again for recovered
        self.create_sample_data_set_dir('first.DAT', REC_DIR, 'C0000001.DAT')

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA, 1)
            log.debug("First RESULT: %s", result)

            result_2 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 3)
            log.debug("Second RESULT: %s", result_2)

            result.extend(result_2)
            log.debug("Extended RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'first.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir('C0000038.DAT', TEL_DIR)
        self.assert_initialize()

        # get results for each of the data particle streams
        result1 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_METADATA,1,10)
        result2 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA,270,40)

        # again for recovered
        self.create_sample_data_set_dir('C0000038.DAT', REC_DIR)
        # get results for each of the data particle streams
        result1 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA,1,10)
        result2 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA,270,40)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first.DAT', TEL_DIR, "C0000001.DAT")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_METADATA)
            result2 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA, 3)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'tel_first.result.yml')
            self.assert_all_queue_empty()

            # stop sampling between telemetered
            self.create_sample_data_set_dir('second.DAT', TEL_DIR, "C0000002.DAT")
            # Now read the first three records (1 metadata, 2 data) of the second file then stop
            result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_METADATA)
            result2 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA, 2)
            result.extend(result2)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # Restart sampling and ensure we get the last 4 records of the file
            self.assert_start_sampling()
            result3 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA, 4)
            log.debug("got result 2 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'tel_second.result.yml')
            self.assert_all_queue_empty()
            
            # stop sampling between recovered
            self.create_sample_data_set_dir('second.DAT', REC_DIR, "C0000002.DAT")
            # Now read the first three records (1 metadata, 2 data) of the second file then stop
            result = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA)
            result2 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 2)
            result.extend(result2)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # Restart sampling and ensure we get the last 4 records of the file
            self.assert_start_sampling()
            result3 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 4)
            log.debug("got result 2 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'rec_second.result.yml')
            self.assert_all_queue_empty()
            
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first.DAT', TEL_DIR, "C0000001.DAT")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first file and verify the data
            result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_METADATA)
            result2 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA, 3)
            result.extend(result2)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'tel_first.result.yml')
            self.assert_all_queue_empty()

            # stop the dataset agent between telemetered
            self.create_sample_data_set_dir('second.DAT', TEL_DIR, "C0000002.DAT")
            # Now read the first three records (1 metadata, 2 data) of the second file then stop
            result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_METADATA)
            result2 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA, 2)
            result.extend(result2)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)
            
            # Slow down processing to 1 per second to give us time to stop again
            self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})

            # Restart sampling and ensure we get the last 4 records of the file
            self.assert_start_sampling()
            result3 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA, 4)
            log.debug("got result 2 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'tel_second.result.yml')
            self.assert_all_queue_empty()
            
            self.create_sample_data_set_dir('second.DAT', REC_DIR, "C0000002.DAT")
            # Now read the first three records (1 metadata, 2 data) of the second file then stop
            result = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA)
            result2 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 2)
            result.extend(result2)
            log.debug("got result 1 %s", result)
            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 4 records of the file
            self.assert_start_sampling()
            result3 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 4)
            log.debug("got result 2 %s", result3)
            result.extend(result3)
            self.assert_data_values(result, 'rec_second.result.yml')
            self.assert_all_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        # cause the error for telemetered
        self.create_sample_data_set_dir('bad_num_samples.DAT', TEL_DIR, 'C0000001.DAT')
        self.create_sample_data_set_dir('first.DAT', TEL_DIR, 'C0000002.DAT')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_METADATA)
        result1 = self.data_subscribers.get_samples(DataParticleType.TELEMETERED_DATA, 3)
        result.extend(result1)
        self.assert_data_values(result, 'tel_first.result.yml')
        self.assert_all_queue_empty();

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        # cause the same error for recovered
        self.event_subscribers.clear_events()
        self.create_sample_data_set_dir('bad_num_samples.DAT', REC_DIR, 'C0000001.DAT')
        self.create_sample_data_set_dir('first.DAT', REC_DIR, 'C0000002.DAT')

        result = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA)
        result1 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 3)
        result.extend(result1)
        self.assert_data_values(result, 'rec_first.result.yml')
        self.assert_all_queue_empty();

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
