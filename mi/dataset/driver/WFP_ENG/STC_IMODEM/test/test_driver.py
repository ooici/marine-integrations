"""
@package mi.dataset.driver.WFP_ENG.STC_IMODEM.test.test_driver
@file marine-integrations/mi/dataset/driver/WFP_ENG/STC_IMODEM/driver.py
@author Emily Hahn
@brief Test cases for WFP_ENG__STC_IMODEM driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import os

from nose.plugins.attrib import attr
from mi.idk.config import Config

from mi.core.log import get_logger
log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter

from mi.dataset.driver.WFP_ENG.STC_IMODEM.driver import WFP_ENG__STC_IMODEM_DataSetDriver, DataTypeKey
from mi.dataset.parser.wfp_eng__stc_imodem_particles import DataParticleType
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStatusRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStartRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemEngineeringRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStatusTelemeteredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStartTelemeteredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemEngineeringTelemeteredDataParticle
from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'WFP_ENG', 'STC_IMODEM', 'resource')

RECOV_DIR = '/tmp/dsatest_rec'
TELEM_DIR = '/tmp/dsatest_tel'
RECOV_FILE_ONE = 'E00000001.DAT'
RECOV_FILE_TWO = 'E00000002.DAT'
TELEM_FILE_ONE = 'E00000001.DAT'
TELEM_FILE_TWO = 'E00000002.DAT'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.WFP_ENG.STC_IMODEM.driver',
    driver_class='WFP_ENG__STC_IMODEM_DataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=WFP_ENG__STC_IMODEM_DataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'wfp_eng__stc_imodem',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: RECOV_DIR,
                DataSetDriverConfigKeys.PATTERN: 'E*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: 'E*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED: {},
            DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED: {},
        }
    }
)

RECOV_PARTICLES = (WfpEngStcImodemStatusRecoveredDataParticle,
                   WfpEngStcImodemStartRecoveredDataParticle,
                   WfpEngStcImodemEngineeringRecoveredDataParticle)
TELEM_PARTICLES = (WfpEngStcImodemStatusTelemeteredDataParticle,
                   WfpEngStcImodemStartTelemeteredDataParticle,
                   WfpEngStcImodemEngineeringTelemeteredDataParticle)


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
        # Clear any existing sampling
        self.clear_sample_data()

        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        # Test simple telemetered data handling
        self.create_sample_data_set_dir('telemetered_one.dat', TELEM_DIR, TELEM_FILE_ONE)
        self.assert_data(TELEM_PARTICLES, 'telemetered.one.yml', count=2, timeout=10)

        # # Test simple recovered data handling
        self.create_sample_data_set_dir('recovered_one.dat', RECOV_DIR, RECOV_FILE_ONE)
        self.assert_data(RECOV_PARTICLES, 'recovered.one.yml', count=2, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # Clear any existing sampling
        self.clear_sample_data()

        path_1 = self.create_sample_data_set_dir('first.DAT', RECOV_DIR, RECOV_FILE_ONE)
        path_2 = self.create_sample_data_set_dir('second.DAT', RECOV_DIR, RECOV_FILE_TWO)
        path_3 = self.create_sample_data_set_dir('first.DAT', TELEM_DIR, TELEM_FILE_ONE)
        path_4 = self.create_sample_data_set_dir('second.DAT', TELEM_DIR, TELEM_FILE_TWO)

        key_rec = DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED
        key_tel = DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED

        # Set the state of the driver to the prior state altered to have ingested the first recovered
        # data file fully, not ingested the second recovered data file, and to have not returned the fifth
        # telemetered data particle in the original version of the telemetered data file
        state = {
            key_rec: {
                # The following recovered file state will be fully read
                RECOV_FILE_ONE: self.get_file_state(path_1, True, position=50),
                # The following recovered file state will start at byte 76
                RECOV_FILE_TWO: self.get_file_state(path_2, False, position=76)
            },
            key_tel: {
                TELEM_FILE_TWO: self.get_file_state(path_4, True, position=76),
                TELEM_FILE_ONE: self.get_file_state(path_3, False, position=0)
}
        }

        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(RECOV_PARTICLES, 'recovered_partial.result.yml', count=2, timeout=10)

        self.assert_data(TELEM_PARTICLES, 'telemetered_partial.result.yml', count=2, timeout=10)

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # Clear any existing sampling
        self.clear_sample_data()

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data_set_dir('first.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('second.DAT', RECOV_DIR, RECOV_FILE_TWO)

        self.assert_data(RECOV_PARTICLES, 'recovered_first.result.yml', count=2, timeout=10)
        self.assert_file_ingested(RECOV_FILE_ONE, DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED)
        self.assert_file_not_ingested(RECOV_FILE_TWO, DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(RECOV_PARTICLES, 'recovered_second.result.yml', count=5, timeout=10)
        self.assert_file_ingested(RECOV_FILE_ONE, DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED)
        self.assert_file_ingested(RECOV_FILE_TWO, DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.create_sample_data_set_dir('first.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.create_sample_data_set_dir('second.DAT', TELEM_DIR, TELEM_FILE_TWO)

        self.assert_data(TELEM_PARTICLES, 'telemetered_first.result.yml', count=2, timeout=10)
        self.assert_file_ingested(TELEM_FILE_ONE, DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED)
        self.assert_file_not_ingested(TELEM_FILE_TWO, DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED)

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data(TELEM_PARTICLES, 'telemetered_second.result.yml', count=5, timeout=10)
        self.assert_file_ingested(TELEM_FILE_ONE, DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED)
        self.assert_file_ingested(TELEM_FILE_TWO, DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED)

    def test_sample_exception(self):
        """
        test that a file is marked as parsed if it has a sample exception (which will happen with an empty file)
        """
        self.clear_async_data()

        filename = 'Efoo.dat'

        self.create_sample_data_set_dir(filename, RECOV_DIR, RECOV_FILE_ONE)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(RECOV_FILE_ONE, DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED)

        self.clear_async_data()

        self.create_sample_data_set_dir(filename, TELEM_DIR, TELEM_FILE_ONE)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(TELEM_FILE_ONE, DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    def setUp(self):
        super(QualificationTest, self).setUp()

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data_set_dir('second.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('second.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # NOTE: If the processing is not slowed down here, the engineering samples are
        # returned in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            result_eng = self.data_subscribers.get_samples(DataParticleType.ENGINEERING_RECOVERED, 4)
            log.debug("Recovered First RESULT: %s", result_eng)

            result = self.data_subscribers.get_samples(DataParticleType.START_TIME_RECOVERED, 1)
            log.debug("Recovered Second RESULT: %s", result)

            result.extend(result_eng)
            log.debug("Recovered Extended RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'recovered_second.result.yml')

            result_eng = self.data_subscribers.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 4)
            log.debug("Telemetered First RESULT: %s", result_eng)

            result = self.data_subscribers.get_samples(DataParticleType.START_TIME_TELEMETERED, 1)
            log.debug("Telemetered Second RESULT: %s", result)

            result.extend(result_eng)
            log.debug("Telemetered Extended RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'telemetered_second.result.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_cp02pmuo(self):
        """
        Test with an example file from cp02pmuo platform
        """
        self.create_sample_data_set_dir('CP02PMUO.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('CP02PMUO.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.assert_initialize()

        self.get_samples(DataParticleType.START_TIME_RECOVERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 316, 60)
        self.get_samples(DataParticleType.STATUS_RECOVERED, 7, 10)

        self.get_samples(DataParticleType.START_TIME_TELEMETERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 316, 60)
        self.get_samples(DataParticleType.STATUS_TELEMETERED, 7, 10)

    def test_cp02pmui(self):
        """
        Test with an example file from cp02pmui platform
        """
        self.create_sample_data_set_dir('CP02PMUI.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('CP02PMUI.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.assert_initialize()

        self.get_samples(DataParticleType.START_TIME_RECOVERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 267, 60)
        self.get_samples(DataParticleType.STATUS_RECOVERED, 7, 10)
        self.get_samples(DataParticleType.START_TIME_TELEMETERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 267, 60)
        self.get_samples(DataParticleType.STATUS_TELEMETERED, 7, 10)


    def test_cp02pmci(self):
        """
        Test with an example file from cp02pmci platform
        """
        self.create_sample_data_set_dir('CP02PMCI.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('CP02PMCI.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.assert_initialize()

        self.get_samples(DataParticleType.START_TIME_RECOVERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 53, 40)
        self.get_samples(DataParticleType.STATUS_RECOVERED, 7, 10)
        self.get_samples(DataParticleType.START_TIME_TELEMETERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 53, 40)
        self.get_samples(DataParticleType.STATUS_TELEMETERED, 7, 10)

    def test_ce09ospm(self):
        """
        Test with an example file from ce09ospm platform
        """
        self.create_sample_data_set_dir('CE09OSPM.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('CE09OSPM.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.assert_initialize()

        self.get_samples(DataParticleType.START_TIME_RECOVERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 14, 10)
        self.get_samples(DataParticleType.STATUS_RECOVERED, 1, 10)
        self.get_samples(DataParticleType.START_TIME_TELEMETERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 14, 10)
        self.get_samples(DataParticleType.STATUS_TELEMETERED, 1, 10)

    def test_cp04ospm(self):
        """
        Test with an example file from cp04ospm platform
        """
        self.create_sample_data_set_dir('CP04OSPM.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('CP04OSPM.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.assert_initialize()

        self.get_samples(DataParticleType.START_TIME_RECOVERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 14, 10)
        self.get_samples(DataParticleType.STATUS_RECOVERED, 1, 10)
        self.get_samples(DataParticleType.START_TIME_TELEMETERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 14, 10)
        self.get_samples(DataParticleType.STATUS_TELEMETERED, 1, 10)

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.create_sample_data_set_dir('E0000303.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('E0000427.DAT', RECOV_DIR, RECOV_FILE_TWO)
        self.create_sample_data_set_dir('E0000303.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.create_sample_data_set_dir('E0000427.DAT', TELEM_DIR, TELEM_FILE_TWO)
        self.assert_initialize()

        # get results for each of the data particle streams
        self.get_samples(DataParticleType.START_TIME_RECOVERED, 2, 10)
        self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 64, 40)
        self.get_samples(DataParticleType.STATUS_RECOVERED, 2, 10)
        self.get_samples(DataParticleType.START_TIME_TELEMETERED, 2, 10)
        self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 64, 40)
        self.get_samples(DataParticleType.STATUS_TELEMETERED, 2, 10)

    def test_status_in_middle(self):
        """
        This file has status particles in the middle and at the end
        """
        self.create_sample_data_set_dir('E0000039.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('E0000039.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.assert_initialize()

        # get results for each of the data particle streams
        self.get_samples(DataParticleType.START_TIME_RECOVERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 53, 40)
        self.get_samples(DataParticleType.STATUS_RECOVERED, 7, 10)
        self.get_samples(DataParticleType.START_TIME_TELEMETERED, 1, 10)
        self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 53, 40)
        self.get_samples(DataParticleType.STATUS_TELEMETERED, 7, 10)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.create_sample_data_set_dir('first.DAT', RECOV_DIR, RECOV_FILE_ONE)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            recov_result = self.get_samples(DataParticleType.START_TIME_RECOVERED)
            recov_result2 = self.get_samples(DataParticleType.ENGINEERING_RECOVERED)
            recov_result.extend(recov_result2)
            log.debug("RECOVERED RESULT: %s", recov_result)

            telem_result = self.get_samples(DataParticleType.START_TIME_TELEMETERED)
            telem_result2 = self.get_samples(DataParticleType.ENGINEERING_TELEMETERED)
            telem_result.extend(telem_result2)
            log.debug("TELEMETERED RESULT: %s", telem_result)

            # Verify values
            self.assert_data_values(recov_result, 'recovered_first.result.yml')
            self.assert_data_values(telem_result, 'telemetered_first.result.yml')
            self.assert_all_queue_empty()

            self.create_sample_data_set_dir('second.DAT', RECOV_DIR, RECOV_FILE_TWO)
            self.create_sample_data_set_dir('second.DAT', TELEM_DIR, TELEM_FILE_TWO)

            # Now read the first three records of the second file then stop
            recov_result = self.get_samples(DataParticleType.START_TIME_RECOVERED)
            recov_result2 = self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 2)
            recov_result.extend(recov_result2)
            log.debug("got recovered result 1 %s", recov_result)

            telem_result = self.get_samples(DataParticleType.START_TIME_TELEMETERED)
            telem_result2 = self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 2)
            telem_result.extend(telem_result2)
            log.debug("got telemetered result 1 %s", telem_result)

            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # Restart sampling and ensure we get the last 5 records of the file
            self.assert_start_sampling()

            recov_result3 = self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 2)
            log.debug("got recovered result 2 %s", recov_result3)
            recov_result.extend(recov_result3)

            telem_result3 = self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 2)
            log.debug("got telemetered result 2 %s", telem_result3)
            telem_result.extend(telem_result3)

            self.assert_data_values(recov_result, 'recovered_second.result.yml')
            self.assert_data_values(telem_result, 'telemetered_second.result.yml')

            self.assert_all_queue_empty()
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_shutdown_restart(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('first.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('first.DAT', TELEM_DIR, TELEM_FILE_ONE)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            recov_result = self.get_samples(DataParticleType.START_TIME_RECOVERED, 1)
            recov_result2 = self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 1)
            recov_result.extend(recov_result2)
            log.debug("Recovered RESULT: %s", recov_result)

            telem_result = self.get_samples(DataParticleType.START_TIME_TELEMETERED, 1)
            telem_result2 = self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 1)
            telem_result.extend(telem_result2)
            log.debug("Telemetered RESULT: %s", telem_result)

            # Verify values
            self.assert_data_values(recov_result, 'recovered_first.result.yml')
            self.assert_data_values(telem_result, 'telemetered_first.result.yml')

            self.assert_all_queue_empty()

            self.create_sample_data_set_dir('second.DAT', RECOV_DIR, RECOV_FILE_TWO)
            self.create_sample_data_set_dir('second.DAT', TELEM_DIR, TELEM_FILE_TWO)

            # Now read the first three records of the second file then stop
            recov_result = self.get_samples(DataParticleType.START_TIME_RECOVERED, 1)
            recov_result2 = self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 2)
            recov_result.extend(recov_result2)
            log.debug("got recovered result 1 %s", recov_result)

            telem_result = self.get_samples(DataParticleType.START_TIME_TELEMETERED, 1)
            telem_result2 = self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 2)
            telem_result.extend(telem_result2)
            log.debug("got telemetered result 1 %s", telem_result)

            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)
            # Restart sampling and ensure we get the last 2 records of the file
            self.assert_start_sampling()

            recov_result3 = self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 2, 200)
            log.debug("got recovered result 2 %s", recov_result3)
            recov_result.extend(recov_result3)
            self.assert_data_values(recov_result, 'recovered_second.result.yml')

            telem_result3 = self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 2, 200)
            log.debug("got telemetered result 2 %s", telem_result3)
            telem_result.extend(telem_result3)
            self.assert_data_values(telem_result, 'telemetered_second.result.yml')

            self.assert_all_queue_empty()
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def assert_all_queue_empty(self):
        """
        Assert the sample queue for all 3 data streams is empty
        """
        self.assert_sample_queue_size(DataParticleType.START_TIME_RECOVERED, 0)
        self.assert_sample_queue_size(DataParticleType.ENGINEERING_RECOVERED, 0)
        self.assert_sample_queue_size(DataParticleType.STATUS_RECOVERED, 0)
        self.assert_sample_queue_size(DataParticleType.START_TIME_TELEMETERED, 0)
        self.assert_sample_queue_size(DataParticleType.ENGINEERING_TELEMETERED, 0)
        self.assert_sample_queue_size(DataParticleType.STATUS_TELEMETERED, 0)

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        self.create_sample_data_set_dir('bad.DAT', RECOV_DIR, RECOV_FILE_ONE)
        self.create_sample_data_set_dir('first.DAT', RECOV_DIR, RECOV_FILE_TWO)
        self.create_sample_data_set_dir('bad.DAT', TELEM_DIR, TELEM_FILE_ONE)
        self.create_sample_data_set_dir('first.DAT', TELEM_DIR, TELEM_FILE_TWO)

        self.assert_initialize()

        self.event_subscribers.clear_events()

        recov_result = self.get_samples(DataParticleType.START_TIME_RECOVERED)
        recov_result2 = self.get_samples(DataParticleType.ENGINEERING_RECOVERED, 1)
        recov_result.extend(recov_result2)
        self.assert_data_values(recov_result, 'recovered_first.result.yml')

        telem_result = self.get_samples(DataParticleType.START_TIME_TELEMETERED)
        telem_result2 = self.get_samples(DataParticleType.ENGINEERING_TELEMETERED, 1)
        telem_result.extend(telem_result2)
        self.assert_data_values(telem_result, 'telemetered_first.result.yml')

        self.assert_all_queue_empty();

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

