"""
@package mi.dataset.driver.flort_dj.dcl.test.test_driver
@file marine-integrations/mi/dataset/driver/flort_dj/dcl/driver.py
@author Steve Myerson
@brief Test cases for flort_dj_dcl driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]

In the following files, Metadata consists of 4 records.
There is 1 group of Sensor Data records for each set of metadata.

Files used for testing:

20020215.flort2.log
  Metadata - 2 sets,  Sensor Data - 15 records

20030413.flort3.log
  Metadata - 4 sets,  Sensor Data - 13 records

20040505.flort4.log
  Metadata - 5 sets,  Sensor Data - 5 records

20050406.flort5.log
  Metadata - 4 sets,  Sensor Data - 6 records

20061220.flort6.log
  Metadata - 1 set,  Sensor Data - 300 records

20071225.flort7.log
  Metadata - 2 sets,  Sensor Data - 200 records
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

from mi.dataset.driver.flort_dj.dcl.driver import \
    FlortDjDclDataSetDriver, \
    DataTypeKey

from mi.dataset.parser.flort_dj_dcl import \
    FlortDjDclRecoveredInstrumentDataParticle, \
    FlortDjDclTelemeteredInstrumentDataParticle, \
    DataParticleType

REC_DIR = '/tmp/dsatest_rec'
TEL_DIR = '/tmp/dsatest_tel'

FILE2 = '20020215.flort2.log'
FILE3 = '20030413.flort3.log'
FILE4 = '20040505.flort4.log'
FILE5 = '20050406.flort5.log'
FILE6 = '20061220.flort6.log'
FILE7 = '20071225.flort7.log'
FILE_REAL = '20140101.flort_real.log'

REC_YML2 = 'rec_20020215.flort2.yml'
REC_YML3 = 'rec_20030413.flort3.yml'
REC_YML4 = 'rec_20040505.flort4.yml'
REC_YML4_LAST4 = 'rec_20040505.flort4_last4.yml'
REC_YML5 = 'rec_20050406.flort5.yml'
REC_YML6 = 'rec_20061220.flort6.yml'
REC_YML7 = 'rec_20071225.flort7.yml'
REC_YML_REAL = 'rec_20140101.flort_real.yml'

TEL_YML2 = 'tel_20020215.flort2.yml'
TEL_YML3 = 'tel_20030413.flort3.yml'
TEL_YML4 = 'tel_20040505.flort4.yml'
TEL_YML5 = 'tel_20050406.flort5.yml'
TEL_YML5_LAST6 = 'tel_20050406.flort5_last6.yml'
TEL_YML6 = 'tel_20061220.flort6.yml'
TEL_YML7 = 'tel_20071225.flort7.yml'
TEL_YML_REAL = 'tel_20140101.flort_real.yml'

# Number of expected particles from the file.
EXPECTED_FILE2 = 30
EXPECTED_FILE3 = 52
EXPECTED_FILE4 = 25
EXPECTED_FILE5 = 24
EXPECTED_FILE6 = 300
EXPECTED_FILE7 = 400

REC_PARTICLE = FlortDjDclRecoveredInstrumentDataParticle
TEL_PARTICLE = FlortDjDclTelemeteredInstrumentDataParticle

REC_STREAM = DataParticleType.REC_INSTRUMENT_PARTICLE
TEL_STREAM = DataParticleType.TEL_INSTRUMENT_PARTICLE

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.flort_dj.dcl.driver',
    driver_class='FlortDjDclDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = FlortDjDclDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.FLORT_DJ_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: REC_DIR,
                DataSetDriverConfigKeys.PATTERN: '[0-9]*.flort*.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
            DataTypeKey.FLORT_DJ_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TEL_DIR,
                DataSetDriverConfigKeys.PATTERN: '[0-9]*.flort*.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.FLORT_DJ_RECOVERED: {},
            DataTypeKey.FLORT_DJ_TELEMETERED: {}
        }
    }
)


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
        self.create_sample_data_set_dir(FILE6, REC_DIR)
        self.create_sample_data_set_dir(FILE7, TEL_DIR)

        # Start sampling.
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML6,
                         count=EXPECTED_FILE6, timeout=EXPECTED_FILE6)
        self.assert_data(TEL_PARTICLE, TEL_YML7,
                         count=EXPECTED_FILE7, timeout=EXPECTED_FILE7)

        log.info("========= END INTEG BIG GIANT INPUT ==============")

    def test_get(self):
        """
        Test that we can get data from multiple files.
        """
        log.info("============ START INTEG TEST GET =================")

        # Create sample data for recovered and telemetered data.
        self.create_sample_data_set_dir(FILE3, REC_DIR)
        self.create_sample_data_set_dir(FILE2, TEL_DIR)

        # Start sampling.
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML3,
                         count=EXPECTED_FILE3, timeout=EXPECTED_FILE3)
        self.assert_data(TEL_PARTICLE, TEL_YML2,
                         count=EXPECTED_FILE2, timeout=EXPECTED_FILE2)

        # Create more sample data for recovered and telemetered data.
        self.create_sample_data_set_dir(FILE4, REC_DIR)
        self.create_sample_data_set_dir(FILE5, TEL_DIR)

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML4,
                         count=EXPECTED_FILE4, timeout=EXPECTED_FILE4)
        self.assert_data(TEL_PARTICLE, TEL_YML5,
                         count=EXPECTED_FILE5, timeout=EXPECTED_FILE5)

        self.driver.stop_sampling()

        log.info("============ END INTEG TEST GET =================")

    def test_harvester_new_file_exception(self):
        """
        Must override the default test_harvester_new_file_exception because
        it won't handle file patterns that are anything other than '*.'
        """
        pass

    def test_harvester_new_file_exception_rec(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        log.info("=== START INTEG TEST HARVESTER NEW FILE EXCEPTION REC ===")

        # Create the file so that it is unreadable.
        self.create_sample_data_set_dir(FILE4, REC_DIR, mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

        log.info("=== END INTEG TEST HARVESTER NEW FILE EXCEPTION REC ===")

    def test_harvester_new_file_exception_tel(self):
        """
        Test an exception raised after the driver is started during
        the file read.  Should call the exception callback.
        """
        log.info("=== START INTEG TEST HARVESTER NEW FILE EXCEPTION TEL ===")

        # Create the file so that it is unreadable.
        self.create_sample_data_set_dir(FILE4, TEL_DIR, mode=000)

        # Start sampling and watch for an exception
        self.driver.start_sampling()

        self.assert_exception(IOError)

        # At this point the harvester thread is dead.  The agent
        # exception handle should handle this case.

        log.info("=== END INTEG TEST HARVESTER NEW FILE EXCEPTION TEL ===")

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

        # Read the first 5 (of 30) Recovered particles
        # and first 41 (of 52) Telemetered particles.
        log.info("========== FIRST READ  ===============")
        rec_part1 = self.get_samples(REC_PARTICLE, count=5, timeout=10)
        tel_part1 = self.get_samples(TEL_PARTICLE, count=41, timeout=50)

        # Stop and then start sampling, resuming from where we left off.
        self.driver.stop_sampling()
        self.driver.start_sampling()

        # Read the final 25 Recovered particles and final 11 Telemetered particles.
        log.info("========== SECOND READ  ===============")
        tel_part2 = self.get_samples(TEL_PARTICLE, count=11, timeout=30)
        rec_part2 = self.get_samples(REC_PARTICLE, count=25, timeout=20)

        # Combine results.
        rec_part1.extend(rec_part2)
        tel_part1.extend(tel_part2)

        # Verify contents of particles.
        self.verify_particle_contents(rec_part1, REC_YML2)
        self.verify_particle_contents(tel_part1, TEL_YML3)

        log.info("===== END INTEG TEST START STOP RESUME  ========")

    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("===== START INTEG TEST STOP RESUME =====")

        rec_path = self.create_sample_data_set_dir(FILE4, REC_DIR)
        tel_path = self.create_sample_data_set_dir(FILE5, TEL_DIR)

        # Start the recovered parser at end of record 21 (of 25).
        # Start the telemetered parser at end of record 18 (of 24).

        state = {
            DataTypeKey.FLORT_DJ_RECOVERED: {
                FILE4: self.get_file_state(rec_path, False, 2851)
            },
            DataTypeKey.FLORT_DJ_TELEMETERED: {
                FILE5: self.get_file_state(tel_path, False, 2373)
            }
        }

        self.driver = self._get_driver_object(memento=state)
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML4_LAST4, count=4, timeout=10)
        self.assert_data(TEL_PARTICLE, TEL_YML5_LAST6, count=6, timeout=10)

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
        Must override the default test_harvester_new_file_exception because
        it won't handle file patterns that are anything other than '*.'
        """
        pass

    def test_harvester_new_file_exception_rec(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        log.debug('===== START QUAL TEST HARVESTER EXCEPTION REC =====')
        self.create_sample_data_set_dir(FILE6, REC_DIR, mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir(FILE5, REC_DIR)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)
        log.debug('===== END QUAL TEST HARVESTER EXCEPTION REC =====')

    def test_harvester_new_file_exception_tel(self):
        """
        Test an exception raised after the driver is started during
        the file read.

        exception callback called.
        """
        log.debug('===== START QUAL TEST HARVESTER EXCEPTION REC =====')
        self.create_sample_data_set_dir(FILE6, TEL_DIR, mode=000)

        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        self.event_subscribers.clear_events()
        self.assert_resource_command(DriverEvent.START_AUTOSAMPLE)
        self.assert_state_change(ResourceAgentState.LOST_CONNECTION, 90)
        self.assert_event_received(ResourceAgentConnectionLostErrorEvent, 10)

        self.clear_sample_data()
        self.create_sample_data_set_dir(FILE5, TEL_DIR)

        # Should automatically retry connect and transition to streaming
        self.assert_state_change(ResourceAgentState.STREAMING, 90)
        log.debug('===== END QUAL TEST HARVESTER EXCEPTION REC =====')

    def test_large_import(self):
        """
        Test a large import
        """
        log.debug('===== START QUAL TEST LARGE IMPORT =====')
        self.create_sample_data_set_dir(FILE7, TEL_DIR)
        self.create_sample_data_set_dir(FILE6, REC_DIR)
        self.assert_initialize()

        self.data_subscribers.get_samples(REC_STREAM, EXPECTED_FILE6, EXPECTED_FILE6)
        self.data_subscribers.get_samples(TEL_STREAM, EXPECTED_FILE7, EXPECTED_FILE7)

        log.debug('===== END QUAL TEST LARGE IMPORT =====')

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        log.debug('===== START QUAL TEST PUBLISH PATH =====')
        self.create_sample_data_set_dir(FILE2, REC_DIR)
        self.create_sample_data_set_dir(FILE4, REC_DIR)
        self.create_sample_data_set_dir(FILE3, TEL_DIR)
        self.create_sample_data_set_dir(FILE5, TEL_DIR)

        self.assert_initialize()

        try:
            # Verify we get samples from first Telemetered file.
            result = self.data_subscribers.get_samples(TEL_STREAM, EXPECTED_FILE3)
            self.assert_data_values(result, TEL_YML3)

            # Verify we get samples from first Recovered file.
            result = self.data_subscribers.get_samples(REC_STREAM, EXPECTED_FILE2)

            self.assert_data_values(result, REC_YML2)

            # Verify we get samples from second Recovered file.
            result = self.data_subscribers.get_samples(REC_STREAM, EXPECTED_FILE4)
            self.assert_data_values(result, REC_YML4)

            # Verify we get samples from second Telemetered file.
            result = self.data_subscribers.get_samples(TEL_STREAM, EXPECTED_FILE5)
            self.assert_data_values(result, TEL_YML5)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST PUBLISH PATH =====')

    def test_real_file(self):
        """
        Verify that records from a real file can be obtained.
        The first 3 and last 3 records will be verified.
        The file contains 108 records.
        """
        log.debug('===== START QUAL TEST REAL FILE =====')

        self.create_sample_data_set_dir(FILE_REAL, REC_DIR)
        self.create_sample_data_set_dir(FILE_REAL, TEL_DIR)
        self.assert_initialize()

        # Verify we get the correct samples
        try:
            # Get the first 3 particles.
            rec_result = self.data_subscribers.get_samples(REC_STREAM, 3, 10)
            tel_result = self.data_subscribers.get_samples(TEL_STREAM, 3, 10)

            # Ignore the next 102 particles.
            self.data_subscribers.get_samples(REC_STREAM, 93, 150)
            self.data_subscribers.get_samples(TEL_STREAM, 93, 150)

            # Get the last 3 particles and combine with the first 3.
            rec_result2 = self.data_subscribers.get_samples(REC_STREAM, 3, 10)
            tel_result2 = self.data_subscribers.get_samples(TEL_STREAM, 3, 10)

            rec_result.extend(rec_result2)
            tel_result.extend(tel_result2)

            # Verify results
            self.assert_data_values(rec_result, REC_YML_REAL)
            self.assert_data_values(tel_result, TEL_YML_REAL)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST REAL FILE =====')

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent and
        confirm it restarts at the correct spot.
        """
        log.debug('===== START QUAL TEST SHUTDOWN RESTART =====')

        self.create_sample_data_set_dir(FILE2, REC_DIR)
        self.create_sample_data_set_dir(FILE3, TEL_DIR)
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get the correct samples
        try:
            # Read the first 7 particles from the Recovered file.
            # Read the first 18 particles from the Telemetered file.
            rec_result = self.data_subscribers.get_samples(REC_STREAM, 7, 10)
            tel_result = self.data_subscribers.get_samples(TEL_STREAM, 18, 20)

            # stop and re-start the agent
            self.stop_dataset_agent_client()
            self.init_dataset_agent_client()
            # re-initialize
            self.assert_initialize()

            # Read the last 34 particles from the Telemetered CT file.
            # Read the last 23 particles from the Recovered file.
            tel_result2 = self.data_subscribers.get_samples(TEL_STREAM, 34, 40)
            rec_result2 = self.data_subscribers.get_samples(REC_STREAM, 23, 30)

            # Combine the results into a single list.
            rec_result.extend(rec_result2)
            tel_result.extend(tel_result2)

            # Verify the results.
            self.assert_data_values(rec_result, REC_YML2)
            self.assert_data_values(tel_result, TEL_YML3)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST SHUTDOWN RESTART =====')

    def test_simple(self):
        """
        Verify that all records from a file can be obtained in a single read.
        """
        log.debug('===== START QUAL TEST SIMPLE =====')

        self.create_sample_data_set_dir(FILE5, REC_DIR)
        self.create_sample_data_set_dir(FILE4, TEL_DIR)
        self.assert_initialize()

        # Verify we get the correct samples
        try:
            # Get the particles.
            tel_result = self.data_subscribers.get_samples(TEL_STREAM, 25, 30)
            rec_result = self.data_subscribers.get_samples(REC_STREAM, 24, 30)

            # Verify results
            self.assert_data_values(tel_result, TEL_YML4)
            self.assert_data_values(rec_result, REC_YML5)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST SIMPLE =====')

    def test_start_stop_restart(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        log.debug('===== START QUAL TEST START STOP RESTART =====')

        self.create_sample_data_set_dir(FILE6, TEL_DIR)
        self.create_sample_data_set_dir(FILE7, REC_DIR)
        self.assert_initialize(final_state=ResourceAgentState.COMMAND)

        # Slow down processing to 1 per second to give us time to stop
        self.dataset_agent_client.set_resource({DriverParameter.RECORDS_PER_SECOND: 1})
        self.assert_start_sampling()

        # Verify we get the correct samples
        try:
            # Get the first 100 Telemetered particles.
            # Get the first 125 Recovered particles.
            tel_result = self.data_subscribers.get_samples(TEL_STREAM, 100, 125)
            rec_result = self.data_subscribers.get_samples(REC_STREAM, 125, 150)

            # Stop and then restart sampling.
            self.assert_stop_sampling()
            self.assert_start_sampling()

            # Get the next 200 Recovered particles.
            # Get the last 200 Telemetered particles.
            # Get the last 75 Recovered particles.
            rec_result2 = self.data_subscribers.get_samples(REC_STREAM, 200, 250)
            tel_result2 = self.data_subscribers.get_samples(TEL_STREAM, 200, 250)
            rec_result3 = self.data_subscribers.get_samples(REC_STREAM, 75, 100)

            # Combine results into a single list.
            rec_result.extend(rec_result2)
            rec_result.extend(rec_result3)
            tel_result.extend(tel_result2)

            # Verify results.
            self.assert_data_values(rec_result, REC_YML7)
            self.assert_data_values(tel_result, TEL_YML6)

        except SampleTimeout as e:
            log.error("Exception trapped: %s", e, exc_info=True)
            self.fail("Sample timeout.")

        log.debug('===== END QUAL TEST START STOP RESTART =====')