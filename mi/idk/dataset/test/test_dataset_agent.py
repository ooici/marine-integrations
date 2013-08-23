"""
@package mi.idk.dataset.test.test_dataset_agent
@file marine-integrations/mi/idkdataset/test/test_dataset_agent.py
@author Bill French
@brief Testing basic functions of the dataset agent
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import os
import unittest

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetUnitTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from pyon.agent.agent import ResourceAgentState
from ion.agents.data.dataset_agent import DataSetAgent
from mi.dataset.dataset_driver import DataSetDriver


DataSetTestCase.initialize(
    driver_module='mi.idk.dataset.test.test_dataset_agent',
    driver_class="TestDataSetDriver",

    agent_preload_id = 'EDA_NOSE_CTD',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = ['foo']
)

cached_memento = None

class TestDataSetDriver(DataSetDriver):
    _memento = None

    def __init__(self, config, memento, data_callback, state_callback, exception_callback):
        super(TestDataSetDriver, self).__init__(config, memento, data_callback, state_callback, exception_callback)
        self._exception_callback(os.getpid())

    def start_sampling(self, memento):
        log.debug("start sampling, memento: %s", memento)
        cached_memento = memento

    def stop_sampling(self):
        log.debug("stop sampling")

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('UNIT', group='mi')
class UnitTest(DataSetUnitTestCase):
    def test_create_plugin(self):
        """
        Verify that we can create a plugin from an egg or class and module
        a path.
        """
        agent = DataSetAgent()
        agent._dvr_config = {
            'dvr_cls': 'TestDataSetDriver',
            'dvr_mod':'mi.idk.dataset.test.test_dataset_agent'
        }
        driver_config = {}
        driver = agent._create_driver_plugin()

        log.debug("Driver object: %s", driver)
        self.assertIsNotNone(driver)
        self.assertIsInstance(driver, TestDataSetDriver)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_initialize(self):
        """
        Test that we can start the container and initialize the dataset agent.
        """
        self.assert_initialize()

        # Verify the memento was stored on init and retrieved on start sampling
        #self.assertEqual(os.getpid(), cached_memento)

        self.assert_stop_sampling()

        self.assert_reset()
