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

import unittest

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
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
    GPS_ADJUSTMENT_CLASS_KEY, \
    BATTERY_STATUS_CLASS_KEY

from mi.dataset.parser.wc_hmr_cspp import \
    WcHmrEngRecoveredDataParticle, \
    WcHmrEngTelemeteredDataParticle, \
    WcHmrMetadataRecoveredDataParticle, \
    WcHmrMetadataTelemeteredDataParticle, \
    WcHmrDataTypeKey

from mi.dataset.parser.wc_sbe_cspp import \
    WcSbeEngRecoveredDataParticle, \
    WcSbeEngTelemeteredDataParticle, \
    WcSbeMetadataRecoveredDataParticle, \
    WcSbeMetadataTelemeteredDataParticle, \
    WcSbeDataTypeKey

from mi.dataset.parser.wc_wm_cspp import \
    WcWmEngRecoveredDataParticle, \
    WcWmEngTelemeteredDataParticle, \
    WcWmMetadataRecoveredDataParticle, \
    WcWmMetadataTelemeteredDataParticle, \
    WcWmDataTypeKey

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
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = CsppEngCsppDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'cspp_eng_cspp',
        DataSourceConfigKey.HARVESTER:
        {
            DbgPdbgDataTypeKey.DBG_PDBG_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: DBG_PDBG_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            DbgPdbgDataTypeKey.DBG_PDBG_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: DBG_PDBG_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcHmrDataTypeKey.WC_HMR_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: WC_HMR_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcHmrDataTypeKey.WC_HMR_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: WC_HMR_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcSbeDataTypeKey.WC_SBE_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: WC_SBE_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcSbeDataTypeKey.WC_SBE_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: WC_SBE_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcWmDataTypeKey.WC_WM_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: WC_WM_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1
            },
            WcWmDataTypeKey.WC_WM_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_CSPP_RECOVERED,
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
 
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        # test that everything works for the telemetered harvester
        self.create_sample_data_set_dir('01554008_DBG_PDBG.txt', DIR_CSPP_RECOVERED)

        log.debug('### Sample file created in dir = %s ', DIR_CSPP_RECOVERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(DBG_PDBG_REC_PARTICLES,
                         '01554008_DBG_PDBG_recov.yml',
                         count=8, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        pass

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

