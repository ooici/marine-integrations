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
from mi.dataset.parser.sio_mule_common import StateKey


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

    def test_start_stop_restart(self):
        """
        Test the ability to start, stop and restart the driver
        """

        recov_filename = 'C0000038.DAT'
        mule_filename = 'node58p1.dat'

        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        # Deploy an initial mule data file into the mule data file deployment directory
        self.create_sample_data_set_dir('SMALL_node58p1.dat', MULE_DATA_DIR, mule_filename)

        # Make sure we receive the correct mule particles
        self.assert_data(MULE_PARTICLES, 'SMALL_node58p1.yml', count=15, timeout=10)

        # Deploy an initial recovered data file into the recovered data file deployment directory
        self.create_sample_data_set_dir('LITTLE_C0000038.DAT', RECOV_DATA_DIR, recov_filename)

        # Make sure we receive the correct mule particles
        self.assert_data(RECOV_PARTICLES, 'LITTLE_C0000038.yml', count=7, timeout=10)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

        # Get the modification time and file statistics information for the mule data file in the
        # mule data file deployment directory
        driver_config = self._driver_config()['startup_config']

        mule_file_path = os.path.join(driver_config['harvester'][DataTypeKey.CTDPF_CKL_WFP_SIO_MULE]['directory'],
                                      driver_config['harvester'][DataTypeKey.CTDPF_CKL_WFP_SIO_MULE]['pattern'])
        mod_time = os.path.getmtime(mule_file_path)
        stat_info = os.stat(os.path.join(mule_file_path))

        # Clear any existing sampling
        self.clear_sample_data()

        # Clear the asynchronous callback results
        self.clear_async_data()

        # Update the mule data file with additional contents
        self.create_sample_data_set_dir('NORMAL_node58p1.dat', MULE_DATA_DIR, mule_filename)

        # Create the data for the Recovered parser.
        self.create_sample_data_set_dir('BIG_C0000038.dat', RECOV_DATA_DIR, recov_filename)

        # Calculate the Recovered file checksum and get the file mod time.
        recov_file_path = os.path.join(
            driver_config['harvester'][DataTypeKey.CTDPF_CKL_WFP]['directory'], recov_filename)
        recov_file_checksum = str(calculate_file_checksum(recov_file_path))
        recov_file_modtime = os.path.getmtime(recov_file_path)

        new_state = {
            DataTypeKey.CTDPF_CKL_WFP_SIO_MULE: {
                mule_filename: {
                    DriverStateKey.FILE_SIZE: stat_info.st_size,
                    DriverStateKey.FILE_CHECKSUM: '86584e1b27baa938c920495f7ed4d000',  # Bogus checksum (intentional)
                    DriverStateKey.FILE_MOD_DATE: mod_time,
                    DriverStateKey.PARSER_STATE:
                        {StateKey.IN_PROCESS_DATA: [],
                         StateKey.UNPROCESSED_DATA: [[2982, 3189], [4058, 4059], [4673, 5540],
                                                     [7423, 7424], [8730, 9828]],
                         StateKey.FILE_SIZE: 9866}
                }
            },
            DataTypeKey.CTDPF_CKL_WFP: {
                recov_filename: {
                    DriverStateKey.FILE_SIZE: 2989,
                    DriverStateKey.FILE_CHECKSUM: recov_file_checksum,
                    DriverStateKey.FILE_MOD_DATE: recov_file_modtime,
                    DriverStateKey.INGESTED: False,
                    DriverStateKey.PARSER_STATE: {
                        'position': 0,
                        'records_read': 0,
                        'metadata_sent': False
                    }
                }
            }
        }

        # Reset the state of the driver
        self.driver = self._get_driver_object(memento=new_state)
        self.create_sample_data_set_dir('NORMAL_node58p1.dat', MULE_DATA_DIR, mule_filename)
        self.create_sample_data_set_dir('BIG_C0000038.dat', RECOV_DATA_DIR, recov_filename)

        # Notify the driver to re-start sampling
        self.driver.start_sampling()

        # Check to make sure we received a correct telemetered data particles
        self.assert_data(MULE_PARTICLES, 'NORMAL_node58p1.yml', count=186, timeout=100)

        # Check to make sure we received a correct recovered data particles
        self.assert_data(RECOV_PARTICLES, 'BIG_C0000038.yml', count=364, timeout=100)

        # Stop the driver from taking processing new samples
        self.driver.stop_sampling()

    def test_midstate_start(self):
        """
        Test the ability to stop and restart the process
        """
        recov_filename = 'C0000038.DAT'
        mule_filename = 'node58p1.dat'

        log.debug('CAG MIDSTATE START set memento')
        memento = {
            DataTypeKey.CTDPF_CKL_WFP: {
                recov_filename: {
                    DriverStateKey.FILE_SIZE: 4012,
                    DriverStateKey.FILE_CHECKSUM: '5d305d5b326baf5e01efe387b99b2285',
                    DriverStateKey.FILE_MOD_DATE: '1405695548.0562634',
                    DriverStateKey.INGESTED: False,
                    DriverStateKey.PARSER_STATE: {
                        'position': 66,
                        'records_read': 6,
                        'metadata_sent': True
                    }
                }
            },
            DataTypeKey.CTDPF_CKL_WFP_SIO_MULE: {
                mule_filename: {
                    DriverStateKey.FILE_SIZE: 9866,
                    DriverStateKey.FILE_CHECKSUM: '86584e1b27baa938c920495f7ed4d000',  # Bogus checksum (intentional)
                    DriverStateKey.FILE_MOD_DATE: '1404933794.0',
                    DriverStateKey.PARSER_STATE: {
                        StateKey.IN_PROCESS_DATA: [[2982, 3189, 15, 14]],
                        StateKey.UNPROCESSED_DATA: [[2982, 3189],
                                                    [4058, 4059],
                                                    [4673, 5540],
                                                    [7423, 7424],
                                                    [8730, 9828]],
                        StateKey.FILE_SIZE: 9866
                    }
                }
            }
        }

        log.debug('CAG MIDSTATE START initial driver config is %s', self._driver_config()['startup_config'])
        log.debug('CAG MIDSTATE START build driver')
        driver = CtdpfCklWfpDataSetDriver(
            self._driver_config()['startup_config'],
            memento,
            self.data_callback,
            self.state_callback,
            self.event_callback,
            self.exception_callback)

        #************************** RECOVERED **************************
        self.clear_async_data()
        log.debug('CAG MIDSTATE START file load')
        self.create_sample_data_set_dir('BIG_C0000038.dat', RECOV_DATA_DIR, recov_filename)
        self.create_sample_data_set_dir('NORMAL_node58p1.dat', MULE_DATA_DIR, mule_filename)

        log.debug('CAG MIDSTATE START start recovered sampling')
        driver.start_sampling()

        log.debug('CAG MIDSTATE START check the results')
        self.assert_data(RECOV_PARTICLES, 'subBIG_C0000038.yml', count=357, timeout=200)

        self.assert_data(MULE_PARTICLES, 'Last_172_NORMAL_node58p1.yml', count=172, timeout=100)
#        self.assert_data(MULE_PARTICLES, 'NORMAL_node58p1.yml', count=186, timeout=100)

        log.debug('CAG MIDSTATE START stop sampling')
        self.driver.stop_sampling()

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

            result_a = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA, 1, 1200)
            result_ab = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 363, 1200)
            result_a.extend(result_ab)

            # Verify values
            self.assert_data_values(result_a, 'BIG_C0000038.yml')

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

            result_a = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA, 1, 1200)
            result_ab = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 363, 1200)
            result_a.extend(result_ab)

            # Verify values
            self.assert_data_values(result_a, 'BIG_C0000038.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_stop_restart(self):
        """
        Read in X records then stop. Reload the file so it appears to be "new"
        then start reading again confirm it reads from the correct spot.
        """
        # Clear any existing sampling
        self.clear_sample_data()

        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('single_node58p1.dat', MULE_DATA_DIR, 'node58p1.dat')
        self.create_sample_data_set_dir('BIG_C0000038.dat', RECOV_DATA_DIR, 'C0000038.DAT')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        try:
            # Read the first 99 records in the mule file then stop
            mule_result = self.get_samples(DataParticleType.METADATA, 1, 1200)
            mule_result2 = self.get_samples(DataParticleType.DATA, 98, 1200)
            mule_result.extend(mule_result2)
            log.debug("got mule result 1 %s", mule_result)

            # Verify mule values
            self.assert_data_values(mule_result, 'node58p1_First_98.yml')

            # Read the first 301 samples in the recovered file then stop
            recov_result = self.data_subscribers.get_samples(DataParticleType.RECOVERED_METADATA, 1, 1200)
            recov_result_2 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 300, 1200)
            recov_result.extend(recov_result_2)
            log.debug("got recovered result 1 %s", recov_result)

            # Verify recovered values
            self.assert_data_values(recov_result, 'C0000038_First_301.yml')

            self.assert_stop_sampling()

            # Restart sampling to get the last 4 records of the mule file
            # and the last 63 records of the recovered file
            self.assert_start_sampling()

            # Now read the last 4 records of the second file then stop
            mule_result2 = self.get_samples(DataParticleType.DATA, 4, 1200)
            recov_result2 = self.data_subscribers.get_samples(DataParticleType.RECOVERED_DATA, 63, 1200)

            # Verify mule values
            self.assert_data_values(mule_result2, 'node58p1_Last_4.yml')

            # Verify recovered values
            self.assert_data_values(recov_result2, 'C0000038_Last_63.yml')

            mule_result.extend(mule_result2)
            log.debug("got mule result 2 %s", mule_result)

            recov_result.extend(recov_result2)
            log.debug("got recovered result 2 %s", recov_result)

            self.assert_stop_sampling()

            # Check that all samples were retrieved
            self.assert_data_values(mule_result, 'node58p1_WC_TWO.yml')
            self.assert_data_values(recov_result, 'C0000038.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")
