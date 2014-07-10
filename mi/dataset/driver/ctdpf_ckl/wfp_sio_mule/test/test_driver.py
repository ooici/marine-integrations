"""
@package mi.dataset.driver.ctdpf_ckl.wfp_sio_mule.test.test_driver
@file marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp_sio_mule/test_driver.py
@author cgoodrich
@brief Test cases for ctdpf_ckl_wfp_sio_mule driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr
from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
import os
import hashlib

from mi.core.log import get_logger
log = get_logger()
from mi.idk.exceptions import SampleTimeout
from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DriverParameter
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.ctdpf_ckl.wfp_sio_mule.driver import CtdpfCklWfpDataSetDriver, DataTypeKey
from mi.dataset.parser.ctdpf_ckl_wfp_sio_mule import CtdpfCklWfpSioMuleDataParticle
from mi.dataset.parser.ctdpf_ckl_wfp_sio_mule import CtdpfCklWfpSioMuleMetadataParticle, DataParticleType
from mi.dataset.parser.ctdpf_ckl_wfp_particles import CtdpfCklWfpDataParticle, CtdpfCklWfpMetadataParticle
from mi.dataset.dataset_driver import DriverStateKey


MULE_PARTICLES = (CtdpfCklWfpSioMuleDataParticle, CtdpfCklWfpSioMuleMetadataParticle)
RECOV_PARTICLES = (CtdpfCklWfpDataParticle, CtdpfCklWfpMetadataParticle)


RECOV_DATA_DIR = '/tmp/recov_dsatest'
MULE_DATA_DIR = '/tmp/mule_dsatest'


# Driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.ctdpf_ckl.wfp_sio_mule.driver',
    driver_class='CtdpfCklWfpDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=CtdpfCklWfpDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'ctdpf_ckl_wfp_sio_mule',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.CTDPF_CKL_WFP:
            {
                DataSetDriverConfigKeys.DIRECTORY: RECOV_DATA_DIR,
                DataSetDriverConfigKeys.PATTERN: 'C*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.CTDPF_CKL_WFP_SIO_MULE:
            {
                DataSetDriverConfigKeys.DIRECTORY: MULE_DATA_DIR,
                DataSetDriverConfigKeys.PATTERN: 'node58p1.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.CTDPF_CKL_WFP: {},
            DataTypeKey.CTDPF_CKL_WFP_SIO_MULE: {}
        }
    }
)

def calculate_file_checksum(filename):
    with open(filename, 'rb') as file_handle:
        checksum = hashlib.md5(file_handle.read()).hexdigest()
    file_handle.close()
    return checksum

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):

    def test_get_simple(self):
        """
        Test that we can get data from small data files.
        """
        self.driver.start_sampling()
        self.clear_async_data()

        # Test for mule data
        self.create_sample_data_set_dir('WC_ONE.DAT', MULE_DATA_DIR, 'node58p1.dat')
        self.assert_data(MULE_PARTICLES, 'WC_ONE.yml', count=96, timeout=10)

        # Test for recovered data
        self.clear_async_data()
        self.create_sample_data_set_dir('TEST_TWO.DAT', RECOV_DATA_DIR, 'C0000034.DAT')
        self.assert_data(RECOV_PARTICLES, 'TEST_TWO.yml', count=96, timeout=10)

        self.driver.stop_sampling()

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        # Create the mule file so that it is unreadable
        self.create_sample_data_set_dir('WC_ONE.DAT', MULE_DATA_DIR, 'node58p1.dat', mode=000)

        self.assert_exception(IOError)
        self.clear_async_data()

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

        # Create the recovered file so that it is unreadable
        self.create_sample_data_set_dir('TEST_TWO.DAT', RECOV_DATA_DIR, 'C0000034.DAT', mode=000)

        # Start sampling and watch for an exception

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_get_large(self):
        """
        Test that we can get data from a large file.
        """
        self.driver.start_sampling()

        # Test a large mule file
        self.clear_async_data()
        self.create_sample_data_set_dir('MINI_node58p1.dat', MULE_DATA_DIR, 'node58p1.dat')
        self.assert_data(MULE_PARTICLES, 'MINI_node58p1.yml', count=186, timeout=10)

        # Test a large recovered file
        self.clear_async_data()
        self.create_sample_data_set_dir('TEST_ONE.DAT', RECOV_DATA_DIR, 'C0000034.DAT')
        self.assert_data(RECOV_PARTICLES, 'TEST_ONE.yml', count=279, timeout=10)

        self.driver.stop_sampling()

#*************************************************************************************
    def test_stop_resume(self):
        """
        Test the capability to stop and restart the process
        """
        self.create_sample_data_set_dir('SMALL_node58p1.dat', MULE_DATA_DIR, 'node58p1.dat')

        driver_config = self._driver_config()['startup_config']

        ctdpf_ckl_wfp_sio_mule_config =\
            driver_config[DataSetDriverConfigKeys.HARVESTER][DataTypeKey.CTDPF_CKL_WFP_SIO_MULE]

        fullfile = os.path.join(
            driver_config['harvester'][DataTypeKey.CTDPF_CKL_WFP_SIO_MULE]['directory'],
            driver_config['harvester'][DataTypeKey.CTDPF_CKL_WFP]['directory'])

        mod_time = os.path.getmtime(fullfile)

        # Create and store the new driver state
        memento = {
            DataTypeKey.CTDPF_CKL_WFP_SIO_MULE: {
                'node58p1.dat': {
                    DriverStateKey.FILE_SIZE: 9866,
                    DriverStateKey.FILE_CHECKSUM: '86584e1b27baa938c920495f7ed4d388',
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE:
                        {'in_process_data': [[4673, 5540, 75, 0], [8730, 9828, 96, 0]],
                         'unprocessed_data': [[4058, 4059], [4673, 5540], [7423, 7424], [8730, 9828]]}
                },
            },
            DataTypeKey.CTDPF_CKL_WFP: {}
        }

        driver = self._get_driver_object()

        # Create some data to parse
        self.clear_async_data()
        self.create_sample_data_set_dir('MINI_node58p1.dat', MULE_DATA_DIR, 'node58p1.dat')

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(MULE_PARTICLES, 'MINI_3rd_node58p1.yml', count=10, timeout=10)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def assert_all_queue_empty(self):
        """
        Assert that the sample queues for all data streams are empty
        """
        self.assert_sample_queue_size(DataParticleType.METADATA, 0)
        self.assert_sample_queue_size(DataParticleType.DATA, 0)
        self.assert_sample_queue_size(DataParticleType.RECOVERED_METADATA, 0)
        self.assert_sample_queue_size(DataParticleType.RECOVERED_DATA, 0)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """

        # Create telemetered data
        self.create_sample_data_set_dir('WC_ONE.DAT', MULE_DATA_DIR, 'node58p1.dat')

        # Create recovered data
        self.create_sample_data_set_dir('TEST_TWO.DAT', RECOV_DATA_DIR, 'C0000034.DAT')

        self.assert_initialize()

        # Verify we get telemetered samples
        try:
            result1 = self.data_subscribers.get_samples(DataParticleType.METADATA, 1)
            log.debug("METADATA RESULT: %s", result1)

            result_2 = self.data_subscribers.get_samples(DataParticleType.DATA, 95, 1200)
            log.debug("DATA RESULT: %s", result_2)

            result1.extend(result_2)
            log.debug("COMBINED RESULT: %s", result1)

            # Verify values
            self.assert_data_values(result1, 'WC_ONE.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        # Verify we get recovered samples
        try:
            result3 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA, 1)
            log.debug("METADATA RESULT: %s", result3)

            result_4 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 95, 1200)
            log.debug("DATA RESULT: %s", result_4)

            result3.extend(result_4)
            log.debug("COMBINED RESULT: %s", result3)

            # Verify values
            self.assert_data_values(result3, 'TEST_TWO.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent using a file with real data
        """
        self.create_sample_data_set_dir('BIG_DATA_FILE.dat', MULE_DATA_DIR, 'node58p1.dat')
        self.create_sample_data_set_dir('BIG_C0000038.dat', RECOV_DATA_DIR, 'C0000038.DAT')

        self.assert_initialize()

        # Verify we get telemetered samples
        try:

            result = self.data_subscribers.get_samples(DataParticleType.METADATA, 1, 1200)
            result_1b = self.data_subscribers.get_samples(DataParticleType.DATA, 14, 1200)
            result.extend(result_1b)

            result_2a = self.data_subscribers.get_samples(DataParticleType.METADATA, 1, 1200)
            result_2b = self.data_subscribers.get_samples(DataParticleType.DATA, 74, 1200)
            result.extend(result_2a)
            result.extend(result_2b)

            result_3a = self.data_subscribers.get_samples(DataParticleType.METADATA, 1, 1200)
            result_3b = self.data_subscribers.get_samples(DataParticleType.DATA, 95, 1200)
            result.extend(result_3a)
            result.extend(result_3b)

            result_4a = self.data_subscribers.get_samples(DataParticleType.METADATA, 1, 1200)
            result_4b = self.data_subscribers.get_samples(DataParticleType.DATA, 102, 1200)
            result.extend(result_4a)
            result.extend(result_4b)

            # Verify values
            self.assert_data_values(result, 'BIG_DATA_FILE.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        # Verify we get recovered samples
        try:

            resultA = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA, 1, 1200)
            result_Ab = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 363, 1200)
            resultA.extend(result_Ab)

            # Verify values
            self.assert_data_values(resultA, 'BIG_C0000038.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_two_streams(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent using a file with real data
        """
        self.create_sample_data_set_dir('BIG_DATA_FILE.dat', MULE_DATA_DIR, 'node58p1.dat')
        self.create_sample_data_set_dir('BIG_C0000038.dat', RECOV_DATA_DIR, 'C0000038.DAT')

        self.assert_initialize()

        # Verify we get telemetered samples
        try:

            result = self.data_subscribers.get_samples(DataParticleType.METADATA, 4, 1200)
            result_1b = self.data_subscribers.get_samples(DataParticleType.DATA, 285, 1200)
            result.extend(result_1b)

            # Verify values
            self.assert_data_values(result, 'jumbled_BIG_DATA_FILE.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        # Verify we get recovered samples
        try:

            resultA = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA, 1, 1200)
            result_Ab = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 363, 1200)
            resultA.extend(result_Ab)

            # Verify values
            self.assert_data_values(resultA, 'BIG_C0000038.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_stop_restart(self):
        """
        Read in X records then stop. Reload the file so it appears to be "new"
        then start reading again confirm it reads from the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('WC_TWO.DAT', MULE_DATA_DIR, 'node58p1.dat')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first 98 records in the file then stop
            result = self.get_samples(DataParticleType.METADATA, 1, 1200)
            result2 = self.get_samples(DataParticleType.DATA, 98, 1200)
            result.extend(result2)
            log.debug("got result 1 %s", result)

            #Reload the file (making the system "think" it's a new file)
            self.create_sample_data_set_dir('WC_TWO.DAT', MULE_DATA_DIR, 'node58p1.dat')

            # Now read the last 4 records of the second file then stop
            result2 = self.get_samples(DataParticleType.DATA, 4, 1200)
            result.extend(result2)
            log.debug("got result 2 %s", result)
            self.assert_stop_sampling()
            self.assert_all_queue_empty()

            # Check that the values match
            self.assert_data_values(result, 'WC_TWO.yml')

            self.assert_all_queue_empty()

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")
