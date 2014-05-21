"""
@package mi.dataset.driver.vel3d_l.wfp.test.test_driver
@file marine-integrations/mi/dataset/driver/vel3d_l/wfp/driver.py
@author Steve Myerson (Raytheon)
@brief Test cases for vel3d_l_wfp driver (for both telemetered and recovered data)

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger; log = get_logger()
import os

from mi.core.exceptions import \
    DatasetParserException, \
    RecoverableSampleException, \
    SampleException, \
    UnexpectedDataException

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.idk.exceptions import IDKConfigMissing, IDKException, SampleTimeout
from mi.idk.util import remove_all_files

from mi.dataset.dataset_driver import \
    DataSourceConfigKey, \
    DataSetDriverConfigKeys, \
    DriverParameter

from mi.dataset.driver.vel3d_l.wfp.driver import \
    Vel3dLWfp, \
    DataTypeKey

from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.parser.vel3d_l_wfp import \
    Vel3dLWfpDataParticleType, \
    Vel3dLWfpStateKey, \
    Vel3dLWfpInstrumentParticle, \
    Vel3dLWfpMetadataParticle, \
    Vel3dLWfpSioMuleMetadataParticle

DIR_REC = '/tmp/dsatest_rec'
DIR_TEL = '/tmp/dsatest_tel'
FILE_REC1 = 'A00000001.DAT'
FILE_REC2 = 'A00000002.DAT'
FILE_REC4 = 'A00000004.DAT'
FILE_TEL = 'node58p1.dat'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.vel3d_l.wfp.driver',
    driver_class='Vel3dLWfp',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = Vel3dLWfp.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'vel3d_l_wfp',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.VEL3D_L_WFP:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_REC,
                DataSetDriverConfigKeys.PATTERN: 'A*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.VEL3D_L_WFP_SIO_MULE:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_TEL,
                DataSetDriverConfigKeys.PATTERN: FILE_TEL,
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {}
    }
)

PARSER_STATE = 'parser_state'

WFP_PARTICLES = (Vel3dLWfpInstrumentParticle, Vel3dLWfpMetadataParticle)
SIO_PARTICLES = (Vel3dLWfpInstrumentParticle, Vel3dLWfpSioMuleMetadataParticle)

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

    def assert_file_ingested(self, filename, data_key):
        """
        Assert that a particular file was ingested
        Need to override for multiple harvester since we have the additional data_key
        If the ingested flag is not set in the driver state for this file, fail the test
        @ param filename name of the file to check that it was ingested using the ingested flag
        """
        log.debug("last state callback result %s", self.state_callback_result[-1])
        last_state = self.state_callback_result[-1][data_key]
        if not filename in last_state or not last_state[filename]['ingested']:
            self.fail("File %s was not ingested" % filename)

    def clear_sample_data(self):
        log.debug("Driver Config: %s", self._driver_config())
        if os.path.exists(DIR_REC):
            log.debug("Clean all data from %s", DIR_REC)
            remove_all_files(DIR_REC)
        else:
            log.debug("Create directory %s", DIR_REC)
            os.makedirs(DIR_REC)

        if os.path.exists(DIR_TEL):
            log.debug("Clean all data from %s", DIR_TEL)
            remove_all_files(DIR_TEL)
        else:
            log.debug("Create directory %s", DIR_TEL)
            os.makedirs(DIR_TEL)
 
    def test_get(self):
        """
        Test that we can get data from multiple files.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.clear_sample_data()
        self.driver.start_sampling()

        # Generated recovered file has 10 instrument
        # records and 1 metadata record.
        log.info("FILE rec_vel3d_l_1.dat INTEG TEST GET")
        self.clear_async_data()
        self.create_sample_data_set_dir('rec_vel3d_l_1.dat', DIR_REC, FILE_REC1)
        self.assert_data(WFP_PARTICLES, 'rec_vel3d_l_1.yml', count=11, timeout=11)

        # Generated telemetered file has 1 SIO block with 10 instrument
        # records and 1 metadata record.
        log.info("FILE tel_vel3d_l_1.dat INTEG TEST GET")
        self.clear_async_data()
        self.create_sample_data_set_dir('tel_vel3d_l_1.dat', DIR_TEL, FILE_TEL)
        self.assert_data(SIO_PARTICLES, 'tel_vel3d_l_1.yml', count=11, timeout=11)

        log.info("================ END INTEG TEST GET ======================")

    def test_get_any_order(self):
        """
        Test that we can get data from files for all harvesters / parsers.
        This isn't a good test since both parsers generate INSTRUMENT particle streams.
        So all files processed by 1 harvester need to be handled before files
        by the other harvester, or the INSTRUMENT particles will get interspersed.
        """
        log.info("=========== START INTEG TEST GET ANY ORDER  ================")

        # Start sampling.
        self.clear_sample_data()
        self.driver.start_sampling()
        self.clear_async_data()

        # Set up the test files.
        # 2 Recovered files
        #   rec_vel3d_l_2 - 4 instrument, 1 metadata, 6 instrument, 1 metadata
        #   rec_vel3d_l_4 - 1 instrument, 2 instrument, 3 instrument,
        #                   4 instrument with metadata after each group
        # 1 Telemetered file
        #   tel_vel3d_l_1 - 10 instrument, 1 metadata
        log.info("=========== CREATE DATA FILES  ================")
        self.create_sample_data_set_dir('rec_vel3d_l_4.dat', DIR_REC, FILE_REC4)
        self.create_sample_data_set_dir('rec_vel3d_l_2.dat', DIR_REC, FILE_REC2)

        # Read files in the following order:
        # Entire recovered data file rec_vel3d_l_2.
        # Entire recovered data file rec_vel3d_l_4.
        # Entire telemetered data file tel_vel3d_l_1.
        log.info("=========== READ RECOVERED DATA FILE #1  ================")
        self.assert_data(WFP_PARTICLES, 'rec_vel3d_l_2.yml', count=12, timeout=10)

        log.info("=========== READ RECOVERED DATA FILE #2  ================")
        self.assert_data(WFP_PARTICLES, 'rec_vel3d_l_4.yml', count=14, timeout=14)

        log.info("=========== READ TELEMETERED DATA FILE #1  ================")
        self.create_sample_data_set_dir('tel_vel3d_l_1.dat', DIR_TEL, FILE_TEL)
        self.assert_data(SIO_PARTICLES, 'tel_vel3d_l_1.yml', count=11, timeout=11)

        log.info("=========== END INTEG TEST GET ANY ORDER  ================")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("=========== START INTEG TEST STOP RESUME  ================")

        self.clear_async_data()
        path_1 = self.create_sample_data_set_dir('rec_vel3d_l_1.dat', DIR_REC, FILE_REC1)
        path_2 = self.create_sample_data_set_dir('rec_vel3d_l_4.dat', DIR_REC, FILE_REC4)
        path_3 = self.create_sample_data_set_dir('tel_vel3d_l_2.dat', DIR_TEL, FILE_TEL)

        # Recovered file 1 position set to EOF.
        # Recovered file 2 position set to record 9 (start of group of 4 records).
        # Telemetered file position set to start of 2nd SIO block (file size = 1122)
        pos_1 = 761
        pos_2 = 1155    # 338 + 385 + 432

        key_rec = DataTypeKey.VEL3D_L_WFP
        key_tel = DataTypeKey.VEL3D_L_WFP_SIO_MULE

        state = {
            key_rec:
                {FILE_REC1: self.get_file_state(path_1, True, pos_1),
                 FILE_REC4: self.get_file_state(path_2, False, pos_2)},
            key_tel:
                {FILE_TEL: self.get_file_state(path_3, False)}
        }

        state[key_rec][FILE_REC1][PARSER_STATE][Vel3dLWfpStateKey.POSITION] = pos_1
        state[key_rec][FILE_REC4][PARSER_STATE][Vel3dLWfpStateKey.POSITION] = pos_2
        state[key_tel][FILE_TEL][PARSER_STATE][StateKey.UNPROCESSED_DATA] = [[515, 1122]]
        state[key_tel][FILE_TEL][PARSER_STATE][StateKey.IN_PROCESS_DATA] = []

        log.info("===== INTEG TEST STOP RESUME SET STATE TO %s =======", state)
        self.driver = self._get_driver_object(memento=state)
        self.driver.start_sampling()

        log.info("=========== READ RECOVERED DATA FILE #2  ================")
        self.assert_data(WFP_PARTICLES, 'rec_vel3d_l_4_10-14.yml', count=5, timeout=10)

        log.info("=========== READ TELEMETERED DATA FILE  ================")
        self.assert_data(SIO_PARTICLES, 'tel_vel3d_l_2_6-12.yml', count=7, timeout=10)

        log.info("=========== END INTEG TEST STOP RESUME  ================")

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

