"""
@package mi.dataset.driver.wfp.flortk.test.test_driver
@file marine-integrations/mi/dataset/driver/wfp/flortk/test/test_driver.py
@author Bill French (template)
@author Roger Unwin 
@brief Test cases for wfp/flortk driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import unittest
import gevent
import os
import time

from nose.plugins.attrib import attr
from mock import Mock

from mi.core.log import get_logger ; log = get_logger()

from exceptions import Exception

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetTestConfig
from mi.idk.dataset.unit_test import DataSetUnitTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.core.exceptions import ConfigurationException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentParameterException
from mi.idk.exceptions import SampleTimeout

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter
from mi.core.instrument.instrument_driver import DriverEvent
from mi.dataset.parser.wfp_parser import FlortkParser
from mi.dataset.parser.wfp_parser import WfpFlortkDataParticle
from mi.dataset.parser.test.test_wfp_parser import WfpParserUnitTestCase
from mi.dataset.harvester import AdditiveSequentialFileHarvester
from mi.dataset.driver.wfp.flortk.driver import WfpFLORTKDataSetDriver

from pyon.agent.agent import ResourceAgentState

from interface.objects import CapabilityType
from interface.objects import AgentCapability
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.wfp.flortk.driver',
    driver_class="WfpFLORTKDataSetDriver",

    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = WfpFLORTKDataSetDriver.stream_config(),
    startup_config = {
        'harvester':
        {
            'directory': '/tmp/dsatest',
            'pattern': '*.TXT',
            'frequency': 1,
        },
        'parser': {}
    }
)

SAMPLE_STREAM='wfp_flort_k_parsed'

###############################################################################
#                                INT TESTS                                    #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################


@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
    def setUp(self):
        super(IntegrationTest, self).setUp()

    def test_harvester_config_exception(self):
        """
        Start the a driver with a bad configuration.  Should raise
        an exception.
        """
        with self.assertRaises(ConfigurationException):
            self.driver = WfpFLORTKDataSetDriver({},
                self.memento,
                self.data_callback,
                self.state_callback,
                self.exception_callback)

    def test_parameters(self):
        """
        Verify that we can get, set, and report all driver parameters.
        """
        expected_params = [DriverParameter.BATCHED_PARTICLE_COUNT, DriverParameter.PUBLISHER_POLLING_INTERVAL, DriverParameter.RECORDS_PER_SECOND]
        (res_cmds, res_params) = self.driver.get_resource_capabilities()

        # Ensure capabilities are as expected
        self.assertEqual(len(res_cmds), 0)
        self.assertEqual(len(res_params), len(expected_params))
        self.assertEqual(sorted(res_params), sorted(expected_params))

        # Verify default values are as expected.
        params = self.driver.get_resource(DriverParameter.ALL)
        log.debug("Get Resources Result: %s", params)
        self.assertEqual(params[DriverParameter.BATCHED_PARTICLE_COUNT], 1)
        self.assertEqual(params[DriverParameter.PUBLISHER_POLLING_INTERVAL], 1)
        self.assertEqual(params[DriverParameter.RECORDS_PER_SECOND], 60)

        # Try set resource individually
        self.driver.set_resource({DriverParameter.BATCHED_PARTICLE_COUNT: 2})
        self.driver.set_resource({DriverParameter.PUBLISHER_POLLING_INTERVAL: 2})
        self.driver.set_resource({DriverParameter.RECORDS_PER_SECOND: 59})

        params = self.driver.get_resource(DriverParameter.ALL)
        log.debug("Get Resources Result: %s", params)
        self.assertEqual(params[DriverParameter.BATCHED_PARTICLE_COUNT], 2)
        self.assertEqual(params[DriverParameter.PUBLISHER_POLLING_INTERVAL], 2)
        self.assertEqual(params[DriverParameter.RECORDS_PER_SECOND], 59)

        # Try set resource in bulk
        self.driver.set_resource(
            {DriverParameter.BATCHED_PARTICLE_COUNT: 1,
             DriverParameter.PUBLISHER_POLLING_INTERVAL: .1,
             DriverParameter.RECORDS_PER_SECOND: 60})

        params = self.driver.get_resource(DriverParameter.ALL)
        log.debug("Get Resources Result: %s", params)
        self.assertEqual(params[DriverParameter.BATCHED_PARTICLE_COUNT], 1)
        self.assertEqual(params[DriverParameter.PUBLISHER_POLLING_INTERVAL], .1)
        self.assertEqual(params[DriverParameter.RECORDS_PER_SECOND], 60)

        # Set with some bad values
        with self.assertRaises(InstrumentParameterException):
            self.driver.set_resource({DriverParameter.BATCHED_PARTICLE_COUNT: 'a'})
        with self.assertRaises(InstrumentParameterException):
            self.driver.set_resource({DriverParameter.BATCHED_PARTICLE_COUNT: -1})
        with self.assertRaises(InstrumentParameterException):
            self.driver.set_resource({DriverParameter.BATCHED_PARTICLE_COUNT: 0})

        # Try to configure with the driver startup config
        driver_config = self._driver_config()['startup_config']
        cfg = {
            DataSourceConfigKey.HARVESTER: driver_config.get(DataSourceConfigKey.HARVESTER),
            DataSourceConfigKey.PARSER: driver_config.get(DataSourceConfigKey.PARSER),
            DataSourceConfigKey.DRIVER: {
                DriverParameter.PUBLISHER_POLLING_INTERVAL: .2,
                DriverParameter.RECORDS_PER_SECOND: 3,
                DriverParameter.BATCHED_PARTICLE_COUNT: 3,
            }
        }
        self.driver = WfpFLORTKDataSetDriver(
            cfg,
            self.memento,
            self.data_callback,
            self.state_callback,
            self.exception_callback)

        params = self.driver.get_resource(DriverParameter.ALL)
        log.debug("Get Resources Result: %s", params)
        self.assertEqual(params[DriverParameter.BATCHED_PARTICLE_COUNT], 3)
        self.assertEqual(params[DriverParameter.PUBLISHER_POLLING_INTERVAL], .2)
        self.assertEqual(params[DriverParameter.RECORDS_PER_SECOND], 3)

        # Finally verify we get a KeyError when sending in bad config keys
        cfg[DataSourceConfigKey.DRIVER] = {
            DriverParameter.PUBLISHER_POLLING_INTERVAL: .2,
            DriverParameter.RECORDS_PER_SECOND: 3,
            DriverParameter.BATCHED_PARTICLE_COUNT: 3,
            'something_extra': 1
        }

        with self.assertRaises(KeyError):
            self.driver = WfpFLORTKDataSetDriver(
                cfg,
                self.memento,
                self.data_callback,
                self.state_callback,
                self.exception_callback)

    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver sampling
        can be started and stopped.
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('test_data_1.txt', "DATA001.TXT")
        log.error("*** WfpFlortkDataParticle = " + repr(WfpFlortkDataParticle))
        self.assert_data(WfpFlortkDataParticle, 'test_data_1.txt.result.yml', count=1, timeout=10)

        self.clear_async_data()
        self.create_sample_data('test_data_3.txt', "DATA002.TXT")
        self.assert_data(WfpFlortkDataParticle, 'test_data_3.txt.result.yml', count=8, timeout=10)

        self.clear_async_data()
        self.create_sample_data('E0000152.TXT', "DATA003.TXT")
        self.assert_data(WfpFlortkDataParticle, count=11, timeout=30) # 20

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('test_data_1.txt', "DATA004.TXT")
        self.assert_data(WfpFlortkDataParticle, count=1, timeout=10)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # Create and store the new driver state
        #"""
        self.memento = {DataSourceConfigKey.HARVESTER: '/tmp/dsatest/DATA001.TXT',
                        DataSourceConfigKey.PARSER: {'position': 201, 'timestamp': 3575062804.0}}
        self.driver = WfpFLORTKDataSetDriver(
            self._driver_config()['startup_config'],
            self.memento,
            self.data_callback,
            self.state_callback,
            self.exception_callback)
        #"""
        # create some data to parse
        self.clear_async_data()
        self.create_sample_data('test_data_1.txt', "DATA001.TXT")
        self.create_sample_data('test_data_3.txt', "DATA002.TXT")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(WfpFlortkDataParticle, 'test_data_3B.txt.partial_results.yml', count=5, timeout=10)


###############################################################################

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
        self.create_sample_data('test_data_1.txt', 'DATA001.TXT')
        self.assert_initialize()
        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """
        self.create_sample_data('E0000152.TXT', 'E0000152.TXT')
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM, 11, 10)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        self.create_sample_data('test_data_1.txt', 'DATA001.TXT')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('test_data_3.txt', 'DATA003.TXT')
            # Now read the first three records of the second file then stop

            result = self.get_samples(SAMPLE_STREAM, 3)
            self.assert_stop_sampling()
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            # Restart sampling and ensure we get the last 5 records of the file
            self.assert_start_sampling()
            result = self.get_samples(SAMPLE_STREAM, 5)
            self.assert_data_values(result, 'test_data_3.txt.partial_results.yml')

            self.assert_sample_queue_size(SAMPLE_STREAM, 0)
        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        self.create_sample_data('test_data_2.txt', 'DATA002.TXT')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(SAMPLE_STREAM, 9, timeout=30)
        self.assert_sample_queue_size(SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
