"""
@package mi.dataset.driver.VEL3D_K.stc_imodem.test.test_driver
@file marine-integrations/mi/dataset/driver/VEL3D_K/stc_imodem/driver.py
@author Steve Myerson (Raytheon)
@brief Test cases for VEL3D_K__stc_imodem driver

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

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys

from mi.dataset.driver.VEL3D_K.stc_imodem.driver import VEL3D_K__stc_imodem_DataSetDriver
from mi.dataset.parser.vel3d_k__stc_imodem import Vel3d_k__stc_imodemTimeDataParticle
from mi.dataset.parser.vel3d_k__stc_imodem import Vel3d_k__stc_imodemVelocityDataParticle

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.VEL3D_K.stc_imodem.driver',
    driver_class='VEL3D_K__stc_imodem_DataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = VEL3D_K__stc_imodem_DataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'vel3d_k__stc_imodem',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: 'A*.DEC',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM = 'vel3d_k__stc_imodem_parsed'

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
        log.info("=================== START INTEG GET ======================")

        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('first.DAT', "A000010.DAT")
        self.assert_data_multiple_class('first.result.yml', count=2, timeout=10)

        #self.clear_async_data()
        #self.create_sample_data('second.DAT', "E0000002.DAT")
        #self.assert_data_multiple_class('second.result.yml', count=5, timeout=10)

        #self.clear_async_data()
        #self.create_sample_data('E0000303.DAT', "E0000303.DAT")
        # start is the same particle here, just use the same results
        #self.assert_data_multiple_class(count=34, timeout=10)

        log.info("=================== END INTEG GET ======================")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        pass

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

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        pass

