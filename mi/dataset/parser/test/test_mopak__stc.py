#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_mopak__stc
@file marine-integrations/mi/dataset/parser/test/test_mopak__stc.py
@author Emily Hahn
@brief Test code for a Mopak__stc data parser
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
from mi.dataset.parser.mopak__stc import Mopak__stcParser, StateKey
from mi.dataset.parser.mopak__stc import Mopak__stcAccelParserDataParticle, Mopak__stcRateParserDataParticle

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'MOPAK',
			     'STC', 'resource')

@attr('UNIT', group='mi')
class Mopak__stcParserUnitTestCase(ParserUnitTestCase):
    """
    Mopak__stc Parser unit test suite
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
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.mopak__stc',
            DataSetDriverConfigKeys.PARTICLE_CLASS: ['Mopak__stcAccelParserDataParticle',
                                                     'Mopak__stcRateParserDataParticle']
            }
        self.start_state = {StateKey.POSITION: 0}
        # using the same file, and hence the same start time, so just convert the start time here
        file_datetime = datetime.strptime('20140120_140004', "%Y%m%d_%H%M%S")
        local_seconds = time.mktime(file_datetime.timetuple())
        self._start_time_utc = local_seconds - time.timezone
        
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
        self.timestamp1 = self.timer_to_timestamp(b'\x00\x00\x82\xb0')
        self.particle_a_accel = Mopak__stcAccelParserDataParticle(b"\xcb\xbd\xe6\xac<\xbd\xd9\nA\xbf\x83\xa4" \
            "+;\xaf\xb4\x01\xbd\xf2o\xd4\xbd\xfe\x9d'>P\xfd\xfc>t\xd5\xc4>\xed\x10\xb2\x00\x00\x82\xb0\x16I",
            internal_timestamp=self.timestamp1)

	self.timestamp2 = self.timer_to_timestamp(b'\x00\x00\x9b\x1a')
	self.particle_b_accel = Mopak__stcAccelParserDataParticle(b"\xcb\xbe\x17Q\x8e\xbd\xc7_\x8a\xbf\x85\xc3" \
	    "e\xbc\xebN\x18\xbd\x9a\x86P\xbd\xf4\xe4\xd4>T38>s\xc8\xb9>\xea\xce\xd0\x00\x00\x9b\x1a\x15\xa5",
	    internal_timestamp=self.timestamp2)

	self.timestamp3 = self.timer_to_timestamp(b'\x00\x00\xb3\x84')
	self.particle_c_accel = Mopak__stcAccelParserDataParticle(b"\xcb\xbe1\xeak\xbd\xae?\x8a\xbf\x86\x18" \
	    "\x8a\xbd~\xde\xf0\xbc\xb2\x1d\xec\xbd\xd7\xe4\x04>U\xbcW>p\xf3U>\xeaOh\x00\x00\xb3\x84\x15\xd8",
	    internal_timestamp=self.timestamp3)

	self.timestamp4 = self.timer_to_timestamp(b'\x00\x00\xcb\xee')
	self.particle_d_accel = Mopak__stcAccelParserDataParticle(b"\xcb\xbe8\xed\xf0\xbd\xa7\x98'\xbf\x88" \
	    "\x0e\xca\xbd\xeegZ<\xf63\xdc\xbd\xe6b\x8d>U\xa5U>l6p>\xe9\xfc\x8d\x00\x00\xcb\xee\x16e",
	    internal_timestamp=self.timestamp4)
	
	self.timestamp5 = self.timer_to_timestamp(b'\x00\x00\xe4X')
	self.particle_e_accel = Mopak__stcAccelParserDataParticle(b"\xcb\xbe9t\xb5\xbd\x89\xd1\x16\xbf\x87" \
	    "\r\x14\xbe\r\xca\x9d=\xa9\x85+\xbd\xf3\x1c\xcb>R9\x1b>f\xcen>\xead\xb4\x00\x00\xe4X\x13\x1e",
	    internal_timestamp=self.timestamp5)

	# uncomment the following to generate particles in yml format for driver testing results files
	#self.particle_to_yml(self.particle_a_accel)
        #self.particle_to_yml(self.particle_b_accel)
        #self.particle_to_yml(self.particle_c_accel)
        #self.particle_to_yml(self.particle_d_accel)
        #self.particle_to_yml(self.particle_e_accel)

        self.timestamp6 = self.timer_to_timestamp(b'\x04ud\x1e')
        self.particle_last_accel = Mopak__stcAccelParserDataParticle(b"\xcb=\xfd\xb6?=0\x84\xf6\xbf\x82\xff" \
            "\xed>\x07$\x16\xbe\xaf\xf3\xb9=\x93\xb5\xad\xbd\x97\xcb8\xbeo\x0bI>\xf4_K\x04ud\x1e\x14\x87",
            internal_timestamp=self.timestamp6)

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def timer_to_timestamp(self, timer):
        """
        convert a timer value to a ntp formatted timestamp
        """
        fields = struct.unpack('>I', timer)
        # first divide timer by 62500 to go from counts to seconds
        offset_secs = int(fields[0])/62500
        # add in the utc start time
        time_secs = self._start_time_utc + offset_secs
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
                fid.write('    %s: %16.18f\n' % (val.get('value_id'), val.get('value')))
            else:
                fid.write('    %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()

    def assert_result(self, result, position, particle, ingested):
        self.assertEqual(result, [particle])
        self.assertEqual(self.file_ingested_value, ingested)

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 
                                               'first.mopak.log'))
        self.parser =  Mopak__stcParser(self.config, self.start_state, self.stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.except_callback, '20140120_140004.mopak.log') 
        # next get engineering records
        result = self.parser.get_records(1)
        self.assert_result(result, 43, self.particle_a_accel, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 86, self.particle_b_accel, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 129, self.particle_c_accel, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 172, self.particle_d_accel, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 215, self.particle_e_accel, True)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 215)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 215)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_e_accel)
        self.assertEqual(self.exception_callback_value, None)

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 
                                               'first.mopak.log'))
        self.parser =  Mopak__stcParser(self.config, self.start_state, self.stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.except_callback, '20140120_140004.mopak.log') 
        # next get engineering records
        result = self.parser.get_records(5)
        self.assertEqual(result, [self.particle_a_accel,
                                  self.particle_b_accel,
                                  self.particle_c_accel,
                                  self.particle_d_accel,
                                  self.particle_e_accel])
        self.assertEqual(self.parser._state[StateKey.POSITION], 215)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 215)
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
        self.parser =  Mopak__stcParser(self.config, self.start_state, self.stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.except_callback, '20140120_140004.mopak.log') 
        result = self.parser.get_records(11964)
        self.assertEqual(result[0], self.particle_a_accel)
        self.assertEqual(result[-1], self.particle_last_accel)
        self.assertEqual(self.parser._state[StateKey.POSITION], 514452)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 514452)
        self.assertEqual(self.publish_callback_value[-1], self.particle_last_accel)
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:86}
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 
                                               'first.mopak.log'))
        self.parser =  Mopak__stcParser(self.config, new_state, self.stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.except_callback, '20140120_140004.mopak.log') 
        result = self.parser.get_records(1)
        self.assert_result(result, 129, self.particle_c_accel, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 172, self.particle_d_accel, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 215, self.particle_e_accel, True)
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION:129}
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 
                                               'first.mopak.log'))
        self.parser =  Mopak__stcParser(self.config, self.start_state, self.stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.except_callback, '20140120_140004.mopak.log') 
        result = self.parser.get_records(1)
        self.assert_result(result, 43, self.particle_a_accel, False)

        # set the new state, the essentially skips b and c
        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 172, self.particle_d_accel, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 215, self.particle_e_accel, True)
        self.assertEqual(self.exception_callback_value, None)

    def test_non_data_exception(self):
        """
        Test that we get a sample exception from non data being found in the file
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'noise.mopak.log'))
        self.parser =  Mopak__stcParser(self.config, self.start_state, self.stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.except_callback, '20140120_140004.mopak.log') 

        # next get engineering records
        result = self.parser.get_records(5)
        self.assertEqual(result, [self.particle_a_accel,
                                  self.particle_b_accel,
                                  self.particle_c_accel,
                                  self.particle_d_accel,
                                  self.particle_e_accel])
        self.assertEqual(self.parser._state[StateKey.POSITION], 218)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 218)
        self.assertEqual(self.publish_callback_value[0], self.particle_a_accel)
        self.assertEqual(self.publish_callback_value[1], self.particle_b_accel)
        self.assertEqual(self.publish_callback_value[2], self.particle_c_accel)
        self.assertEqual(self.publish_callback_value[3], self.particle_d_accel)
        self.assertEqual(self.publish_callback_value[4], self.particle_e_accel)
        self.assertEqual(self.file_ingested_value, True)
        self.assert_(isinstance(self.exception_callback_value, SampleException))

