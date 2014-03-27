#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_vel3d_k_wfp_stc
@file marine-integrations/mi/dataset/parser/test/test_vel3d_k_wfp_stc.py
@author Steve Myerson (Raytheon)
@brief Test code for a vel3d_k_wfp_stc data parser
"""

import ntplib

from nose.plugins.attrib import attr
from StringIO import StringIO

from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.data_particle import DataParticleKey

from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.vel3d_k_wfp_stc import Vel3dKWfpStcParser, Vel3dKWfpStcTimeDataParticle, Vel3dKWfpStcVelocityDataParticle, StateKey
from mi.dataset.test.test_parser import ParserUnitTestCase

FLAG_RECORD_SIZE = 26 
VELOCITY_RECORD_SIZE = 24  # fixed only for test data - variable in real life
TIME_RECORD_SIZE = 8

## First byte of flag record is bad.
TEST_DATA_BAD_FLAG_RECORD = \
  '\x09\x00\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00' \
  '\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8' \
  '\x52\x60\x53\x24\x53\x42\x40\x44' \
  '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x52\x48\x4E\x82\x52\x48\x4F\x9B'

## Flag record is too short.
TEST_DATA_SHORT_FLAG_RECORD = \
  '\x01\x00\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

## Flag record, first velocity record, and time record
## from A000010.DEC sample file. IDD has expected outputs.
TEST_DATA_GOOD_1_REC = \
  '\x01\x00\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00' \
  '\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8' \
  '\x52\x60\x53\x24\x53\x42\x40\x44' \
  '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x52\x48\x4E\x82\x52\x48\x4F\x9B'

## Flag record, first and last velocity record, and time record
## from A000010.DEC sample file. IDD has expected outputs.
TEST_DATA_GOOD_2_REC = \
  '\x01\x00\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00' \
  '\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8' \
  '\x52\x60\x53\x24\x53\x42\x40\x44' \
  '\x71\x08\x1D\x10\x04\x25\xC4\x08\xBF\x0B\x5E\x03\xF0\xFD' \
  '\xFC\x26\x51\xF6\x51\xFC\x50\x43\x40\x45' \
  '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x52\x48\x4E\x82\x52\x48\x4F\x9B'

## Flag record, many velocity records, and time record.
## Multiple records are the first and last repeated in pairs.
TEST_DATA_GOOD_BIG_FILE = \
  '\x01\x00\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00' \
  '\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8' \
  '\x52\x60\x53\x24\x53\x42\x40\x44' \
  '\x71\x08\x1D\x10\x04\x25\xC4\x08\xBF\x0B\x5E\x03\xF0\xFD' \
  '\xFC\x26\x51\xF6\x51\xFC\x50\x43\x40\x45' \
  '\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8' \
  '\x52\x60\x53\x24\x53\x42\x40\x44' \
  '\x71\x08\x1D\x10\x04\x25\xC4\x08\xBF\x0B\x5E\x03\xF0\xFD' \
  '\xFC\x26\x51\xF6\x51\xFC\x50\x43\x40\x45' \
  '\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8' \
  '\x52\x60\x53\x24\x53\x42\x40\x44' \
  '\x71\x08\x1D\x10\x04\x25\xC4\x08\xBF\x0B\x5E\x03\xF0\xFD' \
  '\xFC\x26\x51\xF6\x51\xFC\x50\x43\x40\x45' \
  '\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8' \
  '\x52\x60\x53\x24\x53\x42\x40\x44' \
  '\x71\x08\x1D\x10\x04\x25\xC4\x08\xBF\x0B\x5E\x03\xF0\xFD' \
  '\xFC\x26\x51\xF6\x51\xFC\x50\x43\x40\x45' \
  '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x00\x00\x00\x00\x00\x00\x00\x00' \
  '\x52\x48\x4E\x82\x52\x48\x4F\x9B'

VELOCITY_1_GROUPS = (113, 8, 29, 16, 0, 17, 2243, 3017, 864, 
  -519, -4, 21224, 21344, 21284, 66, 64, 68)

VELOCITY_2_GROUPS = (113, 8, 29, 16, 4, 37, 2244, 3007, 862, 
  -528, -4, 20774, 20982, 20732, 67, 64, 69)

TIME_1_GROUPS = (1380470402, 1380470683, 1)
TIME_2_GROUPS = (1380470402, 1380470683, 2)
TIME_8_GROUPS = (1380470402, 1380470683, 8)

@attr('UNIT', group='mi')
class Vel3dKWfpStcParserUnitTestCase(ParserUnitTestCase):
    """
    Vel3d_k__stc_imodem Parser unit test suite
    """

    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the 
        position callback """
        self.state_callback_value = state
        self.file_ingested = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the 
        publish callback """
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: \
              'mi.dataset.parser.vel3d_k__stc_imodem',
            DataSetDriverConfigKeys.PARTICLE_CLASS: \
              ['Vel3dKWfpStcTimeDataParticle',
               'Vel3dKWfpStcVelocityDataParticle']
            }
        # Define test data particles and their associated timestamps 
        # which will be compared with returned results

        self.state_callback_value = None
        self.publish_callback_value = None
        self.state = {StateKey.POSITION: 0,
          StateKey.FIRST_RECORD: True,
          StateKey.VELOCITY_END: False}

        ##
        ## This parser stores the groups from the data matcher in raw_data.
        ##
        ntptime = ntplib.system_to_ntp_time(1380470402.0)
        self.expected_particle1 = Vel3dKWfpStcVelocityDataParticle(
          VELOCITY_1_GROUPS, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380470402.5)
        self.expected_particle2 = Vel3dKWfpStcVelocityDataParticle(
          VELOCITY_2_GROUPS, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380470403.0)
        self.expected_particle3 = Vel3dKWfpStcVelocityDataParticle(
          VELOCITY_1_GROUPS, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380470403.5)
        self.expected_particle4 = Vel3dKWfpStcVelocityDataParticle(
          VELOCITY_2_GROUPS, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380470402.0)
        self.expected_time1 = Vel3dKWfpStcTimeDataParticle(
          TIME_1_GROUPS, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380470402.0)
        self.expected_time2 = Vel3dKWfpStcTimeDataParticle(
          TIME_2_GROUPS, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380470402.0)
        self.expected_time8 = Vel3dKWfpStcTimeDataParticle(
          TIME_8_GROUPS, internal_timestamp=ntptime)

    def verify_contents(self, actual_particle, expected_particle):
        ## log.debug('EXP %s XXX', dir(expected_particle))
        ## log.debug('ACT %s YYY', dir(actual_particle))
        self.assertEqual(actual_particle, [expected_particle])
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], expected_particle)

    def verify_file_info(self, expected_end_of_file, expected_file_position):
        self.assertEqual(self.file_ingested, expected_end_of_file)
        self.assertEqual(self.parser._state[StateKey.POSITION], 
          expected_file_position)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        File is valid.  Has 1 velocity record.
        """
        log.info("=================== START SIMPLE ======================")
        log.info("Simple length %d", len(TEST_DATA_GOOD_1_REC))
        input_file = StringIO(TEST_DATA_GOOD_1_REC)
        self.parser = Vel3dKWfpStcParser(self.config, input_file, 
          self.state, self.state_callback, self.pub_callback)

        log.info("SIMPLE VERIFY VELOCITY RECORD 1")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle1)

        expected_file_position = FLAG_RECORD_SIZE + VELOCITY_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        log.info("SIMPLE VERIFY TIME RECORD")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_time1)

        ## Must skip past the zero filled end of velocity record also.
        expected_file_position += TIME_RECORD_SIZE + VELOCITY_RECORD_SIZE
        self.verify_file_info(True, expected_file_position)
        log.info("=================== END SIMPLE ======================")

    def test_get_some(self):
        """
        Read test data and pull out multiple data particles one at a time.
        Assert that the results are those we expected.
        File is valid.  Has 2 velocity records.
        """
        log.info("=================== START SOME ======================")
        log.info("Some length %d", len(TEST_DATA_GOOD_2_REC))
        input_file = StringIO(TEST_DATA_GOOD_2_REC)
        self.parser = Vel3dKWfpStcParser(self.config, input_file, 
          self.state, self.state_callback, self.pub_callback)

        log.info("SOME VERIFY VELOCITY RECORD 1")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle1)

        expected_file_position = FLAG_RECORD_SIZE + VELOCITY_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        log.info("SOME VERIFY VELOCITY RECORD 2")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle2)

        expected_file_position += VELOCITY_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        log.info("SOME VERIFY TIME RECORD")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_time2)

        ## Must skip past the zero filled end of velocity record also.
        expected_file_position += TIME_RECORD_SIZE + VELOCITY_RECORD_SIZE
        self.verify_file_info(True, expected_file_position)
        log.info("=================== END SOME ==========================")

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        File is valid.  Has many velocity records.
        """
        log.info("=================== START MANY ======================")
        log.info("Many length %d", len(TEST_DATA_GOOD_BIG_FILE))
        input_file = StringIO(TEST_DATA_GOOD_BIG_FILE)
        self.parser = Vel3dKWfpStcParser(self.config, input_file, 
          self.state, self.state_callback, self.pub_callback)

        log.info("MANY VERIFY VELOCITY RECORD 1")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle1)

        expected_file_position = FLAG_RECORD_SIZE + VELOCITY_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        log.info("MANY VERIFY VELOCITY RECORDS 2-4")
        result = self.parser.get_records(3)
        self.assertEqual(result, [self.expected_particle2,
          self.expected_particle3, self.expected_particle4])

        self.assertEqual(self.publish_callback_value[0], 
          self.expected_particle2)

        self.assertEqual(self.publish_callback_value[1], 
          self.expected_particle3)

        self.assertEqual(self.publish_callback_value[2], 
          self.expected_particle4)

        expected_file_position += 3 * VELOCITY_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        ## Skip over the next 4 velocity records.
        log.info("MANY SKIPPING")
        skip_result = self.parser.get_records(4)
        expected_file_position += 4 * VELOCITY_RECORD_SIZE

        ## We should now be at the time record.
        log.info("MANY VERIFY TIME RECORD")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_time8)

        ## Must skip past the zero filled end of velocity record also.
        expected_file_position += \
          TIME_RECORD_SIZE + VELOCITY_RECORD_SIZE
        self.verify_file_info(True, expected_file_position)
        log.info("=================== END MANY ==========================")

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        log.info("=================== START MID-STATE ======================")
        log.info("Mid-state length %d", len(TEST_DATA_GOOD_BIG_FILE))
        input_file = StringIO(TEST_DATA_GOOD_BIG_FILE)

        ## Skip past the flag record and the first 2 velocity records.
        position = FLAG_RECORD_SIZE + (2 * VELOCITY_RECORD_SIZE)
        new_state = {StateKey.POSITION: position,
          StateKey.FIRST_RECORD: True,
          StateKey.VELOCITY_END: False}

        self.parser = Vel3dKWfpStcParser(self.config, input_file, 
          new_state, self.state_callback, self.pub_callback)

        ## This should get record 3.
        log.info("MID-STATE AFTER RECORD 2, POSITION %d", 
          self.parser._read_state[StateKey.POSITION])
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle3)

        expected_file_position = position + VELOCITY_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)
        log.info("=================== END MID-STATE ======================")

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has changed
        """
        log.info("=================== SET STATE ======================")
        log.info("Set state length %d", len(TEST_DATA_GOOD_BIG_FILE))
        input_file = StringIO(TEST_DATA_GOOD_BIG_FILE)

        self.parser = Vel3dKWfpStcParser(self.config, input_file, 
          self.state, self.state_callback, self.pub_callback)

        log.info("SET STATE VERIFY VELOCITY RECORD 1")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle1)

        expected_file_position = FLAG_RECORD_SIZE + VELOCITY_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        ## Skip to velocity record 4.
        position = FLAG_RECORD_SIZE + (3 * VELOCITY_RECORD_SIZE)
        log.info("SET STATE SKIPPING TO POSITION %d", position)
        new_state = {StateKey.POSITION: position,
          StateKey.FIRST_RECORD: True,
          StateKey.VELOCITY_END: False}
        self.parser.set_state(new_state)

        log.info("SET STATE VERIFY VELOCITY RECORD 4")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle4)

        expected_file_position = position + VELOCITY_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

    def test_bad_flag_record(self):
        """
        Ensure that bad data is skipped when flag record is invalid.
        This should raise an exception indicating that the Flag record
        is invalid.
        """
        log.info("=================== START BAD FLAG ======================")
        log.info("Bad Flag length %d", len(TEST_DATA_BAD_FLAG_RECORD))
        input_file = StringIO(TEST_DATA_BAD_FLAG_RECORD)
        with self.assertRaises(SampleException):
            self.parser = Vel3dKWfpStcParser(self.config, input_file, 
              self.state, self.state_callback, self.pub_callback)
        log.info("=================== END BAD FLAG ======================")

    def test_short_flag_record(self):
        """
        Ensure that data is skipped when flag record is too short.
        This should raise an exception indicating that end of file was
        reached while reading the Flag record.
        """
        log.info("=================== START SHORT FLAG ======================")
        log.info("Short Flag length %d", len(TEST_DATA_SHORT_FLAG_RECORD))
        input_file = StringIO(TEST_DATA_SHORT_FLAG_RECORD)
        with self.assertRaises(SampleException):
            self.parser = Vel3dKWfpStcParser(self.config, input_file, 
              self.state, self.state_callback, self.pub_callback)
        log.info("=================== END SHORT FLAG ======================")

