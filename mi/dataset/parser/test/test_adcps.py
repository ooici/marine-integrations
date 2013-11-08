#!/usr/bin/env python

import gevent
import unittest
import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.dataset.metadata import Metadata

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.mflm import StateKey
from mi.dataset.parser.adcps import AdcpsParser, AdcpsParserDataParticle
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey

@attr('UNIT', group='mi')
class AdcpsParserUnitTestCase(ParserUnitTestCase):

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
	ParserUnitTestCase.setUp(self)
	self.config = {
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcps',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpsParserDataParticle'
	    }

	# first AD tag from 871-1257 (there is 1 previous AD but the data is corrupted in it)
	self.timestamp1 = 3583725976.97
	self.particle_a = AdcpsParserDataParticle(b'n\x7f\x02\x01m\x00\x00\x00\x002(\xdd\x07\x07\x19\x07\x1a' \
	    '\x10aE#c\xff\r\x00m\x01\\(\x00\x00/\x01\x1c\xc9\xff\x1e\x00\xf9\xff\xca\xff\xd0\xff\xb5\xff\x8a' \
	    '\xff\xa7\xff~\xff\x92\xff\x96\xff\xa1\xff]\xffc\xff\x86\xff_\xff\xd4\xff\xa5\xff\x95\xff\x87\xff' \
	    '\x0c\xffO\xff\xc8\xfff\x00\xaa\x00\xdb\xff\xa6\xffn\xff\r\x00*\x00\xfd\xff\x17\x00\xf8\xff\xf9' \
	    '\xff-\x006\x00:\x00\x1f\x00\xf1\xff\x03\x00\xea\xff\xf1\xff\x06\x00\x08\x00\xca\xff\xa3\xff\x08' \
	    '\x00\x1d\x00\xf1\xff\xfd\xff\xc7\xff\x06\xfe\xd1\xfcr\xfd3\xfe\xa5\xff\xfa\xff\x02\x00\xff\xff' \
	    '\xfe\xff\x00\x00\xfc\xff\xfc\xff\xf6\xff\xfd\xff\x01\x00\xfd\xff\xf6\xff\xf9\xff\xfe\xff\xf5\xff' \
	    '\xf1\xff\x05\x00\xfb\xff\xf1\xff\xf0\xff\xfa\xff\xed\xff\x01\x00\xdb\xff\xe7\xff\xf2\xff\x14\x00' \
	    '\x1f\x00\x0e\x00\x01\x00\xde\xff0\x00\x04\x00\x07\x00\x00\x00\xfa\xff\xed\xff\x1b\x00\x0f\x007' \
	    '\x00\xe1\xff\x10\x00\xf5\xff\xf1\xff\xe2\xff\x0f\x00\x17\x00 \x00\x12\x00\xe3\xff\xf0\xff}\x00-' \
	    '\x00L\x00\x0e\x00\x00\x80\x91\x89',
              internal_timestamp=self.timestamp1, new_sequence=True)
	# second AD block from 1447-1833
	self.timestamp2 = 3583733176.97
	self.particle_b = AdcpsParserDataParticle(b'n\x7f\x02\x01o\x00\x00\x00\x002(\xdd\x07\x07\x19\t\x1a' \
	    '\x10a\x7f:a\xff\n\x00m\x01[(\x00\x00/\x01\x1c\xea\xff\xe4\xff\xe8\xff\xb0\xff\xbf\xff\x98\xff' \
	    '\xc2\xff\xdd\xff\xce\xff\xd7\xff\xaa\xff\x91\xff\x8a\xff\x96\xff\x83\xff\xda\xff\x81\xff\xb6' \
	    '\xff\xca\xff\\\xffK\xff\x85\xff;\x00\xbc\x00\n\x00\x94\x00\xc7\xff \x00\x10\x00\x15\x00A\x009' \
	    '\x00 \x00\x1b\x00\x7f\x00R\x00c\x00S\x00D\x00a\x00X\x00t\x00\xa8\x003\x00\x1c\x00J\x00s\x00]' \
	    '\x00\x8d\x00D\x00a\xff\xf0\xfb\xcd\xfa\x9d\xfb\xb0\xfd\x05\xff\xfe\xff\xf9\xff\xf6\xff\x05' \
	    '\x00\xfe\xff\x05\x00\x02\x00\x14\x00\x0c\x00\n\x00\x13\x00\t\x00\x06\x00\n\x00\x13\x00\x0c' \
	    '\x00\r\x00\x19\x00\x0b\x00\x11\x00\x0c\x00\x04\x00%\x00\xec\xff\xd8\xff\xcb\xff!\x00%\x00' \
	    '\xfa\xff\xf7\xff\xf4\xff\xff\xff\xee\xff\xf1\xff\x03\x00\xe2\xff\xe0\xff\x12\x00\xe5\xff\xf3' \
	    '\xff\xdd\xff\xe1\xff\x03\x00\t\x00\x05\x00\x12\x00\x0b\x00\x02\x00\xec\xff\x16\x00\xc0\x00G' \
	    '\x00\xf7\xff\xd0\xff\xd5\xff\x00\x801n',
	      internal_timestamp=self.timestamp2, new_sequence=False)
	# new particle version for mid-state start
	self.particle_b_new = AdcpsParserDataParticle(b'n\x7f\x02\x01o\x00\x00\x00\x002(\xdd\x07\x07\x19\t\x1a' \
	    '\x10a\x7f:a\xff\n\x00m\x01[(\x00\x00/\x01\x1c\xea\xff\xe4\xff\xe8\xff\xb0\xff\xbf\xff\x98\xff' \
	    '\xc2\xff\xdd\xff\xce\xff\xd7\xff\xaa\xff\x91\xff\x8a\xff\x96\xff\x83\xff\xda\xff\x81\xff\xb6' \
	    '\xff\xca\xff\\\xffK\xff\x85\xff;\x00\xbc\x00\n\x00\x94\x00\xc7\xff \x00\x10\x00\x15\x00A\x009' \
	    '\x00 \x00\x1b\x00\x7f\x00R\x00c\x00S\x00D\x00a\x00X\x00t\x00\xa8\x003\x00\x1c\x00J\x00s\x00]' \
	    '\x00\x8d\x00D\x00a\xff\xf0\xfb\xcd\xfa\x9d\xfb\xb0\xfd\x05\xff\xfe\xff\xf9\xff\xf6\xff\x05' \
	    '\x00\xfe\xff\x05\x00\x02\x00\x14\x00\x0c\x00\n\x00\x13\x00\t\x00\x06\x00\n\x00\x13\x00\x0c' \
	    '\x00\r\x00\x19\x00\x0b\x00\x11\x00\x0c\x00\x04\x00%\x00\xec\xff\xd8\xff\xcb\xff!\x00%\x00' \
	    '\xfa\xff\xf7\xff\xf4\xff\xff\xff\xee\xff\xf1\xff\x03\x00\xe2\xff\xe0\xff\x12\x00\xe5\xff\xf3' \
	    '\xff\xdd\xff\xe1\xff\x03\x00\t\x00\x05\x00\x12\x00\x0b\x00\x02\x00\xec\xff\x16\x00\xc0\x00G' \
	    '\x00\xf7\xff\xd0\xff\xd5\xff\x00\x801n',
	      internal_timestamp=self.timestamp2, new_sequence=True)
	# third AD block 3827-4214
	self.timestamp3 = 3583761976.97
	self.particle_c = AdcpsParserDataParticle(b'n\x7f\x02\x01w\x00\x00\x00\x002(\xdd\x07\x07\x19' \
	    '\x11\x1a\x10a\xc9\x06d\xff\x04\x00m\x01!(\x00\x00/\x01\x1cZ\x00\xf8\xff\x0f\x00\xef\xff\xe8' \
	    '\xff\xd7\xff\xe9\xff\xae\xff\xa2\xff\xd1\xff\xba\xff\xd3\xff\xf0\xff\xda\xff\xe7\xff\x05\x00' \
	    '\xf6\xff\xd2\xff\xa6\xff\x8e\xff\xa1\xff\x92\xff\x16\x00\x8b\x00\xd2\x00\xad\x00\xd2\xffw\xff' \
	    '\xc6\xff\xc9\xff\xdc\xff\xac\xff\xc4\xff\x9d\xffl\xffl\xffr\xff\x8b\xff\x94\xff\xbc\xff\x8d' \
	    '\xffr\xff\x97\xff\x98\xff\xbf\xff\xd0\xff\xe5\xff\x92\xffr\xff\x8c\xff7\xffA\xfb\x8d\xfa$\xfb' \
	    '\r\xfd7\xfe\x06\x00\x00\x00\x01\x00\t\x00\x01\x00\xfa\xff\x00\x00\xfb\xff\xff\xff\x02\x00\x06' \
	    '\x00\x05\x00\x01\x00\x02\x00\x00\x00\xf6\xff\xfd\xff\x04\x00\x02\x00\xfb\xff\x01\x00\x01\x00' \
	    '\x02\x00(\x00\x12\x00*\x00L\x00\x17\x00\x12\x00\x02\x00\xff\xff\xf5\xff\t\x00\xf1\xff\xfd\xff ' \
	    '\x00\xee\xff\x0c\x00\xef\xff\x1c\x00\xfb\xff\xfd\xff\xd4\xff\xd8\xff\xe0\xff\x10\x00\xe4\xff-' \
	    '\x00\xe6\xff\xf5\xff\xd4\xff\xce\xff\xf6\xffl\x00-\x00\x00\x80\x9b\x88',
              internal_timestamp = self.timestamp3, new_sequence=True)
	# fourth AD block 4471-4857
	self.timestamp4 = 3583769176.97
	self.particle_d = AdcpsParserDataParticle(b'n\x7f\x02\x01y\x00\x00\x00\x002(\xdd\x07\x07\x19\x13\x1a' \
	    '\x10a\x9d\x1ba\xff\x06\x00m\x01$(\x00\x00/\x01\x1c\xf7\xff\xfa\xff\xd5\xff\xc5\xff\xb5\xff\x90' \
	    '\xffb\xffn\xff\x90\xffq\xff\x9e\xff\x8c\xff\x93\xff\x80\xff\xa6\xff\x82\xff\xa9\xff\xa8\xff\xb4' \
	    '\xfff\xffu\xff\x94\xffg\xff\t\xff\x08\xff\x13\xff\x1c\xffx\xff\x07\x00\x1b\x00\xe8\xff\x07\x00' \
	    '\x04\x00\x10\x00\x0e\x008\x00;\x00"\x00#\x00\xe6\xff\xf5\xff\xf6\xff\xce\xff\xc4\xff\xec\xff\xc4' \
	    '\xff\xd0\xff\xb9\xff\x9f\xff\xca\xff8\xff|\xfbC\xfa2\xfb\x1d\xfeJ\xff\x02\x00\xfe\xff\x00\x00' \
	    '\xfd\xff\xf8\xff\x01\x00\xff\xff\xfc\xff\n\x00\r\x00\x06\x00\x06\x00\xfe\xff\x04\x00\x04\x00\x05' \
	    '\x00\x04\x00\x08\x00\t\x00\x08\x00\x03\x00\x0f\x00\xea\xff\xf8\xff\xf7\xff(\x00\x17\x00\xef\xff)' \
	    '\x00\x13\x00\x03\x00\xf7\xff\x13\x00\xff\xff\xe9\xff\xf9\xff\x1a\x00\x12\x00\xdc\xff-\x00\xfe' \
	    '\xff\xed\xff\xfa\xff\xf2\xff\x08\x00\xe0\xff\n\x00\x01\x00!\x00\x17\x00\xd0\xff\xd9\xff\xda\xff' \
	    '\x88\x00\x8e\x00\x00\x80\x1e\x7f',
              internal_timestamp = self.timestamp4, new_sequence=True)
	# eleventh AD block 17981-18366
	self.timestamp_k = 3583877176.97
	self.particle_k = AdcpsParserDataParticle(b'n\x7f\x02\x01\x97\x00\x00\x00\x002(\xdd\x07\x07\x1b\x01' \
	    '\x1a\x10a\xe8,T\xff\x07\x00m\x01X(\x00\x00/\x01\x1c\xf6\xff1\x00\x17\x00 \x00\x15\x00/\x00\x16' \
	    '\x00\x16\x00\x14\x00L\x00`\x00^\x00K\x00.\x001\x00%\x00\xf5\xff\xf1\xff\x95\xff\x9f\xff\x8a\xff' \
	    '\xed\xff\'\xff\xe2\xfb\x0f\xfb\x8c\xfb\xb4\xfc\xef\xfd\xff\xff6\x000\x00\x1a\x00;\x00s\x00\x1f\x00' \
	    'M\x00U\x00;\x00Y\x00\r\x00\x14\x00%\x00[\x00a\x00\x16\x00\xe8\xff\xbd\xff\xc9\xff\xd7\xff\xd6\xff' \
	    'Y\x005\x02u\x02j\x02\xb5\x01\x11\x01\t\x00\r\x00\x0c\x00\x0c\x00\x0c\x00\r\x00\xfe\xff\xfc\xff' \
	    '\xfd\xff\x05\x00\x0c\x00\x05\x00\x00\x00\xff\xff\x05\x00\x06\x00\xfb\xff\xfc\xff\xf7\xff\xf5\xff' \
	    '\xfa\xff\xfb\xff\x08\x00\x0b\x00\x07\x00\x11\x00\x10\x00#\x00!\x00\x03\x00\x0c\x00\xff\xff\x0c' \
	    '\x00\x19\x00\t\x00\t\x00\xf0\xff\x14\x00\xe3\xff\n\x00\x1b\x00\x05\x00\xf8\xff\x1a\x00\x08\x00' \
	    '\xfc\xff\x19\x00\xfa\xff\x07\x00\x16\x00\x10\x00\xe2\xff\x9c\xff#\x00\xd8\xff\x00\x80\xc1W',
              internal_timestamp = self.timestamp_k, new_sequence=True)
	# twelvth AD block 18556-18943
	self.timestamp_l = 3583884376.97
	self.particle_l = AdcpsParserDataParticle(b'n\x7f\x02\x01\x99\x00\x00\x00\x002(\xdd\x07\x07\x1b\x03' \
	    '\x1a\x10a\x05\x02]\xff\n\x00j\x013(\x00\x00/\x01\x1c\xed\xff\x01\x00&\x00\'\x002\x00\x1b\x00#' \
	    '\x00D\x00D\x00\xf4\xff&\x003\x00\x17\x00\x19\x00\xf3\xffc\x00\x02\x00\x0f\x00\xdb\xff\xe8\xff' \
	    '\xfd\xff\xfe\xff\xd7\xff\'\xfb\x01\xfaS\xfa\xcc\xfc\xb7\xfe\xdb\xff\xc3\xff\xd2\xff\xf2\xff\xdd' \
	    '\xff\xc5\xff\xce\xff\x92\xff\xd4\xff\xca\xff\xe5\xffy\xff\xa7\xff\xe4\xff\xcb\xff\xb8\xff\xdc' \
	    '\xff\xc5\xff\xab\xff\x84\xff\xc1\xff\x8e\xff]\xff9\xff\x00\xff\x1f\xff\t\xff\x01\x00\xfc\xff\xf4' \
	    '\xff\xf2\xff\xfb\xff\xf8\xff\xfb\xff\xf2\xff\xfd\xff\xf9\xff\xfe\xff\xf9\xff\x07\x00\xf7\xff\xfb' \
	    '\xff\x00\x00\n\x00\x01\x00\x04\x00\x13\x00\x0f\x00\xfb\xff\x05\x00\x0f\x00\x04\x00\xf4\xff\xe1' \
	    '\xff"\x00 \x00\xee\xff\xea\xff\x1c\x00\xda\xff\xfc\xff:\x00\xf0\xff\xe8\xff$\x00\x16\x00\x06' \
	    '\x00\xf5\xff\xe1\xff\n\x00\xf9\xff/\x00\xdd\xff:\x00\x13\x00\x03\x00\xf4\xff\x05\x00\x1d\x00' \
	    '\x04\x00 \x002\x00\xe0\xff\x00\x80\xb6\x83',
              internal_timestamp = self.timestamp_l, new_sequence=False)

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
        self.assertAlmostEqual(self.state_callback_value[StateKey.TIMESTAMP], timestamp, places=6)

    def test_simple(self):
	"""
	Read test data from the file and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
	log.debug('Starting test_simple')
	self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
	# NOTE: using the unprocessed data state of 0,5000 limits the file to reading
	# just 5000 bytes, so even though the file is longer it only reads the first
	# 5000
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	self.parser = AdcpsParser(self.config, self.state, self.stream_handle,
				  self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
	self.assert_result(result,
			   [[1447,1833,1,0,0],[3827,4214,1,0,1],[4471,4857,1,0,1]],
			   [[0,32],[222,871],[1447,3058],[3248,4281],[4471,5000]], 
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[3827,4214,1,0,1],[4471,4857,1,0,1]],
			   [[0,32], [222,871],[1833,3058],[3248,4281],[4471,5000]],
			   self.timestamp4, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [[4471,4857,1,0,1]],
			   [[0,32],[222,871],[1833,3058],[3248,3827],[4214,4281],[4471,5000]], 
			   self.timestamp4, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [],
			   [[0,32],[222,871],[1833,3058],[3248,3827],[4214,4281],[4857,5000]],
			   self.timestamp4, self.particle_d)
	self.stream_handle.close()

    def test_get_many(self):
	"""
	Read test data from the file and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
	log.debug('Starting test_get_many')
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(4)
	self.stream_handle.close()
        self.assertEqual(result,
			 [self.particle_a, self.particle_b, self.particle_c, self.particle_d])
	self.assert_state([],
			[[0,32],[222,871],[1833,3058],[3248,3827],[4214,4281],[4857,5000]],
			self.timestamp4)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
	self.assertEqual(self.publish_callback_value[2], self.particle_c)
	self.assertEqual(self.publish_callback_value[3], self.particle_d)

    def test_long_stream(self):
	log.debug('Starting test_long_stream')
	self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
	data = self.stream_handle.read()
	data_len = len(data)
	self.stream_handle.seek(0)
	self.state = {StateKey.UNPROCESSED_DATA:[[0, data_len]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(12)
	self.stream_handle.close()
	self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
	self.assertEqual(result[2], self.particle_c)
	self.assertEqual(result[3], self.particle_d)
	self.assertEqual(result[-2], self.particle_k)
	self.assertEqual(result[-1], self.particle_l)
	self.assert_state([],
	    [[0, 32], [222, 871], [1833, 3058], [3248, 3827], [4214, 4281],
		[5047, 5153], [5539, 5730], [5786, 6433], [7009, 7396], [7586, 9200],
		[14220, 14608], [15374, 15830], [16596, 17280], [17722, 17791], [19133, 22000]],
	    self.timestamp_l)
	self.assertEqual(self.publish_callback_value[-2], self.particle_k)
        self.assertEqual(self.publish_callback_value[-1], self.particle_l)

    def test_mid_state_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
	log.debug('Starting test_mid_state_start')
        new_state = {StateKey.IN_PROCESS_DATA:[],
	    StateKey.UNPROCESSED_DATA:[[0,32], [222,871], [1447,5000]],
	    StateKey.TIMESTAMP:self.timestamp1}
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, [[3827,4214,1,0,1],[4471,4857,1,0,1]],
			   [[0,32], [222,871],[1833,3058],[3248,4281],[4471,5000]],
			   self.timestamp4, self.particle_b_new)
	result = self.parser.get_records(1)
        self.assert_result(result, [[4471,4857,1,0,1]],
			   [[0,32], [222,871],[1833,3058],[3248,3827],[4214,4281],[4471,5000]],
			   self.timestamp4, self.particle_c)
	
	self.stream_handle.close()

    def test_in_process_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
	log.debug('Starting test_in_process_start')
        new_state = {StateKey.IN_PROCESS_DATA:[[1447,1833,1,0,0],[3827,4214,1,0,1],[4471,4857,1,0,1]],
	    StateKey.UNPROCESSED_DATA:[[0,32], [222,871],[1447,3058],[3248,4281],[4471,5000]],
	    StateKey.TIMESTAMP:self.timestamp4}
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
	
	# even though the state says this particle is not a new sequence, since it is the
	# first after setting the state it will be new
        self.assert_result(result, [[3827,4214,1,0,1],[4471,4857,1,0,1]],
			   [[0,32], [222,871],[1833,3058],[3248,4281],[4471,5000]],
			   self.timestamp2, self.particle_b_new)
	
	result = self.parser.get_records(2)
	self.assertEqual(result[0], self.particle_c)
	self.assertEqual(result[1], self.particle_d)
	self.assert_state([],
	    [[0,32],[222,871],[1833,3058],[3248,3827],[4214,4281],[4857,5000]],
	    self.timestamp4)
	self.assertEqual(self.publish_callback_value[-1], self.particle_d)

    def test_set_state(self):
	"""
	test changing the state after initializing
	"""
	log.debug('Starting test_set_state')
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 4500]], StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:0.0}
        new_state = {StateKey.UNPROCESSED_DATA:[[0,32],[222,871],[1833,3058],[3248,3827],[4214,4281],[4471,5000]],
	    StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:self.timestamp2}

        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
	# there should only be 6 records, make sure we stop there
        result = self.parser.get_records(6)
	self.assert_state([],
	    [[0,32],[222,871],[1833,3058],[3248,3827],[4214,4281],[4471,4500]],
	    self.timestamp3)
	result = self.parser.get_records(1)
	self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [],
			   [[0,32],[222,871],[1833,3058],[3248,3827],[4214,4281],[4857,5000]],
			   self.timestamp4, self.particle_d)

    def test_update(self):
	"""
	Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
	then using the returned state make a new parser with the test data that has the 0s filled in
	"""
	log.debug('Starting test_update')
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	# this file has a block of AD data replaced by 0s
        self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_replaced.dat'))
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
	self.assert_result(result, [[1447,1833,1,0,0],[4471,4857,1,0,1]],
			   [[0,32],[222,871],[1447,3058],[3248,4281],[4471,5000]],
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[4471,4857,1,0,1]],
			   [[0,32],[222,871],[1833,3058],[3248,4281],[4471,5000]],
			   self.timestamp4, self.particle_b)
	self.stream_handle.close()

	next_state = self.parser._state
	# this file has the block of CT data that was missing in the previous file
	self.stream_handle = open(os.path.join(Metadata().resource_dir(),
					       'node59p1_shorter.dat'))
	self.parser = AdcpsParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

	# first get the old 'in process' records
	# Once those are done, the un processed data will be checked
	result = self.parser.get_records(1)
	self.assert_result(result, [],
			   [[0,32],[222,871],[1833,3058],[3248,4281],[4857,5000]],
			   self.timestamp4, self.particle_d)

	# this should be the first of the newly filled in particles from
        result = self.parser.get_records(1)
        self.assert_result(result, [],
			   [[0,32],[222,871],[1833,3058],[3248,3827],[4214,4281],[4857,5000]],
			   self.timestamp3, self.particle_c)
	self.stream_handle.close()

