"""
@package mi.dataset.driver.optaa_dj.cspp.test.test_driver
@file marine-integrations/mi/dataset/driver/optaa_dj/cspp/driver.py
@author Joe Padula
@brief Test cases for optaa_dj_cspp driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

import hashlib
import os

from nose.plugins.attrib import attr

from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentErrorEvent

from mi.core.log import get_logger
log = get_logger()

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase

from mi.dataset.dataset_driver import \
    DataSourceConfigKey, \
    DataSetDriverConfigKeys, \
    DriverParameter

from mi.dataset.driver.optaa_dj.cspp.driver import \
    OptaaDjCsppDataSetDriver, \
    DataTypeKey

from mi.dataset.parser.cspp_base import StateKey
from mi.dataset.parser.optaa_dj_cspp import \
    OptaaDjCsppMetadataTelemeteredDataParticle, \
    OptaaDjCsppMetadataRecoveredDataParticle, \
    OptaaDjCsppInstrumentTelemeteredDataParticle, \
    OptaaDjCsppInstrumentRecoveredDataParticle, \
    DataParticleType

DIR_OPTAA_TELEMETERED = '/tmp/optaa/telem/test'
DIR_OPTAA_RECOVERED = '/tmp/optaa/recov/test'

OPTAA_REC_PATTERN = '*ACS_ACS.txt'
OPTAA_TEL_PATTERN = '*ACD_ACS.txt'

RECOVERED_SAMPLE_DATA = '11079364_ACS_ACS.txt'
TELEMETERED_SAMPLE_DATA = '11079364_ACD_ACS.txt'

# Driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.optaa_dj.cspp.driver',
    driver_class='OptaaDjCsppDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=OptaaDjCsppDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'optaa_dj_cspp',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.OPTAA_DJ_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_OPTAA_TELEMETERED,
                DataSetDriverConfigKeys.PATTERN: OPTAA_TEL_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.OPTAA_DJ_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.DIRECTORY: DIR_OPTAA_RECOVERED,
                DataSetDriverConfigKeys.PATTERN: OPTAA_REC_PATTERN,
                DataSetDriverConfigKeys.FREQUENCY: 1,
            }
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.OPTAA_DJ_CSPP_TELEMETERED: {},
            DataTypeKey.OPTAA_DJ_CSPP_RECOVERED: {}
        }
    }
)

REC_PARTICLES = (OptaaDjCsppMetadataRecoveredDataParticle,
                 OptaaDjCsppInstrumentRecoveredDataParticle)
TEL_PARTICLES = (OptaaDjCsppMetadataTelemeteredDataParticle,
                 OptaaDjCsppInstrumentTelemeteredDataParticle)

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
 
    def get_file_state(self, path, ingested=False, position=None, metadata_extracted=False):
        """
        Create a state object for a file. If a position is passed then add a parser state as well.
        """
        mod_time = os.path.getmtime(path)
        file_size = os.path.getsize(path)
        with open(path) as filehandle:
            md5_checksum = hashlib.md5(filehandle.read()).hexdigest()

        parser_state = {
            StateKey.POSITION: position,
            StateKey.METADATA_EXTRACTED: metadata_extracted
        }

        return {
            'ingested': ingested,
            'file_mod_date': mod_time,
            'file_checksum': md5_checksum,
            'file_size': file_size,
            'parser_state': parser_state
        }

    def test_get(self):
        """
        Test that we can get data from files.
        Assert that the particles are correct.
        """
        log.info("================ START INTEG TEST GET =====================")

        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        # test that everything works for the telemetered harvester
        self.create_sample_data_set_dir(TELEMETERED_SAMPLE_DATA, DIR_OPTAA_TELEMETERED)

        log.debug('### Sample file created in dir = %s ', DIR_OPTAA_TELEMETERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(TEL_PARTICLES,
                         '11079364_ACD_ACS_telem.yml',
                         count=20, timeout=60)

        # test that everything works for the recovered harvester
        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, DIR_OPTAA_RECOVERED)

        log.debug('### Sample file created in dir = %s ', DIR_OPTAA_RECOVERED)

        # check the metadata particle and the first 19 instrument particles
        self.assert_data(REC_PARTICLES,
                         '11079364_ACS_ACS_recov.yml',
                         count=20, timeout=60)

    def test_mid_state_start(self):
        """
        Test the ability to start the driver with a saved state
        """
        log.info("================ START INTEG TEST MID STATE START =====================")

        recovered_file_one = RECOVERED_SAMPLE_DATA
        telemetered_file_one = TELEMETERED_SAMPLE_DATA

        recovered_path_1 = self.create_sample_data_set_dir(recovered_file_one, DIR_OPTAA_RECOVERED)
        telemetered_path_1 = self.create_sample_data_set_dir(telemetered_file_one, DIR_OPTAA_TELEMETERED)

        # For recovered, we will assume first 19 records have been processed and put position to 20
        # For telemetered, we will assume first 13 records have been processed and put position to 14
        state = {
            DataTypeKey.OPTAA_DJ_CSPP_RECOVERED: {
                recovered_file_one: self.get_file_state(recovered_path_1,
                                                        ingested=False,
                                                        position=35725,
                                                        metadata_extracted=True),
            },
            DataTypeKey.OPTAA_DJ_CSPP_TELEMETERED: {
                telemetered_file_one: self.get_file_state(telemetered_path_1,
                                                          ingested=False,
                                                          position=24168,
                                                          metadata_extracted=True),
            }
        }

        driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        driver.start_sampling()

        # verify data is produced
        self.assert_data(REC_PARTICLES, 'test_recovered_midstate_start.yml', count=1, timeout=60)

        self.assert_data(TEL_PARTICLES, 'test_telemetered_midstate_start.yml', count=2, timeout=60)

    def test_start_stop_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order
        """
        recovered_file_one = RECOVERED_SAMPLE_DATA
        telemetered_file_one = TELEMETERED_SAMPLE_DATA

        self.create_sample_data_set_dir(recovered_file_one, DIR_OPTAA_RECOVERED)
        self.create_sample_data_set_dir(telemetered_file_one, DIR_OPTAA_TELEMETERED)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(REC_PARTICLES, 'test_recovered_start_stop_resume_one.yml', count=1, timeout=10)

        self.assert_data(TEL_PARTICLES, 'test_telemetered_start_stop_resume_one.yml', count=1, timeout=10)

        self.driver.stop_sampling()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(REC_PARTICLES, 'test_recovered_start_stop_resume_two.yml', count=4, timeout=60)

        self.assert_data(TEL_PARTICLES, 'test_telemetered_start_stop_resume_two.yml', count=4, timeout=10)

        self.driver.stop_sampling()

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        log.info("================ START INTEG TEST SAMPLE EXCEPTION =====================")

        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        # test that everything works for the telemetered harvester
        self.create_sample_data_set_dir('11079364_BAD_ACS_ACS.txt', DIR_OPTAA_RECOVERED)

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
        log.info("=========== START QUAL TEST PUBLISH PATH =================")

        self.create_sample_data_set_dir(TELEMETERED_SAMPLE_DATA, DIR_OPTAA_TELEMETERED)
        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, DIR_OPTAA_RECOVERED)

        self.assert_initialize()

        # get the telemetered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 10)
        #get the telemetered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 19, 620)

        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, '11079364_ACD_ACS_telem.yml')

        # get the recovered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 10)
        # get the recovered instrument particle
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 19, 1000)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, '11079364_ACS_ACS_recov.yml')

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        Assert that we get the correct number of particles
        """
        log.info("=========== START QUAL TEST LARGE IMPORT =================")

        self.create_sample_data_set_dir(TELEMETERED_SAMPLE_DATA, DIR_OPTAA_TELEMETERED)
        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, DIR_OPTAA_RECOVERED)

        self.assert_initialize()

        # get the telemetered metadata particle
        self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 10)
        # get ALL of the telemetered instrument particles
        self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 10, 500)

        # get the recovered metadata particle
        self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 60)
        # get the recovered metadata particle
        self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 200, 10000)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("=========== START QUAL TEST STOP START =================")

        self.create_sample_data_set_dir(TELEMETERED_SAMPLE_DATA, DIR_OPTAA_TELEMETERED)
        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, DIR_OPTAA_RECOVERED)

        # Put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # get the telemetered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 10)
        # get the first 4 telemetered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 4, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, 'test_telemetered_stop_start_one.yml')

        # get the recovered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 10)
        # get the first 7 recovered instrument particle
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 7, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, 'test_recovered_stop_start_one.yml')

        # stop sampling
        self.assert_stop_sampling()

        # restart sampling
        self.assert_start_sampling()

        # get the next 12 telemetered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 12, 180)

        # check the results
        self.assert_data_values(result2, 'test_telemetered_stop_start_two.yml')

        # get the next 8 recovered instrument particle
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 8, 180)

        # check the results
        self.assert_data_values(result2, 'test_recovered_stop_start_two.yml')

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("=========== START QUAL TEST SHUTDOWN RESTART =================")

        self.create_sample_data_set_dir(TELEMETERED_SAMPLE_DATA, DIR_OPTAA_TELEMETERED)
        self.create_sample_data_set_dir(RECOVERED_SAMPLE_DATA, DIR_OPTAA_RECOVERED)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # get the telemetered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 10)
        #get the first 4 telemetered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 4, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, 'test_telemetered_stop_start_one.yml')

        # get the recovered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 10)
        # get the first 7 recovered instrument particle
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 7, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, 'test_recovered_stop_start_one.yml')

        # stop sampling
        self.assert_stop_sampling()

        self.stop_dataset_agent_client()
        # Re-start the agent
        self.init_dataset_agent_client()
        # Re-initialize and enter streaming state
        self.assert_initialize()

        # get the next 12 telemetered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 12, 240)

        # check the results
        self.assert_data_values(result2, 'test_telemetered_stop_start_two.yml')

        # get the next 8 recovered instrument particle
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 8, 240)

        # check the results
        self.assert_data_values(result2, 'test_recovered_stop_start_two.yml')

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        log.info("=========== START QUAL TEST PARSER EXCEPTION =================")

        self.create_sample_data_set_dir('11079364_BAD_ACS_ACS.txt', DIR_OPTAA_RECOVERED)

        self.assert_initialize()

        self.assert_event_received(ResourceAgentErrorEvent, 60)


