"""
@package mi.dataset.driver.nutnr_j.cspp.test.test_driver
@file marine-integrations/mi/dataset/driver/nutnr_j/cspp/driver.py
@author Emily Hahn
@brief Test cases for nutnr_j_cspp driver

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

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.nutnr_j.cspp.driver import NutnrJCsppDataSetDriver, DataSourceKey
from mi.dataset.parser.nutnr_j_cspp import NutnrJCsppParserDataParticle

TEST_DIR_1 = '/tmp/dsatest1'
TEST_DIR_2 = '/tmp/dsatest2'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.nutnr_j.cspp.driver',
    driver_class='NutnrJCsppDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = NutnrJCsppDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'nutnr_j_cspp',
        DataSourceConfigKey.HARVESTER:
        {
            DataSourceKey.KEY_1: {
                DataSetDriverConfigKeys.DIRECTORY: TEST_DIR_1,
                DataSetDriverConfigKeys.PATTERN: '',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataSourceKey.KEY_2: {
                DataSetDriverConfigKeys.DIRECTORY: TEST_DIR_2,
                DataSetDriverConfigKeys.PATTERN: '',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.KEY_1: {}
            DataSourceKey.KEY_2: {}
        }
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
 
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver
        sampling can be started and stopped
        """
        pass

    def test_stop_resume(self):
        """
        Start the driver in a state that it could have previously stopped at,
        and confirm the driver starts outputting particles where it left off
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

