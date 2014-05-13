#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_mopak_o_dcl
@file marine-integrations/mi/dataset/parser/test/test_mopak_o_dcl.py
@author Emily Hahn
@brief Test code for a mopak_o_dcl data parser
"""
import ntplib
import struct
import os
from datetime import datetime
import time
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.mopak_o_dcl import MopakODclParser, StateKey
from mi.dataset.parser.mopak_o_dcl import MopakODclAccelParserDataParticle, MopakODclRateParserDataParticle

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'cg_stc_eng',
			     'stc', 'resource')

@attr('UNIT', group='mi')
class MopakODclParserUnitTestCase(ParserUnitTestCase):
    """
    MopakODcl Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def except_callback(self, exception):
        """
        Callback method to watch what comes in via the exception callback
        """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.mopak_o_dcl',
            DataSetDriverConfigKeys.PARTICLE_CLASS: ['MopakODclAccelParserDataParticle',
                                                     'MopakODclRateParserDataParticle']
            }
        self.start_state = {StateKey.POSITION: 0, StateKey.TIMER_ROLLOVER: 0, StateKey.TIMER_START: None}
        # using the same file, and hence the same start time, so just convert the start time here
        file_datetime = datetime.strptime('20140120_140004', "%Y%m%d_%H%M%S")
        local_seconds = time.mktime(file_datetime.timetuple())
        start_time_utc = local_seconds - time.timezone

        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
	self._timer_start = 33456
        self.timestamp1 = self.timer_to_timestamp(b'\x00\x00\x82\xb0', start_time_utc, 0, self._timer_start)
        self.particle_a_accel = MopakODclAccelParserDataParticle(b"\xcb\xbd\xe6\xac<\xbd\xd9\nA\xbf\x83\xa4" \
            "+;\xaf\xb4\x01\xbd\xf2o\xd4\xbd\xfe\x9d'>P\xfd\xfc>t\xd5\xc4>\xed\x10\xb2\x00\x00\x82\xb0\x16I",
            internal_timestamp=self.timestamp1)
	self.timestamp2 = self.timer_to_timestamp(b'\x00\x00\x9b\x1a', start_time_utc, 0, self._timer_start)
	self.particle_b_accel = MopakODclAccelParserDataParticle(b"\xcb\xbe\x17Q\x8e\xbd\xc7_\x8a\xbf\x85\xc3" \
	    "e\xbc\xebN\x18\xbd\x9a\x86P\xbd\xf4\xe4\xd4>T38>s\xc8\xb9>\xea\xce\xd0\x00\x00\x9b\x1a\x15\xa5",
	    internal_timestamp=self.timestamp2)
	self.timestamp3 = self.timer_to_timestamp(b'\x00\x00\xb3\x84', start_time_utc, 0, self._timer_start)
	self.particle_c_accel = MopakODclAccelParserDataParticle(b"\xcb\xbe1\xeak\xbd\xae?\x8a\xbf\x86\x18" \
	    "\x8a\xbd~\xde\xf0\xbc\xb2\x1d\xec\xbd\xd7\xe4\x04>U\xbcW>p\xf3U>\xeaOh\x00\x00\xb3\x84\x15\xd8",
	    internal_timestamp=self.timestamp3)
	self.timestamp4 = self.timer_to_timestamp(b'\x00\x00\xcb\xee', start_time_utc, 0, self._timer_start)
	self.particle_d_accel = MopakODclAccelParserDataParticle(b"\xcb\xbe8\xed\xf0\xbd\xa7\x98'\xbf\x88" \
	    "\x0e\xca\xbd\xeegZ<\xf63\xdc\xbd\xe6b\x8d>U\xa5U>l6p>\xe9\xfc\x8d\x00\x00\xcb\xee\x16e",
	    internal_timestamp=self.timestamp4)
	self.timestamp5 = self.timer_to_timestamp(b'\x00\x00\xe4X', start_time_utc, 0, self._timer_start)
	self.particle_e_accel = MopakODclAccelParserDataParticle(b"\xcb\xbe9t\xb5\xbd\x89\xd1\x16\xbf\x87" \
            "\r\x14\xbe\r\xca\x9d=\xa9\x85+\xbd\xf3\x1c\xcb>R9\x1b>f\xcen>\xead\xb4\x00\x00\xe4X\x13\x1e",
            internal_timestamp=self.timestamp5)

        self.timestamp6 = self.timer_to_timestamp(b'\x04ud\x1e', start_time_utc, 0, self._timer_start)
        self.particle_last_accel = MopakODclAccelParserDataParticle(b"\xcb=\xfd\xb6?=0\x84\xf6\xbf\x82\xff" \
            "\xed>\x07$\x16\xbe\xaf\xf3\xb9=\x93\xb5\xad\xbd\x97\xcb8\xbeo\x0bI>\xf4_K\x04ud\x1e\x14\x87",
            internal_timestamp=self.timestamp6)

        # got a second file with rate particles in it after writing tests, so adding new tests but leaving
        # the old, resulting in many test particles

        # after this is for a new file with rate in it
        # using the same file, and hence the same start time, so just convert the start time here
        file_datetime = datetime.strptime('20140313_191853', "%Y%m%d_%H%M%S")
        local_seconds = time.mktime(file_datetime.timetuple())
        start_time_utc = local_seconds - time.timezone

        # first in larger file
        self._rate_long_timer_start = 11409586
        self.timestampa11 = self.timer_to_timestamp(b'\x00\xae\x18\xb2', start_time_utc, 0, self._rate_long_timer_start)
        self.particle_a11_accel = MopakODclAccelParserDataParticle(b"\xcb?(\xf4\x85?.\xf6k>\x9dq\x91\xba7r" \
            "\x9b\xba\xca\x19T:\xff\xbc[\xbe\xfb\xd3\xdf\xbd\xc6\x0b\xbb\xbe\x7f\xa8T\x00\xae\x18\xb2\x15\xfa",
            internal_timestamp=self.timestampa11)

        self._first_rate_timer_start = 11903336
        # first in first_rate file
        self.timestampa1 = self.timer_to_timestamp(b'\x00\xb5\xa1h', start_time_utc, 0, self._first_rate_timer_start)
        self.particle_a1_accel = MopakODclAccelParserDataParticle(b"\xcb?(\xd3d?/\x0bd>\x9dxr\xba$eZ\xbbl" \
            "\xaa\xea:\xed\xe7\xa6\xbe\xfb\xe1J\xbd\xc6\xfa\x90\xbe\x7f\xcc2\x00\xb5\xa1h\x16\x01",
            internal_timestamp=self.timestampa1)
        self.timestampb1 = self.timer_to_timestamp(b'\x00\xb5\xb9\xd2', start_time_utc, 0, self._first_rate_timer_start)
        self.particle_b1_accel = MopakODclAccelParserDataParticle(b"\xcb?))$?/(\x9b>\x9e\x15w\xb9\x92\xc0" \
            "\x16\xbah\xb6\x0e:\xe5\x97\xf3\xbe\xfc\x044\xbd\xc6\xf5\x1b\xbe\x80ym\x00\xb5\xb9\xd2\x13\xb2",
            internal_timestamp=self.timestampb1)

        self.timestamp1r = self.timer_to_timestamp(b'\x00\xd0\xe7\xd4', start_time_utc, 0, self._first_rate_timer_start)
        self.particle_a_rate = MopakODclRateParserDataParticle(b"\xcf\xbf\xffNJ?:\x90\x8b@\x1e\xde\xa8\xba" \
            "\tU\xe8\xbb\x07Z\xf2:\xb8\xa9\xc7\x00\xd0\xe7\xd4\x0f\x98", internal_timestamp=self.timestamp1r)
        self.timestamp2r = self.timer_to_timestamp(b'\x00\xd1\x00>', start_time_utc, 0, self._first_rate_timer_start)
        self.particle_b_rate = MopakODclRateParserDataParticle(b"\xcf\xbf\xffD\xa1?:\x92\x85@\x1e\xde\xcc:\xa3" \
            "6\xf1\xba\xf7I@;\xc4\x05\x85\x00\xd1\x00>\r\xe0", internal_timestamp=self.timestamp2r)
        self.timestamp3r = self.timer_to_timestamp(b'\x00\xd1\x18\xa8', start_time_utc, 0, self._first_rate_timer_start)
        self.particle_c_rate = MopakODclRateParserDataParticle(b"\xcf\xbf\xffC\xcb?:\x8dL@\x1e\xdf6\xb9\xf5" \
            "\xb1:\xb9\xdf\x06\n;\x05\\a\x00\xd1\x18\xa8\r/", internal_timestamp=self.timestamp3r)
        # last in first_rate file
        self.timestamp4r = self.timer_to_timestamp(b'\x00\xd11\x12', start_time_utc, 0, self._first_rate_timer_start)
        self.particle_d_rate = MopakODclRateParserDataParticle(b"\xcf\xbf\xffF/?:\x8a\x1d@\x1e\xe0.\xba\xd3" \
            "9*\xba\x80\x1c{:?-\xe9\x00\xd11\x12\x0b\xf2", internal_timestamp=self.timestamp4r)

        # last in larger file
        self.timestamp8r = self.timer_to_timestamp(b'\x00\xd73(', start_time_utc, 0, self._rate_long_timer_start)
        self.particle_last_rate = MopakODclRateParserDataParticle(b"\xcf\xbf\xffK ?:r\xd4@\x1e\xf4\xf09\xa7\x91" \
            "\xb0\xb9\x9b\x82\x85;$\x1f\xc7\x00\xd73(\r\xec", internal_timestamp=self.timestamp8r)

        # uncomment the following to generate particles in yml format for driver testing results files
        #self.particle_to_yml(self.particle_a1_accel)
        #self.particle_to_yml(self.particle_b1_accel)
        #self.particle_to_yml(self.particle_a_rate)
        #self.particle_to_yml(self.particle_b_rate)
        #self.particle_to_yml(self.particle_c_rate)
        #self.particle_to_yml(self.particle_d_rate)

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def timer_to_timestamp(self, timer, start_time_utc, rollover_count, timer_start):
        """
        convert a timer value to a ntp formatted timestamp
        """
        fields = struct.unpack('>I', timer)
        # if the timer has rolled over, multiply by the maximum value for timer so the time keeps increasing
        rollover_offset = rollover_count * 4294967296
        # make sure the timer starts at 0 for the file by subtracting the first timer
        # divide timer by 62500 to go from counts to seconds
        offset_secs = float(int(fields[0]) + rollover_offset - timer_start)/62500.0
        # add in the utc start time
        time_secs = float(start_time_utc) + offset_secs
        # convert to ntp64
        return float(ntplib.system_to_ntp_time(time_secs))

    def particle_to_yml(self, particle):
        """
        This is added as a testing helper, not actually as part of the parser tests. Since the same particles
        will be used for the driver test it is helpful to write them to .yml in the same form they need in the
        results.yml files here.
        """
        particle_dict = particle.generate_dict()
        # open write append, if you want to start from scratch manually delete this file
        fid = open('particle.yml', 'a')
        fid.write('  - _index: 0\n')
        fid.write('    internal_timestamp: %f\n' % particle_dict.get('internal_timestamp'))
        fid.write('    particle_object: %s\n' % particle.__class__.__name__)
        fid.write('    particle_type: %s\n' % particle_dict.get('stream_name'))
        for val in particle_dict.get('values'):
            if isinstance(val.get('value'), float):
                fid.write('    %s: %16.20f\n' % (val.get('value_id'), val.get('value')))
            else:
                fid.write('    %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()

    def assert_result(self, result, position, particle, ingested, timer_start, timer_rollover=0):
        self.assertEqual(result, [particle])
        self.assertEqual(self.file_ingested_value, ingested)

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)
        self.assertEqual(self.parser._state[StateKey.TIMER_ROLLOVER], timer_rollover)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_ROLLOVER], timer_rollover)
        self.assertEqual(self.parser._state[StateKey.TIMER_START], timer_start)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_START], timer_start)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 
                                               'first.mopak.log'))
        self.parser =  MopakODclParser(self.config, self.start_state, self.stream_handle,
                                       '20140120_140004.mopak.log',
                                       self.state_callback, self.pub_callback,
                                       self.except_callback) 
        # next get acceleration records
        result = self.parser.get_records(1)
        self.assert_result(result, 43, self.particle_a_accel, False, self._timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 86, self.particle_b_accel, False, self._timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 129, self.particle_c_accel, False, self._timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 172, self.particle_d_accel, False, self._timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 215, self.particle_e_accel, True, self._timer_start)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 215)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 215)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_e_accel)
        self.assertEqual(self.exception_callback_value, None)

    def test_simple_rate(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'first_rate.mopak.log'))
        self.parser =  MopakODclParser(self.config, self.start_state, self.stream_handle,
                                       '20140313_191853.mopak.log',
                                       self.state_callback, self.pub_callback,
                                       self.except_callback)
        # next get accel and rate records
        result = self.parser.get_records(1)
        self.assert_result(result, 43, self.particle_a1_accel, False, self._first_rate_timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 86, self.particle_b1_accel, False, self._first_rate_timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 117, self.particle_a_rate, False, self._first_rate_timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 148, self.particle_b_rate, False, self._first_rate_timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 179, self.particle_c_rate, False, self._first_rate_timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 210, self.particle_d_rate, True, self._first_rate_timer_start)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 210)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 210)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_d_rate)
        self.assertEqual(self.exception_callback_value, None)

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 
                                               'first.mopak.log'))
        self.parser =  MopakODclParser(self.config, self.start_state, self.stream_handle,
                                       '20140120_140004.mopak.log',
                                        self.state_callback, self.pub_callback,
                                        self.except_callback) 
        # next get accel records
        result = self.parser.get_records(5)
        self.assertEqual(result, [self.particle_a_accel,
                                  self.particle_b_accel,
                                  self.particle_c_accel,
                                  self.particle_d_accel,
                                  self.particle_e_accel])
        self.assertEqual(self.parser._state[StateKey.POSITION], 215)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 215)
        self.assertEqual(self.parser._state[StateKey.TIMER_START], self._timer_start)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_START], self._timer_start)
        self.assertEqual(self.parser._state[StateKey.TIMER_ROLLOVER], 0)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_ROLLOVER], 0)
        self.assertEqual(self.publish_callback_value[0], self.particle_a_accel)
        self.assertEqual(self.publish_callback_value[1], self.particle_b_accel)
        self.assertEqual(self.publish_callback_value[2], self.particle_c_accel)
        self.assertEqual(self.publish_callback_value[3], self.particle_d_accel)
        self.assertEqual(self.publish_callback_value[4], self.particle_e_accel)
        self.assertEqual(self.file_ingested_value, True)
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream(self):
        """
        Test a long (normal length file)
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               '20140120_140004.mopak.log'))
        self.parser =  MopakODclParser(self.config, self.start_state, self.stream_handle,
                                       '20140120_140004.mopak.log', self.state_callback,
                                       self.pub_callback, self.except_callback)
        result = self.parser.get_records(11964)
        self.assertEqual(result[0], self.particle_a_accel)
        self.assertEqual(result[-1], self.particle_last_accel)
        self.assertEqual(self.parser._state[StateKey.POSITION], 514452)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 514452)
        self.assertEqual(self.parser._state[StateKey.TIMER_START], self._timer_start)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_START], self._timer_start)
        self.assertEqual(self.parser._state[StateKey.TIMER_ROLLOVER], 0)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_ROLLOVER], 0)
        self.assertEqual(self.publish_callback_value[-1], self.particle_last_accel)
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream_rate(self):
        """
        Test a long (normal length file) with accel and rate particles
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               '20140313_191853.3dmgx3.log'))
        self.parser =  MopakODclParser(self.config, self.start_state, self.stream_handle,
                                       '20140313_191853.3dmgx3.log',
                                       self.state_callback, self.pub_callback,
                                       self.except_callback)
        result = self.parser.get_records(148)
        self.assertEqual(result[0], self.particle_a11_accel)
        self.assertEqual(result[-1], self.particle_last_rate)
        self.assertEqual(self.parser._state[StateKey.POSITION], 5560)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 5560)
        self.assertEqual(self.parser._state[StateKey.TIMER_START], self._rate_long_timer_start)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_START], self._rate_long_timer_start)
        self.assertEqual(self.parser._state[StateKey.TIMER_ROLLOVER], 0)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_ROLLOVER], 0)
        self.assertEqual(self.publish_callback_value[-1], self.particle_last_rate)
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:86,
                     StateKey.TIMER_ROLLOVER:0,
                     StateKey.TIMER_START:self._timer_start}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'first.mopak.log'))
        self.parser =  MopakODclParser(self.config, new_state, self.stream_handle,
                                    '20140120_140004.mopak.log', self.state_callback, self.pub_callback,
                                        self.except_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 129, self.particle_c_accel, False, self._timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 172, self.particle_d_accel, False, self._timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 215, self.particle_e_accel, True, self._timer_start)
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION:129,
                     StateKey.TIMER_ROLLOVER:0,
                     StateKey.TIMER_START:self._timer_start}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'first.mopak.log'))
        self.parser =  MopakODclParser(self.config, self.start_state, self.stream_handle,
                                        '20140120_140004.mopak.log',
                                        self.state_callback, self.pub_callback,
                                        self.except_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 43, self.particle_a_accel, False, self._timer_start)

        # set the new state, the essentially skips b and c
        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 172, self.particle_d_accel, False, self._timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 215, self.particle_e_accel, True, self._timer_start)
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state_rate(self):
        """
        Test changing to a new state after initializing the parser and
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION:117,
                     StateKey.TIMER_ROLLOVER:0,
                     StateKey.TIMER_START:self._first_rate_timer_start}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'first_rate.mopak.log'))
        self.parser =  MopakODclParser(self.config, self.start_state, self.stream_handle,
                                      '20140313_191853.3dmgx3.log',
                                      self.state_callback, self.pub_callback,
                                      self.except_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 43, self.particle_a1_accel, False, self._first_rate_timer_start)

        # set the new state, the essentially skips b accel, a rate
        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 148, self.particle_b_rate, False, self._first_rate_timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 179, self.particle_c_rate, False, self._first_rate_timer_start)
        result = self.parser.get_records(1)
        self.assert_result(result, 210, self.particle_d_rate, True, self._first_rate_timer_start)
        self.assertEqual(self.exception_callback_value, None)

    def test_non_data_exception(self):
        """
        Test that we get a sample exception from non data being found in the file
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'noise.mopak.log'))
        self.parser =  MopakODclParser(self.config, self.start_state, self.stream_handle,
                                       '20140120_140004.mopak.log',
                                        self.state_callback, self.pub_callback,
                                        self.except_callback)

        # next get accel records
        result = self.parser.get_records(5)
        self.assertEqual(result, [self.particle_a_accel,
                                  self.particle_b_accel,
                                  self.particle_c_accel,
                                  self.particle_d_accel,
                                  self.particle_e_accel])
        self.assertEqual(self.parser._state[StateKey.POSITION], 218)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 218)
        self.assertEqual(self.parser._state[StateKey.TIMER_START], self._timer_start)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_START], self._timer_start)
        self.assertEqual(self.parser._state[StateKey.TIMER_ROLLOVER], 0)
        self.assertEqual(self.state_callback_value[StateKey.TIMER_ROLLOVER], 0)
        self.assertEqual(self.publish_callback_value[0], self.particle_a_accel)
        self.assertEqual(self.publish_callback_value[1], self.particle_b_accel)
        self.assertEqual(self.publish_callback_value[2], self.particle_c_accel)
        self.assertEqual(self.publish_callback_value[3], self.particle_d_accel)
        self.assertEqual(self.publish_callback_value[4], self.particle_e_accel)
        self.assertEqual(self.file_ingested_value, True)
        self.assert_(isinstance(self.exception_callback_value, SampleException))

