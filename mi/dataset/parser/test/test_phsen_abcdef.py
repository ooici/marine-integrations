#!/usr/bin/env python

"""
@package mi.dataset.parser.test
@file marine-integrations/mi/dataset/parser/test/test_phsen_abcdef.py
@author Joseph Padula
@brief Test code for a Phsen_abcdef data parser
"""
import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.phsen_abcdef import PhsenRecoveredParser, PhsenRecoveredMetadataDataParticle, PhsenRecoveredInstrumentDataParticle
from mi.core.exceptions import SampleException

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
                 'dataset', 'driver', 'mflm',
                 'phsen', 'resource')

@attr('UNIT', group='mi')
class PhsenRecoveredParserUnitTestCase(ParserUnitTestCase):
    """
    Phsen Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value.append(exception)

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.phsen',
            DataSetDriverConfigKeys.PARTICLE_CLASS: ['PhsenRecoveredMetadataDataParticle']
            }
        # Define test data particles and their associated timestamps which will be
        # compared with returned results
        # starts file index 367

        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = []

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
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'SAMI_P0080_180713_simple.txt'))

        self.parser = PhsenRecoveredParser(self.config, None, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredMetadataDataParticle(['128',	'3456970176', '65', '1', '0', '512'],
                                                            internal_timestamp=3456970176)
        self.assertEqual(result, [expected_value])

        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredMetadataDataParticle(['133',	'3456974356', '65', '2', '0', '530'],
                                                            internal_timestamp=3456974356)
        self.assertEqual(result, [expected_value])

        # skipping over second 133 record
        self.parser.get_records(1)

        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredMetadataDataParticle(['129',	'3456975599', '67', '4', '0', '566'],
                                                            internal_timestamp=3456975599)
        self.assertEqual(result, [expected_value])

        # next record is 191, which we handle but should not get
        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredMetadataDataParticle(['191',	'3456975599', '67', '4', '0', '566', '666'],
                                                            internal_timestamp=3456975599)
        self.assertEqual(result, [expected_value])

        # next record is 255, which we handle but should not get
        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredMetadataDataParticle(['255',	'3456975599', '67', '4', '0', '566', '777'],
                                                            internal_timestamp=3456975599)
        self.assertEqual(result, [expected_value])

        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredMetadataDataParticle(['192',	'3456975599', '67', '4', '0', '566', '888'],
                                                            internal_timestamp=3456975599)
        self.assertEqual(result, [expected_value])

        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredMetadataDataParticle(['193',	'3456975599', '67', '4', '0', '566', '999'],
                                                            internal_timestamp=3456975599)
        self.assertEqual(result, [expected_value])

        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredInstrumentDataParticle(['10', '3456975600', '2276',
                                                               '2955', '2002', '2436', '2495',
                                                                '2962', '1998', '2440', '2492',
                                                                '2960', '2001', '2440', '2494',
                                                                '2964', '2002', '2444', '2496',
                                                                 '2962', '2004', '2438', '2496',
                                                                 '2960', '2002', '2437', '2494',
                                                                 '2959', '1977', '2438', '2477',
                                                                 '2963', '1653', '2440', '2219',
                                                                 '2961', '1121', '2441', '1757',
                                                                 '2962', '694', '2437', '1327',
                                                                 '2963', '465', '2439', '1059',
                                                                 '2958', '365', '2436', '933',
                                                                 '2959', '343', '2434', '901',
                                                                 '2961', '370', '2443', '937',
                                                                 '2960', '425', '2441', '1013',
                                                                 '2961', '506', '2438', '1118',
                                                                 '2962', '602', '2441', '1232',
                                                                 '2963', '707', '2439', '1356',
                                                                 '2964', '828', '2440', '1484',
                                                                 '2962', '948', '2439', '1604',
                                                                 '2962', '1065', '2440', '1716',
                                                                 '2968', '1173', '2444', '1816',
                                                                 '2962', '1273', '2440', '1910',
                                                                 '2961', '1363', '2442', '1986',
                                                                 '2959', '1449', '2439', '2059',
                                                                 '2963', '1521', '2442', '2120',
                                                                 '2962', '1585', '2439', '2171',
                                                                 '0', '2857', '2297'],
                                                            internal_timestamp=3456975600)

        # log.debug("actual %s", result[0].raw_data)
        # log.debug("expected %s", expected_value.raw_data)
        self.assertEqual(result, [expected_value])

        result = self.parser.get_records(1)
        expected_value = PhsenRecoveredMetadataDataParticle(['131',	'3456982799', '71', '29', '0', '6128'],
                                                            internal_timestamp=3456982799)
        self.assertEqual(result, [expected_value])
        stream_handle.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 17600]],
            StateKey.IN_PROCESS_DATA:[]}
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, state, stream_handle, self.state_callback,
                                  self.pub_callback, self.exception_callback)

        result = self.parser.get_records(7)
        stream_handle.close()
        self.assertEqual(result,
                         [self.particle_control, self.particle_a, self.particle_b,
                          self.particle_c, self.particle_d, self.particle_e, self.particle_f])
        # the remaining in process data is actually a particle with a bad sample
        in_process = [[15536, 16040, 1, 0], [16301, 16805, 1, 0], [16998, 17502, 1, 0]]
        unprocessed = [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764],[9654,9723],
             [11451,11520], [15536, 16040], [16301, 16805], [16998, 17600]]
        self.assert_state(in_process, unprocessed)
        self.assertEqual(self.publish_callback_value[0], self.particle_control)
        self.assertEqual(self.publish_callback_value[1], self.particle_a)
        self.assertEqual(self.publish_callback_value[2], self.particle_b)
        self.assertEqual(self.publish_callback_value[3], self.particle_c)
        self.assertEqual(self.publish_callback_value[4], self.particle_d)
        self.assertEqual(self.publish_callback_value[5], self.particle_e)
        self.assertEqual(self.publish_callback_value[6], self.particle_f)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0, 172], [4100, 4171], [5899, 5968],
                [7697, 7764], [8636, 16000]]}
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, new_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, [[14142, 14646, 1, 0], [14839, 15343, 1, 0]],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14142,14646], [14839,15343], [15536, 16000]],
                           self.particle_d)
        result = self.parser.get_records(1)
        self.assert_result(result, [[14839, 15343, 1, 0]],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14839,15343], [15536, 16000]],
                           self.particle_e)
        stream_handle.close()

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[[1804, 2308, 1, 0]],
            StateKey.UNPROCESSED_DATA:[[0, 172], [1804, 2308], [4100, 4171], [5899, 5968],
                                       [7697, 7764], [8636, 16000]]}
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, new_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [8636, 16000]],
                           self.particle_c)

        result = self.parser.get_records(1)
        self.assert_result(result, [[14142, 14646, 1, 0], [14839, 15343, 1, 0]],
                        [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14142,14646], [14839,15343], [15536, 16000]],
                        self.particle_d)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and
        reading data, as if new data has been found and the state has
        changed
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 9000]], StateKey.IN_PROCESS_DATA:[]}
        new_state = {StateKey.UNPROCESSED_DATA:[[0, 172], [4100, 4171], [5899, 5968],
                                                [7697, 7764], [8636, 14700]],
                     StateKey.IN_PROCESS_DATA:[]}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # there should only be 4 records, make sure we stop there
        result = self.parser.get_records(4)
        self.assert_state([], [[0, 172], [4100, 4171], [5899, 5968],
                                [7697, 7764], [8636, 9000]])
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        stream_handle.close()
        self.assert_result(result, [[14142, 14646, 1, 0]],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14142,14700]],
                           self.particle_d)

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        log.debug('Starting test_update')
        state = {StateKey.UNPROCESSED_DATA:[[0, 14700]],
            StateKey.IN_PROCESS_DATA:[]}
        # this file has a block of FL data replaced by 0s
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'node59p1_replaced.dat'))
        self.parser = PhsenParser(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(3)
        self.assertEqual(result, [self.particle_b, self.particle_c, self.particle_d])
        self.assert_state([[14142, 14646, 1, 0]],
            [[0, 172], [367,911], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14142,14700]])
        # was b and c
        stream_handle.close()

        next_state = self.parser._state
        # this file has the block of data that was missing in the previous file
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, next_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # get last in process record
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [367,911], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14646,14700]],
                           self.particle_e)
        # now get the filled in record
        result = self.parser.get_records(1)
        self.assert_result(result, [[367,911,2,1]],
                           [[0, 172], [367,911], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14646,14700]],
                           self.particle_control)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14646,14700]],
                           self.particle_a)
        stream_handle.close()
