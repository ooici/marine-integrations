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


from mi.dataset.parser.vel3d_l_wfp import \
    Vel3dLWfpDataParticleType, \
    Vel3dLWfpStateKey, \
    Vel3dLWfpInstrumentParticle, \
    Vel3dLWfpMetadataParticle


DIR_WFP = '/tmp/dsatest1'
DIR_WFP_SIO_MULE = '/tmp/dsatest2'

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
            DataTypeKey.VEL3D_K_WFP:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_WFP,
                DataSetDriverConfigKeys.PATTERN: 'A*.DAT',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.VEL3D_L_WFP_SIO_MULE:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_WFP_SIO_MULE,
                DataSetDriverConfigKeys.PATTERN: 'node*.dat',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {}
    }
)

WFP_PARTICLES = (Vel3dLWfpInstrumentParticle, Vel3dLWfpMetadataParticle)

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

    def clear_sample_data(self):
        log.debug("Driver Config: %s", self._driver_config())
        if os.path.exists(DIR_WFP):
            log.debug("Clean all data from %s", DIR_WFP)
            remove_all_files(DIR_WFP)
        else:
            log.debug("Create directory %s", DIR_WFP)
            os.makedirs(DIR_WFP)

        if os.path.exists(DIR_WFP_SIO_MULE):
            log.debug("Clean all data from %s", DIR_WFP_SIO_MULE)
            remove_all_files(DIR_WFP_SIO_MULE)
        else:
            log.debug("Create directory %s", DIR_WFP_SIO_MULE)
            os.makedirs(DIR_WFP_SIO_MULE)
 
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.clear_sample_data()
        log.info("TTTTTTTTTTTT  call start sampling")
        self.driver.start_sampling()

        # Generated telemetered file has 1 SIO block with 10 instrument records
        # and 1 metadata record.
        log.info("FILE sgm_vel3d_l_1_tel.dat INTEG TEST GET")
        self.clear_async_data()
        self.create_sample_data_set_dir(
            'sgm_vel3d_l_1_tel.dat', DIR_WFP_SIO_MULE, 'node01p1.dat')
        self.assert_data(WFP_PARTICLES, 'sgm_vel3d_l_1_tel.yml',
            count=4, timeout=4)


        log.info("================ END INTEG TEST GET ======================")

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

