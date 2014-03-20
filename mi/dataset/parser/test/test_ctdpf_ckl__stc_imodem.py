#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_ctdpf_ckl__stc_imodem
@file marine-integrations/mi/dataset/parser/test/test_ctdpf_ckl__stc_imodem.py
@author cgoodrich
@brief Test code for a Ctdpf_ckl__stc_imodem data parser
"""

import ntplib
from nose.plugins.attrib import attr
from StringIO import StringIO


from mi.core.log import get_logger
log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.parser.ctdpf_ckl__stc_imodem import Ctdpf_ckl__stc_imodemParser,\
    Ctdpf_ckl__stc_imodemMetaDataParticle, Ctdpf_ckl__stc_imodemInstDataParticle, StateKey

DATA_RECORD_SIZE = 11
TIME_RECORD_SIZE = 8

GOOD_TEST_DATA_1 = \
    '\x00\x1A\x88\x03\xE3\x3B\x00\x03\xEB\x0A\xC8' \
    '\x00\x1A\x8C\x03\xE2\xC0\x00\x03\xEB\x0A\x81' \
    '\x00\x1A\x90\x03\xE1\x5B\x00\x03\xEB\x0A\x65' \
    '\x00\x1A\x92\x03\xE0\x28\x00\x03\xEB\x0A\x86' \
    '\x00\x1A\x85\x03\xDF\x61\x00\x03\xEB\x0A\xCB' \
    '\x00\x1A\x8A\x03\xDF\x36\x00\x03\xEB\x0B\x12' \
    '\x00\x1A\x8C\x03\xDF\xCB\x00\x03\xEB\x0B\x34' \
    '\x00\x1A\x8A\x03\xE0\xCB\x00\x03\xEB\x0B\x2A' \
    '\x00\x1A\x8C\x03\xE1\x87\x00\x03\xEB\x0B\x09' \
    '\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF' \
    '\x52\x46\x1c\x03\x52\x46\x22\x95'

LINE_01 = (6792, 254779, 1003)
LINE_02 = (6796, 254656, 1003)
LINE_03 = (6800, 254299, 1003)
LINE_04 = (6802, 253992, 1003)
LINE_05 = (6789, 253793, 1003)
LINE_06 = (6794, 253750, 1003)
LINE_07 = (6796, 253899, 1003)
LINE_08 = (6794, 254155, 1003)
LINE_09 = (6796, 254343, 1003)
LINE_10 = (16777215, 16777215, 16777215)
LINE_11 = (1380326403, 1380328085)

# The flag record is invalid
BAD_TEST_DATA_1 = \
    '\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8' \
    '\x00\x1a\x8c\x03\xe2\xc0\x00\x03\xeb\x0a\x81' \
    '\xff\xff\xff\xff\xff\xff\xff\xff\xf0\xff\xff' \
    '\x52\x46\x1c\x03\x52\x46\x22\x95'

# The time stamp record only has 7 bytes
BAD_TEST_DATA_2 = \
    '\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8' \
    '\x00\x1a\x8c\x03\xe2\xc0\x00\x03\xeb\x0a\x81' \
    '\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff' \
    '\x52\x46\x1c\x03\x52\x46\x22'

# There is no flag record
BAD_TEST_DATA_3 = \
    '\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8' \
    '\x00\x1a\x8c\x03\xe2\xc0\x00\x03\xeb\x0a\x81' \
    '\x00\x1a\x8c\x03\xe2\xc0\x00\x03\xeb\x0a\x81' \
    '\x52\x46\x1c\x03\x52\x46\x22\x95'

@attr('UNIT', group='mi')
class Ctdpf_ckl__stc_imodemParserUnitTestCase(ParserUnitTestCase):
    """
    Ctdpf_ckl__stc_imodem Parser unit test suite
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
        self.config = {DataSetDriverConfigKeys.PARTICLE_MODULE: \
                           'mi.dataset.parser.ctdpf_ckl__stc_imodem',
                       DataSetDriverConfigKeys.PARTICLE_CLASS: \
                           ['Ctdpf_ckl__stc_imodemMetaDataParticle',
                            'Ctdpf_ckl__stc_imodemInstDataParticle']
        }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results

        self.state_callback_value = None
        self.publish_callback_value = None
        self.state = {StateKey.POSITION:0}

        ##
        ## This parser stores the groups from the data matcher in raw_data.
        ##
        ntptime = ntplib.system_to_ntp_time(1380326403.0)
        self.expected_particle_01 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_01, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380326404.0)
        self.expected_particle_02 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_02, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380326405.0)
        self.expected_particle_03 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_03, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380326406.0)
        self.expected_particle_04 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_04, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380326407.0)
        self.expected_particle_05 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_05, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380326408.0)
        self.expected_particle_06 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_06, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380326409.0)
        self.expected_particle_07 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_07, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380326410.0)
        self.expected_particle_08 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_08, internal_timestamp=ntptime)

        ntptime = ntplib.system_to_ntp_time(1380326411.0)
        self.expected_particle_09 = Ctdpf_ckl__stc_imodemInstDataParticle(LINE_09, internal_timestamp=ntptime)

    def verify_contents(self, actual_particle, expected_particle):
        ## log.info('EXP %s XXX', dir(expected_particle))
        ## log.info('ACT %s YYY', dir(actual_particle))
        self.assertEqual(actual_particle, [expected_particle])
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], expected_particle)

    def verify_file_info(self, expected_end_of_file, expected_file_position):
        self.assertEqual(self.file_ingested, expected_end_of_file)
        self.assertEqual(self.parser._state[StateKey.POSITION], expected_file_position)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        log.info("=================== START SIMPLE ======================")
        test_file = StringIO(GOOD_TEST_DATA_1)
        self.parser = Ctdpf_ckl__stc_imodemParser(self.config,
                                                  test_file,
                                                  self.state,
                                                  self.state_callback,
                                                  self.pub_callback,
                                                  None)

        log.info("VERIFY DATA RECORD 1")
        result = self.parser.get_records(1)
        log.info("Actual is %s", dir(result))
        log.info("Expected is %s", dir(self.expected_particle_01))
        self.verify_contents(result, self.expected_particle_01)

        expected_file_position = DATA_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        log.info("VERIFY DATA RECORD 2")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_02)

        expected_file_position += DATA_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        log.info("VERIFY DATA RECORD 3")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_03)

        expected_file_position += DATA_RECORD_SIZE
        self.verify_file_info(False, expected_file_position)

        log.info("VERIFY TIME RECORD")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_04)

        expected_file_position += TIME_RECORD_SIZE
        self.verify_file_info(True, expected_file_position)
        log.info("===================== END SIMPLE ======================")

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        log.info("=================== START MANY ======================")
        pass
        log.info("===================== END MANY ======================")

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        log.info("=================== START MID-STATE ======================")
        pass
        log.info("===================== END MID-STATE ======================")

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        log.info("=================== START SET STATE ======================")
        pass
        log.info("===================== END SET STATE ======================")

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        log.info("=================== START BAD DATA ======================")
        pass
        log.info("===================== END BAD DATA ======================")
