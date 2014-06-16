"""
@package mi.dataset.driver.ctdpf_ckl.mmp_cds.test.test_driver
@file marine-integrations/mi/dataset/driver/ctdpf_ckl/mmp_cds/driver.py
@author Mark Worden
@brief Test cases for CtdpfCklMmpCds driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger
log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.driver.ctdpf_ckl.mmp_cds.driver import CtdpfCklMmpCdsDataSetDriver
from mi.dataset.parser.ctdpf_ckl_mmp_cds import CtdpfCklMmpCdsParserDataParticle

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.ctdpf_ckl.mmp_cds.driver',
    driver_class='CtdpfCklMmpCdsDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=CtdpfCklMmpCdsDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'ctdpf_ckl_mmp_cds',
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/dsatest',
            DataSetDriverConfigKeys.PATTERN: '*.mpk',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)

SAMPLE_STREAM = 'ctdpf_ckl_mmp_cds_parsed'

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

        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('ctd_1_20131124T005004_458.mpk', "ctd_1_20131124T005004_458.mpk")
        self.assert_data(CtdpfCklMmpCdsParserDataParticle, 'first.yml', count=1, timeout=10)

        # # Read the remaining values in first.DAT
        # self.assert_data(CtdpfCklMmpCdsParserDataParticle, None, count=682, timeout=100)
        #
        # self.clear_async_data()
        # self.create_sample_data('ctd_1_20131124T005004_458.mpk', "ctd_1_20131124T005004_458.mpk")
        # self.assert_data(CtdpfCklMmpCdsParserDataParticle, 'six_samples.yml', count=6, timeout=10)
        #
        # # Read the remaining values in second.DAT
        # self.assert_data(CtdpfCklMmpCdsParserDataParticle, None, count=677, timeout=100)
        #
        # self.clear_async_data()
        # self.create_sample_data('ctd_1_20131124T005004_458.mpk', "ctd_1_20131124T005004_458.mpk")
        # # start is the same particle here, just use the same results
        # self.assert_data(CtdpfCklMmpCdsParserDataParticle, count=30, timeout=10)


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

