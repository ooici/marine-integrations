#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_dofst_k_wfp
@file marine-integrations/mi/dataset/parser/test/test_dofst_k_wfp.py
@author Emily Hahn
@brief Test code for a dofst_k_wfp data parser
"""
import os
import struct
import ntplib
from StringIO import StringIO
import binascii

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticleKey
from mi.idk.config import Config

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.dofst_k_wfp import DofstKWfpParser, DataParticleType
from mi.dataset.parser.dofst_k_wfp import DofstKWfpParserDataParticle
from mi.dataset.parser.wfp_c_file_common import WfpMetadataParserDataParticle, StateKey


RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'dofst_k',
			     'wfp', 'resource')

@attr('UNIT', group='mi')
class DofstKWfpParserUnitTestCase(ParserUnitTestCase):
    TEST_DATA = b"\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8\x00\x1a\x8c\x03\xe2" + \
    "\xc0\x00\x03\xeb\x0a\x81\x00\x1a\x90\x03\xe1\x5b\x00\x03\xeb\x0a\x65\xff\xff" + \
    "\xff\xff\xff\xff\xff\xff\xff\xff\xff\x52\x4e\x75\x82\x52\x4e\x76\x9a"

    TEST_DATA_PAD = b"\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8\x00\x1a\x8c\x03\xe2" + \
    "\xc0\x00\x03\xeb\x0a\x81\x00\x1a\x90\x03\xe1\x5b\x00\x03\xeb\x0a\x65\xff\xff" + \
    "\xff\xff\xff\xff\xff\xff\xff\xff\xff\x52\x4e\x75\x82\x52\x4e\x76\x9a\x0a"
    
    # not enough bytes for final timestamps
    TEST_DATA_BAD_TIME = b"\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8\x00\x1a\x8c\x03\xe2" + \
    "\xc0\x00\x03\xeb\x0a\x81\x00\x1a\x90\x03\xe1\x5b\x00\x03\xeb\x0a\x65\xff\xff" + \
    "\xff\xff\xff\xff\xff\xff\xff\xff\xff\x52\x4e\x75\x82\x52\x4e"
    
    TEST_DATA_BAD_SIZE = b"\x00\x1a\x88\x03\xe3\x3b\xc8\x00\x1a\x8c\x03\xe2" + \
    "\xc0\x00\x03\xeb\x0a\x81\x00\x1a\x90\x03\xe1\x5b\x00\x03\xeb\x0a\x65\xff\xff" + \
    "\xff\xff\xff\xff\xff\xff\xff\xff\xff\x52\x4e\x75\x82\x52\x4e\x76\x9a"
    
    TEST_DATA_BAD_EOP = b"\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8\x00\x1a\x8c\x03\xe2" + \
    "\xc0\x00\x03\xeb\x0a\x81\x00\x1a\x90\x03\xe1\x5b\x00\x03\xeb\x0a\x65" + \
    "\xff\xff\xff\xff\x52\x4e\x75\x82\x52\x4e\x76\x9a"

    """
    dofst_k_wfp Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dofst_k_wfp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: ['DofstKWfpParserDataParticle',
                                                     'WfpMetadataParserDataParticle']
            }
        self.start_state = {StateKey.POSITION: 0,
                            StateKey.TIMESTAMP: 0.0,
                            StateKey.RECORDS_READ: 0,
                            StateKey.METADATA_SENT: False}
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
        timefields = struct.unpack('>II', '\x52\x4e\x75\x82\x52\x4e\x76\x9a')
        start_time = int(timefields[0])
        end_time = int(timefields[1])
        # even though there are only 3 samples in TEST_DATA, there are 270 samples in the original file,
        # so this needs to be used to determine the time increment for each time sample
        time_increment_3 = float(end_time - start_time) / 3.0
        time_increment_270 = float(end_time - start_time) / 270.0

        self.start_timestamp = self.calc_timestamp(start_time, time_increment_3, 0)
        self.particle_meta = WfpMetadataParserDataParticle((b"\x52\x4e\x75\x82\x52\x4e\x76\x9a", 3.0),
            internal_timestamp=self.start_timestamp)
        self.particle_meta.set_data_particle_type(DataParticleType.METADATA)
        self.start_timestamp_long = self.calc_timestamp(start_time, time_increment_270, 0)
        self.particle_meta_long = WfpMetadataParserDataParticle((b"\x52\x4e\x75\x82\x52\x4e\x76\x9a", 270.0),
            internal_timestamp=self.start_timestamp_long)
        self.particle_meta_long.set_data_particle_type(DataParticleType.METADATA)

        self.particle_a = DofstKWfpParserDataParticle(b"\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8",
                                                          internal_timestamp=self.start_timestamp)
        self.particle_a_long = DofstKWfpParserDataParticle(b"\x00\x1a\x88\x03\xe3\x3b\x00\x03\xeb\x0a\xc8",
                                                               internal_timestamp=self.start_timestamp_long)
        self.timestamp_2 = self.calc_timestamp(start_time, time_increment_3, 1)
        self.particle_b = DofstKWfpParserDataParticle(b"\x00\x1a\x8c\x03\xe2\xc0\x00\x03\xeb\x0a\x81",
                                                          internal_timestamp=self.timestamp_2)
        self.timestamp_2_long = self.calc_timestamp(start_time, time_increment_270, 1)
        self.particle_b_long = DofstKWfpParserDataParticle(b"\x00\x1a\x8c\x03\xe2\xc0\x00\x03\xeb\x0a\x81",
                                                          internal_timestamp=self.timestamp_2_long)
        timestamp_3 = self.calc_timestamp(start_time, time_increment_3, 2)
        self.particle_c = DofstKWfpParserDataParticle(b"\x00\x1a\x90\x03\xe1\x5b\x00\x03\xeb\x0a\x65",
                                                          internal_timestamp=timestamp_3)
        timestamp_last = self.calc_timestamp(start_time, time_increment_270, 269)
        self.particle_last = DofstKWfpParserDataParticle(b"\x00\x1a\x8f\x03\xe5\x91\x00\x03\xeb\x0bS",
                                                            internal_timestamp=timestamp_last)

	# uncomment to generate yml
        self.particle_to_yml(self.particle_meta)
        self.particle_to_yml(self.particle_a)
        self.particle_to_yml(self.particle_b)
        self.particle_to_yml(self.particle_c)

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

    def calc_timestamp(self, start, increment, sample_idx):
        new_time = start + (increment*sample_idx)
        return float(ntplib.system_to_ntp_time(new_time))
    
    def assert_result(self, result, position, particle, ingested, rec_read, metadata_sent):
        self.assertEqual(result, [particle])
        self.assertEqual(self.file_ingested_value, ingested)

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)
	
	self.assertEqual(self.parser._state[StateKey.METADATA_SENT], metadata_sent)
        self.assertEqual(self.state_callback_value[StateKey.METADATA_SENT], metadata_sent)
	
	self.assertEqual(self.parser._state[StateKey.RECORDS_READ], rec_read)
        self.assertEqual(self.state_callback_value[StateKey.RECORDS_READ], rec_read)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def particle_to_yml(self, particle):
        """
        This is added as a testing helper, not actually as part of the parser tests. Since the same particles
        will be used for the driver test it is helpful to write them to .yml in the same form they need in the
        results.yml files here.
        """
        particle_dict = particle.generate_dict()
        # open write append, if you want to start from scratch manually delete this file
        fid = open('particle.yml', 'a')
        fid.write('  - _index: 1\n')
        fid.write('    internal_timestamp: %f\n' % particle_dict.get('internal_timestamp'))
        fid.write('    particle_object: %s\n' % particle.__class__.__name__)
        fid.write('    particle_type: %s\n' % particle_dict.get('stream_name'))
        for val in particle_dict.get('values'):
            if isinstance(val.get('value'), float):
                fid.write('    %s: %16.20f\n' % (val.get('value_id'), val.get('value')))
            else:
                fid.write('    %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()
    
    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        stream_handle = StringIO(DofstKWfpParserUnitTestCase.TEST_DATA)
        self.parser =  DofstKWfpParser(self.config, self.start_state, stream_handle,
                                        self.state_callback, self.pub_callback,
                                        len(DofstKWfpParserUnitTestCase.TEST_DATA)) 
        # next get records
        result = self.parser.get_records(1)
        self.assert_result(result, 0, self.particle_meta, False, 0, True)
        result = self.parser.get_records(1)
        self.assert_result(result, 11, self.particle_a, False, 1, True)
        result = self.parser.get_records(1)
        self.assert_result(result, 22, self.particle_b, False, 2, True)
        result = self.parser.get_records(1)
        self.assert_result(result, 33, self.particle_c, True, 3, True)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 33)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 33)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_c)

    def test_simple_pad(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        stream_handle = StringIO(DofstKWfpParserUnitTestCase.TEST_DATA_PAD)
        self.parser =  DofstKWfpParser(self.config, self.start_state, stream_handle,
                                        self.state_callback, self.pub_callback,
                                        len(DofstKWfpParserUnitTestCase.TEST_DATA_PAD)) 
        # next get records
        result = self.parser.get_records(1)
        self.assert_result(result, 0, self.particle_meta, False, 0, True)
        result = self.parser.get_records(1)
        self.assert_result(result, 11, self.particle_a, False, 1, True)
        result = self.parser.get_records(1)
        self.assert_result(result, 22, self.particle_b, False, 2, True)
        result = self.parser.get_records(1)
        self.assert_result(result, 33, self.particle_c, True, 3, True)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 33)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 33)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_c)

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(DofstKWfpParserUnitTestCase.TEST_DATA)
        self.parser =  DofstKWfpParser(self.config, self.start_state, self.stream_handle,
                                        self.state_callback, self.pub_callback,
                                        len(DofstKWfpParserUnitTestCase.TEST_DATA)) 
        # next get records
        result = self.parser.get_records(4)
        self.assertEqual(result, [self.particle_meta, self.particle_a, self.particle_b, self.particle_c])
        self.assertEqual(self.parser._state[StateKey.POSITION], 33)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 33)
        self.assertEqual(self.publish_callback_value[0], self.particle_meta)
        self.assertEqual(self.publish_callback_value[1], self.particle_a)
        self.assertEqual(self.publish_callback_value[2], self.particle_b)
        self.assertEqual(self.publish_callback_value[3], self.particle_c)
        self.assertEqual(self.file_ingested_value, True)
        self.assertEqual(self.parser._state[StateKey.RECORDS_READ], 3)
        self.assertEqual(self.state_callback_value[StateKey.RECORDS_READ], 3)
        self.assertEqual(self.parser._state[StateKey.METADATA_SENT], True)
        self.assertEqual(self.state_callback_value[StateKey.METADATA_SENT], True)

    def test_long_stream(self):
        """
        Test a long stream 
        """
        filepath = os.path.join(RESOURCE_PATH, 'C0000038.DAT')
        filesize = os.path.getsize(filepath)
        stream_handle = open(filepath)
        self.parser =  DofstKWfpParser(self.config, self.start_state, stream_handle,
                                        self.state_callback, self.pub_callback,
                                        filesize) 
        result = self.parser.get_records(271)
        self.assertEqual(result[0], self.particle_meta_long)
        self.assertEqual(result[1], self.particle_a_long)
        self.assertEqual(result[2], self.particle_b_long)
        self.assertEqual(result[-1], self.particle_last)
        self.assertEqual(self.parser._state[StateKey.POSITION], 2970)
        self.assertEqual(self.parser._state[StateKey.RECORDS_READ], 270)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 2970)
        self.assertEqual(self.state_callback_value[StateKey.RECORDS_READ], 270)
        self.assertEqual(self.publish_callback_value[-1], self.particle_last)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        # set the state after the metadata and first record
        new_state = {StateKey.POSITION: 11,
                     StateKey.TIMESTAMP: self.start_timestamp,
                     StateKey.RECORDS_READ: 1,
                     StateKey.METADATA_SENT: True}
        self.stream_handle = StringIO(DofstKWfpParserUnitTestCase.TEST_DATA)
        self.parser =  DofstKWfpParser(self.config, new_state, self.stream_handle,
                                        self.state_callback, self.pub_callback,
                                        len(DofstKWfpParserUnitTestCase.TEST_DATA))

        result = self.parser.get_records(1)
        self.assert_result(result, 22, self.particle_b, False, 2, True)
        result = self.parser.get_records(1)
        self.assert_result(result, 33, self.particle_c, True, 3, True)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION: 11,
                     StateKey.TIMESTAMP: self.start_timestamp,
                     StateKey.RECORDS_READ: 1,
                     StateKey.METADATA_SENT: True}
        stream_handle = StringIO(DofstKWfpParserUnitTestCase.TEST_DATA)
        self.parser =  DofstKWfpParser(self.config, self.start_state, stream_handle,
                                        self.state_callback, self.pub_callback,
                                        len(DofstKWfpParserUnitTestCase.TEST_DATA))
        result = self.parser.get_records(1)
        self.assert_result(result, 0, self.particle_meta, False, 0, True)
        
        # essentially skips particle a
        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 22, self.particle_b, False, 2, True)
        result = self.parser.get_records(1)
        self.assert_result(result, 33, self.particle_c, True, 3, True)

    def test_bad_time_data(self):
        """
        Ensure that missing timestamps causes us to sample exception and not parse the file
        """
        with self.assertRaises(SampleException):
            stream_handle = StringIO(DofstKWfpParserUnitTestCase.TEST_DATA_BAD_TIME)
            self.parser =  DofstKWfpParser(self.config, self.start_state, stream_handle,
                                            self.state_callback, self.pub_callback,
                                            len(DofstKWfpParserUnitTestCase.TEST_DATA_BAD_TIME))

    def test_bad_size_data(self):
        """
        Ensure that missing timestamps causes us to sample exception and not parse the file
        """
        with self.assertRaises(SampleException):
            stream_handle = StringIO(DofstKWfpParserUnitTestCase.TEST_DATA_BAD_SIZE)
            self.parser =  DofstKWfpParser(self.config, self.start_state, stream_handle,
                                            self.state_callback, self.pub_callback,
                                            len(DofstKWfpParserUnitTestCase.TEST_DATA_BAD_SIZE))

    def test_bad_eop_data(self):
        """
        Ensure that missing timestamps causes us to sample exception and not parse the file
        """
        with self.assertRaises(SampleException):
            stream_handle = StringIO(DofstKWfpParserUnitTestCase.TEST_DATA_BAD_EOP)
            self.parser =  DofstKWfpParser(self.config, self.start_state, stream_handle,
                                            self.state_callback, self.pub_callback,
                                            len(DofstKWfpParserUnitTestCase.TEST_DATA_BAD_EOP))

