"""
@package mi.dataset.driver.dosta_abcdjm.cspp.test.test_driver
@file marine-integrations/mi/dataset/driver/dosta_abcdjm/cspp/driver.py
@author Mark Worden
@brief Test cases for dosta_abcdjm_cspp driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
"""

__author__ = 'Mark Worden'
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
from mi.dataset.driver.dosta_abcdjm.cspp.driver import DostaAbcdjmCsppDataSetDriver, DataTypeKey

from mi.dataset.parser.cspp_base import StateKey

from mi.dataset.parser.dosta_abcdjm_cspp import \
    DostaAbcdjmCsppInstrumentRecoveredDataParticle, \
    DostaAbcdjmCsppInstrumentTelemeteredDataParticle, \
    DostaAbcdjmCsppMetadataRecoveredDataParticle, \
    DostaAbcdjmCsppMetadataTelemeteredDataParticle, \
    DataParticleType

DIR_REC = '/tmp/dsatest_rec'
DIR_TEL = '/tmp/dsatest_tel'

DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.dosta_abcdjm.cspp.driver',
    driver_class='DostaAbcdjmCsppDataSetDriver',
    agent_resource_id='123xyz',
    agent_name='Agent007',
    agent_packet_config=DostaAbcdjmCsppDataSetDriver.stream_config(),
    startup_config={
        DataSourceConfigKey.RESOURCE_ID: 'dosta_abcdjm_cspp',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_REC,
                DataSetDriverConfigKeys.PATTERN: '*_PPB_OPT.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
            DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: DIR_TEL,
                DataSetDriverConfigKeys.PATTERN: '*_PPD_OPT.txt',
                DataSetDriverConfigKeys.FREQUENCY: 1,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED: {},
            DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED: {},
        }
    }
)

REC_PARTICLES = (DostaAbcdjmCsppMetadataRecoveredDataParticle,
                 DostaAbcdjmCsppInstrumentRecoveredDataParticle)
TEL_PARTICLES = (DostaAbcdjmCsppMetadataTelemeteredDataParticle,
                 DostaAbcdjmCsppInstrumentTelemeteredDataParticle)


###############################################################################
#                            INTEGRATION TESTS                                #
# Device specific integration tests are for                                   #
# testing device specific capabilities                                        #
###############################################################################
@attr('INT', group='mi')
class IntegrationTest(DataSetIntegrationTestCase):

    def get_file_state(self, path, ingested=False, position=None, metadata_extracted=False):
        """
        Create a parser state object for a file and return it.
        """

        if position is None:
            position = 0

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
        """

        # Clear the asynchronous callback results
        self.clear_async_data()

        # Notify the driver to start sampling
        self.driver.start_sampling()

        # Test simple recovered data handling
        self.create_sample_data_set_dir('11079419_PPB_OPT.txt', DIR_REC)
        self.assert_data(REC_PARTICLES, '11079419_PPB_OPT.yml', count=20, timeout=10)

        # Test simple telemetered data handling
        self.create_sample_data_set_dir('11194982_PPD_OPT.txt', DIR_TEL)
        self.assert_data(TEL_PARTICLES, '11194982_PPD_OPT.yml', count=18, timeout=10)

    def test_midstate_start(self):
        """
        Test the ability to stop and restart the process
        """

        recovered_file_one = '11079419_PPB_OPT.txt'
        telemetered_file_one = '11194982_PPD_OPT.txt'

        # Clear any existing sampling
        self.clear_sample_data()

        recovered_path_1 = self.create_sample_data_set_dir(recovered_file_one, DIR_REC)
        telemetered_path_1 = self.create_sample_data_set_dir(telemetered_file_one, DIR_TEL)

        state = {
            DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED: {
                recovered_file_one: self.get_file_state(recovered_path_1,
                                                        ingested=False,
                                                        position=521,
                                                        metadata_extracted=True),
            },
            DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED: {
                telemetered_file_one: self.get_file_state(telemetered_path_1,
                                                          ingested=False,
                                                          position=433,
                                                          metadata_extracted=True),
            }
        }

        driver = self._get_driver_object(memento=state)

        # create some data to parse
        self.clear_async_data()

        driver.start_sampling()

        # verify data is produced
        self.assert_data(REC_PARTICLES, 'test_recovered_midstate_start.yml', count=1, timeout=10)

        self.assert_data(TEL_PARTICLES, 'test_telemetered_midstate_start.yml', count=2, timeout=10)

    def test_start_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """

        recovered_file_one = '11079419_PPB_OPT.txt'
        telemetered_file_one = '11194982_PPD_OPT.txt'

        # Clear any existing sampling
        self.clear_sample_data()

        self.create_sample_data_set_dir(recovered_file_one, DIR_REC)
        self.create_sample_data_set_dir(telemetered_file_one, DIR_TEL)

        # create some data to parse
        self.clear_async_data()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(REC_PARTICLES, 'test_recovered_start_stop_resume_one.yml', count=1, timeout=10)

        self.assert_data(TEL_PARTICLES, 'test_telemetered_start_stop_resume_one.yml', count=1, timeout=10)

        self.driver.stop_sampling()

        self.driver.start_sampling()

        # verify data is produced
        self.assert_data(REC_PARTICLES, 'test_recovered_start_stop_resume_two.yml', count=4, timeout=10)

        self.assert_data(TEL_PARTICLES, 'test_telemetered_start_stop_resume_two.yml', count=4, timeout=10)

        self.driver.stop_sampling()

    def test_sample_exception(self):
        """
        Test a case that should produce a sample exception and confirm the
        sample exception occurs
        """
        # Start sampling.
        self.driver.start_sampling()
        self.clear_async_data()

        self.create_sample_data_set_dir('BadDataRecord_PPB_OPT.txt', DIR_REC)

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

        self.create_sample_data_set_dir('11079419_PPB_OPT.txt', DIR_REC)
        self.create_sample_data_set_dir('11194982_PPD_OPT.txt', DIR_TEL)

        self.assert_initialize()

        # get the recovered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 10)
        #get the recovered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 19, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, '11079419_PPB_OPT.yml')

        # get the telemetered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 10)
        # get the telemetered insturment particle
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 17, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, '11194982_PPD_OPT.yml')

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        log.info("=========== START QUAL TEST LARGE IMPORT =================")

        # using the same file for both telemetered and recovered because
        # there are no large telemetered files available at this time
        self.create_sample_data_set_dir('11079364_PPB_OPT.txt', DIR_REC)
        self.create_sample_data_set_dir('11079364_PPB_OPT.txt', DIR_TEL, '11079364_PPD_OPT.txt')

        self.assert_initialize()

        # get the recovered metadata particle
        self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 10)
        #get the recovered instrument particles
        self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 271, 40)

        # get the telemetered metadata particle
        self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 20)
        # # get the telemetered insturment particle
        self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 271, 40)

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.info("=========== START QUAL TEST STOP START =================")

        self.create_sample_data_set_dir('11079419_PPB_OPT.txt', DIR_REC)
        self.create_sample_data_set_dir('11194982_PPD_OPT.txt', DIR_TEL)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # get the recovered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 10)
        #get the first 5 recovered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 5, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, 'test_recovered_stop_start_one.yml')

        # get the telemetered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 10)
        # get the first 9 telemetered insturment particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 9, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, 'test_telemetered_stop_start_one.yml')

        # stop sampling
        self.assert_stop_sampling()

        #restart sampling
        self.assert_start_sampling()

        #get the next 8 recovered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 8, 40)

        self.assert_data_values(result2, 'test_recovered_stop_start_two.yml')

        # get the next 4 telemetered insturment particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 4, 40)

        self.assert_data_values(result2, 'test_telemetered_stop_start_two.yml')

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        log.info("========== START QUAL TEST SHUTDOWN RESTART ===============")

        self.create_sample_data_set_dir('11079419_PPB_OPT.txt', DIR_REC)
        self.create_sample_data_set_dir('11194982_PPD_OPT.txt', DIR_TEL)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # get the recovered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 10)
        #get the first 5 recovered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 5, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, 'test_recovered_stop_start_one.yml')

        # get the telemetered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 10)
        # get the first 9 telemetered insturment particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 9, 40)
        # combine the results
        result1.extend(result2)

        # check the results
        self.assert_data_values(result1, 'test_telemetered_stop_start_one.yml')

        # stop sampling
        self.assert_stop_sampling()

        self.stop_dataset_agent_client()
        # Re-start the agent
        self.init_dataset_agent_client()
        # Re-initialize
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        #restart sampling
        self.assert_start_sampling()

        #get the next 8 recovered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 8, 40)

        self.assert_data_values(result2, 'test_recovered_stop_start_two.yml')

        # get the next 4 telemetered insturment particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 4, 40)

        self.assert_data_values(result2, 'test_telemetered_stop_start_two.yml')


    def test_shutdown_restart_2(self):
        """
        Test a full stop of the dataset agent, then restart the agent
        and confirm it restarts at the correct spot.

        This tests verifies that the parser will restart correctly if only the meta data particle
        was retrieved before being shutdown
        """
        log.info("========== START QUAL TEST SHUTDOWN RESTART 2 ===============")

        self.create_sample_data_set_dir('11079419_PPB_OPT.txt', DIR_REC)
        self.create_sample_data_set_dir('11194982_PPD_OPT.txt', DIR_TEL)

        #put the driver in command mode so it can be started and stopped
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)
        self.dataset_agent_client.set_resource(
            {DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # get the recovered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_RECOVERED, 1, 10)

        # check the results
        self.assert_data_values(result1, 'test_recovered_stop_meta_one.yml')

        # get the telemetered metadata particle
        result1 = self.data_subscribers.get_samples(DataParticleType.METADATA_TELEMETERED, 1, 10)
        # check the results

        self.assert_data_values(result1, 'test_telemetered_stop_meta_one.yml')

        # stop sampling
        self.assert_stop_sampling()

        self.stop_dataset_agent_client()
        # Re-start the agent
        self.init_dataset_agent_client()
        # Re-initialize
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        #restart sampling
        self.assert_start_sampling()

        # verify the metadata queues are empty
        self.assert_sample_queue_size(DataParticleType.METADATA_RECOVERED, 0)
        self.assert_sample_queue_size(DataParticleType.METADATA_TELEMETERED, 0)

        #get the first 5 recovered instrument particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_RECOVERED, 5, 40)

        # check the results
        self.assert_data_values(result2, 'test_recovered_stop_meta_two.yml')

        # get the first 9 telemetered insturment particles
        result2 = self.data_subscribers.get_samples(DataParticleType.INSTRUMENT_TELEMETERED, 9, 40)

        # check the results
        self.assert_data_values(result2, 'test_telemetered_stop_meta_two.yml')

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        log.info("=========== START QUAL TEST PARSER EXCEPTION =================")

        self.create_sample_data_set_dir('BadDataRecord_PPB_OPT.txt', DIR_REC)

        self.assert_initialize()

        self.assert_event_received(ResourceAgentErrorEvent, 10)
