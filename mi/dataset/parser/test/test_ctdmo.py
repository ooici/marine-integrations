#!/usr/bin/env python

import gevent
import unittest
import os
from nose.plugins.attrib import attr
from StringIO import StringIO

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.dataset.metadata import Metadata

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.mflm import StateKey
from mi.dataset.parser.ctdmo import CtdmoParser, CtdmoParserDataParticle
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey

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
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'CtdmoParserDataParticle'
	    }


	# packets have the same timestamp, the first has 3 data samples [394-467]
	self.timestamp1 = 3583612801.0
        self.particle_a = CtdmoParserDataParticle(b'\x15\x38\x53\x66\x9e\x1a\xa2\x0c\x81\xd5\x81\x19\x0d',
                                                  internal_timestamp=self.timestamp1, new_sequence=True)
	self.particle_b = CtdmoParserDataParticle(b'\x35\x3b\xa2\x10\xc3\x5a\xe7\x0a\x81\xd5\x81\x19\x0d',
						  internal_timestamp=self.timestamp1, new_sequence=False)
	self.particle_c = CtdmoParserDataParticle(b'\x37\x39\x4c\xe0\xc3\x54\xe6\x0a\x81\xd5\x81\x19\x0d',
						  internal_timestamp=self.timestamp1, new_sequence=False)
	# this is the start of packet 2 [5354:5544]
	self.timestamp2 = 3583634401.0
	self.particle_d = CtdmoParserDataParticle(b'\x40\x21\xbe\x25\x94\x9d\xa0\x1c\xe1\x29\x82\x19\x0d',
						  internal_timestamp=self.timestamp2, new_sequence=True)
	self.particle_e = CtdmoParserDataParticle(b'\x41\x21\xc4\xd5\x94\x39\xe7\x1b\xe1\x29\x82\x19\x0d',
						  internal_timestamp=self.timestamp2, new_sequence=False)
	# particle 14
	self.particle_n = CtdmoParserDataParticle(b'58;v\x9d=%\x0b\xe1)\x82\x19\r',
						  internal_timestamp=self.timestamp2, new_sequence=False)
	# particle 15
	self.particle_o = CtdmoParserDataParticle(b'75\x8b\xe0\xc3T\xe5\n\xe1)\x82\x19\r',
						  internal_timestamp=self.timestamp2, new_sequence=False)
	# start of packet 3 [6970-7160]
	# particle 16
	self.timestamp3 = 3583656001.0
	self.particle_p = CtdmoParserDataParticle(b'@\x1e\x0b5\x8a]\x07iA~\x82\x19\r',
						   internal_timestamp=self.timestamp3, new_sequence=True)
	self.particle_q = CtdmoParserDataParticle(b'A\x1f\x8a5\x92\x9d?IA~\x82\x19\r',
						   internal_timestamp=self.timestamp3, new_sequence=False)
	# packet 4 [7547-7737]
	self.timestamp4 = 3583663201.0
	self.particle_y = CtdmoParserDataParticle(b'@\x1e\x04\xf5\x8a\x12\xf6ha\x9a\x82\x19\r',
						   internal_timestamp=self.timestamp4, new_sequence=True)
	self.particle_z = CtdmoParserDataParticle(b'A\x1fu\xa5\x91\xaf/Ia\x9a\x82\x19\r',
						   internal_timestamp=self.timestamp4, new_sequence=False)

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
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 6000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
	self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
				  self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
	self.stream_handle.close()
	self.assert_result(result, [[394, 467, 3, 1, 1], [5354, 5544, 12, 0, 1]],
			   [[0, 12], [336, 2010], [5354, 6000]],
			   self.timestamp2, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[394, 467, 3, 2, 1], [5354, 5544, 12, 0, 1]],
			   [[0, 12], [336, 2010], [5354, 6000]],
			   self.timestamp2, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [[5354, 5544, 12, 0, 1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 6000]],
			   self.timestamp2, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [[5354, 5544, 12, 1, 1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 6000]],
			   self.timestamp2, self.particle_d)
	result = self.parser.get_records(1)
	self.assert_result(result, [[5354, 5544, 12, 2, 1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 6000]],
			   self.timestamp2, self.particle_e)

    def test_get_many(self):
	"""
	Read test data from the file and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 6000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(3)
	self.stream_handle.close()
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c])
	self.assert_state([[5354, 5544, 12, 0, 1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 6000]], self.timestamp2)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
	self.assertEqual(self.publish_callback_value[2], self.particle_c)

    def test_long_stream(self):
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 8000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(29)
	self.stream_handle.close()
	self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
	self.assertEqual(result[2], self.particle_c)
	self.assertEqual(result[3], self.particle_d)
	self.assertEqual(result[-16], self.particle_n)
        self.assertEqual(result[-15], self.particle_o)
	self.assertEqual(result[-14], self.particle_p)
	self.assertEqual(result[-13], self.particle_q)
	self.assertEqual(result[-2], self.particle_y)
	self.assertEqual(result[-1], self.particle_z)
	self.assert_state([[7547, 7737, 12, 2, 1]],
	    [[0, 12], [336, 394], [467, 2010], [5544, 6970], [7160, 8000]],
	    self.timestamp4)
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)

    def test_mid_state_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
        new_state = {StateKey.IN_PROCESS_DATA:[],
	    StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [467, 2010], [5354, 6000]],
	    StateKey.TIMESTAMP:self.timestamp1}
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [[5354, 5544, 12, 1, 1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 6000]],
			   self.timestamp2, self.particle_d)

    def test_in_process_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
        new_state = {StateKey.IN_PROCESS_DATA:[[5354, 5544, 12, 1, 1]],
	    StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [467, 2010], [5354, 7160]],
	    StateKey.TIMESTAMP:self.timestamp2}
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, [[5354, 5544, 12, 2, 1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 7160]],
			   self.timestamp2, self.particle_e)
	
	result = self.parser.get_records(11)
	self.assertEqual(result[-1], self.particle_p)
	self.assert_state([[6970, 7160, 12, 1, 1]],
			[[0, 12], [336, 394], [467, 2010], [5544, 7160]],
			   self.timestamp3)
	self.assertEqual(self.publish_callback_value[-1], self.particle_p)

    def test_set_state(self):
	"""
	test changing the state after initializing
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 500]], StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:0.0}
        new_state = {StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [467, 2010], [5354, 6000]],
	    StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:self.timestamp1}

        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
	# there should only be 3 records, make sure we stop there
        result = self.parser.get_records(3)
	result = self.parser.get_records(1)
	self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [[5354, 5544, 12, 1, 1]],
			   [[0, 12], [336, 394], [467, 2010], [5354, 6000]],
			   self.timestamp2, self.particle_d)

    def test_update(self):
	"""
	Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
	then using the returned state make a new parser with the test data that has the 0s filled in
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 7160]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	# this file has a block of CT data replaced by 0s
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_replace.dat'))
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
	self.assert_result(result, [[394, 467, 3, 1, 1], [6970, 7160, 12, 0, 1]],
			   [[0, 12], [336, 2010], [5354, 7160]],
			   self.timestamp3, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[394, 467, 3, 2, 1], [6970, 7160, 12, 0, 1]],
			   [[0, 12], [336, 2010], [5354, 7160]],
			   self.timestamp3, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [[6970, 7160, 12, 0, 1]],
			   [[0, 12], [336,394], [467, 2010], [5354, 7160]],
			   self.timestamp3, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [[6970, 7160, 12, 1, 1]],
			   [[0, 12], [336,394], [467, 2010], [5354, 7160]],
			   self.timestamp3, self.particle_p)
	self.stream_handle.close()

	next_state = self.parser._state
	# this file has the block of CT data that was missing in the previous file
	self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
	self.parser = CtdmoParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

	# first get the old 'in process' records from [6970-7160]
	# Once those are done, the un processed data will be checked
	result = self.parser.get_records(11)
	self.assertEqual(result[0], self.particle_q)
	self.assert_state([], [[0, 12], [336,394], [467, 2010], [5354, 6970]],
			   self.timestamp3)

	# this should be the first of the newly filled in particles from [5354-5544]
        result = self.parser.get_records(1)
        self.assert_result(result, [[5354, 5544, 12, 1, 1]],
			   [[0, 12], [336,394], [467, 2010], [5354, 6970]],
			   self.timestamp2, self.particle_d)
	self.stream_handle.close()

