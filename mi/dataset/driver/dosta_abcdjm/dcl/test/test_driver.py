"""
@package mi.dataset.driver.dosta_abcdjm.dcl.test.test_driver
@file marine-integrations/mi/dataset/driver/dosta_abcdjm/dcl/driver.py
@author Steve Myerson
@brief Test cases for dosta_abcdjm_dcl driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]

In the following files, Metadata consists of 4 records
and Garbled consist of 3 records.
There is 1 group of Sensor Data records for each set of metadata.

Files used for testing:

20010121.dosta1.log
  Metadata - 1 set,  Sensor Data - 21 records,  Garbled - 0,  Newline - \n

20020222.dosta2.log
  Metadata - 2 sets,  Sensor Data - 22 records,  Garbled - 0,  Newline - \r\n

20030314.dosta3.log
  Metadata - 3 sets,  Sensor Data - 14 records,  Garbled - 0,  Newline - \n

20041225.dosta4.log
  Metadata - 2 sets,  Sensor Data - 250 records,  Garbled - 0,  Newline - \n

20050103.dosta5.log
   Metadata - 1 set,  Sensor Data - 3 records,  Garbled - 1,  Newline - \n

20060207.dosta6.log
  Metadata - 2 sets,  Sensor Data - 7 records,  Garbled - 2,  Newline \r\n
"""

__author__ = 'Steve Myerson'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from pyon.agent.agent import ResourceAgentState
from interface.objects import ResourceAgentConnectionLostErrorEvent
from mi.core.log import get_logger; log = get_logger()
from mi.core.instrument.instrument_driver import DriverEvent

from mi.idk.dataset.unit_test import DataSetTestCase
from mi.idk.dataset.unit_test import DataSetIntegrationTestCase
from mi.idk.dataset.unit_test import DataSetQualificationTestCase
from mi.idk.exceptions import SampleTimeout
from mi.idk.result_set import ResultSet

from mi.dataset.dataset_driver import DataSourceConfigKey, DataSetDriverConfigKeys
from mi.dataset.dataset_driver import DriverParameter

from mi.dataset.driver.dosta_abcdjm.dcl.driver import \
    DostaAbcdjmDclDataSetDriver, \
    DataTypeKey

from mi.dataset.parser.dosta_abcdjm_dcl import \
    DostaAbcdjmDclRecoveredInstrumentDataParticle, \
    DostaAbcdjmDclTelemeteredInstrumentDataParticle, \
    DataParticleType

REC_DIR = '/tmp/dsatest_rec'
TEL_DIR = '/tmp/dsatest_tel'

FILE1 = '20010121.dosta1.log'
FILE2 = '20020222.dosta2.log'
FILE3 = '20030314.dosta3.log'
FILE4 = '20041225.dosta4.log'
FILE5 = '20050103.dosta5.log'
FILE6 = '20060207.dosta6.log'

REC_YML1 = 'rec_20010121.dosta1.yml'
REC_YML2 = 'rec_20020222.dosta2.yml'
REC_YML2_LAST14 = 'rec_20020222.dosta2_last14.yml'
REC_YML3 = 'rec_20030314.dosta3.yml'
REC_YML4 = 'rec_20041225.dosta4.yml'
REC_YML5 = 'rec_20050103.dosta5.yml'
REC_YML6 = 'rec_20060207.dosta6.yml'

TEL_YML1 = 'tel_20010121.dosta1.yml'
TEL_YML2 = 'tel_20020222.dosta2.yml'
TEL_YML3 = 'tel_20030314.dosta3.yml'
TEL_YML3_LAST7 = 'tel_20030314.dosta3_last7.yml'
TEL_YML4 = 'tel_20041225.dosta4.yml'
TEL_YML5 = 'tel_20050103.dosta5.yml'
TEL_YML6 = 'tel_20060207.dosta6.yml'

REC_PARTICLE = DostaAbcdjmDclRecoveredInstrumentDataParticle
TEL_PARTICLE = DostaAbcdjmDclTelemeteredInstrumentDataParticle

REC_STREAM = DataParticleType.REC_INSTRUMENT_PARTICLE
TEL_STREAM = DataParticleType.TEL_INSTRUMENT_PARTICLE

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.dosta_abcdjm.dcl.driver',
    driver_class='DostaAbcdjmDclDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = DostaAbcdjmDclDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.DOSTA_ABCDJM_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: REC_DIR,
                DataSetDriverConfigKeys.PATTERN: '[0-9]*.dosta*.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
            DataTypeKey.DOSTA_ABCDJM_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TEL_DIR,
                DataSetDriverConfigKeys.PATTERN: '[0-9]*.dosta*.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.DOSTA_ABCDJM_RECOVERED: {},
            DataTypeKey.DOSTA_ABCDJM_TELEMETERED: {}
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

    def test_big_giant_input(self):
        """
        Test that we can get data from large files.
        """
        log.info("========= START INTEG BIG GIANT INPUT ==============")

        # Create sample data for recovered and telemetered data.
        self.create_sample_data_set_dir(FILE4, REC_DIR)
        self.create_sample_data_set_dir(FILE4, TEL_DIR)

        # Start sampling.
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML4, count=500, timeout=500)
        self.assert_data(TEL_PARTICLE, TEL_YML4, count=500, timeout=500)

        self.driver.stop_sampling()

        log.info("========= END INTEG BIG GIANT INPUT ==============")

    def test_get(self):
        """
        Test that we can get data from multiple files.
        """
        log.info("============ START INTEG TEST GET =================")

        # Create sample data for recovered and telemetered data.
        self.create_sample_data_set_dir(FILE1, REC_DIR)
        self.create_sample_data_set_dir(FILE2, TEL_DIR)

        # Start sampling.
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML1, count=21, timeout=25)
        self.assert_data(TEL_PARTICLE, TEL_YML2, count=44, timeout=50)

        self.driver.stop_sampling()

        log.info("============ END INTEG TEST GET =================")

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        log.info("=== START INTEG TEST HARVESTER NEW FILE EXCEPTION ===")

        # Create the file so that it is unreadable.
        self.create_sample_data_set_dir(FILE1, REC_DIR, mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

        log.info("=== END INTEG TEST HARVESTER NEW FILE EXCEPTION ===")

    def test_mal_formed_records(self):
        """
        This test verifies that files containing mal-formed records are correctly parsed.
        Files contain valid records as well as mal-formed records.
        """
        log.info("====== START INTEG TEST MAL-FORMED RECORDS  ===========")

        self.create_sample_data_set_dir(FILE6, REC_DIR)
        self.create_sample_data_set_dir(FILE5, TEL_DIR)

        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML6, count=14, timeout=20)
        self.assert_data(TEL_PARTICLE, TEL_YML5, count=3, timeout=10)

        log.info("====== END INTEG TEST MAL-FORMED RECORDS  ===========")

    def test_start_stop_resume(self):
        """
        Test the ability to stop and restart sampling, ingesting files in the
        correct order.
        """
        log.info("====== START INTEG TEST START STOP RESUME  ===========")

        self.create_sample_data_set_dir(FILE2, REC_DIR)
        self.create_sample_data_set_dir(FILE3, TEL_DIR)

        self.clear_async_data()
        self.driver.start_sampling()

        # Read the first 8 (of 44) Recovered particles
        # and first 25 (of 42) Telemetered particles.
        log.info("========== FIRST READ  ===============")
        rec_part1 = self.get_samples(REC_PARTICLE, count=8, timeout=10)
        tel_part1 = self.get_samples(TEL_PARTICLE, count=25, timeout=30)

        # Stop and then start sampling, resuming from where we left off.
        self.driver.stop_sampling()
        self.driver.start_sampling()

        # Read the next 13 Recovered particles and next 6 Telemetered particles.
        log.info("========== SECOND READ  ===============")
        tel_part2 = self.get_samples(TEL_PARTICLE, count=6, timeout=20)
        rec_part2 = self.get_samples(REC_PARTICLE, count=13, timeout=20)

        # Read the final 23 Recovered particles and final 11 Telemetered particles.
        log.info("========== FINAL READ  ===============")
        rec_part3 = self.get_samples(REC_PARTICLE, count=23, timeout=30)
        tel_part3 = self.get_samples(TEL_PARTICLE, count=11, timeout=20)

        # Combine results.
        rec_part1.extend(rec_part2)
        rec_part1.extend(rec_part3)
        tel_part1.extend(tel_part2)
        tel_part1.extend(tel_part3)

        # Verify contents of particles.
        self.verify_particle_contents(rec_part1, REC_YML2)
        self.verify_particle_contents(tel_part1, TEL_YML3)

        log.info("===== END INTEG TEST START STOP RESUME  ========")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("===== START INTEG TEST STOP RESUME =====")

        rec_path = self.create_sample_data_set_dir(FILE2, REC_DIR)
        tel_path = self.create_sample_data_set_dir(FILE3, TEL_DIR)

        # Start the recovered parser at end of record 30 (of 44).
        # Start the telemetered parser at end of record 35 (of 42).

        state = {
            DataTypeKey.DOSTA_ABCDJM_RECOVERED: {
                FILE2: self.get_file_state(rec_path, False, 3857)
            },
            DataTypeKey.DOSTA_ABCDJM_TELEMETERED: {
                FILE3: self.get_file_state(tel_path, False, 4694)
            }
        }

        self.driver = self._get_driver_object(memento=state)
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML2_LAST14, count=14, timeout=20)
        self.assert_data(TEL_PARTICLE, TEL_YML3_LAST7, count=7, timeout=10)

        log.info("===== END INTEG TEST STOP RESUME =====")

    def verify_particle_contents(self, particles, result_set_file):
        """
        Verify that the contents of the particles match those in the result file.
        """

        rs_file = self._get_source_data_file(result_set_file)
        rs = ResultSet(rs_file)
        self.assertTrue(rs.verify(particles),
                        msg='Failed Integration test data validation')


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class QualificationTest(DataSetQualificationTestCase):

    def test_harvester_new_file_exception(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        log.debug('===== START QUAL TEST HARVESTER EXCEPTION =====')
        self.create_sample_data_set_dir(FILE1, REC_DIR, mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir(FILE1, REC_DIR)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)
        log.debug('===== END QUAL TEST HARVESTER EXCEPTION =====')

    def test_large_import(self):
        """
        Test a large import
        """
        log.debug('===== START QUAL TEST LARGE IMPORT =====')
        self.create_sample_data_set_dir(FILE4, TEL_DIR)
        self.create_sample_data_set_dir(FILE4, REC_DIR)
        self.assert_initialize()

        self.data_subscribers.get_samples(REC_STREAM, 500, 200)
        self.data_subscribers.get_samples(TEL_STREAM, 500, 200)

        log.debug('===== END QUAL TEST LARGE IMPORT =====')

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.debug('===== START QUAL TEST PUBLISH PATH =====')
        self.create_sample_data_set_dir(FILE1, REC_DIR)
        self.create_sample_data_set_dir(FILE2, REC_DIR)
        self.create_sample_data_set_dir(FILE3, TEL_DIR)

        self.assert_initialize()

        try:
            # Verify we get samples from first Recovered file.
            result = self.data_subscribers.get_samples(REC_STREAM, 21)
            self.assert_data_values(result, REC_YML1)

            # Verify we get samples from first Telemetered file.
            result = self.data_subscribers.get_samples(TEL_STREAM, 42)
            self.assert_data_values(result, TEL_YML3)

            # Verify we get samples from second Recovered file.
            result = self.data_subscribers.get_samples(REC_STREAM, 44)
            self.assert_data_values(result, REC_YML2)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST PUBLISH PATH =====')

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent and
        confirm it restarts at the correct spot.
        """
        log.debug('===== START QUAL TEST SHUTDOWN RESTART =====')

        self.create_sample_data_set_dir(FILE4, REC_DIR)
        self.create_sample_data_set_dir(FILE4, TEL_DIR)
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get the correct samples
        try:
            # Read the first 200 particles from the Recovered file.
            # Read the first 300 particles from the Telemetered file.
            rec_result = self.data_subscribers.get_samples(REC_STREAM, 200, 250)
            tel_result = self.data_subscribers.get_samples(TEL_STREAM, 300, 350)

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()

            # Read the last 200 particles from the Telemetered CT file.
            # Read the last 300 particles from the Recovered file.
            tel_result2 = self.data_subscribers.get_samples(TEL_STREAM, 200, 250)
            rec_result2 = self.data_subscribers.get_samples(REC_STREAM, 300, 350)

            # Combine the results into a single list.
            rec_result.extend(rec_result2)
            tel_result.extend(tel_result2)

            # Verify the results.
            self.assert_data_values(rec_result, REC_YML4)
            self.assert_data_values(tel_result, TEL_YML4)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST SHUTDOWN RESTART =====')

    def test_simple(self):
        """
        Verify that all records from a file can be obtained in a single read.
        """
        log.debug('===== START QUAL TEST SIMPLE =====')

        self.create_sample_data_set_dir(FILE3, REC_DIR)
        self.create_sample_data_set_dir(FILE2, TEL_DIR)
        self.assert_initialize()

        # Verify we get the correct samples
        try:
            # Get the particles.
            tel_result = self.data_subscribers.get_samples(TEL_STREAM, 44, 50)
            rec_result = self.data_subscribers.get_samples(REC_STREAM, 42, 50)

            # Verify results
            self.assert_data_values(tel_result, TEL_YML2)
            self.assert_data_values(rec_result, REC_YML3)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST SIMPLE =====')

    def test_start_stop_restart(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.debug('===== START QUAL TEST START STOP RESTART REC =====')

        self.create_sample_data_set_dir(FILE1, TEL_DIR)
        self.create_sample_data_set_dir(FILE2, REC_DIR)
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get the correct samples
        try:
            # Get the first 7 Telemetered particles.
            # Get the first 28 Recovered particles.
            tel_result = self.data_subscribers.get_samples(TEL_STREAM, 7, 10)
            rec_result = self.data_subscribers.get_samples(REC_STREAM, 28, 30)

            # Stop and then restart sampling.
            self.assert_stop_sampling()
            self.assert_start_sampling()

            # Get the next 8 Recovered particles.
            # Get the last 14 Telemetered particles.
            # Get the last 8 Recovered particles.
            rec_result2 = self.data_subscribers.get_samples(REC_STREAM, 8, 10)
            tel_result2 = self.data_subscribers.get_samples(TEL_STREAM, 14, 20)
            rec_result3 = self.data_subscribers.get_samples(REC_STREAM, 8, 10)

            # Combine results into a single list.
            rec_result.extend(rec_result2)
            rec_result.extend(rec_result3)
            tel_result.extend(tel_result2)

            # Verify results.
            self.assert_data_values(rec_result, REC_YML2)
            self.assert_data_values(tel_result, TEL_YML1)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST START STOP RESTART REC =====')
