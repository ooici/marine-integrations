"""
@package mi.dataset.driver.cspp_eng.cspp.test.test_driver
@file marine-integrations/mi/dataset/driver/cspp_eng/cspp/driver.py
@author Jeff Roy
@brief Test cases for cspp_eng_cspp driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import hashlib
import os

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import \
    DataSourceConfigKey, \
    DataSetDriverConfigKeys, \
    DriverParameter
from mi.dataset.driver.cspp_eng.cspp.driver import CsppEngCsppDataSetDriver

from mi.dataset.parser.cspp_base import StateKey

from mi.dataset.parser.dbg_pdbg_cspp import \
    DbgPdbgRecoveredGpsParticle, \
    DbgPdbgTelemeteredGpsParticle, \
    DbgPdbgRecoveredBatteryParticle, \
    DbgPdbgTelemeteredBatteryParticle, \
    DbgPdbgMetadataTelemeteredDataParticle, \
    DbgPdbgMetadataRecoveredDataParticle, \
    DbgPdbgDataTypeKey, \
    DbgPdbgDataParticleType

from mi.dataset.parser.wc_hmr_cspp import \
    WcHmrEngRecoveredDataParticle, \
    WcHmrEngTelemeteredDataParticle, \
    WcHmrMetadataRecoveredDataParticle, \
    WcHmrMetadataTelemeteredDataParticle, \
    WcHmrDataTypeKey, \
    WcHmrDataParticleType

from mi.dataset.parser.wc_sbe_cspp import \
    WcSbeEngRecoveredDataParticle, \
    WcSbeEngTelemeteredDataParticle, \
    WcSbeMetadataRecoveredDataParticle, \
    WcSbeMetadataTelemeteredDataParticle, \
    WcSbeDataTypeKey, \
    WcSbeDataParticleType

from mi.dataset.parser.wc_wm_cspp import \
    WcWmEngRecoveredDataParticle, \
    WcWmEngTelemeteredDataParticle, \
    WcWmMetadataRecoveredDataParticle, \
    WcWmMetadataTelemeteredDataParticle, \
    WcWmDataTypeKey, \
    WcWmDataParticleType

DIR_CSPP_TELEMETERED = '/tmp/cspp/telem/test'
DIR_CSPP_RECOVERED = '/tmp/cspp/recov/test'

DBG_PDBG_PATTERN = '*_DBG_PDBG.txt'
WC_HMR_PATTERN = '*_WC_HMR.txt'
WC_SBE_PATTERN = '*_WC_SBE.txt'
WC_WM_PATTERN = '*_WC_WM.txt'


# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.cspp_eng.cspp.driver',
    driver_class='CsppEngCsppDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=CsppEngCsppDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'cspp_eng_cspp',
        DataSourceConfigKey.HARVESTER:
        {
            DbgPdbgDataTypeKey.DBG_PDBG_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: DBG_PDBG_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            DbgPdbgDataTypeKey.DBG_PDBG_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: DBG_PDBG_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcHmrDataTypeKey.WC_HMR_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: WC_HMR_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcHmrDataTypeKey.WC_HMR_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: WC_HMR_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcSbeDataTypeKey.WC_SBE_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: WC_SBE_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcSbeDataTypeKey.WC_SBE_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: WC_SBE_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcWmDataTypeKey.WC_WM_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: WC_WM_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcWmDataTypeKey.WC_WM_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: WC_WM_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            }
        },
        DataSourceConfigKey.PARSER: {
            DbgPdbgDataTypeKey.DBG_PDBG_CSPP_TELEMETERED: {},
            DbgPdbgDataTypeKey.DBG_PDBG_CSPP_RECOVERED: {},
            WcHmrDataTypeKey.WC_HMR_CSPP_TELEMETERED: {},
            WcHmrDataTypeKey.WC_HMR_CSPP_RECOVERED: {},
            WcSbeDataTypeKey.WC_SBE_CSPP_TELEMETERED: {},
            WcSbeDataTypeKey.WC_SBE_CSPP_RECOVERED: {},
            WcWmDataTypeKey.WC_WM_CSPP_TELEMETERED: {},
            WcWmDataTypeKey.WC_WM_CSPP_RECOVERED: {}
        }
    }
)

# Particle tuples used in integration tests for each parser
DBG_PDBG_TEL_PARTICLES = (DbgPdbgTelemeteredGpsParticle,
                          DbgPdbgTelemeteredBatteryParticle,
                          DbgPdbgMetadataTelemeteredDataParticle)

WC_HMR_TEL_PARTICLES = (WcHmrEngTelemeteredDataParticle,
                        WcHmrMetadataTelemeteredDataParticle)

WC_SBE_TEL_PARTICLES = (WcSbeEngTelemeteredDataParticle,
                        WcSbeMetadataTelemeteredDataParticle)

WC_WM_TEL_PARTICLES = (WcWmEngTelemeteredDataParticle,
                       WcWmMetadataTelemeteredDataParticle)

DBG_PDBG_REC_PARTICLES = (DbgPdbgRecoveredGpsParticle,
                          DbgPdbgRecoveredBatteryParticle,
                          DbgPdbgMetadataRecoveredDataParticle)

WC_HMR_REC_PARTICLES = (WcHmrEngRecoveredDataParticle,
                        WcHmrMetadataRecoveredDataParticle)

WC_SBE_REC_PARTICLES = (WcSbeEngRecoveredDataParticle,
                        WcSbeMetadataRecoveredDataParticle)

WC_WM_REC_PARTICLES = (WcWmEngRecoveredDataParticle,
                       WcWmMetadataRecoveredDataParticle)

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
 
    def get_file_state(self, path, ingested=False, position=None, metadata_extracted=False):
        """
        Create a state object for a file.
        """
        mod_time = os.path.getmtime(path)
        file_size = os.path.getsize(path)
        with open(path) as filehandle:
            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()

        parser_state = {
            StateKey.POSITION: position,
            StateKey.METADATA_EXTRACTED: metadata_extracted
        }

        return {
            'ingested': ingested,
            'file_mod_date': mod_time,
            'file_checksum': md5_checksum,
            'file_size': file_size,
            'parser_state': parser_state
        }

    def test_get(self):
        """
        Test that we can get data from files.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        # test that everything works for the dbg_pdbg recovered harvester
        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_RECOVERED)

        log.debug('### DBG_PDBG Sample file created in dir = %s ', DIR_CSPP_RECOVERED)

        # check the metadata particle and the first 7 instrument particles
        self.assert_data(DBG_PDBG_REC_PARTICLES,
                         '01554008_DBG_PDBG_recov.yml',
                         count=8, timeout=10)

        # test that everything works for the dbg_pdbg telemetered harvester
        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_TELEMETERED)

        log.debug('### DBG_PDBG Sample file created in dir = %s ', DIR_CSPP_TELEMETERED)

        # check the metadata particle and the first 7 instrument particles
        self.assert_data(DBG_PDBG_TEL_PARTICLES,
                         '01554008_DBG_PDBG_telem.yml',
                         count=8, timeout=10)

        #--------------------------------------------------------------------------------
        # test that everything works for the wc_hmr recovered harvester
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_RECOVERED)

        log.debug('### WC_HMR Sample file created in dir = %s ', DIR_CSPP_RECOVERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(WC_HMR_REC_PARTICLES,
                         '11079364_WC_HMR_recov.yml',
                         count=20, timeout=10)

        # test that everything works for the wc_hmr telemetered harvester
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_TELEMETERED)

        log.debug('### WC_HMR Sample file created in dir = %s ', DIR_CSPP_TELEMETERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(WC_HMR_TEL_PARTICLES,
                         '11079364_WC_HMR_telem.yml',
                         count=20, timeout=10)

        #--------------------------------------------------------------------------------
        # test that everything works for the wc_sbe recovered harvester
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_RECOVERED)

        log.debug('### WC_SBE Sample file created in dir = %s ', DIR_CSPP_RECOVERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(WC_SBE_REC_PARTICLES,
                         '11079364_WC_SBE_recov.yml',
                         count=20, timeout=10)

        # test that everything works for the wc_sbe telemetered harvester
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_TELEMETERED)

        log.debug('### WC_SBE Sample file created in dir = %s ', DIR_CSPP_TELEMETERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(WC_SBE_TEL_PARTICLES,
                         '11079364_WC_SBE_telem.yml',
                         count=20, timeout=10)

        #--------------------------------------------------------------------------------
        # test that everything works for the wc_wm recovered harvester
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_RECOVERED)

        log.debug('### WC_WM Sample file created in dir = %s ', DIR_CSPP_RECOVERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(WC_WM_REC_PARTICLES,
                         '11079364_WC_WM_recov.yml',
                         count=20, timeout=10)

        # test that everything works for the wc_wm telemetered harvester
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_TELEMETERED)

        log.debug('### WC_WM Sample file created in dir = %s ', DIR_CSPP_TELEMETERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(WC_WM_TEL_PARTICLES,
                         '11079364_WC_WM_telem.yml',
                         count=20, timeout=10)

    def test_mid_state_start(self):
        """
        Test the ability to start the driver with a saved state
        """
        log.info("================ START INTEG TEST MID STATE START =====================")

        # Clear any existing sampling
        self.clear_sample_data()

        # create some data to parse
        dbg_pdbg_recov_file = '01554008_DBG_PDBG.txt'
        dbg_pdbg_telem_file = '01554008_DBG_PDBG.txt'
        wc_hmr_recov_file = '11079364_WC_HMR.txt'
        wc_hmr_telem_file = '11079364_WC_HMR.txt'
        wc_sbe_recov_file = '11079364_WC_SBE.txt'
        wc_sbe_telem_file = '11079364_WC_SBE.txt'
        wc_wm_recov_file = '11079364_WC_WM.txt'
        wc_wm_telem_file = '11079364_WC_WM.txt'

        dbg_pdbg_recov_path = self.create_sample_data_set_dir(dbg_pdbg_recov_file, DIR_CSPP_RECOVERED)
        dbg_pdbg_telem_path = self.create_sample_data_set_dir(dbg_pdbg_telem_file, DIR_CSPP_TELEMETERED)
        wc_hmr_recov_path = self.create_sample_data_set_dir(wc_hmr_recov_file, DIR_CSPP_RECOVERED)
        wc_hmr_telem_path = self.create_sample_data_set_dir(wc_hmr_telem_file, DIR_CSPP_TELEMETERED)
        wc_sbe_recov_path = self.create_sample_data_set_dir(wc_sbe_recov_file, DIR_CSPP_RECOVERED)
        wc_sbe_telem_path = self.create_sample_data_set_dir(wc_sbe_telem_file, DIR_CSPP_TELEMETERED)
        wc_wm_recov_path = self.create_sample_data_set_dir(wc_wm_recov_file, DIR_CSPP_RECOVERED)
        wc_wm_telem_path = self.create_sample_data_set_dir(wc_wm_telem_file, DIR_CSPP_TELEMETERED)

        state = {
            DbgPdbgDataTypeKey.DBG_PDBG_CSPP_RECOVERED: {
                dbg_pdbg_recov_file: self.get_file_state(dbg_pdbg_recov_path,
                                                         ingested=False,
                                                         position=5032,          # end of 3rd data record
                                                         metadata_extracted=True)
            },
            DbgPdbgDataTypeKey.DBG_PDBG_CSPP_TELEMETERED: {
                dbg_pdbg_telem_file: self.get_file_state(dbg_pdbg_telem_path,
                                                         ingested=False,
                                                         position=1239,          # end of first data record
                                                         metadata_extracted=True)
            },

            WcHmrDataTypeKey.WC_HMR_CSPP_RECOVERED: {
                wc_hmr_recov_file: self.get_file_state(wc_hmr_recov_path,
                                                       ingested=False,
                                                       position=549,             # end of 7th data record
                                                       metadata_extracted=True)
            },
            WcHmrDataTypeKey.WC_HMR_CSPP_TELEMETERED: {
                wc_hmr_telem_file: self.get_file_state(wc_hmr_telem_path,
                                                       ingested=False,
                                                       position=666,             # end of 10th data record
                                                       metadata_extracted=True)
            },

            WcSbeDataTypeKey.WC_SBE_CSPP_RECOVERED: {
                wc_sbe_recov_file: self.get_file_state(wc_sbe_recov_path,
                                                       ingested=False,
                                                       position=618,             # end of 12th data record
                                                       metadata_extracted=True)
            },
            WcSbeDataTypeKey.WC_SBE_CSPP_TELEMETERED: {
                wc_sbe_telem_file: self.get_file_state(wc_sbe_telem_path,
                                                       ingested=False,
                                                       position=375,             # end of 4th data record
                                                       metadata_extracted=True)
            },

            WcWmDataTypeKey.WC_WM_CSPP_RECOVERED: {
                wc_wm_recov_file: self.get_file_state(wc_wm_recov_path,
                                                      ingested=False,
                                                      position=1445,             # end of 15th data record
                                                      metadata_extracted=True)
            },
            WcWmDataTypeKey.WC_WM_CSPP_TELEMETERED: {
                wc_wm_recov_file: self.get_file_state(wc_wm_telem_path,
                                                      ingested=False,
                                                      position=643,             # end of 4th data record
                                                      metadata_extracted=True)
            }
        }

        driver = self._get_driver_object(memento=state)

        self.clear_async_data()

        driver.start_sampling()

        # verify data produced is what we expect
        self.assert_data(DBG_PDBG_REC_PARTICLES, 'DBG_PDBG_recov_midstate.yml', count=4, timeout=10)
        self.assert_data(DBG_PDBG_TEL_PARTICLES, 'DBG_PDBG_telem_midstate.yml', count=6, timeout=10)
        self.assert_data(WC_HMR_REC_PARTICLES, 'WC_HMR_recov_midstate.yml', count=8, timeout=10)
        self.assert_data(WC_HMR_TEL_PARTICLES, 'WC_HMR_telem_midstate.yml', count=9, timeout=10)
        self.assert_data(WC_SBE_REC_PARTICLES, 'WC_SBE_recov_midstate.yml', count=7, timeout=10)
        self.assert_data(WC_SBE_TEL_PARTICLES, 'WC_SBE_telem_midstate.yml', count=6, timeout=10)
        self.assert_data(WC_WM_REC_PARTICLES, 'WC_WM_recov_midstate.yml', count=4, timeout=10)
        self.assert_data(WC_WM_TEL_PARTICLES, 'WC_WM_telem_midstate.yml', count=5, timeout=10)

        # self.assert_data(TEL_PARTICLES, 'test_telemetered_midstate_start.yml', count=2, timeout=10)

    def test_start_stop_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """

        log.info("================ START INTEG TEST START STOP RESUME =====================")

        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_TELEMETERED)

        self.clear_async_data()

        self.driver.start_sampling()

        # get some samples from each of the parsers
        self.assert_data(DBG_PDBG_REC_PARTICLES, 'DBG_PDBG_recov_start_stop1.yml', count=5, timeout=60)
        self.assert_data(DBG_PDBG_TEL_PARTICLES, 'DBG_PDBG_telem_start_stop1.yml', count=2, timeout=60)
        self.assert_data(WC_HMR_REC_PARTICLES, 'WC_HMR_recov_start_stop1.yml', count=6, timeout=60)
        self.assert_data(WC_HMR_TEL_PARTICLES, 'WC_HMR_telem_start_stop1.yml', count=11, timeout=60)
        self.assert_data(WC_SBE_REC_PARTICLES, 'WC_SBE_recov_start_stop1.yml', count=9, timeout=60)
        self.assert_data(WC_SBE_TEL_PARTICLES, 'WC_SBE_telem_start_stop1.yml', count=4, timeout=60)
        self.assert_data(WC_WM_REC_PARTICLES, 'WC_WM_recov_start_stop1.yml', count=3, timeout=60)
        self.assert_data(WC_WM_TEL_PARTICLES, 'WC_WM_telem_start_stop1.yml', count=8, timeout=60)

        self.driver.stop_sampling()

        self.driver.start_sampling()

        # get some more samples from each of the parsers picking up where we left off
        self.assert_data(DBG_PDBG_REC_PARTICLES, 'DBG_PDBG_recov_start_stop2.yml', count=3, timeout=60)
        self.assert_data(DBG_PDBG_TEL_PARTICLES, 'DBG_PDBG_telem_start_stop2.yml', count=6, timeout=60)
        self.assert_data(WC_HMR_REC_PARTICLES, 'WC_HMR_recov_start_stop2.yml', count=4, timeout=60)
        self.assert_data(WC_HMR_TEL_PARTICLES, 'WC_HMR_telem_start_stop2.yml', count=6, timeout=60)
        self.assert_data(WC_SBE_REC_PARTICLES, 'WC_SBE_recov_start_stop2.yml', count=7, timeout=60)
        self.assert_data(WC_SBE_TEL_PARTICLES, 'WC_SBE_telem_start_stop2.yml', count=7, timeout=60)
        self.assert_data(WC_WM_REC_PARTICLES, 'WC_WM_recov_start_stop2.yml', count=4, timeout=60)
        self.assert_data(WC_WM_TEL_PARTICLES, 'WC_WM_telem_start_stop2.yml', count=7, timeout=60)

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        log.info("================ START INTEG TEST SAMPLE EXCEPTION =====================")

        # Start sampling.
        self.clear_async_data()
        self.driver.start_sampling()

        self.create_sample_data_set_dir('01554008_BAD_DBG_PDBG.txt', DIR_CSPP_RECOVERED)
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.clear_async_data()

        self.create_sample_data_set_dir('01554008_BAD_DBG_PDBG.txt', DIR_CSPP_TELEMETERED)
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.clear_async_data()

        self.create_sample_data_set_dir('11079364_BAD_WC_HMR.txt', DIR_CSPP_RECOVERED)
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.clear_async_data()

        self.create_sample_data_set_dir('11079364_BAD_WC_HMR.txt', DIR_CSPP_TELEMETERED)
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.clear_async_data()

        self.create_sample_data_set_dir('11079364_BAD_WC_SBE.txt', DIR_CSPP_RECOVERED)
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.clear_async_data()

        self.create_sample_data_set_dir('11079364_BAD_WC_SBE.txt', DIR_CSPP_TELEMETERED)
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.clear_async_data()

        self.create_sample_data_set_dir('11079364_BAD_WC_WM.txt', DIR_CSPP_RECOVERED)
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.clear_async_data()

        self.create_sample_data_set_dir('11079364_BAD_WC_WM.txt', DIR_CSPP_TELEMETERED)
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.clear_async_data()


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
        published out the agent for each of teh 8 harvesters
        """
        log.info("=========== START QUAL TEST PUBLISH PATH =================")

        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_TELEMETERED)

        self.assert_initialize()

        #-------------------DBG PDBG RECOVERED------------------------
        # check the metadata particle and the 7 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_RECOVERED, 6, 10)
        result3 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.GPS_RECOVERED, 1, 10)

        result1.extend(result2)
        result1.extend(result3)

        self.assert_data_values(result1, '01554008_DBG_PDBG_recov.yml')

        #-------------------DBG PDBG TELEMETERED------------------------
        # check the metadata particle and the 7 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_TELEMETERED, 6, 10)
        result3 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.GPS_TELEMETERED, 1, 10)

        result1.extend(result2)
        result1.extend(result3)

        self.assert_data_values(result1, '01554008_DBG_PDBG_telem.yml')

        #-------------------WC HMR RECOVERED------------------------
        # check the metadata particle and the first 19 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_RECOVERED, 19, 20)

        result1.extend(result2)

        self.assert_data_values(result1, '11079364_WC_HMR_recov.yml')

        #-------------------WC HMR TELEMETERED------------------------
        # check the metadata particle and the first 19 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_TELEMETERED, 19, 20)

        result1.extend(result2)

        self.assert_data_values(result1, '11079364_WC_HMR_telem.yml')

        #-------------------WC SBE RECOVERED------------------------
        # check the metadata particle and the first 19 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_RECOVERED, 19, 20)

        result1.extend(result2)

        self.assert_data_values(result1, '11079364_WC_SBE_recov.yml')

        #-------------------WC SBE TELEMETERED------------------------
        # check the metadata particle and the first 19 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_TELEMETERED, 19, 20)

        result1.extend(result2)

        self.assert_data_values(result1, '11079364_WC_SBE_telem.yml')

        #-------------------WC WM RECOVERED------------------------
        # check the metadata particle and the first 19 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_RECOVERED, 19, 20)

        result1.extend(result2)

        self.assert_data_values(result1, '11079364_WC_WM_recov.yml')

        #-------------------WC WM TELEMETERED------------------------
        # check the metadata particle and the first 19 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_TELEMETERED, 19, 20)

        result1.extend(result2)

        self.assert_data_values(result1, '11079364_WC_WM_telem.yml')

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        log.info("=========== START QUAL TEST LARGE IMPORT =================")

        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_TELEMETERED)

        self.assert_initialize()

        #-------------------DBG PDBG RECOVERED------------------------
        # Note: dbg_pdbg files do not have many useful records in them
        self.data_subscribers.get_samples(DbgPdbgDataParticleType.METADATA_RECOVERED, 1, 10)
        self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_RECOVERED, 6, 10)
        self.data_subscribers.get_samples(DbgPdbgDataParticleType.GPS_RECOVERED, 1, 10)

        #-------------------DBG PDBG TELEMETERED------------------------
        # Note: dbg_pdbg files do not have many useful records in them
        self.data_subscribers.get_samples(DbgPdbgDataParticleType.METADATA_TELEMETERED, 1, 10)
        self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_TELEMETERED, 6, 10)
        self.data_subscribers.get_samples(DbgPdbgDataParticleType.GPS_TELEMETERED, 1, 10)

        #-------------------WC HMR RECOVERED------------------------
        self.data_subscribers.get_samples(WcHmrDataParticleType.METADATA_RECOVERED, 1, 10)
        self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_RECOVERED, 1000, 120)

        #-------------------WC HMR TELEMETERED------------------------
        self.data_subscribers.get_samples(WcHmrDataParticleType.METADATA_TELEMETERED, 1, 10)
        self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_TELEMETERED, 1000, 120)

        #-------------------WC SBE RECOVERED------------------------
        self.data_subscribers.get_samples(WcSbeDataParticleType.METADATA_RECOVERED, 1, 10)
        self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_RECOVERED, 1000, 120)

        #-------------------WC SBE TELEMETERED------------------------
        self.data_subscribers.get_samples(WcSbeDataParticleType.METADATA_TELEMETERED, 1, 10)
        self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_TELEMETERED, 1000, 120)

        #-------------------WC WM RECOVERED------------------------
        self.data_subscribers.get_samples(WcWmDataParticleType.METADATA_RECOVERED, 1, 10)
        self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_RECOVERED, 1000, 120)

        #-------------------WC WM TELEMETERED------------------------
        self.data_subscribers.get_samples(WcWmDataParticleType.METADATA_TELEMETERED, 1, 10)
        self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_TELEMETERED, 1000, 120)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("================ START QUAL TEST STOP START =====================")

        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_TELEMETERED)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        #-------------------DBG PDBG RECOVERED------------------------
        # check the metadata particle and 4 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_RECOVERED, 4, 10)

        result1.extend(result2)

        self.assert_data_values(result1, 'DBG_PDBG_recov_start_stop1.yml')

        #-------------------DBG PDBG TELEMETERED------------------------
        # check the metadata particle and 1 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_TELEMETERED, 1, 10)

        result1.extend(result2)

        self.assert_data_values(result1, 'DBG_PDBG_telem_start_stop1.yml')

        #-------------------WC HMR RECOVERED------------------------
        # check the metadata particle and the first 5 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_RECOVERED, 5, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_HMR_recov_start_stop1.yml')

        #-------------------WC HMR TELEMETERED------------------------
        # check the metadata particle and the first 10 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_TELEMETERED, 10, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_HMR_telem_start_stop1.yml')

        #-------------------WC SBE RECOVERED------------------------
        # check the metadata particle and the first 8 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_RECOVERED, 8, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_SBE_recov_start_stop1.yml')

        #-------------------WC SBE TELEMETERED------------------------
        # check the metadata particle and the first 3 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_TELEMETERED, 3, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_SBE_telem_start_stop1.yml')

        #-------------------WC WM RECOVERED------------------------
        # check the metadata particle and the first 19 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_RECOVERED, 2, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_WM_recov_start_stop1.yml')

        #-------------------WC WM TELEMETERED------------------------
        # check the metadata particle and the first 19 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_TELEMETERED, 7, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_WM_telem_start_stop1.yml')

        # stop sampling
        self.assert_stop_sampling()

        #restart sampling
        self.assert_start_sampling()

        #-------------------DBG PDBG RECOVERED------------------------
        # check the last 3 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_RECOVERED, 2, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.GPS_RECOVERED, 1, 10)

        result1.extend(result2)

        self.assert_data_values(result1, 'DBG_PDBG_recov_start_stop2.yml')

        #-------------------DBG PDBG TELEMETERED------------------------
        # check the last 6 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_TELEMETERED, 5, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.GPS_TELEMETERED, 1, 10)

        result1.extend(result2)

        self.assert_data_values(result1, 'DBG_PDBG_telem_start_stop2.yml')

        #-------------------WC HMR RECOVERED------------------------
        # check the next 5 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_RECOVERED, 4, 20)

        self.assert_data_values(result1, 'WC_HMR_recov_start_stop2.yml')

        #-------------------WC HMR TELEMETERED------------------------
        # check the next 6 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_TELEMETERED, 6, 20)

        self.assert_data_values(result1, 'WC_HMR_telem_start_stop2.yml')

        #-------------------WC SBE RECOVERED------------------------
        # check the next 7 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_RECOVERED, 7, 20)

        self.assert_data_values(result1, 'WC_SBE_recov_start_stop2.yml')

        #-------------------WC SBE TELEMETERED------------------------
        # check the next 7 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_TELEMETERED, 7, 20)

        self.assert_data_values(result1, 'WC_SBE_telem_start_stop2.yml')

        #-------------------WC WM RECOVERED------------------------
        # check the next 4 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_RECOVERED, 4, 20)

        self.assert_data_values(result1, 'WC_WM_recov_start_stop2.yml')

        #-------------------WC WM TELEMETERED------------------------
        # check next 7 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_TELEMETERED, 7, 20)

        self.assert_data_values(result1, 'WC_WM_telem_start_stop2.yml')

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("================ START QUAL TEST SHUTDOWN RESTART =====================")

        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_HMR.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_SBE.txt', DIR_CSPP_TELEMETERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_RECOVERED)
        self.create_sample_data_set_dir('11079364_WC_WM.txt', DIR_CSPP_TELEMETERED)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        #-------------------DBG PDBG RECOVERED------------------------
        # check the metadata particle and 4 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_RECOVERED, 4, 10)

        result1.extend(result2)

        self.assert_data_values(result1, 'DBG_PDBG_recov_start_stop1.yml')

        #-------------------DBG PDBG TELEMETERED------------------------
        # check the metadata particle and 1 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_TELEMETERED, 1, 10)

        result1.extend(result2)

        self.assert_data_values(result1, 'DBG_PDBG_telem_start_stop1.yml')

        #-------------------WC HMR RECOVERED------------------------
        # check the metadata particle and the first 5 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_RECOVERED, 5, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_HMR_recov_start_stop1.yml')

        #-------------------WC HMR TELEMETERED------------------------
        # check the metadata particle and the first 10 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_TELEMETERED, 10, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_HMR_telem_start_stop1.yml')

        #-------------------WC SBE RECOVERED------------------------
        # check the metadata particle and the first 8 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_RECOVERED, 8, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_SBE_recov_start_stop1.yml')

        #-------------------WC SBE TELEMETERED------------------------
        # check the metadata particle and the first 3 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_TELEMETERED, 3, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_SBE_telem_start_stop1.yml')

        #-------------------WC WM RECOVERED------------------------
        # check the metadata particle and the first 2 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.METADATA_RECOVERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_RECOVERED, 2, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_WM_recov_start_stop1.yml')

        #-------------------WC WM TELEMETERED------------------------
        # check the metadata particle and the first 7 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.METADATA_TELEMETERED, 1, 10)
        result2 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_TELEMETERED, 7, 20)

        result1.extend(result2)

        self.assert_data_values(result1, 'WC_WM_telem_start_stop1.yml')

        # stop sampling
        self.assert_stop_sampling()

        self.stop_dataset_agent_client()
        # Re-start the agent
        self.init_dataset_agent_client()
        # Re-initialize
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        #restart sampling
        self.assert_start_sampling()

        #-------------------DBG PDBG RECOVERED------------------------
        # check the last 3 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_RECOVERED, 2, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.GPS_RECOVERED, 1, 10)

        result1.extend(result2)

        self.assert_data_values(result1, 'DBG_PDBG_recov_start_stop2.yml')

        #-------------------DBG PDBG TELEMETERED------------------------
        # check the last 6 instrument particles
        result1 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.BATTERY_TELEMETERED, 5, 10)
        result2 = self.data_subscribers.get_samples(DbgPdbgDataParticleType.GPS_TELEMETERED, 1, 10)

        result1.extend(result2)

        self.assert_data_values(result1, 'DBG_PDBG_telem_start_stop2.yml')

        #-------------------WC HMR RECOVERED------------------------
        # check the next 5 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_RECOVERED, 4, 20)

        self.assert_data_values(result1, 'WC_HMR_recov_start_stop2.yml')

        #-------------------WC HMR TELEMETERED------------------------
        # check the next 6 instrument particles
        result1 = self.data_subscribers.get_samples(WcHmrDataParticleType.ENGINEERING_TELEMETERED, 6, 20)

        self.assert_data_values(result1, 'WC_HMR_telem_start_stop2.yml')

        #-------------------WC SBE RECOVERED------------------------
        # check the next 7 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_RECOVERED, 7, 20)

        self.assert_data_values(result1, 'WC_SBE_recov_start_stop2.yml')

        #-------------------WC SBE TELEMETERED------------------------
        # check the next 7 instrument particles
        result1 = self.data_subscribers.get_samples(WcSbeDataParticleType.ENGINEERING_TELEMETERED, 7, 20)

        self.assert_data_values(result1, 'WC_SBE_telem_start_stop2.yml')

        #-------------------WC WM RECOVERED------------------------
        # check the next 4 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_RECOVERED, 4, 20)

        self.assert_data_values(result1, 'WC_WM_recov_start_stop2.yml')

        #-------------------WC WM TELEMETERED------------------------
        # check the next 7 instrument particles
        result1 = self.data_subscribers.get_samples(WcWmDataParticleType.ENGINEERING_TELEMETERED, 7, 20)

        self.assert_data_values(result1, 'WC_WM_telem_start_stop2.yml')

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        log.info("=========== START QUAL TEST PARSER EXCEPTION =================")

        self.assert_initialize()

        self.create_sample_data_set_dir('01554008_BAD_DBG_PDBG.txt', DIR_CSPP_RECOVERED)
        self.assert_event_received(ResourceAgentErrorEvent, 10)

        # note this required a bug fix in /instrument_agent_client.py to work correctly
        self.event_subscribers.clear_events()

        self.create_sample_data_set_dir('01554008_BAD_DBG_PDBG.txt', DIR_CSPP_TELEMETERED)
        self.assert_event_received(ResourceAgentErrorEvent, 10)

        self.event_subscribers.clear_events()

        self.create_sample_data_set_dir('11079364_BAD_WC_HMR.txt', DIR_CSPP_RECOVERED)
        self.assert_event_received(ResourceAgentErrorEvent, 10)

        self.event_subscribers.clear_events()

        self.create_sample_data_set_dir('11079364_BAD_WC_HMR.txt', DIR_CSPP_TELEMETERED)
        self.assert_event_received(ResourceAgentErrorEvent, 10)

        self.event_subscribers.clear_events()

        self.create_sample_data_set_dir('11079364_BAD_WC_SBE.txt', DIR_CSPP_RECOVERED)
        self.assert_event_received(ResourceAgentErrorEvent, 10)

        self.event_subscribers.clear_events()

        self.create_sample_data_set_dir('11079364_BAD_WC_SBE.txt', DIR_CSPP_TELEMETERED)
        self.assert_event_received(ResourceAgentErrorEvent, 10)

        self.event_subscribers.clear_events()

        self.create_sample_data_set_dir('11079364_BAD_WC_WM.txt', DIR_CSPP_RECOVERED)
        self.assert_event_received(ResourceAgentErrorEvent, 10)

        self.event_subscribers.clear_events()

        self.create_sample_data_set_dir('11079364_BAD_WC_WM.txt', DIR_CSPP_TELEMETERED)
        self.assert_event_received(ResourceAgentErrorEvent, 10)
