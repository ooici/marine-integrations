#!/usr/bin/env python

import gevent
import unittest
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.mflm import StateKey
from mi.dataset.parser.ctdmo import CtdmoParser, CtdmoParserDataParticle
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

TEST_FILE='/tmp/dsatest/node59p1_short.dat'
BAD_TEST_FILE='/tmp/dsatest/node59p1_bad.dat'

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

	# blocks have the same timestamp, chunk 1 has 3 data samples
	self.timestamp1 = 3583656001.0
        self.particle_a = CtdmoParserDataParticle(b'\x15\x38\x53\x66\x9e\x1a\xa2\x0c\x81\xd5\x81\x19\x0d',
                                                  internal_timestamp=self.timestamp1)
	self.particle_b = CtdmoParserDataParticle(b'\x35\x3b\xa2\x10\xc3\x5a\xe7\x0a\x81\xd5\x81\x19\x0d',
						  internal_timestamp=self.timestamp1)
	self.particle_c = CtdmoParserDataParticle(b'\x37\x39\x4c\xe0\xc3\x54\xe6\x0a\x81\xd5\x81\x19\x0d',
						  internal_timestamp=self.timestamp1)
	# this is the start of block 2
	self.timestamp2 = 3583663201.0
	self.particle_d = CtdmoParserDataParticle(b'\x40\x3a\x7f\xa0\xc3\x56\xe0\x0a\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2)
	self.particle_e = CtdmoParserDataParticle(b'\x41\x22\xf2\xa5\x95\x31\xaf\x13\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2)
	# particle 14
	self.particle_x = CtdmoParserDataParticle(b'\x35\x38\x99\xa6\xa1\x76\x0f\x0b\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2)
	# particle 15
	self.particle_z = CtdmoParserDataParticle(b'\x37\x37\xf0\x00\xc3\x54\xe5\x0a\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2)
	# particle 16 (block 3)
	self.timestamp3 = 3583670401.0
	self.particle_zz = CtdmoParserDataParticle(b'\x40\x21\xcb\xc5\x97\x38\x4a\x1e\xc1\x0d\x82\x19\x0d',
						   internal_timestamp=self.timestamp3)
	# block 4
	self.timestamp4 = 3583677601.0
	self.particle_aa = CtdmoParserDataParticle(b'\x40\x21\xbe\x25\x94\x9d\xa0\x1c\xe1\x29\x82\x19\x0d',
						   internal_timestamp=self.timestamp4)
	self.particle_bb = CtdmoParserDataParticle(b'\x41\x21\xc4\xd5\x94\x39\xe7\x1b\xe1\x29\x82\x19\x0d',
						   internal_timestamp=self.timestamp4)

	self.state = {StateKey.PROCESSED_BLOCKS:[], StateKey.IN_PROCESS_BLOCKS:[], StateKey.TIMESTAMP:0.0}

	self.state_callback_value = None
        self.publish_callback_value = None

    def assert_result(self, result, processed_blocks, timestamp, particle):
        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.PROCESSED_BLOCKS], processed_blocks)
        self.assertEqual(self.state_callback_value[StateKey.PROCESSED_BLOCKS], processed_blocks)
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP], timestamp)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
	"""
	Read test data from the file and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
	self.stream_handle = open(TEST_FILE, 'rb')
	self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
				  self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
	self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')],
			   self.timestamp2, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')],
			   self.timestamp2, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')],
			   self.timestamp2, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')],
			   self.timestamp2, self.particle_d)
	result = self.parser.get_records(1)
	self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')],
			   self.timestamp2, self.particle_e)

    def test_get_many(self):
	"""
	Read test data from the file and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
        self.stream_handle = open(TEST_FILE, 'rb')
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(3)
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c])
        self.assertEqual(self.parser._state[StateKey.PROCESSED_BLOCKS],
			 [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')])
        self.assertEqual(self.state_callback_value[StateKey.PROCESSED_BLOCKS],
			 [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')])
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP],
                         self.timestamp2)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
	self.assertEqual(self.publish_callback_value[2], self.particle_c)

    def test_long_stream(self):
        self.stream_handle = open(TEST_FILE, 'rb')
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(16)
	self.assertEqual(result[-3], self.particle_x)
        self.assertEqual(result[-2], self.particle_z)
	self.assertEqual(result[-1], self.particle_zz)
        self.assertEqual(self.parser._state[StateKey.PROCESSED_BLOCKS],
			 [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6'), (70, '51EF6F16')])
        self.assertEqual(self.state_callback_value[StateKey.PROCESSED_BLOCKS],
			 [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6'), (70, '51EF6F16')])
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP],
                         self.timestamp3)
        self.assertEqual(self.publish_callback_value[-1], self.particle_zz)

    def test_mid_state_start(self):
        new_state = {StateKey.IN_PROCESS_BLOCKS: [],
	    StateKey.PROCESSED_BLOCKS: [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')],
	    StateKey.TIMESTAMP:self.timestamp2}
        self.stream_handle = open(TEST_FILE, 'rb')
        self.parser = CtdmoParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6'), (70, '51EF6F16')],
			   self.timestamp3, self.particle_zz)

    def test_set_state(self):
        new_state = {StateKey.IN_PROCESS_BLOCKS: [],
	    StateKey.PROCESSED_BLOCKS: [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6'), (70, '51EF6F16')],
	    StateKey.TIMESTAMP:self.timestamp3}

        self.stream_handle = open(TEST_FILE, 'rb')
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
	self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6')],
			   self.timestamp2, self.particle_a)

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6'), (70, '51EF6F16'), (87, '51EF8B36')],
			   self.timestamp4, self.particle_aa)
        result = self.parser.get_records(1)
        self.assert_result(result, [(19, '51EF1AB5'), (36, '51EF36D6'), (53, '51EF52F6'), (70, '51EF6F16'), (87, '51EF8B36')],
			   self.timestamp4, self.particle_bb)

    def test_bad_data(self):
        """ There's a bad sample in the data! Ack! Skip it! """
        self.stream_handle = open(BAD_TEST_FILE, 'rb')
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
        self.assert_result(result, [(19, '51EF1AB5'), (53, '51EF52F6')],
			   self.timestamp2, self.particle_d)

