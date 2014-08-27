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

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.exceptions import SampleTimeout

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import DataSourceConfigKey, \
                                      DataSetDriverConfigKeys, \
                                      DriverStateKey, \
                                      DriverParameter
from mi.dataset.driver.nutnr_j.cspp.driver import NutnrJCsppDataSetDriver, DataSourceKey
from mi.dataset.parser.cspp_base import StateKey
from mi.dataset.parser.nutnr_j_cspp import NutnrJCsppMetadataTelemeteredDataParticle, \
                                           NutnrJCsppTelemeteredDataParticle, \
                                           NutnrJCsppMetadataRecoveredDataParticle, \
                                           NutnrJCsppRecoveredDataParticle, \
                                           DataParticleType

TELEM_DIR = '/tmp/dsatest1'
RECOV_DIR = '/tmp/dsatest2'

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
            DataSourceKey.NUTNR_J_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: TELEM_DIR,
                DataSetDriverConfigKeys.PATTERN: '*SNA_SNA.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataSourceKey.NUTNR_J_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: RECOV_DIR,
                DataSetDriverConfigKeys.PATTERN: '*SNA_SNA.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataSourceKey.NUTNR_J_CSPP_TELEMETERED: {},
            DataSourceKey.NUTNR_J_CSPP_RECOVERED: {}
        }
    }
)

TELEM_PARTICLES = (NutnrJCsppMetadataTelemeteredDataParticle,
                   NutnrJCsppTelemeteredDataParticle)
RECOV_PARTICLES = (NutnrJCsppMetadataRecoveredDataParticle,
                   NutnrJCsppRecoveredDataParticle)

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
        self.create_sample_data_set_dir('short_SNA_SNA.txt', TELEM_DIR)
        self.create_sample_data_set_dir('short_SNA_SNA.txt', RECOV_DIR)

        self.driver.start_sampling()

        self.assert_data(TELEM_PARTICLES, 'short_SNA_telem.yml', count=6)
        self.assert_data(RECOV_PARTICLES, 'short_SNA_recov.yml', count=6)

    def test_resume(self):
        """
        Start the driver in a state that it could have previously stopped at,
        and confirm the driver starts outputting particles where it left off
        """
        filename = 'short_SNA_SNA.txt'
        path_1 = self.create_sample_data_set_dir(filename, TELEM_DIR)
        path_2 = self.create_sample_data_set_dir(filename, RECOV_DIR)
        
        PARTICLE_2_POS = 6136
        PARTICLE_4_POS = 9055
        
        state = {DataSourceKey.NUTNR_J_CSPP_TELEMETERED:
                    # telemetered starting after 2nd particle
                    {filename: self.get_file_state(path_1, False, PARTICLE_2_POS)},
                 DataSourceKey.NUTNR_J_CSPP_RECOVERED:
                    # recovered starting after 4th particle
                    {filename: self.get_file_state(path_2, False, PARTICLE_4_POS)}
                 }
        state[DataSourceKey.NUTNR_J_CSPP_TELEMETERED][filename] \
        [DriverStateKey.PARSER_STATE][StateKey.METADATA_EXTRACTED] = True
        state[DataSourceKey.NUTNR_J_CSPP_RECOVERED][filename] \
        [DriverStateKey.PARSER_STATE][StateKey.METADATA_EXTRACTED] = True

        # set the driver to the predetermined state and start sampling
        self.driver = self._get_driver_object(memento=state)
        self.driver.start_sampling()
        
        self.assert_data(TELEM_PARTICLES, 'last_3_SNA_telem.yml', count=3)
        self.assert_data(RECOV_PARTICLES, 'last_SNA_recov.yml', count=1)

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """

        self.driver.start_sampling()
        self.clear_async_data()
        
        self.create_sample_data_set_dir('bad_SNA_SNA.txt', RECOV_DIR)

        self.assert_data(RECOV_PARTICLES, 'last_and_meta_SNA_recov.yml', count=2)
        
        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

    def test_no_header(self):
        """
        Test a case where the file has no header, which should not make a
        metadata particle and throw an exception
        """

        self.driver.start_sampling()
        self.clear_async_data()

        self.create_sample_data_set_dir('no_header_SNA_SNA.txt', TELEM_DIR)

        self.assert_data(TELEM_PARTICLES, 'short_SNA_telem_no_meta.yml', count=5)

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')

    def test_partial_header(self):
        """
        Test a case where we are missing part of the header, but it is not
        the source file so we still want to create the header
        """
        self.driver.start_sampling()
        self.clear_async_data()

        self.create_sample_data_set_dir('part_header_SNA_SNA.txt', TELEM_DIR)

        self.assert_data(TELEM_PARTICLES, 'short_SNA_telem_part.yml', count=6,
                         timeout=20)

    def test_bad_matches(self):
        """
        Test that a file that has a data sample that is causing the regex
        matcher to hang (which is killing ingestion tests).  This test confirms 
        the fix doesn't hang and causes exceptions for not matching data
        """
        self.driver.start_sampling()
        self.clear_async_data()

        self.create_sample_data_set_dir('11129553_SNA_SNA.txt', TELEM_DIR)
        # there are 59 data sample lines in the file with 2 bad samples
        self.assert_data(TELEM_PARTICLES, count=57, timeout=20)

        # an event catches the sample exception
        self.assert_event('ResourceAgentErrorEvent')


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
        self.assert_initialize()
        
        self.create_sample_data_set_dir('short_SNA_SNA.txt', TELEM_DIR)
        self.create_sample_data_set_dir('short_SNA_SNA.txt', RECOV_DIR)
        
        # get telemetered particles
        result_t = self.data_subscribers.get_samples(DataParticleType.METADATA, 1)
        result_t2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 5)
        result_t.extend(result_t2)
        # compare telemetered particles
        self.assert_data_values(result_t, 'short_SNA_telem.yml')

        # get recovered particles
        result_r = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1)
        result_r2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 5)
        result_r.extend(result_r2)
        # compare recovered particles
        self.assert_data_values(result_r, 'short_SNA_recov.yml')

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        self.assert_initialize()
        
        self.create_sample_data_set_dir('11079419_SNA_SNA.txt', TELEM_DIR)
        self.create_sample_data_set_dir('11079364_SNA_SNA.txt', RECOV_DIR)
        
        # for long test just confirm we get the right number of particles, get_samples won't
        # return successfully unless the requested number are found
        result_t = self.data_subscribers.get_samples(DataParticleType.METADATA, 1, 60)
        result_t2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 171, 60)

        result_r = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 60)
        result_r2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 181, 60)
        
    def test_stop_start_telem(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot for the telemetered parser.
        """
        # slow down sampling to give us time to stop
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        self.create_sample_data_set_dir('short_SNA_SNA.txt', TELEM_DIR)

        # get the metadata and first 2 samples
        result_t = self.data_subscribers.get_samples(DataParticleType.METADATA, 1)
        result_t2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
        result_t.extend(result_t2)

        # stop sampling
        self.assert_stop_sampling()
        #restart sampling
        self.assert_start_sampling()

        # should get the last 3 samples
        result_t3 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
        result_t.extend(result_t3)

        # confirm we got particles in the order expected
        self.assert_data_values(result_t, 'short_SNA_telem.yml')

    def test_stop_start_recov(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot for the recovered parser.
        """
        # slow down sampling to give us time to stop
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        self.create_sample_data_set_dir('short_SNA_SNA.txt', RECOV_DIR)

        # get the metadata and first 2 samples
        result_r = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1)
        result_r2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 2)
        result_r.extend(result_r2)

        # stop sampling
        self.assert_stop_sampling()
        #restart sampling
        self.assert_start_sampling()

        # should get the last 3 samples
        result_r3 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 3)
        result_r.extend(result_r3)

        # confirm we got particles in the order expected
        self.assert_data_values(result_r, 'short_SNA_recov.yml')

    def test_shutdown_restart_telem(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot for telemetered.
        """
        # slow down sampling to give us time to stop
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        self.create_sample_data_set_dir('short_SNA_SNA.txt', TELEM_DIR)

        # get the metadata and first 2 samples
        result_t = self.data_subscribers.get_samples(DataParticleType.METADATA, 1)
        result_t2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
        result_t.extend(result_t2)

        # stop sampling
        self.assert_stop_sampling()
        # stop the dataset agent
        self.stop_dataset_agent_client()
        # Re-start the agent
        self.init_dataset_agent_client()
        #restart sampling
        self.assert_initialize()

        # should get the last 3 samples
        result_t3 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 3)
        result_t.extend(result_t3)

        # confirm we got particles in the order expected
        self.assert_data_values(result_t, 'short_SNA_telem.yml')
        
    def test_shutdown_restart_recov(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot for recovered.
        """
        # slow down sampling to give us time to stop
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        self.create_sample_data_set_dir('short_SNA_SNA.txt', RECOV_DIR)

        # get the metadata and first 2 samples
        result_r = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1)
        result_r2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 2)
        result_r.extend(result_r2)

        # stop sampling
        self.assert_stop_sampling()
        # stop the dataset agent
        self.stop_dataset_agent_client()
        # Re-start the agent
        self.init_dataset_agent_client()
        #restart sampling
        self.assert_initialize()

        # should get the last 3 samples
        result_r3 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 3)
        result_r.extend(result_r3)

        # confirm we got particles in the order expected
        self.assert_data_values(result_r, 'short_SNA_recov.yml')

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        self.create_sample_data_set_dir('bad_SNA_SNA.txt', RECOV_DIR)

        self.assert_initialize()

        # get just the last sample which is the only not bad sample, which also makes a metadata
        result_r = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1)
        result_r2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE_RECOVERED, 1)
        result_r.extend(result_r2)
        self.assert_data_values(result_r, 'last_and_meta_SNA_recov.yml')

        # confirm an exception occured
        self.assert_event_received(ResourceAgentErrorEvent)

    def test_byte_loss(self):
        """
        Test that a file with known byte loss occuring in the form of hex ascii
        lines of data creates an exception
        """
        self.create_sample_data_set_dir('11330408_SNA_SNA.txt', TELEM_DIR)

        self.assert_initialize()

        # first sample occurs before block of 27 hex ascii lines that produce errors,
        # the second sample occurs after this block
        result_t = self.data_subscribers.get_samples(DataParticleType.METADATA, 1)
        result_t2 = self.data_subscribers.get_samples(DataParticleType.SAMPLE, 2)
        result_t.extend(result_t2)

        # make sure we get the one ok sample in the file and metadata
        self.assert_data_values(result_t, 'byte_loss.yml')

        # confirm an exception occured
        self.assert_event_received(ResourceAgentErrorEvent)
