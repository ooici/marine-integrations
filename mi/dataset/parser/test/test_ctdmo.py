#!/usr/bin/env python

import gevent
import unittest
import os
from nose.plugins.attrib import attr
from StringIO import StringIO

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.mflm import StateKey
from mi.dataset.parser.ctdmo import CtdmoParser, CtdmoParserDataParticle
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import DatasetParserException

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'mflm',
			     'ctd', 'resource')

@attr('UNIT', group='mi')
class CtdmoParserUnitTestCase(ParserUnitTestCase):

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
	ParserUnitTestCase.setUp(self)
	self.config = {
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'CtdmoParserDataParticle',
	    'inductive_id': 55
	    }

	# packets have the same timestamp, the first has 3 data samples [394-467]
	self.timestamp1 = 3583612801.0
	self.particle_a = CtdmoParserDataParticle(b'\x37\x39\x4c\xe0\xc3\x54\xe6\x0a\x81\xd5\x81\x19\x0d',
						  internal_timestamp=self.timestamp1)
	# this is the start of packet 2 [5354:5544]
	self.timestamp2 = 3583634401.0
	self.particle_b = CtdmoParserDataParticle(b'\x37\x35\x8b\xe0\xc3T\xe5\n\xe1)\x82\x19\r',
						  internal_timestamp=self.timestamp2)
	# start of packet 3 [6970-7160]
	self.timestamp3 = 3583656001.0
	self.particle_c = CtdmoParserDataParticle(b'\x37\x36\xe7\xe6\x89W9\x10A~\x82\x19\r',
						   internal_timestamp=self.timestamp3)
	# packet 4 [7547-7737]
	self.timestamp4 = 3583663201.0
	self.particle_d = CtdmoParserDataParticle(b'\x37\x32\t6F\x0c\xd5\x0fa\x9a\x82\x19\r',
						   internal_timestamp=self.timestamp4)

	self.timestamp_last = 3583692001.0
	self.particle_z = CtdmoParserDataParticle(b'73\xcd\x86_\x92\x13\x10\xe1\n\x83\x19\r',
						   internal_timestamp=self.timestamp_last)

	self.state_callback_value = None
        self.publish_callback_value = None

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
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 8000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
	self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
				  self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
	self.assert_result(result, [[5354, 5544, 1, 0, 1], [6970,7160,1,0,1], [7547,7737,1,0,1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 8000]],
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[6970,7160,1,0,1], [7547,7737,1,0,1]],
			   [[0, 12], [336, 394], [467, 2010], [5544, 8000]],
			   self.timestamp4, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [[7547,7737,1,0,1]],
			   [[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 8000]],
			   self.timestamp4, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [],
			   [[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 7547],[7737, 8000]],
			   self.timestamp4, self.particle_d)
	self.stream_handle.close()

    def test_missing_inductive_id_config(self):
	"""
	Make sure that the driver complains about a missing inductive ID in the config
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 8000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
	bad_config = {
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'CtdmoParserDataParticle',
	    }
	with self.assertRaises(DatasetParserException):
	    self.parser = CtdmoParser(bad_config, self.state, self.stream_handle,
				      self.state_callback, self.pub_callback)

    def test_get_many(self):
	"""
	Read test data from the file and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 7500]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(3)
	self.stream_handle.close()
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c])
	self.assert_state([],
			   [[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 7500]], self.timestamp3)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
	self.assertEqual(self.publish_callback_value[2], self.particle_c)

    def test_long_stream(self):
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 14000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_longer.dat'))
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(6)
	self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
	self.assertEqual(result[2], self.particle_c)
	self.assertEqual(result[3], self.particle_d)
	self.assertEqual(result[-1], self.particle_z)
	self.assert_state([],
	    [[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 7547],
		[7737, 8773], [8963, 10037], [10283, 10672], [12873, 14000]],
	    self.timestamp_last)
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)
	self.stream_handle.close()

    def test_mid_state_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
        new_state = {StateKey.IN_PROCESS_DATA:[],
	    StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [467, 2010], [5544, 7500]],
	    StateKey.TIMESTAMP:self.timestamp1}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [],
			   [[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 7500]],
			   self.timestamp3, self.particle_c)

    def test_in_process_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
        new_state = {StateKey.IN_PROCESS_DATA:[[6970,7160,1,0,1], [7547,7737,1,0,1]],
	    StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [467, 2010], [5544, 8000]],
	    StateKey.TIMESTAMP:self.timestamp2}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

	result = self.parser.get_records(2)
	self.assertEqual(result[0], self.particle_c)
	self.assertEqual(result[-1], self.particle_d)
	self.assert_state([],
			[[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 7547],[7737, 8000]],
			   self.timestamp4)
	self.assertEqual(self.publish_callback_value[-1], self.particle_d)

    def test_set_state(self):
	"""
	test changing the state after initializing
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 500]], StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:0.0}
        new_state = {StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [467, 2010], [5544, 7500]],
	    StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:self.timestamp1}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
	# there should only be 1 records, make sure we stop there
        result = self.parser.get_records(1)
	self.assertEqual(result[0], self.particle_a)
	result = self.parser.get_records(1)
	self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [],
			   [[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 7500]],
			   self.timestamp3, self.particle_c)

    def test_update(self):
	"""
	Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
	then using the returned state make a new parser with the test data that has the 0s filled in
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 8000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	# this file has a block of CT data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_replace.dat'))
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
	self.assert_result(result, [[6970,7160,1,0,1], [7547,7737,1,0,1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 8000]],
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[7547,7737,1,0,1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 6970], [7160, 8000]],
			   self.timestamp4, self.particle_c)
	self.stream_handle.close()

	next_state = self.parser._state
	# this file has the block of CT data that was missing in the previous file
	self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
	self.parser = CtdmoParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

	# first get the old 'in process' records from [6970-7160]
	# Once those are done, the un processed data will be checked
	result = self.parser.get_records(1)
	self.assert_result(result, [],
			   [[0, 12], [336, 394], [467, 2010], [5354, 6970], [7160, 7547],[7737, 8000]],
			   self.timestamp4, self.particle_d)

	# this should be the first of the newly filled in particles from [5354-5544]
        result = self.parser.get_records(1)
        self.assert_result(result, [],
			   [[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 7547],[7737, 8000]],
			   self.timestamp2, self.particle_b)
	self.stream_handle.close()

