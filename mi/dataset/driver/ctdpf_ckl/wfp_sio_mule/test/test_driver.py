"""
@package mi.dataset.driver.ctdpf_ckl.wfp_sio_mule.test.test_driver
@file marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp_sio_mule/driver.py
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
#from mi.dataset.parser.ctdpf_ckl_wfp import CtdpfCklWfpDataParticle, CtdpfCklWfpMetadataParticle

SIO_PARTICLES = (CtdpfCklWfpSioMuleDataParticle, CtdpfCklWfpSioMuleMetadataParticle)
#WFP_PARTICLES = (CtdpfCklWfpDataParticle, CtdpfCklWfpMetadataParticle)


DIR_WFP = '/tmp/dsatest1'
DIR_WFP_SIO_MULE = '/tmp/dsatest'


# Fill in driver details
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
                DataSetDriverConfigKeys.DIRECTORY: DIR_WFP,
                DataSetDriverConfigKeys.PATTERN: 'C*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.CTDPF_CKL_WFP_SIO_MULE:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_WFP_SIO_MULE,
                DataSetDriverConfigKeys.PATTERN: 'node58p1.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {}
    }
)


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

    def test_get_simple(self):
        """
        Test that we can get data from a small file.
        """

        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir('WC_ONE.DAT', DIR_WFP_SIO_MULE, 'node58p1.dat')
        self.assert_data(SIO_PARTICLES, 'WC_ONE.yml', count=96, timeout=10)

        self.driver.stop_sampling()

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """

        # create the file so that it is unreadable
        self.create_sample_data_set_dir('WC_ONE.DAT', DIR_WFP_SIO_MULE, 'node58p1.dat', mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(ValueError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

    def test_get_large(self):
        """
        Test that we can get data from a large file.
        """

        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data_set_dir('BIG_GIANT_HEAD.dat', DIR_WFP_SIO_MULE, 'node58p1.dat')
        self.assert_data(SIO_PARTICLES, count=42062, timeout=1800)

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
        Assert the sample queue for all 3 data streams is empty
        """
        self.assert_sample_queue_size(DataParticleType.METADATA, 0)
        self.assert_sample_queue_size(DataParticleType.DATA, 0)

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data_set_dir('WC_ONE.DAT', DIR_WFP_SIO_MULE, 'node58p1.dat')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # NOTE: If the processing is not slowed down here, the engineering samples are
        # returned in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get samples
        try:
            result = self.data_subscribers.get_samples(DataParticleType.METADATA, 1)
            log.debug("METADATA RESULT: %s", result)

            result_2 = self.data_subscribers.get_samples(DataParticleType.DATA, 95, 1200)
            log.debug("DATA RESULT: %s", result_2)

            result.extend(result_2)
            log.debug("COMBINED RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'WC_ONE.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent using a file with real data
        """
        self.create_sample_data_set_dir('BIG_GIANT_HEAD.dat', DIR_WFP_SIO_MULE, 'node58p1.dat')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.assert_start_sampling()

        # Verify we get samples
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
            self.assert_data_values(result, 'miniBGH.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_stop_restart(self):
        """
        Read in X records then stop. Reload the file so it appears to be "new"
        then start reading again confirm it reads from the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('WC_TWO.DAT', DIR_WFP_SIO_MULE, 'node58p1.dat')

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

            #Reload the file (make the system think it's a new file)
            self.create_sample_data_set_dir('WC_TWO.DAT', DIR_WFP_SIO_MULE, 'node58p1.dat')

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

    def test_two_streams(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent using a file with real data
        """
        self.create_sample_data_set_dir('BIG_GIANT_HEAD.dat', DIR_WFP_SIO_MULE, 'node58p1.dat')
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # NOTE: If the processing is not slowed down here, the engineering samples are
        # returned in the wrong order
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get samples
        try:

            result = self.data_subscribers.get_samples(DataParticleType.METADATA, 4, 1200)
            result_1b = self.data_subscribers.get_samples(DataParticleType.DATA, 285, 2400)
            result.extend(result_1b)

            # Verify values
            self.assert_data_values(result, 'jumbledBGH.yml')

        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")
