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

@attr('UNIT', group='mi')
class CtdmoParserUnitTestCase(ParserUnitTestCase):

    TEST_DATA=b'\nDeploy loop started on Tue Jul 23 22:33:23 2013\n\x03\x01CS1237101_0012u51EF04CE' \
	      '_04_C3AF\x02\n18.72 17.4 2 1 1\n\x03\x01AD1237111_003Au51EF0FAB_06_36BC\x02<ERROR ' \
	      'type=\'FAILED\' msg=\'No reply from remote device\'/>\r\n\x03\x01CT1237100_0000b51E' \
	      'F1AB5_13_0000\x02\x03\x01CS1237101_0014u51EF1B95_14_C795\x02\n18.88 18.5 206 6 0\n\x03' \
	      '\x01AD1237111_003Au51EF1DBB_15_36BC\x02<ERROR type=\'FAILED\' msg=\'No reply from remote '\
	      'device\'/>\r\n\x03<ERROR type=\'FAILED\' msg=\'No reply from remote device\'/>\r\n\x01CT1' \
	      '237100_0027b51EF36D6_24_507E\x02\x158Sf\x9e\x1a\xa2\x0c\x81\xd5\x81\x19\r5;\xa2\x10\xc3Z' \
	      '\xe7\n\x81\xd5\x81\x19\r79L\xe0\xc3T\xe6\n\x81\xd5\x81\x19\r\x03\x01AD1237111_0160u51EF39' \
	      'DB_26_C346\x02<Executing/>\r\n<SampleData ID=\'0x1ba\' LEN=\'260\' CRC=\'0x419c3b95\'>n\x7f' \
	      '\x02\x01O\x00\x00\x00\x002(\xdd\x07\x07\x18X\x01\x1a\x10a6`\xea\tP\x05.\x05\x01\x00\x00' \
	      '\x00/\x01\x1c\xc9\xff\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00' \
	      '\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x02\x00\x00\x80\x00\x80\x00\x80\x00' \
	      '\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00' \
	      '\x80S\xff\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00' \
	      '\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x0f\x00\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\xb1></SampleData>\r\n<E' \
	      'xecuted/>\r\n\x03\x01CT1237100_009Cb51EF52F6_35_210A\x02@:\x7f\xa0\xc3V\xe0\n\xa1\xf1\x81\x19\rA"\xf2\xa5' \
	      '\x951\xaf\x13\xa1\xf1\x81\x19\rB$\x8f\x05\xa2\xf3\xb3\x12\xa1\xf1\x81\x19\r:%\xb7e\x9d5J\x1b\xa1' \
	      '\xf1\x81\x19\r\x100x\xf6/\x9f\xf0\x0f\xa1\xf1\x81\x19\r?%\xc8\x95\x9e\r\xb8\x1a\xa1\xf1\x81' \
	      '\x19\r;\'\\\xd5\xb2\xbe\xc0\x16\xa1\xf1\x81\x19\r\x11\x18k\xf9\xb5\xf0\xce\x13\x14\xa1\xf1\x81' \
	      '\x19\r\x16&\xf8\xb5\xad\x86\xfe\x17\xa1\xf1\x81\x19\r\x158\x97\x06\xa1\xbd\xca\x0c\xa1\xf1\x81' \
	      '\x19\r58\x99\xa6\xa1v\x0f\x0b\xa1\xf1\x81\x19\r77\xf0\x00\xc3T\xe5\n\xa1\xf1\x81\x19\r\x03' \
	      '\x01AD1237111_0160u51EF55FB_37_3F1D\x02<Executing/>\r\n<SampleData ID=\'0x1bc\' LEN=\'260\' CRC=' \
	      '\'0xb14a36ac\'>n\x7f\x02\x01Q\x00\x00\x00\x002(\xdd\x07\x07\x18X\x03\x1a\x10a!k\xf2\x05\xf0\x04' \
	      '\xff\x04\xff\xff\xff\xff/\x01\x1c\xa3\xff\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00' \
	      '\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\xe0\xff\x00\x80\x00' \
	      '\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00' \
	      '\x80\x00\x80\x00\x80\xb7\xfe\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00' \
	      '\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\xdc\xff\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00' \
	      '\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\xffG</SampleData>\r\n<Executed/>\r\n\x03\x01CT1237100_009Cb51EF6F16_46_D500\x02@!\xcb' \
	      '\xc5\x978J\x1e\xc1\r\x82\x19\rA!\x94\x95\x928*\x1d\xc1\r\x82\x19\rB!\xe3\x05\x8f\xc8\xbb\x16' \
	      '\xc1\r\x82\x19\r:&R5\xa5\xcc?\x1b\xc1\r\x82\x19\r\x100\x98\x160#\xec\x0f\xc1\r\x82\x19\r?&\x85' \
	      '\xe5\xa8e\xbe\x1a\xc1\r\x82\x19\r;\'\xd9\x05\xb9\xeb\xd1\x16\xc1\r\x82\x19\r\x11*\x93\x95\xdc' \
	      '\xdb\xfd\x13\xc1\r\x82\x19\r\x16&\xe3\x85\xac\xaa\xf2\x17\xc1\r\x82\x19\r\x158_V\x9e\xaf\xc5\x0c' \
	      '\xc1\r\x82\x19\r58Wv\x9e\x18k-\x0b\xc1\r\x82\x19\r76$p\xc3T\xe4\n\xc1\r\x82\x19\r\x03\x01AD12371' \
	      '11_0160u51EF721B_48_70C2\x02<Executing/>\r\n<SampleData ID=\'0x1be\' LEN=\'260\' CRC=\'0x17edae6d\'>n' \
	      '\x7f\x02\x01S\x00\x00\x00\x002(\xdd\x07\x07\x18X\x05\x1a\x10aYl\x8d\t\x19\x06\xfc\x04\xff\xff\xff' \
	      '\xff/\x01\x1c4\xff\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\xa7\xff\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\xda\xfe\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\xf7\xff\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80' \
	      '\x00\x80\x00\x80\x00\x80\x00\x80\x00\x80\x99F</SampleData>\r\n<Executed/>\r\n\x03\x01CS1236501_00' \
	      '14u51EF1B95_0D_B13D\x02\n18.93 14.2 71 11 0\n\x03\x01FL1236501_002Au51EF6D61_41_411A\x0207/24/13' \
	      '\t06:00:05\t700\t78\t695\t72\t460\t51\t553\x03\x01DO1236501_0053u51EF6D61_42_F3C7\x02\xff\x11%\x11' \
	      '4831\t128\t326.544\t96.726\t11.873\t31.965\t31.965\t37.134\t5.169\t1370.7\t1245.9\t444.4\r\n\x03' \
	      '\x01CT1237100_009Cb51EF8B36_57_678B\x02@!\xbe%\x94\x9d\xa0\x1c\xe1)\x82\x19\rA!\xc4\xd5\x949\xe7' \
	      '\x1b\xe1)\x82\x19\rB"\x00\x85\x90\r\xd1\x15\xe1)\x82\x19\r:%\x9f\xd5\x9b\xdc\xe1\x19\xe1)\x82\x19' \
	      '\r\x104\xe0fm\x94\x9a\x0f\xe1)\x82\x19\r?%\xaf\x05\x9c\x93N\x19\xe1)\x82\x19\r;*#\xb5\xd8\xa4\xe7' \
	      '\x15\xe1)\x82\x19\r\x11.d6\x12\xe1D\x13\xe1)\x82\x19\r\x16\'\x9a\xf5\xb6s\xce\x16\xe1)\x82\x19\r' \
	      '\x158Bv\x9d\xb1\xac\x0c\xe1)\x82\x19\r58;v\x9d=%\x0b\xe1)\x82\x19\r75\x8b\xe0\xc3T\xe5\n\xe1)\x82' \
	      '\x19\r\x03'

    # replace the 3rd CT (2nd with data) packet with 0s
    REPLACE_TEST_DATA = TEST_DATA[:892] + \
    '000000000000000000000000000000000000000000000000000000000000000000000000000000000000' + \
    '00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000' + \
    TEST_DATA[1083:]

    # mess with the 2nd CT (1st with data) packet header
    BAD_TEST_DATA = TEST_DATA[:438] + 'BAD' + TEST_DATA[439:]

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

	# there is one CT tag from 194-228 that has no data samples
	# blocks have the same timestamp, packet 2 has 3 data samples [432:505]
	self.timestamp1 = 3583656001.0 #07/24/2013 05:00:01
        self.particle_a = CtdmoParserDataParticle(b'\x15\x38\x53\x66\x9e\x1a\xa2\x0c\x81\xd5\x81\x19\x0d',
                                                  internal_timestamp=self.timestamp1, new_sequence=True)
	self.particle_b = CtdmoParserDataParticle(b'\x35\x3b\xa2\x10\xc3\x5a\xe7\x0a\x81\xd5\x81\x19\x0d',
						  internal_timestamp=self.timestamp1, new_sequence=False)
	self.particle_c = CtdmoParserDataParticle(b'\x37\x39\x4c\xe0\xc3\x54\xe6\x0a\x81\xd5\x81\x19\x0d',
						  internal_timestamp=self.timestamp1, new_sequence=False)
	# this is the start of packet 3 [892:1083]
	# there is no missing data between packet 2 and 3
	self.timestamp2 = 3583663201.0 #07/24/2013 07:00:01
	self.particle_d = CtdmoParserDataParticle(b'\x40\x3a\x7f\xa0\xc3\x56\xe0\x0a\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2, new_sequence=False)
	self.particle_d_new = CtdmoParserDataParticle(b'\x40\x3a\x7f\xa0\xc3\x56\xe0\x0a\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2, new_sequence=True)
	self.particle_e = CtdmoParserDataParticle(b'\x41\x22\xf2\xa5\x95\x31\xaf\x13\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2, new_sequence=False)
	# particle 14
	self.particle_x = CtdmoParserDataParticle(b'\x35\x38\x99\xa6\xa1\x76\x0f\x0b\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2, new_sequence=False)
	# particle 15
	self.particle_z = CtdmoParserDataParticle(b'\x37\x37\xf0\x00\xc3\x54\xe5\x0a\xa1\xf1\x81\x19\x0d',
						  internal_timestamp=self.timestamp2, new_sequence=False)
	# particle 16 (packet 4) [1470-1661]
	# missing block [1197-1470] between 3 and 4
	self.timestamp3 = 3583670401.0 #07/24/2013 09:00:01
	self.particle_xx = CtdmoParserDataParticle(b'\x40\x21\xcb\xc5\x97\x38\x4a\x1e\xc1\x0d\x82\x19\x0d',
						   internal_timestamp=self.timestamp3, new_sequence=True)
	self.particle_zz = CtdmoParserDataParticle(b'A!\x94\x95\x928*\x1d\xc1\r\x82\x19\r',
						   internal_timestamp=self.timestamp3, new_sequence=False)
	# packet 5 [5392-5582]
	# no missing blocks between 4 and 5 
	self.timestamp4 = 3583677601.0
	self.particle_aa = CtdmoParserDataParticle(b'\x40\x21\xbe\x25\x94\x9d\xa0\x1c\xe1\x29\x82\x19\x0d',
						   internal_timestamp=self.timestamp4, new_sequence=False)
	self.particle_bb = CtdmoParserDataParticle(b'\x41\x21\xc4\xd5\x94\x39\xe7\x1b\xe1\x29\x82\x19\x0d',
						   internal_timestamp=self.timestamp4, new_sequence=False)

	self.state_callback_value = None
        self.publish_callback_value = None

    def assert_result(self, result, unprocessed_data, timestamp, particle):
        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP], timestamp)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
	"""
	Read test data from the file and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, len(CtdmoParserUnitTestCase.TEST_DATA)]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	self.stream_handle = StringIO(CtdmoParserUnitTestCase.TEST_DATA)
	self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
				  self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
	self.stream_handle.close()
	self.assert_result(result, [[0,50],[374,432],[1197,1470]],
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[1197,1470]],
			   self.timestamp4, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[1197,1470]],
			   self.timestamp4, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[1197,1470]],
			   self.timestamp4, self.particle_d)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[1197,1470]],
			   self.timestamp4, self.particle_e)

    def test_simple_section(self):
	"""
	Read test data from the file and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, len(CtdmoParserUnitTestCase.REPLACE_TEST_DATA)]],
	    StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:0.0}
	self.stream_handle = StringIO(CtdmoParserUnitTestCase.REPLACE_TEST_DATA)
	self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
				  self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_xx)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_zz)
	self.stream_handle.close()

    def test_get_many(self):
	"""
	Read test data from the file and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, len(CtdmoParserUnitTestCase.TEST_DATA)]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = StringIO(CtdmoParserUnitTestCase.TEST_DATA)
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(3)
	self.stream_handle.close()
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c])
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA],
			 [[0,50],[374,432],[1197,1470]])
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA],
			 [[0,50],[374,432],[1197,1470]])
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP],
                         self.timestamp4)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
	self.assertEqual(self.publish_callback_value[2], self.particle_c)

    def test_long_stream(self):
	self.state = {StateKey.UNPROCESSED_DATA:[[0, len(CtdmoParserUnitTestCase.TEST_DATA)]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = StringIO(CtdmoParserUnitTestCase.TEST_DATA)
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(29)
	self.stream_handle.close()
	self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
	self.assertEqual(result[2], self.particle_c)
	self.assertEqual(result[3], self.particle_d)
	self.assertEqual(result[-16], self.particle_x)
        self.assertEqual(result[-15], self.particle_z)
	self.assertEqual(result[-14], self.particle_xx)
	self.assertEqual(result[-13], self.particle_zz)
	self.assertEqual(result[-2], self.particle_aa)
	self.assertEqual(result[-1], self.particle_bb)
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA],
			 [[0,50],[374,432],[1197,1470]])
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA],
			 [[0,50],[374,432],[1197,1470]])
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP],
                         self.timestamp4)
        self.assertEqual(self.publish_callback_value[-1], self.particle_bb)

    def test_mid_state_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
        new_state = {StateKey.UNPROCESSED_DATA:[[0,50],[374,432],[1197, 2485]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:self.timestamp1}
        self.stream_handle = StringIO(CtdmoParserUnitTestCase.TEST_DATA)
        self.parser = CtdmoParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [[0,50],[374,432],[1197,1470]],
			   self.timestamp4, self.particle_xx)

    def test_set_state(self):
	"""
	test changing the state after initializing
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 1197]], StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:0.0}
        new_state = {StateKey.UNPROCESSED_DATA:[[0,50],[374,432],[1197,2485]],
	    StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:self.timestamp2}

        self.stream_handle = StringIO(CtdmoParserUnitTestCase.TEST_DATA)
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
	# there should only be 16 records, make sure we stop there
        result = self.parser.get_records(16)
	result = self.parser.get_records(1)
	self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [[0,50],[374,432],[1197,1470]],
			   self.timestamp4, self.particle_xx)

    def test_bad_data(self):
        """ There's a bad sample in the data! Skip it! """
	self.state = {StateKey.UNPROCESSED_DATA:[[0, len(CtdmoParserUnitTestCase.BAD_TEST_DATA)]],
	    StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:0.0}
        self.stream_handle = StringIO(CtdmoParserUnitTestCase.BAD_TEST_DATA)
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [[0,50],[374,507],[1199,1472]],
			   self.timestamp4, self.particle_d_new)

    def test_update(self):
	"""
	Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
	then using the returned state make a new parser with the test data that has the 0s filled in
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, len(CtdmoParserUnitTestCase.REPLACE_TEST_DATA)]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	# this file has a block of CT data replaced by 0s
        self.stream_handle = StringIO(CtdmoParserUnitTestCase.REPLACE_TEST_DATA)
        self.parser = CtdmoParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_c)
	result = self.parser.get_records(1)
	self.assert_result(result, [[0,50],[374,432],[892,1083],[1197,1470]],
			   self.timestamp4, self.particle_xx)
	self.stream_handle.close()

	next_state = self.parser._state
	# this file has the block of CT data that was missing in the previous file
	self.stream_handle = StringIO(CtdmoParserUnitTestCase.TEST_DATA)
	self.parser = CtdmoParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, [[0,50],[374,432],[1197,1470]],
			   self.timestamp2, self.particle_d_new)
	self.stream_handle.close()

