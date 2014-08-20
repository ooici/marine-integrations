"""
@package mi.dataset.driver.optaa_dj.dcl.test.test_driver
@file marine-integrations/mi/dataset/driver/optaa_dj/dcl/driver.py
@author Steve Myerson (Raytheon)
@brief Test cases for optaa_dj_dcl driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]
       
Files used for testing:

20010314_010314.optaa1.log
  Records - 3, Measurements - 1, 3, 14

20020704_020704.optaa2.log
  Records - 5, Measurements - 0, 2, 7, 4, 27

20031031_031031.optaa3.log
  Records - 3, Measurements - 50, 255, 125

20041220_041220.optaa4.log
  Records - 4, Measurements - 255, 175, 150, 255

20061225_061225.optaa6.log
  Records - 10, Measurements - 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
"""

__author__ = 'Steve Myerson (Raytheon)'
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

from mi.dataset.driver.optaa_dj.dcl.driver import \
    OptaaDjDclDataSetDriver, \
    DataTypeKey

from mi.dataset.parser.optaa_dj_dcl import \
    OptaaDjDclRecoveredInstrumentDataParticle, \
    OptaaDjDclRecoveredMetadataDataParticle, \
    OptaaDjDclTelemeteredInstrumentDataParticle, \
    OptaaDjDclTelemeteredMetadataDataParticle, \
    OptaaStateKey, \
    DataParticleType

REC_DIR = '/tmp/dsatest_rec'
TEL_DIR = '/tmp/dsatest_tel'

FILE1 = '20010314_010314.optaa1.log'
FILE2 = '20020704_020704.optaa2.log'
FILE3 = '20031031_031031.optaa3.log'
FILE4 = '20041220_041220.optaa4.log'
FILE6 = '20061225_061225.optaa6.log'

REC_YML1 = 'rec_20010314_010314.optaa1.yml'
REC_YML2 = 'rec_20020704_020704.optaa2.yml'
REC_YML3 = 'rec_20031031_031031.optaa3.yml'
REC_YML4 = 'rec_20041220_041220.optaa4.yml'
REC_YML6 = 'rec_20061225_061225.optaa6.yml'
REC_YML6_LAST6 = 'rec_20061225_061225.optaa6_last6.yml'

TEL_YML1 = 'tel_20010314_010314.optaa1.yml'
TEL_YML2 = 'tel_20020704_020704.optaa2.yml'
TEL_YML3 = 'tel_20031031_031031.optaa3.yml'
TEL_YML4 = 'tel_20041220_041220.optaa4.yml'
TEL_YML4_LAST3 = 'tel_20041220_041220.optaa4_last3.yml'
TEL_YML6 = 'tel_20061225_061225.optaa6.yml'

# Number of expected particles from the file.
EXPECTED_FILE1 = 4
EXPECTED_FILE2 = 6
EXPECTED_FILE3 = 4
EXPECTED_FILE4 = 5
EXPECTED_FILE6 = 11

REC_PARTICLE = (OptaaDjDclRecoveredInstrumentDataParticle,
                OptaaDjDclRecoveredMetadataDataParticle)
TEL_PARTICLE = (OptaaDjDclTelemeteredInstrumentDataParticle,
                OptaaDjDclTelemeteredMetadataDataParticle)

REC_INST_STREAM = DataParticleType.REC_INSTRUMENT_PARTICLE
REC_META_STREAM = DataParticleType.REC_METADATA_PARTICLE
TEL_INST_STREAM = DataParticleType.TEL_INSTRUMENT_PARTICLE
TEL_META_STREAM = DataParticleType.TEL_METADATA_PARTICLE

PARSER_STATE = 'parser_state'

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.optaa_dj.dcl.driver',
    driver_class='OptaaDjDclDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = OptaaDjDclDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.RESOURCE_ID: 'optaa_dj_dcl',
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.OPTAA_DJ_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: REC_DIR,
                DataSetDriverConfigKeys.PATTERN: '[0-9]*_[0-9]*.optaa*.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
            DataTypeKey.OPTAA_DJ_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TEL_DIR,
                DataSetDriverConfigKeys.PATTERN: '[0-9]*_[0-9]*.optaa*.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.OPTAA_DJ_RECOVERED: {},
            DataTypeKey.OPTAA_DJ_TELEMETERED: {}
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
        self.create_sample_data_set_dir(FILE4, TEL_DIR)

        # Start sampling.
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML6,
                         count=EXPECTED_FILE6, timeout=EXPECTED_FILE6)
        self.assert_data(TEL_PARTICLE, TEL_YML4,
                         count=EXPECTED_FILE4, timeout=EXPECTED_FILE4)

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
        self.assert_data(REC_PARTICLE, REC_YML1,
                         count=EXPECTED_FILE1, timeout=EXPECTED_FILE1)
        self.assert_data(TEL_PARTICLE, TEL_YML2,
                         count=EXPECTED_FILE2, timeout=EXPECTED_FILE2)

        # Create more sample data for recovered and telemetered data.
        self.create_sample_data_set_dir(FILE3, REC_DIR)
        self.create_sample_data_set_dir(FILE4, TEL_DIR)

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML3,
                         count=EXPECTED_FILE3, timeout=EXPECTED_FILE3)
        self.assert_data(TEL_PARTICLE, TEL_YML4,
                         count=EXPECTED_FILE4, timeout=EXPECTED_FILE4)

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
        self.create_sample_data_set_dir(FILE6, TEL_DIR, mode=000)

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
        self.create_sample_data_set_dir(FILE6, TEL_DIR)

        self.clear_async_data()
        self.driver.start_sampling()

        # Read the first 4 (of 6) Recovered particles
        # and first 3 (of 11) Telemetered particles.
        log.info("========== FIRST READ  ===============")
        rec_part1 = self.get_samples(REC_PARTICLE, count=4, timeout=10)
        tel_part1 = self.get_samples(TEL_PARTICLE, count=3, timeout=10)

        # Stop and then start sampling, resuming from where we left off.
        self.driver.stop_sampling()
        self.driver.start_sampling()

        # Read the final 2 Recovered particles and final 8 Telemetered particles.
        log.info("========== SECOND READ  ===============")
        tel_part2 = self.get_samples(TEL_PARTICLE, count=8, timeout=10)
        rec_part2 = self.get_samples(REC_PARTICLE, count=2, timeout=10)

        # Combine results.
        rec_part1.extend(rec_part2)
        tel_part1.extend(tel_part2)

        # Verify contents of particles.
        self.verify_particle_contents(rec_part1, REC_YML2)
        self.verify_particle_contents(tel_part1, TEL_YML6)

        log.info("===== END INTEG TEST START STOP RESUME  ========")
        
    def test_stop_resume(self):
        """
        Test the ability to stop and restart the process
        """
        log.info("===== START INTEG TEST STOP RESUME =====")

        rec_path = self.create_sample_data_set_dir(FILE6, REC_DIR)
        tel_path = self.create_sample_data_set_dir(FILE4, TEL_DIR)

        # Start the recovered parser at end of record 4 (of 10).
        # Start the telemetered parser at end of record 1 (of 4).

        rec_key = DataTypeKey.OPTAA_DJ_RECOVERED
        tel_key = DataTypeKey.OPTAA_DJ_TELEMETERED

        state = {
            rec_key: {
                FILE6: self.get_file_state(rec_path, False, 220)
            },
            tel_key: {
                FILE4: self.get_file_state(tel_path, False, 2075)
            }
        }
        state[rec_key][FILE6][PARSER_STATE][OptaaStateKey.TIME_SINCE_POWER_UP] = 0.666
        state[rec_key][FILE6][PARSER_STATE][OptaaStateKey.METADATA_GENERATED] = True

        state[tel_key][FILE4][PARSER_STATE][OptaaStateKey.TIME_SINCE_POWER_UP] = 0.444
        state[tel_key][FILE4][PARSER_STATE][OptaaStateKey.METADATA_GENERATED] = True

        self.driver = self._get_driver_object(memento=state)
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML6_LAST6, count=6, timeout=10)
        self.assert_data(TEL_PARTICLE, TEL_YML4_LAST3, count=3, timeout=10)

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

