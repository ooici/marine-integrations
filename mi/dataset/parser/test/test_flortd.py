#!/usr/bin/env python

import gevent
import unittest
import os
import time
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.parser.flortd import FlortdParser, FlortdParserDataParticle
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'mflm',
			     'flort', 'resource')

@attr('UNIT', group='mi')
class FlortdParserUnitTestCase(ParserUnitTestCase):

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
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flortd',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlortdParserDataParticle'
            }

        # first FL tag
        self.particle_a = FlortdParserDataParticle(
            '51EF0E7507/23/13\t23:15:06\t700\t50\t695\t50\t460\t53\t545')
        self.particle_a_dash = FlortdParserDataParticle(
            '51EF0E7507/23/13\t23:15:06\t700\t50\t--\t50\t460\t53\t545')
        self.particle_b = FlortdParserDataParticle(
            '51EF190107/24/13\t00:00:06\t700\t85\t695\t50\t460\t51\t548')
        self.particle_c = FlortdParserDataParticle(
            '51EF6D6107/24/13\t06:00:05\t700\t78\t695\t72\t460\t51\t553')
        self.particle_d = FlortdParserDataParticle(
            '51EFC1C207/24/13\t12:00:06\t700\t169\t695\t127\t460\t58\t553')
        self.particle_e = FlortdParserDataParticle(
            '51F0162207/24/13\t18:00:06\t700\t262\t695\t84\t460\t55\t555')
        self.particle_f = FlortdParserDataParticle(
            '51F06A8207/25/13\t00:00:06\t700\t159\t695\t95\t460\t59\t554')

        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

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
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'node59p1_shorter.dat'))
        # NOTE: using the unprocessed data state of 0,1000 limits the file to reading
        # just 1000 bytes, so even though the file is longer it only reads the first
        # 1000
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                   self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        # 0-69, 944-1000 are incomplete samples, 314-390 and 561-637 are samples that have
        # parsed but not yet returned (in_process)
        self.assert_result(result,
                           [[314,390,1,0], [561,637,1,0]],
                           [[0,69],[314,390],[561,637],[944,1000]], self.particle_a)
        result = self.parser.get_records(1)
        # 0-69, 944-1000 are incomplete samples, 561-637 is parsed but not yet 
        # returned (in_process)
        self.assert_result(result, [[561,637,1,0]],
                           [[0,69],[561,637],[944,1000]], self.particle_b)
        result = self.parser.get_records(1)
        # all three samples that were parsed have been returned, no more in process
        self.assert_result(result, [],
                           [[0,69],[944,1000]], self.particle_c)

        self.stream_handle.close()

    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                   self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(3)
        self.stream_handle.close()
        self.assertEqual(result,
                         [self.particle_a, self.particle_b, self.particle_c])
        # 0-69, 944-1000 are incomplete samples
        self.assert_state([],
                        [[0,69],[944,1000]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)

    def test_dash(self):
        """
        Test that the particle with a field replaced by dashes is found
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_dash.dat'))
        self.parser = FlortdParser(self.config, None, self.stream_handle,
                                   self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result,
                           [[313,389,1,0]],
                           [[0,69],[313,499]], self.particle_a_dash)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69],[389,499]], self.particle_b)

    def test_long_stream(self):
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        data = self.stream_handle.read()
        data_len = len(data)
        self.stream_handle.seek(0)
        self.state = {StateKey.UNPROCESSED_DATA:[[0, data_len]],
            StateKey.IN_PROCESS_DATA:[]}
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(6)
        self.stream_handle.close()
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[4], self.particle_e)
        self.assertEqual(result[5], self.particle_f)
        # 0-69 contains an incomplete block (end of a sample)
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_state([],
            [[0, 69], [1329,1332],[2294,2363],[4092,4161],[4351,4927], [9020,9400]])
        self.assertEqual(self.publish_callback_value[4], self.particle_e)
        self.assertEqual(self.publish_callback_value[5], self.particle_f)

    def test_mid_state_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0,69], [197,1000]]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # 0-69, 944-1000 are incomplete samples
        result = self.parser.get_records(1)
        self.assert_result(result, [[561,637,1,0]],
                           [[0,69],[561,637],[944,1000]],
                           self.particle_b)
        result = self.parser.get_records(1)
        # 0-69, 944-1000 are incomplete samples
        self.assert_result(result, [],
                           [[0,69],[944,1000]],
                           self.particle_c)

	self.stream_handle.close()

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[[314,390,1,0], [561,637,1,0]],
            StateKey.UNPROCESSED_DATA:[[0,69],[314,390],[561,637],[944,6150]]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)

        self.assert_result(result, [[561,637,1,0]],
                           [[0,69],[561,637],[944,6150]],
                           self.particle_b)

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_c)
        self.assertEqual(result[1], self.particle_d)
        # 0-69, 6131-6150 contains an incomplete block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_state([],
            [[0,69],[1329,1332],[2294,2363],[4092,4161],[4351,4927], [6131,6150]])
        self.assertEqual(self.publish_callback_value[-1], self.particle_d)

    def test_set_state(self):
        """
        test changing the state after initializing
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 1000]], StateKey.IN_PROCESS_DATA:[]}
        new_state = {StateKey.UNPROCESSED_DATA:[[0,69],[944,6150]],
            StateKey.IN_PROCESS_DATA:[]}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # there should only be 3 records, make sure we stop there
        result = self.parser.get_records(3)
        self.assert_state([],
            [[0,69],[944,1000]])
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.stream_handle.close()
        # 0-69, 6131-6150 contains an incomplete block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [],
                           [[0,69], [1329,1332],[2294,2363],[4092,4161],[4351,4927], [6131,6150]],
                           self.particle_d)

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 6150]],
            StateKey.IN_PROCESS_DATA:[]}
        # this file has a block of FL data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replaced.dat'))
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, [[561,637,1,0], [6053,6131,1,0]],
                           [[0,69],[314,390],[561,637],[1329,1332],[2294,2363],[4092,4161],[4351,4927],[6053,6150]],
                           self.particle_a)
        result = self.parser.get_records(1)
        # 0-69, 6131-6150 contains an incomplete block
        # 314-390 is the zeroed block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [[6053,6131,1,0]],
                           [[0,69],[314,390],[1329,1332],[2294,2363],[4092,4161],[4351,4927],[6053,6150]],
                           self.particle_c)
        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # first get the old 'in process' records from 6053-6131
        # Once those are done, the un processed data will be checked
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69], [314,390], [1329,1332],[2294,2363],[4092,4161],[4351,4927],[6131,6150]],
                           self.particle_d)

        # this should be the first of the newly filled in particles from 314-390
        result = self.parser.get_records(1)
        # 0-69, 6131-6150 contains an incomplete block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [],
                           [[0,69], [1329,1332],[2294,2363],[4092,4161],[4351,4927],[6131,6150]],
                           self.particle_b)
        self.stream_handle.close()
