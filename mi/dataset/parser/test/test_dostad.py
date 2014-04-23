#!/usr/bin/env python

import gevent
import unittest
import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.parser.dostad import DostadParser, DostadParserDataParticle
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'mflm',
			     'dosta', 'resource')

@attr('UNIT', group='mi')
class DostadParserUnitTestCase(ParserUnitTestCase):

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
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dostad',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostadParserDataParticle'
            }

        # first DO tag
        self.timestamp1 = 3583610101.0
        self.particle_a = DostadParserDataParticle('\xff\x11\x25\x11' \
            '4831\t128\t302.636\t98.918\t16.355\t30.771\t' \
            '30.771\t36.199\t5.429\t1309.9\t1175.7\t299.6\x0d\x0a',
              internal_timestamp=self.timestamp1)

        self.timestamp2 = 3583612801.0
        self.particle_b = DostadParserDataParticle('\xff\x11\x25\x11' \
            '4831\t128\t317.073\t98.515\t14.004\t31.299\t31.299' \
            '\t36.647\t5.349\t1338.5\t1212.4\t375.8\x0d\x0a',
              internal_timestamp=self.timestamp2)

        self.timestamp3 = 3583634401.0
        self.particle_c = DostadParserDataParticle('\xff\x11\x25\x11' \
            '4831\t128\t326.544\t96.726\t11.873\t31.965\t31.965' \
            '\t37.134\t5.169\t1370.7\t1245.9\t444.4\x0d\x0a',
              internal_timestamp=self.timestamp3)

        self.timestamp4 = 3583656002.0
        self.particle_d = DostadParserDataParticle('\xff\x11\x25\x11' \
            '4831\t128\t332.060\t99.617\t12.432\t31.490\t31.490' \
            '\t36.812\t5.323\t1026.0\t1100.0\t426.5\x0d\x0a',
              internal_timestamp=self.timestamp4)

        self.timestamp5 = 3583677602.0
        self.particle_e = DostadParserDataParticle('\xff\x11\x25\x11' \
            '4831\t128\t354.515\t101.592\t10.440\t31.666\t31.666' \
            '\t36.930\t5.263\t1020.1\t1123.0\t490.0\x0d\x0a',
              internal_timestamp=self.timestamp5)

        self.timestamp6 = 3583699202.0
        self.particle_f = DostadParserDataParticle('\xff\x11\x25\x11' \
            '4831\t128\t337.540\t100.172\t11.955\t31.521\t31.521' \
            '\t36.805\t5.284\t983.8\t1092.6\t441.7\x0d\x0a',
              internal_timestamp=self.timestamp6)

        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def assert_result(self, result, in_process_data, unprocessed_data, timestamp, particle):
        self.assertEqual(result, [particle])
        self.assert_state(in_process_data, unprocessed_data, timestamp)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def assert_state(self, in_process_data, unprocessed_data, timestamp):
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP], timestamp)

    def test_simple(self):
        """
        Read test data from the file and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        # NOTE: using the unprocessed data state of 0,6300 limits the file to reading
        # just 6300 bytes, so even though the file is longer it only reads the first
        # 6300
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 6300]],
            StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	self.parser = DostadParser(self.config, self.state, self.stream_handle,
				  self.state_callback, self.pub_callback, self.exception_callback)

	result = self.parser.get_records(1)
	self.assert_result(result,
			   [[390, 507, 1, 0], [637, 754, 1, 0], [6150, 6267, 1, 0]],
			   [[0,69], [390,507], [637,754], [944, 2370], [2560, 2947],
			    [3137, 4173], [4363, 4943], [5049, 5437], [5683, 6072], [6150, 6300]], 
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[637, 754, 1, 0], [6150, 6267, 1, 0]],
			   [[0,69], [637,754], [944, 2370], [2560, 2947],
			    [3137, 4173], [4363, 4943], [5049, 5437], [5683, 6072], [6150, 6300]],
			   self.timestamp4, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [[6150, 6267, 1, 0]],
			   [[0,69], [944, 2370], [2560, 2947], [3137, 4173], 
			    [4363, 4943], [5049, 5437], [5683, 6072], [6150, 6300]], 
			   self.timestamp4, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [],
			   [[0,69], [944, 2370], [2560, 2947], [3137, 4173], 
			    [4363, 4943], [5049, 5437], [5683, 6072], [6267, 6300]],
			   self.timestamp4, self.particle_d)
	self.stream_handle.close()
	self.assertEqual(self.exception_callback_value, None)

    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
            StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(3)
        self.stream_handle.close()
        self.assertEqual(result,
                         [self.particle_a, self.particle_b, self.particle_c])
        self.assert_state([],
                        [[0,69],[944,1000]],
                        self.timestamp3)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream(self):
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        data = self.stream_handle.read()
        data_len = len(data)
        self.stream_handle.seek(0)
        self.state = {StateKey.UNPROCESSED_DATA:[[0, data_len]],
            StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.parser = DostadParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(6)
        self.stream_handle.close()
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[-3], self.particle_d)
        self.assertEqual(result[-2], self.particle_e)
        self.assertEqual(result[-1], self.particle_f)
        self.assert_state([],
            [[0, 69], [944, 2370], [2560, 2947], [3137, 4173], [4363, 4943], [5049, 5437], [5683, 6072], [8273, 9400]],
            self.timestamp6)
        self.assertEqual(self.publish_callback_value[-2], self.particle_e)
        self.assertEqual(self.publish_callback_value[-1], self.particle_f)
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0,69], [314,1000]],
            StateKey.TIMESTAMP:self.timestamp1}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, [[637, 754, 1, 0],],
                           [[0,69],[637,754],[944,1000]],
                           self.timestamp3, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69],[944,1000]],
                           self.timestamp3, self.particle_c)
        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[[390, 507, 1, 0], [637, 754, 1, 0]],
            StateKey.UNPROCESSED_DATA:[[0,69], [390,507], [637,754], [944,6300]],
            StateKey.TIMESTAMP:self.timestamp3}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)

        # even though the state says this particle is not a new sequence, since it is the
        # first after setting the state it will be new
        self.assert_result(result, [[637, 754, 1, 0]],
                           [[0,69],[637,754],[944,6300]],
                           self.timestamp2, self.particle_b)

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_c)
        self.assertEqual(result[1], self.particle_d)
        self.assert_state([],
            [[0,69],[944, 2370], [2560, 2947], [3137, 4173],
                [4363, 4943], [5049, 5437], [5683, 6072], [6267, 6300]],
            self.timestamp4)
        self.assertEqual(self.publish_callback_value[-1], self.particle_d)
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state(self):
        """
        test changing the state after initializing
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 1000]], StateKey.IN_PROCESS_DATA:[],
            StateKey.TIMESTAMP:0.0}
        new_state = {StateKey.UNPROCESSED_DATA:[[0,69],[944,6300]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.TIMESTAMP:self.timestamp2}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # there should only be 3 records, make sure we stop there
        result = self.parser.get_records(3)
        self.assert_state([],
            [[0,69],[944,1000]],
            self.timestamp3)
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result, [],
                           [[0,69],[944, 2370], [2560, 2947], [3137, 4173],
                            [4363, 4943], [5049, 5437], [5683, 6072], [6267, 6300]],
                           self.timestamp4, self.particle_d)
        self.assertEqual(self.exception_callback_value, None)

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 6300]],
            StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        # this file has a block of FL data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replaced.dat'))
        self.parser = DostadParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, [[637,754,1,0], [6150,6267,1,0]],
                           [[0,69], [390,507], [637,754], [944, 2370], [2560, 2947],
                            [3137, 4173], [4363, 4943], [5049, 5437], [5683, 6072], [6150, 6300]],
                           self.timestamp4, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, [[6150,6267,1,0]],
                           [[0,69], [390,507], [944, 2370], [2560, 2947],
                            [3137, 4173], [4363, 4943], [5049, 5437], [5683, 6072], [6150, 6300]],
                           self.timestamp4, self.particle_c)
        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # first get the old 'in process' records
        # Once those are done, the un processed data will be checked
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69], [390,507], [944, 2370], [2560, 2947], [3137, 4173],
                            [4363, 4943], [5049, 5437], [5683, 6072], [6267, 6300]],
                           self.timestamp4, self.particle_d)

        # this should be the first of the newly filled in particles from
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69], [944, 2370], [2560, 2947], [3137, 4173], [4363, 4943], [5049, 5437],
                            [5683, 6072], [6267, 6300]],
                           self.timestamp2, self.particle_b)
        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)
