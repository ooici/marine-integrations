"""
@package mi.dataset.driver.dosta_abcdjm.cspp.test.test_driver
@file marine-integrations/mi/dataset/driver/dosta_abcdjm/cspp/driver.py
@author Mark Worden
@brief Test cases for dosta_abcdjm_cspp driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.dosta_abcdjm.cspp.driver import DostaAbcdjmCsppDataSetDriver, DataTypeKey
from mi.dataset.parser.dosta_abcdjm_cspp import \
    DostaAbcdjmCsppInstrumentRecoveredDataParticle, DostaAbcdjmCsppInstrumentTelemeteredDataParticle, \
    DostaAbcdjmCsppMetadataRecoveredDataParticle, DostaAbcdjmCsppMetadataTelemeteredDataParticle

DIR_REC = '/tmp/dsatest_rec'
DIR_TEL = '/tmp/dsatest_tel'

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.dosta_abcdjm.cspp.driver',
    driver_class='DostaAbcdjmCsppDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=DostaAbcdjmCsppDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'dosta_abcdjm_cspp',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_REC,
                DataSetDriverConfigKeys.PATTERN: '*_PPB_OPT.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_TEL,
                DataSetDriverConfigKeys.PATTERN: '*_PPD_OPT.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED: {},
            DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED: {},
        }
    }
)

REC_PARTICLES = (DostaAbcdjmCsppMetadataRecoveredDataParticle,
                 DostaAbcdjmCsppInstrumentRecoveredDataParticle)
TEL_PARTICLES = (DostaAbcdjmCsppMetadataTelemeteredDataParticle,
                 DostaAbcdjmCsppInstrumentTelemeteredDataParticle)


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
        """

        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        # Test simple telemetered data handling
        self.create_sample_data_set_dir('11079894_PPD_OPT.txt', DIR_TEL)
        self.assert_data(TEL_PARTICLES, 'test_get_telemetered.yml', count=5, timeout=10)

        # # Test simple recovered data handling
        self.create_sample_data_set_dir('11079894_PPB_OPT.txt', DIR_REC)
        self.assert_data(REC_PARTICLES, 'test_get_recovered.yml', count=5, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """

#         # Clear any existing sampling
#         self.clear_sample_data()
#
#         path_1 = self.create_sample_data_set_dir('11079894_PPB_OPT.txt', DIR_REC)
#         path_2 = self.create_sample_data_set_dir('11079419_PPB_OPT.txt', DIR_REC)
#         path_3 = self.create_sample_data_set_dir('11079894_PPD_OPT.txt', DIR_TEL)
#         path_4 = self.create_sample_data_set_dir('11079419_PPD_OPT.txt', DIR_TEL)
#
#         key_rec = DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED
#         key_tel = DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED
#
#         # Set the state of the driver to the prior state altered to have ingested the first recovered
#         # data file fully, not ingested the second recovered data file, and to have not returned the fifth
#         # telemetered data particle in the original version of the telemetered data file
#         state = {
#             key_rec: {
#                 # The following recovered file state will be fully read
#                 RECOV_FILE_ONE: self.get_file_state(path_1, True, position=50),
#                 # The following recovered file state will start at byte 76
#                 RECOV_FILE_TWO: self.get_file_state(path_2, False, position=76)
#             },
#             key_tel: {
#                 TELEM_FILE_TWO: self.get_file_state(path_4, True, position=76),
#                 TELEM_FILE_ONE: self.get_file_state(path_3, False, position=0)
# }
#         }
#
#         self.driver = self._get_driver_object(memento=state)
#
#         # create some data to parse
#         self.clear_async_data()
#
#         self.driver.start_sampling()
#
#         # verify data is produced
#         self.assert_data(RECOV_PARTICLES, 'recovered_partial.result.yml', count=2, timeout=10)
#
#         self.assert_data(TELEM_PARTICLES, 'telemetered_partial.result.yml', count=2, timeout=10)


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

