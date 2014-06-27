#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_ctdmo
@file marine-integrations/mi/dataset/parser/test/test_ctdmo.py
@author Emily Hahn, Steve Myerson (recovered)
@brief Test code for a Ctdmo data parser
Files used for Recovered CO:
  CTD2000.DAT
    1 CT block
    0 CO blocks
  CTD2001.DAT
    1 CT
    1 CO w/6 records, 5 valid IDs
  CTD2002.DAT
    1 CO w/4 records, 3 valid IDs
    1 CT
    1 CO w/6 records, 4 valid IDs
  CTD2004.DAT
    1 CT
    1 CO w/2 records, 0 valid IDs
    1 CO w/2 records, 1 valid ID
    1 CO w/5 records, 4 valid IDs
    1 CT
    1 CO w/10 records, 10 valid IDs
  CTD2100.DAT
    1 CT
    1 CO w/100 records, 100 valid IDs
    1 CO w/150 records, 150 valid IDs
"""

import gevent
import unittest
import os
from nose.plugins.attrib import attr
from StringIO import StringIO

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase

from mi.dataset.parser.sio_mule_common import StateKey

from mi.dataset.parser.ctdmo import \
    CtdmoRecoveredCoParser, \
    CtdmoRecoveredCtParser, \
    CtdmoRecoveredInstrumentDataParticle, \
    CtdmoRecoveredOffsetDataParticle, \
    CtdmoTelemeteredParser, \
    CtdmoTelemeteredInstrumentDataParticle, \
    CtdmoTelemeteredOffsetDataParticle, \
    CtdmoStateKey

from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import DatasetParserException

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver',
                 'mflm', 'ctd', 'resource')

# Expected tuples for recovered CO data in file CTD02001.DAT
EXPECTED_CTD02001_1 = [
    ('51532002', '7', '\xff\xff\xff\xe7'),
    ('51532002', '7', '\xff\xff\xff\xf1'),
    ('51532002', '7', '\xff\xff\xff\xfb'),
    ('51532002', '7', '\x00\x00\x00\x0f'),
    ('51532002', '7', '\x00\x00\x00\x19')
]

# Expected tuples for recovered CO data in file CTD02002.DAT
EXPECTED_CTD02002_1 = [
    ('51532002', '7', '\xff\xff\xff\x88'),
    ('51532002', '7', '\xff\xff\xff\xa6'),
    ('51532002', '7', '\xff\xff\xff\xc4')
]
EXPECTED_CTD02002_2 = [
    ('51532004', '7', '\x00\x00\x00\x00'),
    ('51532004', '7', '\x00\x00\x00<'),
    ('51532004', '7', '\x00\x00\x00x'),
    ('51532004', '7', '\x00\x00\x00\x96')
]

# Expected tuples for recovered CO data in file CTD02004.DAT
EXPECTED_CTD02004_1 = []

EXPECTED_CTD02004_2 = [
    ('51532006', '7', '\xff\xff\xff\xe2')
]

EXPECTED_CTD02004_3 = [
    ('51532007', '7', '\x00\x00\x00\n'),
    ('51532007', '7', '\x00\x00\x00Z'),
    ('51532007', '7', '\x00\x00\x00\x82'),
    ('51532007', '7', '\x00\x00\x00\xaa')
]

EXPECTED_CTD02004_4 = [
    ('51532009', '7', '\x00\x00\x00\xd2'),
    ('51532009', '7', '\x00\x00\x00\xfa'),
    ('51532009', '7', '\x00\x00\x01"'),
    ('51532009', '7', '\x00\x00\x01J'),
    ('51532009', '7', '\x00\x00\x01r'),
    ('51532009', '7', '\x00\x00\x01\x9a'),
    ('51532009', '7', '\x00\x00\x01\xc2'),
    ('51532009', '7', '\x00\x00\x01\xea'),
    ('51532009', '7', '\x00\x00\x02\x12'),
    ('51532009', '7', '\x00\x00\x02:')
]

# List of all expected values for file CTD02004.DAT
EXPECTED_CTD02004 = [
    EXPECTED_CTD02004_1,
    EXPECTED_CTD02004_2,
    EXPECTED_CTD02004_3,
    EXPECTED_CTD02004_4
]


@attr('UNIT', group='mi')
class CtdmoParserUnitTestCase(ParserUnitTestCase):

    def create_rec_co_parser(self, file_handle, new_state=None):
        """
        This function creates a Ctdmo parser for recovered CO data.
        """
        parser = CtdmoRecoveredCoParser(self.config_rec_co, file_handle, new_state,
            self.rec_state_callback, self.pub_callback, self.exception_callback)
        return parser

    def create_rec_ct_parser(self, file_handle, new_state=None):
        """
        This function creates a Ctdmo parser for recovered CT data.
        """
        parser = CtdmoRecoveredCtParser(self.config_rec_ct, file_handle, new_state,
            self.rec_state_callback, self.pub_callback, self.exception_callback)
        return parser

    def rec_state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                ['CtdmoTelemeteredInstrumentDataParticle',
                 'CtdmoTelemeteredOffsetDataParticle'],
            CtdmoStateKey.INDUCTIVE_ID: 55
        }

        self.config_rec_co = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredOffsetDataParticle',
            CtdmoStateKey.INDUCTIVE_ID: 55
        }

        self.config_rec_ct = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredInstrumentDataParticle',
            CtdmoStateKey.INDUCTIVE_ID: 55,
            CtdmoStateKey.SERIAL_NUMBER: '03710261'
        }

        # all indices give in the comments are in actual file position, not escape sequence replace indices
        # packets have the same timestamp, the first has 3 data samples [394-467]
        self.particle_a = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF36D6',
             b'\x37',
             b'\x39\x4c\xe0\xc3\x54\xe6\x0a',
             b'\x81\xd5\x81\x19'))

        # this is the start of packet 2 [855:1045]
        self.particle_b = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF52F6',
             b'7',
             b'7\xf0\x00\xc3T\xe5\n',
             b'\xa1\xf1\x81\x19'))
        
        # this is the start of packet 3 [1433:1623]
        self.particle_c = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF6F16',
             b'7',
             b'6$p\xc3T\xe4\n',
             b'\xc1\r\x82\x19'))
        
        # this is the start of packet 4 [5354:5544]
        self.particle_d = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF8B36',
             b'\x37',
             b'\x35\x8b\xe0\xc3T\xe5\n',
             b'\xe1)\x82\x19'))
        
        # this is the start of packet 5 [6321:6511]
        self.particle_e = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFC376',
             b'7',
             b'7\x17\xd6\x8eI;\x10',
             b'!b\x82\x19'))
        
        # start of packet 6 [6970-7160]
        self.particle_f = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFDF96',
             b'\x37',
             b'\x36\xe7\xe6\x89W9\x10',
             b'A~\x82\x19'))
        
        # packet 7 [7547-7737]
        self.particle_g = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFFBB6',
             b'\x37',
             b'\x32\t6F\x0c\xd5\x0f',
             b'a\x9a\x82\x19'))

        # first offset at 9543
        self.particle_a_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F05016', b'7', b'\x00\x00\x00\x00'))

        # in long file, starts at 13453
        self.particle_z = CtdmoTelemeteredInstrumentDataParticle(
            (b'51F0A476',
             b'7',
             b'3\xb9\xa6]\x93\xf2\x0f',
             b'!C\x83\x19'))

        # in longest file second offset at 19047
        self.particle_b_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F1A196', b'7', b'\x00\x00\x00\x00'))
        
        # third offset at 30596
        self.particle_c_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F2F316', b'7', b'\x00\x00\x00\x00'))

        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None
        self.maxDiff = None

    def assert_result(self, result, in_process_data, unprocessed_data, particle):
        self.assertEqual(result, [particle])
        self.assert_state(in_process_data, unprocessed_data)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def assert_state(self, in_process_data, unprocessed_data):
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)

    def test_simple(self):
        """
        Read test data from the file and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                  'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            None, self.state_callback, self.pub_callback, self.exception_callback)

        log.debug('===== TEST SIMPLE GET RECORD 1 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
             [[853,1043,1,0], [1429,1619,1,0], [5349,5539,1,0],
                 [6313,6503,1,0], [6958,7148,1,0], [7534,7724,1,0]],
             [[0, 12], [336, 394], [853,1043], [1429,1619], [5349,5539],
                 [5924,5927], [6313,6503], [6889,7148], [7534,7985]],
             self.particle_a)

        log.debug('===== TEST SIMPLE GET RECORD 2 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[1429,1619,1,0], [5349,5539,1,0], [6313,6503,1,0],
                [6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [1429,1619], [5349,5539], [5924,5927],
                [6313,6503], [6889,7148], [7534,7985]],
            self.particle_b)

        log.debug('===== TEST SIMPLE GET RECORD 3 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0],
                [7534,7724,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7148], [7534,7985]],
            self.particle_c)

        log.debug('===== TEST SIMPLE GET RECORD 4 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[6313,6503,1,0], [6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5924,5927], [6313,6503], [6889,7148],
                [7534,7985]],
            self.particle_d)

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_missing_inductive_id_config(self):
        """
        Make sure that the driver complains about a missing inductive ID in the config
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 8000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        bad_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoTelemeteredInstrumentDataParticle',
            }
        with self.assertRaises(DatasetParserException):
            self.parser = CtdmoTelemeteredParser(bad_config, self.stream_handle,
                self.state, self.state_callback,
                self.pub_callback, self.exception_callback)

    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 7500]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            self.state, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(5)
        self.stream_handle.close()
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c, self.particle_d, self.particle_e])
        self.assert_state([[6958,7148,1,0]],
                           [[0, 12], [336, 394], [5924,5927], [6889,7500]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_d)
        self.assertEqual(self.publish_callback_value[4], self.particle_e)
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream(self):
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 14000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_longer.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            self.state, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(13)
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[9], self.particle_a_offset)
        self.assertEqual(result[-1], self.particle_z)
        self.assert_state([],
            [[0, 12], [336, 394], [5924,5927],  [6889, 6958], [8687,8756], 
               [8946,9522], [13615, 14000]])
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)
        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_longest_for_co(self):
        """
        Test an even longer file which contains more of the CO samples
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_longest.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle, None,
            self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(36)
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[9], self.particle_a_offset)
        self.assertEqual(result[12], self.particle_z)
        self.assertEqual(result[22], self.particle_b_offset)
        self.assertEqual(result[-1], self.particle_c_offset)

        self.assert_state([],
            [[0, 12], [336, 394], [5924,5927],  [6889, 6958], [8687,8756], 
             [8946,9522], [14576,14647], [16375,16444], [18173,18240],
             [20130,20199], [21927,21996], [29707,29776], [30648,30746]])

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [1429,7500]]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            new_state, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7500]],
            self.particle_c)
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {
            StateKey.IN_PROCESS_DATA:
                [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0],
                    [7534,7724,1,0]],
            StateKey.UNPROCESSED_DATA:
                [[0, 12], [336, 394], [5349,5539], [5924,5927],
                    [6313,6503], [6889,7148], [7534,7985]]}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            new_state, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_d)
        self.assertEqual(result[-1], self.particle_e)
        self.assert_state([[6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5924,5927], [6889,7148], [7534,7985]])

        self.assertEqual(self.publish_callback_value[-1], self.particle_e)
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state(self):
        """
        test changing the state after initializing
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 500]],
                      StateKey.IN_PROCESS_DATA:[]}

        new_state = {
            StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [1429,7500]],
            StateKey.IN_PROCESS_DATA:[]}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            self.state, self.state_callback,
            self.pub_callback, self.exception_callback)

        # there should only be 1 records, make sure we stop there
        result = self.parser.get_records(1)
        self.assertEqual(result[0], self.particle_a)
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7500]],
            self.particle_c)

        self.assertEqual(self.exception_callback_value, None)

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        # this file has a block of CT data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replace.dat'))

        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle, None,
             self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(4)

        # particle d has been replaced in this file with zeros
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c, self.particle_e])
        self.assert_state([[6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927], [6889,7148],
                [7534,7985]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_e)

        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of CT data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            next_state, self.state_callback,
            self.pub_callback, self.exception_callback)

        # first get the old 'in process' records from [6970-7160]
        # Once those are done, the un processed data will be checked
        result = self.parser.get_records(2)
        self.assertEqual(result, [self.particle_f, self.particle_g])
        self.assert_state([],
            [[0, 12], [336, 394], [5349,5539], [5924,5927], [6889,6958],
                [7724,7985]])

        self.assertEqual(self.publish_callback_value[0], self.particle_f)
        self.assertEqual(self.publish_callback_value[1], self.particle_g)

        # this should be the first of the newly filled in particles from [5354-5544]
        result = self.parser.get_records(1)
        self.assert_result(result,
            [],
            [[0, 12], [336, 394], [5924,5927], [6889,6958], [7724,7985]],
            self.particle_d)

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_big_giant_input(self):
        """
        Read a large file and verify that all expected particles can be read.
        Verification is not done at this time, but will be done during
        integration and qualification testing.
        File used for this test has 250 total CO particles.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02100.DAT'))
        parser = self.create_rec_co_parser(in_file)

        number_expected_results = 250

        # In a single read, get all particles in this file.
        result = parser.get_records(number_expected_results)
        self.assertEqual(len(result), number_expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_get_many(self):
        """
        Read Recovered CO data and pull out multiple data particles at one time.
        Verify that the results are those we expected.
        File used for this test has 2 CO SIO blocks.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02002.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Generate a list of expected result particles.
        expected_results = []
        for record in range(0, len(EXPECTED_CTD02002_1)):
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02002_1[record])
            expected_results.append(particle)

        # In a single read, get all particles for this CO record.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        # Do it again for the other CO SIO block.
        expected_results = []
        for record in range(0, len(EXPECTED_CTD02002_2)):
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02002_2[record])
            expected_results.append(particle)

        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_invalid_state(self):
        """
        Make sure that an exception is raised when the state is not
        a dictionary.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02000.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Instead of a dictionary, use a list of dictionaries for the state.
        new_state = [{'POSITION': 0}, {'invalid key': 22}]
        with self.assertRaises(DatasetParserException):
            parser.set_state(new_state)

    def test_rec_co_long_stream(self):
        """
        Read test data and pull out all particles from a file at once.
        File used for this test has 3 CO SIO blocks and a total of 15 CO records.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02004.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Generate a list of expected result particles.
        expected_results = []

        for block in range(0, len(EXPECTED_CTD02004)):
            for record in range(0, len(EXPECTED_CTD02004[block])):
                particle = CtdmoRecoveredOffsetDataParticle(
                    EXPECTED_CTD02004[block][record])
                expected_results.append(particle)

        # In a single read, get all particles in this file.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_mid_state_start(self):
        """
        Test starting a recovered CO parser with a state in the
        middle of processing.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02002.DAT'))

        # Start at the second SIO block.
        # Value obtained via UltraEdit.
        initial_state = {StateKey.POSITION: 0x92}

        parser = self.create_rec_co_parser(in_file, new_state=initial_state)

        # Generate the expected results.
        expected_results = []
        for record in range(0, len(EXPECTED_CTD02002_2)):
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02002_2[record])
            expected_results.append(particle)

        # Read the records from the CO SIO block.
        # Verify what we read is what we expect.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_missing_inductive_id_config(self):
        """
        Make sure that an exception is raised when building the
        Recovered CO parser if the inductive ID is missing in the config.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02000.DAT'))

        bad_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredOffsetDataParticle',
            }

        with self.assertRaises(DatasetParserException):
            CtdmoRecoveredCoParser(bad_config, in_file, None,
                self.state_callback, self.pub_callback, self.exception_callback)

    def test_rec_co_missing_state_key(self):
        """
        Make sure that an exception is raised when the POSITION state key
        is missing.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02000.DAT'))
        parser = self.create_rec_co_parser(in_file)

        new_state = {'Not a valid key': 18}
        with self.assertRaises(DatasetParserException):
            parser.set_state(new_state)

    def test_rec_co_no_records(self):
        """
        Read a Recovered CO data file that has no CO records.
        Verify that no particles are generated.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02000.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Not expecting any particles.
        expected_results = []

        # Try to get one particle and verify we didn't get any.
        result = parser.get_records(1)
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_set_state(self):
        """
        test changing the state after initializing
        File used for this test has 2 CO SIO blocks.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02002.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Read 1 record (of the 3 that are in the first SIO block).
        parser.get_records(1)

        # Skip ahead to the second SIO block.
        # Value obtained via UltraEdit.
        new_state = {StateKey.POSITION: 0x92}

        # Set the state.
        parser.set_state(new_state)

        # Generate the expected results.
        expected_results = []
        for record in range(0, len(EXPECTED_CTD02002_2)):
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02002_2[record])
            expected_results.append(particle)

        # Read the records from the CO SIO block.
        # Verify what we read is what we expect.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_simple(self):
        """
        Read Recovered CO data from the file and pull out data particles
        one at a time. Verify that the results are those we expected.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02001.DAT'))
        parser = self.create_rec_co_parser(in_file)

        for record in range(0, len(EXPECTED_CTD02001_1)):
            log.debug('===== TEST REC CO SIMPLE GET RECORD %d =====', record + 1)

            # Generate expected particle
            expected_results = []
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02001_1[record])
            expected_results.append(particle)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)


