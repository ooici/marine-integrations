"""
@package mi.dataset.driver.moas.gl.engineering.test.test_driver
@file marine-integrations/mi/dataset/driver/moas/gl/engineering/test/test_driver.py
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

import unittest

from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent
from exceptions import Exception

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.idk.exceptions import SampleTimeout

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter
from mi.dataset.driver.moas.gl.engineering.driver import EngineeringDataSetDriver
from mi.dataset.parser.glider import EngineeringTelemeteredDataParticle, DataParticleType
from mi.dataset.parser.glider import EngineeringScienceTelemeteredDataParticle, EngineeringMetadataDataParticle


DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.moas.gl.engineering.driver',
    driver_class="EngineeringDataSetDriver",

    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = EngineeringDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataSetDriverConfigKeys.DIRECTORY: '/tmp/engtest',
            DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_engineeringtest',
            DataSetDriverConfigKeys.PATTERN: '*.mrg',
            DataSetDriverConfigKeys.FREQUENCY: 1,
        },
        DataSourceConfigKey.PARSER: {}
    }
)
    
###############################################################################
#                                UNIT TESTS                                   #
# Device specific unit tests are for                                          #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):

    #
    # INTEGRATION TESTS FOR ENGINEERING & SCIENCE DATA PARTICLE
    #
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver sampling
        can be started and stopped.
        """
        self.clear_sample_data()
        log.debug("cleared sample data")
        # Start sampling and watch for an exception
        self.driver.start_sampling()
        log.debug("started sampling")
        self.clear_async_data()
        self.create_sample_data('single_glider_record-engDataOnly.mrg', "CopyOf-single_glider_record-engDataOnly.mrg")
        # Results file, Number of Particles (rows) expected to compare, timeout
        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'single_glider_record-engDataOnly.mrg.result.yml', count=3, timeout=10)

        self.clear_async_data()
        self.create_sample_data('multiple_glider_record-engDataOnly.mrg',
                                "CopyOf-multiple_glider_record-engDataOnly.mrg")
        # Results file, Number of Particles (rows) expected to compare, timeout
        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'multiple_glider_record-engDataOnly.mrg.result.yml', count=9, timeout=10)

        # log.debug("IntegrationTest.test_get(): Start second file ingestion")
        self.clear_async_data()
        self.create_sample_data('unit_247_2012_051_0_0-engDataOnly.mrg', "CopyOf-unit_247_2012_051_0_0-engDataOnly.mrg")
        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         count=101, timeout=30)
        self.assert_file_ingested("CopyOf-unit_247_2012_051_0_0-engDataOnly.mrg")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data('single_glider_record-engDataOnly.mrg',
                                         "CopyOf-single_glider_record-engDataOnly.mrg")
        path_2 = self.create_sample_data('multiple_glider_record-engDataOnly.mrg',
                                         "CopyOf-multiple_glider_record-engDataOnly.mrg")

        # Create and store the new driver state
        state = {
            'CopyOf-single_glider_record-engDataOnly.mrg': self.get_file_state(path_1, True, 1160),
            'CopyOf-multiple_glider_record-engDataOnly.mrg': self.get_file_state(path_2, False, 10816)
        }
        state['CopyOf-single_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = True
        state['CopyOf-multiple_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = True
        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data((EngineeringScienceTelemeteredDataParticle, EngineeringTelemeteredDataParticle),
                         'merged_glider_record-engDataOnly.mrg.result.yml', count=6, timeout=10)

    def test_stop_start_ingest(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data('single_glider_record-engDataOnly.mrg',
                                "CopyOf-single_glider_record-engDataOnly.mrg")
        self.create_sample_data('multiple_glider_record-engDataOnly.mrg',
                                "xCopyOf-multiple_glider_record-engDataOnly.mrg")
        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'single_glider_record-engDataOnly.mrg.result.yml', count=3, timeout=10)
        self.assert_file_ingested("CopyOf-single_glider_record-engDataOnly.mrg")
        self.assert_file_not_ingested("xCopyOf-multiple_glider_record-engDataOnly.mrg")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'multiple_glider_record-engDataOnly.mrg.result.yml', count=9, timeout=10)
        self.assert_file_ingested("xCopyOf-multiple_glider_record-engDataOnly.mrg")

    def test_bad_sample(self):
        """
        Test a bad sample.  To do this we set a state to the middle of a record
        """
        # create some data to parse
        self.clear_async_data()

        path = self.create_sample_data('multiple_glider_record-engDataOnly.mrg',
                                       "CopyOf-multiple_glider_record-engDataOnly.mrg")

        # Create and store the new driver state
        state = {
            'CopyOf-multiple_glider_record-engDataOnly.mrg': self.get_file_state(path, False, 12167),
        }
        state['CopyOf-multiple_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = True
        self.driver = self._get_driver_object(memento=state)

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data((EngineeringScienceTelemeteredDataParticle, EngineeringTelemeteredDataParticle),
                         'bad_sample_engineering_record.mrg.result.yml', count=2, timeout=10)
        self.assert_file_ingested("CopyOf-multiple_glider_record-engDataOnly.mrg")

    def test_sample_exception(self):
        """
        test that a file is marked as parsed if it has a sample exception (which will happen with an empty file)
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester']['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data(filename)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):
    #
    # QUAL TESTS FOR ENGINEERING & SCIENCE DATA PARTICLE
    #
    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data('single_glider_record-engDataOnly.mrg', 'CopyOf-single_glider_record-engDataOnly.mrg')
        self.assert_initialize()

        # Verify we get one sample
        try:
            result0 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_METADATA)
            result1 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED)
            result2 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_publish_path(): RESULT: %s", result0)

            # Verify values in the combined result
            self.assert_data_values(result0, 'single_glider_record-engDataOnly.mrg.result.yml')
        except Exception as e:
            log.error("## QualificationTest.test_publish_path(): Exception trapped: %s", e)
            self.fail("Sample timeout.")

    def test_separate_particles(self):
        """
        Input file has eng particle data in the first two data rows but no eng_sci data, and the next (and last)
         two rows haev eng_sci data but no eng data.  This test ensures the parser can deliver a single particle
         of each type.
        """
        self.create_sample_data('eng_data_separate.mrg', 'CopyOf-eng_data_separate.mrg')
        self.assert_initialize()

        # Verify we get one sample
        try:
            result0 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_METADATA, 1)
            result1 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 2)
            result2 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 2)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_separate_particles(): RESULT: %s", result0)

            # Verify values in the combined result
            self.assert_data_values(result0, 'eng_data_separate.mrg.result.yml')
        except Exception as e:
            log.error("## QualificationTest.test_separate_particles(): Exception trapped: %s", e)
            self.fail("## QualificationTest.test_separate_particles(): Sample timeout.")

    def test_large_import(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """

        self.create_sample_data('unit_247_2012_051_0_0-engDataOnly.mrg')
        self.assert_initialize()

        result0 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_METADATA, 1)
        result1 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 100, 240)
        result2 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 3, 240)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("## QualificationTest.test_stop_start(): CONFIG: %s", self._agent_config())
        self.create_sample_data('single_glider_record-engDataOnly.mrg', "CopyOf-single_glider_record-engDataOnly.mrg")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result0 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_METADATA)
            result1 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED)
            result2 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_stop_start(): RESULT: %s", result0)

            # Verify values
            self.assert_data_values(result0, 'single_glider_record-engDataOnly.mrg.result.yml')
            self.assert_all_queue_size_zero()

            self.create_sample_data('multiple_glider_record-engDataOnly.mrg',
                                    "CopyOf-multiple_glider_record-engDataOnly.mrg")
            # Now read the first three records of the second file then stop
            result0 = self.get_samples(DataParticleType.GLIDER_ENG_METADATA, 1)
            result1 = self.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 1)
            result2 = self.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 1)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_stop_start(): got result 1 %s", result0)
            self.assert_stop_sampling()
            self.assert_all_queue_size_zero()

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result3 = self.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 3)
            result4 = self.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 3)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result3.extend(result4)

            result0.extend(result3)

            log.debug("## QualificationTest.test_stop_start(): got combined result %s", result0)
            self.assert_data_values(result0, 'shutdownrestart_glider_record-engDataOnly.mrg.result.yml')

            self.assert_all_queue_size_zero()
        except SampleTimeout as e:
            log.error("## QualificationTest.test_stop_start(): Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def assert_all_queue_size_zero(self):
        """
        make sure all 3 queues have no samples and are size 0
        """
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_METADATA, 0)
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 0)
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_TELEMETERED, 0)

    def test_shutdown_restart(self):
        """
        Test the agents ability to completely stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data('single_glider_record-engDataOnly.mrg', "CopyOf-single_glider_record-engDataOnly.mrg")

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get one sample
        try:
            # Read the first file and verify the data
            result0 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_METADATA)
            result1 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED)
            result2 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_shutdown_restart(): RESULT: %s", result0)

            # Verify values
            self.assert_data_values(result0, 'single_glider_record-engDataOnly.mrg.result.yml')
            self.assert_all_queue_size_zero()

            self.create_sample_data('multiple_glider_record-engDataOnly.mrg',
                                    "CopyOf-multiple_glider_record-engDataOnly.mrg")
            # Now read the first three records of the second file then stop
            result0 = self.get_samples(DataParticleType.GLIDER_ENG_METADATA, 1)
            result1 = self.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 1)
            result2 = self.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 1)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_shutdown_restart(): got result 1 %s", result0)
            self.assert_stop_sampling()
            self.assert_all_queue_size_zero()

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result3 = self.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 3)
            result4 = self.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 3)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result3.extend(result4)

            result0.extend(result3)

            log.debug("## QualificationTest.test_shutdown_restart(): got combined result %s", result0)
            self.assert_data_values(result0, 'shutdownrestart_glider_record-engDataOnly.mrg.result.yml')

            self.assert_all_queue_size_zero()

        except SampleTimeout as e:
            log.error("## QualificationTest.test_shutdown_restart(): Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    def test_parser_exception(self):
        """
        Test an exception raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        self.create_sample_data('unit_247_2012_051_9_9.mrg')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        self.assert_all_queue_size_zero()

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)