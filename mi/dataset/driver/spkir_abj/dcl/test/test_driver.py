"""
@package mi.dataset.driver.spkir_abj.dcl.test.test_driver
@file marine-integrations/mi/dataset/driver/spkir_abj/dcl/driver.py
@author Steve Myerson
@brief Test cases for spkir_abj_dcl driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/dsa/test_driver
       $ bin/dsa/test_driver -i [-t testname]
       $ bin/dsa/test_driver -q [-t testname]

Files used for testing:

20020113.spkir2.log
  Metadata - 1 set,  Sensor Data - 13 records

20030208.spkir3.log
  Metadata - 2 sets,  Sensor Data - 8 records

20040305.spkir4.log
  Metadata - 3 sets,  Sensor Data - 5 records

20050403.spkir5.log
  Metadata - 4 sets,  Sensor Data - 3 records

20061220.spkir6.log
  Metadata - 1 set,  Sensor Data - 400 records

20071225.spkir7.log
  Metadata - 2 sets,  Sensor Data - 250 records
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

from mi.dataset.driver.spkir_abj.dcl.driver import \
    SpkirAbjDclDataSetDriver, \
    DataTypeKey

from mi.dataset.parser.spkir_abj_dcl import \
    SpkirAbjDclRecoveredInstrumentDataParticle, \
    SpkirAbjDclTelemeteredInstrumentDataParticle, \
    SpkirDataParticleType

REC_DIR = '/tmp/dsatest_rec'
TEL_DIR = '/tmp/dsatest_tel'

FILE2 = '20020113.spkir2.log'
FILE3 = '20030208.spkir3.log'
FILE4 = '20040305.spkir4.log'
FILE5 = '20050403.spkir5.log'
FILE6 = '20061220.spkir6.log'
FILE7 = '20071225.spkir7.log'

REC_YML2 = 'rec_20020113.spkir2.yml'
REC_YML3 = 'rec_20030208.spkir3.yml'
REC_YML4 = 'rec_20040305.spkir4.yml'
REC_YML4_LAST4 = 'rec_20040305.spkir4_last4.yml'
REC_YML5 = 'rec_20050403.spkir5.yml'
REC_YML6 = 'rec_20061220.spkir6.yml'
REC_YML7 = 'rec_20071225.spkir7.yml'

TEL_YML2 = 'tel_20020113.spkir2.yml'
TEL_YML3 = 'tel_20030208.spkir3.yml'
TEL_YML4 = 'tel_20040305.spkir4.yml'
TEL_YML5 = 'tel_20050403.spkir5.yml'
TEL_YML5_LAST6 = 'tel_20050403.spkir5_last6.yml'
TEL_YML6 = 'tel_20061220.spkir6.yml'
TEL_YML7 = 'tel_20071225.spkir7.yml'

REC_PARTICLE = SpkirAbjDclRecoveredInstrumentDataParticle
TEL_PARTICLE = SpkirAbjDclTelemeteredInstrumentDataParticle

REC_STREAM = SpkirDataParticleType.REC_INSTRUMENT_PARTICLE
TEL_STREAM = SpkirDataParticleType.TEL_INSTRUMENT_PARTICLE

# Fill in driver details
DataSetTestCase.initialize(
    driver_module='mi.dataset.driver.spkir_abj.dcl.driver',
    driver_class='SpkirAbjDclDataSetDriver',
    agent_resource_id = '123xyz',
    agent_name = 'Agent007',
    agent_packet_config = SpkirAbjDclDataSetDriver.stream_config(),
    startup_config = {
        DataSourceConfigKey.HARVESTER:
        {
            DataTypeKey.SPKIR_ABJ_RECOVERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: REC_DIR,
                DataSetDriverConfigKeys.PATTERN: '[0-9]*.spkir*.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
            DataTypeKey.SPKIR_ABJ_TELEMETERED:
            {
                DataSetDriverConfigKeys.DIRECTORY: TEL_DIR,
                DataSetDriverConfigKeys.PATTERN: '[0-9]*.spkir*.log',
                DataSetDriverConfigKeys.FREQUENCY: 1,
                DataSetDriverConfigKeys.FILE_MOD_WAIT_TIME: 30,
            },
        },
        DataSourceConfigKey.PARSER: {
            DataTypeKey.SPKIR_ABJ_RECOVERED: {},
            DataTypeKey.SPKIR_ABJ_TELEMETERED: {}
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
        self.create_sample_data_set_dir(FILE6, REC_DIR)
        self.create_sample_data_set_dir(FILE7, TEL_DIR)

        # Start sampling.
        self.clear_async_data()
        self.driver.start_sampling()

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML6, count=400, timeout=400)
        self.assert_data(TEL_PARTICLE, TEL_YML7, count=500, timeout=500)

        self.driver.stop_sampling()

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
        self.assert_data(REC_PARTICLE, REC_YML3, count=16, timeout=20)
        self.assert_data(TEL_PARTICLE, TEL_YML2, count=13, timeout=20)

        # Create more sample data for recovered and telemetered data.
        self.create_sample_data_set_dir(FILE4, REC_DIR)
        self.create_sample_data_set_dir(FILE5, TEL_DIR)

        # Read the particles and verify contents.
        self.assert_data(REC_PARTICLE, REC_YML4, count=15, timeout=20)
        self.assert_data(TEL_PARTICLE, TEL_YML5, count=12, timeout=20)

        self.driver.stop_sampling()

        log.info("============ END INTEG TEST GET =================")

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

        # Read the first 5 (of 13) Recovered particles
        # and first 11 (of 16) Telemetered particles.
        log.info("========== FIRST READ  ===============")
        rec_part1 = self.get_samples(REC_PARTICLE, count=5, timeout=10)
        tel_part1 = self.get_samples(TEL_PARTICLE, count=11, timeout=20)

        # Stop and then start sampling, resuming from where we left off.
        self.driver.stop_sampling()
        self.driver.start_sampling()

        # Read the final 8 Recovered particles and final 5 Telemetered particles.
        log.info("========== SECOND READ  ===============")
        tel_part2 = self.get_samples(TEL_PARTICLE, count=5, timeout=20)
        rec_part2 = self.get_samples(REC_PARTICLE, count=8, timeout=20)

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

        # Start the recovered parser at end of record 12 (of 15).
        # Start the telemetered parser at end of record 7 (of 12).

        state = {
            DataTypeKey.SPKIR_ABJ_RECOVERED: {
                FILE4: self.get_file_state(rec_path, False, 1854)
            },
            DataTypeKey.SPKIR_ABJ_TELEMETERED: {
                FILE5: self.get_file_state(tel_path, False, 1434)
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

    def test_publish_path(self):
        """
        Setup an agent/driver/harvester/parser and verify that data is
        published out the agent
        """
        pass

    def test_large_import(self):
        """
        Test importing a large number of samples from the file at once
        """
        pass

    def test_stop_start(self):
        """
        Test the agents ability to start data flowing, stop, then restart
        at the correct spot.
        """
        pass

    def test_shutdown_restart(self):
        """
        Test a full stop of the dataset agent, then restart the agent 
        and confirm it restarts at the correct spot.
        """
        pass

    def test_parser_exception(self):
        """
        Test an exception is raised after the driver is started during
        record parsing.
        """
        pass

