"""
@package mi.dataset.driver.moas.gl.engineering.test.test_driver
@file marine-integrations/mi/dataset/driver/moas/gl/engineering/test/test_driver.py
@author Bill French, Nick Almonte
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

from mi.dataset.parser.glider import DataParticleType
from mi.dataset.parser.glider import EngineeringTelemeteredDataParticle, EngineeringScienceTelemeteredDataParticle
from mi.dataset.parser.glider import EngineeringRecoveredDataParticle, EngineeringScienceRecoveredDataParticle
from mi.dataset.parser.glider import EngineeringMetadataDataParticle, EngineeringMetadataRecoveredDataParticle

from mi.dataset.driver.moas.gl.engineering.driver import EngineeringDataSetDriver
from mi.dataset.driver.moas.gl.engineering.driver import DataTypeKey

TELEMETERED_TEST_DIR = '/tmp/engTelemeteredTest'
RECOVERED_TEST_DIR = '/tmp/engRecoveredTest'

DataSetTestCase.initialize(

    driver_module='mi.dataset.driver.moas.gl.engineering.driver',
    driver_class="EngineeringDataSetDriver",
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=EngineeringDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'eng',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.ENG_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TELEMETERED_TEST_DIR,
                DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_engTelemeteredTest',
                DataSetDriverConfigKeys.PATTERN: '*.mrg',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.ENG_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: RECOVERED_TEST_DIR,
                DataSetDriverConfigKeys.STORAGE_DIRECTORY: '/tmp/stored_engRecoveredTest',
                DataSetDriverConfigKeys.PATTERN: '*.mrg',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.ENG_TELEMETERED: {}, DataTypeKey.ENG_RECOVERED: {}
        }
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

    ## DONE
    def test_get(self):
        """
        Test that we can get data from files.  Verify that the driver sampling
        can be started and stopped.
        """
        # Start sampling and watch for an exception
        self.driver.start_sampling()
        log.debug("started sampling")

        self.clear_async_data()
        self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "CopyOf-single_glider_record-engDataOnly.mrg")
        # Results file, Number of Particles (rows) expected to compare, timeout
        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'single_glider_record-engDataOnly.mrg.result.yml', count=3, timeout=10)

        self.clear_async_data()
        self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                        RECOVERED_TEST_DIR,
                                        "CopyOf-single_glider_record-engDataOnly.mrg")
        # Results file, Number of Particles (rows) expected to compare, timeout
        self.assert_data((EngineeringMetadataRecoveredDataParticle, EngineeringScienceRecoveredDataParticle,
                          EngineeringRecoveredDataParticle),
                         'single_glider_record_recovered-engDataOnly.mrg.result.yml', count=3, timeout=10)

        self.clear_async_data()
        self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "CopyOf-multiple_glider_record-engDataOnly.mrg")
        # Results file, Number of Particles (rows) expected to compare, timeout
        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'multiple_glider_record-engDataOnly.mrg.result.yml', count=9, timeout=10)


        self.clear_async_data()
        self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                        RECOVERED_TEST_DIR,
                                        "CopyOf-multiple_glider_record-engDataOnly.mrg")
        # Results file, Number of Particles (rows) expected to compare, timeout
        self.assert_data((EngineeringMetadataRecoveredDataParticle, EngineeringScienceRecoveredDataParticle,
                          EngineeringRecoveredDataParticle),
                         'multiple_glider_record_recovered-engDataOnly.mrg.result.yml', count=9, timeout=10)


        # log.debug("IntegrationTest.test_get(): Start second file ingestion - Telemetered")
        self.clear_async_data()
        self.create_sample_data_set_dir('unit_247_2012_051_0_0-engDataOnly.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "CopyOf-unit_247_2012_051_0_0-engDataOnly.mrg")
        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         count=101, timeout=30)

        # log.debug("IntegrationTest.test_get(): Start second file ingestion - Recovered")
        self.clear_async_data()
        self.create_sample_data_set_dir('unit_247_2012_051_0_0-engDataOnly.mrg',
                                        RECOVERED_TEST_DIR,
                                        "CopyOf-unit_247_2012_051_0_0-engDataOnly.mrg")
        self.assert_data((EngineeringMetadataRecoveredDataParticle, EngineeringScienceRecoveredDataParticle,
                          EngineeringRecoveredDataParticle),
                         count=101, timeout=30)

    ##DONE
    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        path_1 = self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                                 TELEMETERED_TEST_DIR,
                                                 "CopyOf-single_glider_record-engDataOnly.mrg")
        path_1a = self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                                  TELEMETERED_TEST_DIR,
                                                  "CopyOf-multiple_glider_record-engDataOnly.mrg")
        path_2 = self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                                 RECOVERED_TEST_DIR,
                                                 "CopyOf-single_glider_record-engDataOnly.mrg")
        path_2a = self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                                  RECOVERED_TEST_DIR,
                                                  "CopyOf-multiple_glider_record-engDataOnly.mrg")

        # Create and store the new driver state
        state = {
            DataTypeKey.ENG_TELEMETERED: {
            'CopyOf-single_glider_record-engDataOnly.mrg': self.get_file_state(path_1, True, 1160),
            'CopyOf-multiple_glider_record-engDataOnly.mrg': self.get_file_state(path_1a, False, 10895)
            },
            DataTypeKey.ENG_RECOVERED: {
            'CopyOf-single_glider_record-engDataOnly.mrg': self.get_file_state(path_2, True, 1160),
            'CopyOf-multiple_glider_record-engDataOnly.mrg': self.get_file_state(path_2a, False, 12593)
            }
        }

        log.debug(" ############################# TEST_STOP_RESUME - State = %s", state)

        state[DataTypeKey.ENG_TELEMETERED]['CopyOf-single_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = True
        state[DataTypeKey.ENG_TELEMETERED]['CopyOf-multiple_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = False
        state[DataTypeKey.ENG_RECOVERED]['CopyOf-single_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = True
        state[DataTypeKey.ENG_RECOVERED]['CopyOf-multiple_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = True

        self.driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced for telemetered particles
        self.assert_data((EngineeringMetadataDataParticle,
                          EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'merged_glider_record-engDataOnly.mrg.result.yml', count=7, timeout=10)

        # verify data is produced for recovered particles - parse last two rows or data, reuse yml from bad_sample...
        self.assert_data((EngineeringMetadataRecoveredDataParticle,
                         EngineeringScienceRecoveredDataParticle,
                         EngineeringRecoveredDataParticle),
                         'bad_sample_engineering_record_recovered.mrg.result.yml', count=4, timeout=10)

    ##DONE
    def test_stop_start_ingest_telemetered(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "CopyOf-single_glider_record-engDataOnly.mrg")
        self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "xCopyOf-multiple_glider_record-engDataOnly.mrg")
        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'single_glider_record-engDataOnly.mrg.result.yml', count=3, timeout=10)
        self.assert_file_ingested("CopyOf-single_glider_record-engDataOnly.mrg", DataTypeKey.ENG_TELEMETERED)
        self.assert_file_not_ingested("xCopyOf-multiple_glider_record-engDataOnly.mrg")

        self.driver.stop_sampling()
        self.driver.start_sampling()

        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'multiple_glider_record-engDataOnly.mrg.result.yml', count=9, timeout=10)
        self.assert_file_ingested("xCopyOf-multiple_glider_record-engDataOnly.mrg", DataTypeKey.ENG_TELEMETERED)


    def test_stop_start_ingest_recovered(self):
        """
        Test the ability to stop and restart sampling, and ingesting files in the correct order
        """
        self.clear_async_data()

        self.driver.start_sampling()

        self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                        RECOVERED_TEST_DIR,
                                        "CopyOf-single_glider_record-engDataOnly.mrg")
        self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                        RECOVERED_TEST_DIR,
                                        "xCopyOf-multiple_glider_record-engDataOnly.mrg")
        self.assert_data((EngineeringMetadataRecoveredDataParticle, EngineeringScienceRecoveredDataParticle,
                          EngineeringRecoveredDataParticle),
                         'single_glider_record_recovered-engDataOnly.mrg.result.yml', count=3, timeout=10)
        self.assert_file_ingested("CopyOf-single_glider_record-engDataOnly.mrg", DataTypeKey.ENG_RECOVERED)
        self.assert_file_not_ingested("xCopyOf-multiple_glider_record-engDataOnly.mrg")

        self.driver.stop_sampling()

        self.driver.start_sampling()
        self.assert_data((EngineeringMetadataRecoveredDataParticle, EngineeringScienceRecoveredDataParticle,
                          EngineeringRecoveredDataParticle),
                         'multiple_glider_record_recovered-engDataOnly.mrg.result.yml', count=9, timeout=10)
        self.assert_file_ingested("xCopyOf-multiple_glider_record-engDataOnly.mrg", DataTypeKey.ENG_RECOVERED)

    ##DONE
    def test_bad_sample_telemetered(self):
        """
        Test a bad sample.  To do this we set a state to the middle of a record
        """
        # create some data to parse
        self.clear_async_data()

        path = self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                               TELEMETERED_TEST_DIR,
                                               "CopyOf-multiple_glider_record-engDataOnly.mrg")
        path_2 = self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                                 RECOVERED_TEST_DIR,
                                                 "CopyOf-multiple_glider_record-engDataOnly.mrg")

        # Create and store the new driver state
        state = {
            DataTypeKey.ENG_TELEMETERED: {
                'CopyOf-multiple_glider_record-engDataOnly.mrg': self.get_file_state(path, False, 12593)
            },
            DataTypeKey.ENG_RECOVERED: {
                'CopyOf-multiple_glider_record-engDataOnly.mrg': self.get_file_state(path_2, False, 12593)
            }
        }

        state[DataTypeKey.ENG_TELEMETERED]['CopyOf-multiple_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = True

        self.driver = self._get_driver_object(memento=state)

        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data((EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         'bad_sample_engineering_record.mrg.result.yml', count=2, timeout=10)

    ##DONE
    def test_bad_sample_recovered(self):
        """
        Test a bad sample.  To do this we set a state to the middle of a record
        """
        # create some data to parse
        self.clear_async_data()

        path = self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                               TELEMETERED_TEST_DIR,
                                               "CopyOf-multiple_glider_record-engDataOnly.mrg")
        path_2 = self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                                 RECOVERED_TEST_DIR,
                                                 "CopyOf-multiple_glider_record-engDataOnly.mrg")

        # Create and store the new driver state
        state = {
            DataTypeKey.ENG_TELEMETERED: {
                'CopyOf-multiple_glider_record-engDataOnly.mrg': self.get_file_state(path, False, 12593)
            },
            DataTypeKey.ENG_RECOVERED: {
                'CopyOf-multiple_glider_record-engDataOnly.mrg': self.get_file_state(path_2, False, 12593)
            }
        }

        state[DataTypeKey.ENG_RECOVERED]['CopyOf-multiple_glider_record-engDataOnly.mrg']['parser_state']['sent_metadata'] = True

        self.driver = self._get_driver_object(memento=state)

        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data((EngineeringScienceRecoveredDataParticle,
                          EngineeringRecoveredDataParticle),
                         'bad_sample_engineering_record_recovered.mrg.result.yml', count=4, timeout=10)

    ##DONE
    def test_sample_exception_telemetered(self):
        """
        test that a file is marked as parsed if it has a sample exception (which will happen with an empty file)
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester'][DataTypeKey.ENG_TELEMETERED]['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data_set_dir(filename, TELEMETERED_TEST_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename, DataTypeKey.ENG_TELEMETERED)

    ##DONE
    def test_sample_exception_recovered(self):
        """
        test that a file is marked as parsed if it has a sample exception (which will happen with an empty file)
        """
        self.clear_async_data()

        config = self._driver_config()['startup_config']['harvester'][DataTypeKey.ENG_RECOVERED]['pattern']
        filename = config.replace("*", "foo")
        self.create_sample_data_set_dir(filename, RECOVERED_TEST_DIR)

        # Start sampling and watch for an exception
        self.driver.start_sampling()
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')
        self.assert_file_ingested(filename, DataTypeKey.ENG_RECOVERED)

    ##DONE
    def test_fileopen_str_parse_telemetered(self):
        """
        Test that we can parse a fileopen string that has a single digit day
        replaced with an underscore.
        """
        path = self.create_sample_data_set_dir('unit_363_2013_245_6_6.mrg', TELEMETERED_TEST_DIR)

        # Start sampling
        self.driver.start_sampling()

        self.assert_data((EngineeringMetadataDataParticle, EngineeringScienceTelemeteredDataParticle,
                          EngineeringTelemeteredDataParticle),
                         None, count=153, timeout=30)
        self.assert_file_ingested('unit_363_2013_245_6_6.mrg', DataTypeKey.ENG_TELEMETERED)

    ##DONE
    def test_fileopen_str_parse_recovered(self):
        """
        Test that we can parse a fileopen string that has a single digit day
        replaced with an underscore.
        """
        path = self.create_sample_data_set_dir('unit_363_2013_245_6_6.mrg', RECOVERED_TEST_DIR)

        # Start sampling
        self.driver.start_sampling()

        self.assert_data((EngineeringMetadataRecoveredDataParticle, EngineeringScienceRecoveredDataParticle,
                          EngineeringRecoveredDataParticle),
                         None, count=153, timeout=30)
        self.assert_file_ingested('unit_363_2013_245_6_6.mrg', DataTypeKey.ENG_RECOVERED)


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

    ##DONE
    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                        TELEMETERED_TEST_DIR,
                                        'CopyOf-single_glider_record-engDataOnly.mrg')
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


        # Again for the recovered particles
        self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                        RECOVERED_TEST_DIR,
                                        'CopyOf-single_glider_record-engDataOnly.mrg')
        # Verify we get one sample
        try:
            result0 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_RECOVERED)
            result1 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_SCI_RECOVERED)
            result2 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_METADATA_RECOVERED)
            # append result2  to result 1
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_publish_path(): RESULT: %s", result0)

            # Verify values in the combined result
            self.assert_data_values(result0, 'single_glider_record_recovered-engDataOnly.mrg.result.yml')
        except Exception as e:
            log.error("## QualificationTest.test_publish_path(): Exception trapped: %s", e)
            self.fail("Sample timeout.")

    ##DONE
    def test_separate_particles(self):
        """
        Input file has eng particle data in the first two data rows but no eng_sci data, and the next (and last)
         two rows have eng_sci data but no eng data.  This test ensures the parser can deliver a single particle
         of each type.
        """
        self.create_sample_data_set_dir('eng_data_separate.mrg',
                                        TELEMETERED_TEST_DIR,
                                        'CopyOf-eng_data_separate.mrg')
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

    ##DONE
    def test_large_import_telemetered(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """
        self.create_sample_data_set_dir('unit_247_2012_051_0_0-engDataOnly.mrg', TELEMETERED_TEST_DIR)
        self.assert_initialize()

        result0 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_METADATA, 1)
        result1 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 100, 240)
        result2 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 3, 240)

    ##DONE
    def test_large_import_recovered(self):
        """
        There is a bug when activating an instrument go_active times out and
        there was speculation this was due to blocking behavior in the agent.
        https://jira.oceanobservatories.org/tasks/browse/OOIION-1284
        """
        self.create_sample_data_set_dir('unit_247_2012_051_0_0-engDataOnly.mrg', RECOVERED_TEST_DIR)
        self.assert_initialize()

        result0 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_METADATA_RECOVERED, 1)
        result1 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_RECOVERED, 100, 240)
        result2 = self.data_subscribers.get_samples(DataParticleType.GLIDER_ENG_SCI_RECOVERED, 3, 240)


    ##DONE
    def test_shutdown_restart_telemetered(self):
        """
        Test the agents ability to completely stop, then restart
        at the correct spot.
        """
        log.info("CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "CopyOf-single_glider_record-engDataOnly.mrg")

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
            ###self.assert_all_queue_size_zero()

            self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                            TELEMETERED_TEST_DIR,
                                            "CopyOf-multiple_glider_record-engDataOnly.mrg")
            # Now read the first three records of the second file then stop
            result0 = self.get_samples(DataParticleType.GLIDER_ENG_METADATA, 1)
            result1 = self.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 1)
            result2 = self.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 1)
            self.assert_stop_sampling()
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_shutdown_restart(): got result 1 %s", result0)
            self.assert_data_values(result0, 'single_glider_record-engDataOnly-StartStopQual.mrg.result.yml')
            ###self.assert_all_queue_size_zero()

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            self.data_subscribers.clear_sample_queue(DataParticleType.GLIDER_ENG_METADATA)
            self.data_subscribers.clear_sample_queue(DataParticleType.GLIDER_ENG_TELEMETERED)
            self.data_subscribers.clear_sample_queue(DataParticleType.GLIDER_ENG_SCI_TELEMETERED)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result1 = self.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 3)
            result2 = self.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 3)
            self.assert_stop_sampling()
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result1.extend(result2)
            log.debug("##")
            log.debug("##")
            log.debug("##                      SHOULD BE ROWS 3 - 4                          ")
            log.debug("##")
            log.debug("##")
            log.debug("## QualificationTest.test_shutdown_restart_telemetered(): got remaining combined result %s", result1)
            log.debug("##")
            log.debug("##")
            self.assert_data_values(result1, 'shutdownrestart_glider_record-engDataOnly.mrg.result.yml')

        except SampleTimeout as e:
            log.error("## QualificationTest.test_shutdown_restart(): Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

    ##DONE
    def test_shutdown_restart_recovered(self):
        """
        Test the agents ability to completely stop, then restart
        at the correct spot.
        """
        log.info("test_shutdown_restart_recovered(): CONFIG: %s", self._agent_config())
        self.create_sample_data_set_dir('single_glider_record-engDataOnly.mrg',
                                        TELEMETERED_TEST_DIR,
                                        "CopyOf-single_glider_record-engDataOnly.mrg")

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
            log.debug("## QualificationTest.test_shutdown_restart_recovered(): RESULT: %s", result0)

            # Verify values
            self.assert_data_values(result0, 'single_glider_record-engDataOnly.mrg.result.yml')
            ###self.assert_all_queue_size_zero()

            self.create_sample_data_set_dir('multiple_glider_record-engDataOnly.mrg',
                                            TELEMETERED_TEST_DIR,
                                            "CopyOf-multiple_glider_record-engDataOnly.mrg")
            # Now read the first three records of the second file then stop
            result0 = self.get_samples(DataParticleType.GLIDER_ENG_METADATA, 1)
            result1 = self.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 1)
            result2 = self.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 1)
            self.assert_stop_sampling()
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result0.extend(result1)
            result0.extend(result2)
            log.debug("## QualificationTest.test_shutdown_restart_recovered(): got result 1 %s", result0)
            self.assert_data_values(result0, 'single_glider_record-engDataOnly-StartStopQual.mrg.result.yml')
            ###self.assert_all_queue_size_zero()

            # stop the agent
            self.stop_dataset_agent_client()
            # re-start the agent
            self.init_dataset_agent_client()
            #re-initialize
            self.assert_initialize(final_state=ResourceAgentState.COMMAND)

            self.data_subscribers.clear_sample_queue(DataParticleType.GLIDER_ENG_METADATA)
            self.data_subscribers.clear_sample_queue(DataParticleType.GLIDER_ENG_TELEMETERED)
            self.data_subscribers.clear_sample_queue(DataParticleType.GLIDER_ENG_SCI_TELEMETERED)

            # Restart sampling and ensure we get the last 3 records of the file
            self.assert_start_sampling()
            result1 = self.get_samples(DataParticleType.GLIDER_ENG_TELEMETERED, 3)
            result2 = self.get_samples(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 3)
            # append result2 (the eng sci particle) to result 1 (the eng particle)
            result1.extend(result2)
            log.debug("##")
            log.debug("##")
            log.debug("##                      SHOULD BE ROWS 3 - 4                          ")
            log.debug("##")
            log.debug("##")
            log.debug("## QualificationTest.test_shutdown_restart_recovered(): got remaining combined result %s", result1)
            log.debug("##")
            log.debug("##")
            self.assert_data_values(result1, 'shutdownrestart_glider_record-engDataOnly.mrg.result.yml')

        except SampleTimeout as e:
            log.error("## QualificationTest.test_shutdown_restart_recovered(): Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")


    ##DONE
    def test_parser_exception(self):
        """
        Test an exception raised after the driver is started during
        record parsing.
        """
        self.clear_sample_data()
        self.create_sample_data_set_dir('non-input_file.mrg',
                                        TELEMETERED_TEST_DIR,
                                        'unit_247_2012_051_9_9.mrg')

        self.assert_initialize()

        self.event_subscribers.clear_events()
        self.assert_all_queue_size_zero()

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

        # # cause the same error for recovered
        self.event_subscribers.clear_events()
        self.clear_sample_data()
        self.create_sample_data_set_dir('non-input_file.mrg',
                                        RECOVERED_TEST_DIR,
                                        "unit_363_2013_245_7_8.mrg")

        self.assert_all_queue_size_zero_recovered()

        # Verify an event was raised and we are in our retry state
        self.assert_event_received(ResourceAgentErrorEvent, 40)
        self.assert_state_change(ResourceAgentState.STREAMING, 10)

    def assert_all_queue_size_zero(self):
        """
        make sure all 3 queues have no samples and are size 0
        """
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_METADATA, 0)
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_SCI_TELEMETERED, 0)
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_TELEMETERED, 0)

    def assert_all_queue_size_zero_recovered(self):
        """
        make sure all 3 queues have no samples and are size 0
        """
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_METADATA_RECOVERED, 0)
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_SCI_RECOVERED, 0)
        self.assert_sample_queue_size(DataParticleType.GLIDER_ENG_RECOVERED, 0)