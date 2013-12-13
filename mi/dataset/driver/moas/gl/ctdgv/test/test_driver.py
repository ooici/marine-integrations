"""
@package mi.dataset.driver.moas.gl.ctdgv.test.test_driver
@file marine-integrations/mi/dataset/driver/moas/gl/ctdgv/test/test_driver.py
@author Bill French
@brief Test cases for glider ctd data

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import gevent
import unittest

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
from mi.dataset.parser.glider import GliderParser
from mi.dataset.parser.test.test_glider import GliderParserUnitTestCase
from mi.dataset.harvester import AdditiveSequentialFileHarvester
from mi.dataset.driver.moas.gl.ctdgv.driver import CTDGVDataSetDriver

from mi.dataset.parser.glider import GgldrCtdgvDelayedDataParticle
from pyon.agent.agent import ResourceAgentState

from interface.objects import CapabilityType
from interface.objects import AgentCapability
from interface.objects import ResourceAgentErrorEvent
from interface.objects import ResourceAgentConnectionLostErrorEvent

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.moas.gl.ctdgv.driver',
    driver_class="CTDGVDataSetDriver",

    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = CTDGVDataSetDriver.stream_config(),
    startup_config = {
        'harvester':
        {
            'directory': '/tmp/dsatest',
            'pattern': '*.mrg',
            'frequency': 1,
        },
        'parser': {}
    }
)

SAMPLE_STREAM='ggldr_ctdgv_delayed'
    
###############################################################################
#                                UNIT TESTS                                   #
# Device specific unit tests are for                                          #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver sampling
        can be started and stopped.
        """
        self.clear_sample_data()

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.clear_async_data()
        self.create_sample_data('single_ctdgv_record.mrg', "unit_363_2013_245_6_6.mrg")
        self.assert_data(GgldrCtdgvDelayedDataParticle, 'single_ctdgv_record.mrg.result.yml', count=1, timeout=10)

        self.clear_async_data()
        self.create_sample_data('multiple_ctdgv_record.mrg', "unit_363_2013_245_7_6.mrg")
        self.assert_data(GgldrCtdgvDelayedDataParticle, 'multiple_ctdgv_record.mrg.result.yml', count=4, timeout=10)

        log.debug("Start second file ingestion")
        # Verify sort order isn't ascii, but numeric
        self.clear_async_data()
        self.create_sample_data('unit_363_2013_245_6_6.mrg', "unit_363_2013_245_10_6.mrg")
        self.assert_data(GgldrCtdgvDelayedDataParticle, count=171, timeout=30)

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        # Create and store the new driver state
        state = {DataSourceConfigKey.HARVESTER: '/tmp/dsatest/unit_363_2013_245_6_8.mrg',
                 DataSourceConfigKey.PARSER: {'position': 2600}}
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()
        self.create_sample_data('multiple_ctdgv_record.mrg', "unit_363_2013_245_6_9.mrg")
        self.create_sample_data('single_ctdgv_record.mrg', "unit_363_2013_245_6_10.mrg")

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(GgldrCtdgvDelayedDataParticle, 'merged_ctdgv_record.mrg.result.yml', count=4, timeout=10)

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
        self.create_sample_data('single_ctdgv_record.mrg', 'unit_363_2013_245_6_9.mrg')
        self.assert_initialize()

        # Verify we get one sample
        try:
            result = self.data_subscribers.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'single_ctdgv_record.mrg.result.yml')
        except Exception as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_large_import(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """
        self.create_sample_data('unit_363_2013_245_6_6.mrg')
        self.assert_initialize()

        result = self.get_samples(SAMPLE_STREAM,171,120)

        self.create_sample_data('unit_192_2013_192_1_0.mrg')
        gevent.sleep(10)

    def test_harvester_new_file_exception(self):
        self.assert_new_file_exception('unit_363_2013_245_6_6.mrg')

    @unittest.skip('foo')
    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.error("CONFIG: %s", self._agent_config())
        self.create_sample_data('test_data_1.txt', 'DATA001.txt')

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result = self.get_samples(SAMPLE_STREAM)
            log.debug("RESULT: %s", result)

            # Verify values
            self.assert_data_values(result, 'test_data_1.txt.result.yml')
            self.assert_sample_queue_size(SAMPLE_STREAM, 0)

            self.create_sample_data('test_data_3.txt', 'DATA003.txt')
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


    @unittest.skip('foo')
    def test_parser_exception(self):
        """
        Test an exception raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        self.create_sample_data('test_data_2.txt', 'DATA002.txt')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        result = self.get_samples(SAMPLE_STREAM, 9)
        self.assert_sample_queue_size(SAMPLE_STREAM, 0)

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 10)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)
