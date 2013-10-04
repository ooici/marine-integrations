"""
@package mi.dataset.driver.mflm.ctd.test.test_driver
@file marine-integrations/mi/dataset/driver/mflm/ctd/driver.py
@author Emily Hahn
@brief Test cases for mflm_ctd driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import unittest
import os
import binascii

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetUnitTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase


    
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.mflm.ctd.driver',
    driver_class="MflmCTDMODataSetDriver",

    agent_preload_id = 'EDA_NOSE_CTD',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = ['nose_ctd_external'],
    startup_config = {
        'harvester':
        {
            'directory': '/tmp/dsatest',
            'pattern': '*.000',
            'frequency': 1,
        },
        'parser': {}
    }
)

class SampleData(object):
    
    TEST_DATA_1 = """
cd3e3c2f53616d706c65446174613e0d0a3c45786563757465642f3e0d0a03014354313233373230305f303039436235314543354239365f35365f3041343802
4321abe596d7bd1f41fa7e190d1d21da659c18282241fa7e190d14383d469c4af80c41fa7e190d1324075588a0991f41fa7e190d36248f258e9b131d41fa7e19
0d3e234eb5842c392341fa7e190d3c2f14f61b6ff51041fa7e190d3423b2059240272641fa7e190d0f25e5d59f0f971641fa7e190d383857c69d9a140b41fa7e
190d39360a40c355eb0a41fa7e190d1a21c4b59025741841fa7e190d0301434f313233373230305f303034387535314543354239365f35375f304541330243ff
"""


    def __init__(self, testdir):
        self.TESTDIR = testdir
    
    def create_sample_data(self):
        """
        Create some test data: Some files with some lines in them. Leave room
        for individual test cases to insert files at the beginning of the sequence
        """
        log.debug("Creating test file directory: %s", self.TESTDIR)
        if(not os.path.exists(self.TESTDIR)):
            os.makedirs(self.TESTDIR)
    
        log.debug("Creating test file: %s/gp03flma_atm_test_20130722.000", self.TESTDIR)
        fh = open(os.path.join(self.TESTDIR, "gp03flma_atm_test_20130722.000"), 'wb')
        fh.write(binascii.unhexlify(self.TEST_DATA_1.replace('/n', '')))
        fh.close()


###############################################################################
#                            UNIT TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('UNIT', group='mi')
class UnitTest(DataSetUnitTestCase):
    def setUp(self):
        sample_data = SampleData(self.test_config.driver_startup_config.harvester.directory)
        sample_data.create_sample_data()
        log.debug("Created test data")
        

###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
    def setUp(self):
        sample_data = SampleData(self.test_config.driver_startup_config.harvester.directory)
        sample_data.create_sample_data()
        log.debug("Created test data")
    
    
###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    def setUp(self):
        super(QualificationTest, self).setUp()
        
    def test_initialize(self):
        """
        Test that we can start the container and initialize the dataset agent.
        """
        self.assert_initialize()
        self.assert_stop_sampling()
        self.assert_reset()

    @unittest.skip("skip for now")
    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        sample_data = SampleData(self.test_config.driver_startup_config.harvester.directory)
        sample_data.create_sample_data()
        self.assert_initialize()

        # Verify we get one sample
        result = self.data_subscribers.get_samples('nose_ctd_external')
