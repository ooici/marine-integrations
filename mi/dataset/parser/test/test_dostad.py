#!/usr/bin/env python

import gevent
import unittest
import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.dostad import DostadParserRecoveredDataParticle, DostadParserTelemeteredDataParticle
from mi.dataset.parser.dostad import DostadParserRecoveredMetadataDataParticle, DostadParserTelemeteredMetadataDataParticle
from mi.dataset.parser.dostad import DostadParser, DostadParserRecovered
from mi.dataset.parser.dostad import StateKey
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
            DataSourceKey.OSTA_ABCDJM_SIO_TELEMETERED: {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dostad',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: DostadParserTelemeteredMetadataDataParticle,
                    DATA_PARTICLE_CLASS_KEY: DostadParserTelemeteredDataParticle,
                }
            },
            DataSourceKey.DOSTA_ABCDJM_SIO_RECOVERED: {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dostad',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: DostadParserRecoveredMetadataDataParticle,
                    DATA_PARTICLE_CLASS_KEY: DostadParserRecoveredDataParticle,
                }
            },
        }

	

            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dostad',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'DostadParserDataParticle'
            }

        # first DO tag
        self.particle_a = DostadParserTelemeteredDataParticle('51EF0E75\xff\x11\x25\x11' \
            '4831\t128\t302.636\t98.918\t16.355\t30.771\t' \
            '30.771\t36.199\t5.429\t1309.9\t1175.7\t299.6\x0d\x0a')

        self.particle_metadata = DostadParserTelemeteredMetadataDataParticle('51EF0E75\xff\x11\x25\x11' \
            '4831\t128\t302.636\t98.918\t16.355\t30.771\t' \
            '30.771\t36.199\t5.429\t1309.9\t1175.7\t299.6\x0d\x0a')

        self.particle_b = DostadParserTelemeteredDataParticle('51EF1901\xff\x11\x25\x11' \
            '4831\t128\t317.073\t98.515\t14.004\t31.299\t31.299' \
            '\t36.647\t5.349\t1338.5\t1212.4\t375.8\x0d\x0a')

        self.particle_c = DostadParserTelemeteredDataParticle('51EF6D61\xff\x11\x25\x11' \
            '4831\t128\t326.544\t96.726\t11.873\t31.965\t31.965' \
            '\t37.134\t5.169\t1370.7\t1245.9\t444.4\x0d\x0a')

        self.particle_d = DostadParserTelemeteredDataParticle('51EFC1C2\xff\x11\x25\x11' \
            '4831\t128\t332.060\t99.617\t12.432\t31.490\t31.490' \
            '\t36.812\t5.323\t1026.0\t1100.0\t426.5\x0d\x0a')

        self.particle_e = DostadParserTelemeteredDataParticle('51F01622\xff\x11\x25\x11' \
            '4831\t128\t354.515\t101.592\t10.440\t31.666\t31.666' \
            '\t36.930\t5.263\t1020.1\t1123.0\t490.0\x0d\x0a')

        self.particle_f = DostadParserTelemeteredDataParticle('51F06A82\xff\x11\x25\x11' \
            '4831\t128\t337.540\t100.172\t11.955\t31.521\t31.521' \
            '\t36.805\t5.284\t983.8\t1092.6\t441.7\x0d\x0a')
	
	# RECOVERED test particles
	self.particle_ra = DostadParserRecoveredDataParticle('51EC7601\xff\x11' \
	    '%\x114831\t128\t302.576\t97.289\t15.584\t31.126\t31.126\t36.306' \
	    '\t5.180\t1336.5\t1171.2\t324.6\r\n')

	self.particle_rmetadata = DostadParserRecoveredMetadataDataParticle('51EC7601\xff\x11' \
	    '%\x114831\t128\t302.576\t97.289\t15.584\t31.126\t31.126\t36.306' \
	    '\t5.180\t1336.5\t1171.2\t324.6\r\n')

	self.particle_rb = DostadParserRecoveredDataParticle('51EC7985\xff\x11%\x11' \
	    '4831\t128\t308.673\t97.333\t14.680\t31.305\t31.305\t36.447\t5.142' \
	    '\t1349.9\t1186.4\t353.9\r\n')

	self.particle_rc = DostadParserRecoveredDataParticle('51EC7D09\xff\x11%\x11' \
	    '4831\t128\t308.517\t97.209\t14.645\t31.328\t31.328\t36.454\t5.126' \
	    '\t1351.5\t1188.4\t355.1\r\n')
	
	self.particle_rd = DostadParserRecoveredDataParticle('51EC808D\xff\x11%\x11' \
	    '4831\t128\t307.609\t97.181\t14.767\t31.307\t31.307\t36.425\t5.119' \
	    '\t1349.9\t1186.2\t351.1\r\n')

	self.particle_re = DostadParserRecoveredDataParticle('51EC8411\xff\x11%\x11' \
	    '4831\t128\t305.890\t97.154\t15.013\t31.259\t31.259\t36.379\t5.120' \
	    '\t1346.7\t1182.9\t343.2\r\n')

	self.particle_rf = DostadParserRecoveredDataParticle('51EC8795\xff\x11%\x11' \
	    '4831\t128\t304.306\t97.139\t15.247\t31.213\t31.213\t36.347\t5.133' \
	    '\t1343.3\t1179.1\t335.6\r\n')

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
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        # NOTE: using the unprocessed data state of 0,6300 limits the file to reading
        # just 6300 bytes, so even though the file is longer it only reads the first
        # 6300
        state = {StateKey.UNPROCESSED_DATA:[[0, 6300]],
            StateKey.IN_PROCESS_DATA:[], StateKey.METADATA_SENT: False, StateKey.FILE_SIZE: 9400}
        self.parser = DostadParser(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # the metadata particle and first particle come from the same block of data, first get
        # the metadata particle (this is why there are 2 particles parsed in the first in process state)
        # after that there are 3 more dosta samples parsed from 390-507, 637-754, and 6131-6248
        # 0-69 contains an incomplete block (end of a sample)
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
	# 4351-4927 has a bad AD then CT message where the size from the header does not line up with
	# the final \x03
	result = self.parser.get_records(1)
	in_process = [[197,314,2,1], [390, 507, 1, 0], [637, 754, 1, 0], [6131, 6248, 1, 0]]
	unprocessed = [[0,69], [197,314], [390,507], [637,754], [1329,1332], [2294,2363],
			    [4092,4161], [4351, 4927], [6131,6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_metadata)
	self.assertEqual(self.parser._state[StateKey.METADATA_SENT], True)
	# then get the first dosta data particle, this clears out the block from 197-314
	result = self.parser.get_records(1)
	in_process = [[390, 507, 1, 0], [637, 754, 1, 0], [6131, 6248, 1, 0]]
	unprocessed = [[0,69], [390,507], [637,754], [1329,1332], [2294,2363],
			    [4092,4161], [4351, 4927], [6131,6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_a)
	self.assertEqual(self.parser._state[StateKey.METADATA_SENT], True)

	result = self.parser.get_records(1)
	in_process = [[637, 754, 1, 0], [6131, 6248, 1, 0]]
	unprocessed = [[0,69], [637,754], [1329,1332], [2294,2363],
			    [4092,4161], [4351, 4927], [6131,6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_b)

	result = self.parser.get_records(1)
	in_process = [[6131, 6248, 1, 0]]
	unprocessed = [[0,69], [1329,1332], [2294,2363], [4092,4161], [4351, 4927], [6131,6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_c)

	result = self.parser.get_records(1)
	in_process = []
	unprocessed = [[0,69], [1329,1332], [2294,2363],[4092,4161], [4351, 4927], [6248,6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_d)

	stream_handle.close()
	self.assertEqual(self.exception_callback_value, None)


    def test_simple_recovered(self):
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'DOS15908_1st7.DAT'))
        # NOTE: using the unprocessed data state of 0,6300 limits the file to reading
        # just 6300 bytes, so even though the file is longer it only reads the first
        # 6300
        state = {StateKey.UNPROCESSED_DATA:[[0, 6300]],
            StateKey.IN_PROCESS_DATA:[], StateKey.METADATA_SENT: False, StateKey.FILE_SIZE: 9400}
        self.parser = DostadParserRecovered(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

	result = self.parser.get_records(1)
	in_process = [[0, 117, 2, 1], [117, 234, 1, 0], [234, 351, 1, 0], [351, 468, 1, 0],
	    [468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[0, 6300]]	
	self.assert_result(result, in_process, unprocessed, self.particle_rmetadata)
	self.assertEqual(self.parser._state[StateKey.METADATA_SENT], True)
	
	# then get the first dosta data particle, this clears out the block from 197-314
	result = self.parser.get_records(1)
	in_process = [[117, 234, 1, 0], [234, 351, 1, 0], [351, 468, 1, 0], [468, 585, 1, 0],
	    [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[117, 6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_ra)
	self.assertEqual(self.parser._state[StateKey.METADATA_SENT], True)

	result = self.parser.get_records(1)
	in_process = [[234, 351, 1, 0], [351, 468, 1, 0], [468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[234, 6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_rb)

	result = self.parser.get_records(1)
	in_process = [[351, 468, 1, 0], [468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[351, 6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_rc)

	result = self.parser.get_records(1)
	in_process = [[468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[468, 6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_rd)

	stream_handle.close()
	self.assertEqual(self.exception_callback_value, None)

    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
            StateKey.IN_PROCESS_DATA:[], StateKey.METADATA_SENT: False, StateKey.FILE_SIZE: 9400}
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(4)
        stream_handle.close()
        self.assertEqual(result,
                         [self.particle_metadata, self.particle_a, self.particle_b, self.particle_c])
        # 0-69 contains an incomplete block (end of a sample)
        self.assert_state([],
                        [[0,69],[944,1000]])
        self.assertEqual(self.publish_callback_value[0], self.particle_metadata)
        self.assertEqual(self.publish_callback_value[1], self.particle_a)
        self.assertEqual(self.publish_callback_value[2], self.particle_b)
        self.assertEqual(self.publish_callback_value[3], self.particle_c)
        self.assertEqual(self.exception_callback_value, None)

    def test_get_many_recovered(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
            StateKey.IN_PROCESS_DATA:[], StateKey.METADATA_SENT: False, StateKey.FILE_SIZE: 9400}
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'DOS15908_1st7.DAT'))
        self.parser = DostadParserRecovered(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(4)
        stream_handle.close()
        self.assertEqual(result,
                         [self.particle_rmetadata, self.particle_ra, self.particle_rb, self.particle_rc])
 
        self.assert_state([[351, 468, 1, 0], [468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]],
                        [[351, 1000]])
        self.assertEqual(self.publish_callback_value[0], self.particle_rmetadata)
        self.assertEqual(self.publish_callback_value[1], self.particle_ra)
        self.assertEqual(self.publish_callback_value[2], self.particle_rb)
        self.assertEqual(self.publish_callback_value[3], self.particle_rc)
        self.assertEqual(self.exception_callback_value, None)


    def test_long_stream(self):
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, None, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(7)
        stream_handle.close()
        self.assertEqual(result[0], self.particle_metadata)
        self.assertEqual(result[1], self.particle_a)
        self.assertEqual(result[2], self.particle_b)
        self.assertEqual(result[3], self.particle_c)
        self.assertEqual(result[4], self.particle_d)
        self.assertEqual(result[5], self.particle_e)
        self.assertEqual(result[6], self.particle_f)
        # 0-69 contains an incomplete block (end of a sample)
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_state([],
            [[0, 69], [1329,1332], [2294,2363], [4092,4161], [4351, 4927], [9020, 9374]])
        self.assertEqual(self.publish_callback_value[5], self.particle_e)
        self.assertEqual(self.publish_callback_value[6], self.particle_f)
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream_recovered(self):
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'DOS15908_1st7.DAT'))
        self.parser = DostadParserRecovered(self.config, None, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(7)
        stream_handle.close()
        self.assertEqual(result[0], self.particle_rmetadata)
        self.assertEqual(result[1], self.particle_ra)
        self.assertEqual(result[2], self.particle_rb)
        self.assertEqual(result[3], self.particle_rc)
        self.assertEqual(result[4], self.particle_rd)
        self.assertEqual(result[5], self.particle_re)
        self.assertEqual(result[6], self.particle_rf)
        self.assert_state([[702, 819, 1, 0]],
            [[702, 819]])
        self.assertEqual(self.publish_callback_value[5], self.particle_re)
        self.assertEqual(self.publish_callback_value[6], self.particle_rf)
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0,69], [314,6300]],
            StateKey.METADATA_SENT: True,
            StateKey.FILE_SIZE: 9400}
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, new_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        # 0-69 contains an incomplete block (end of a sample)
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [[637, 754, 1, 0],[6131, 6248, 1, 0]],
                           [[0,69],[637,754],[1329,1332], [2294,2363],
                            [4092,4161], [4351, 4927], [6131,6300]],
                           self.particle_b)
        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_c)
        self.assertEqual(result[1], self.particle_d)
        self.assert_state([], [[0,69],[1329,1332], [2294,2363],
                            [4092,4161], [4351, 4927], [6248,6300]])
        stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start_recovered(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[117,6300]],
            StateKey.METADATA_SENT: True,
            StateKey.FILE_SIZE: 9400}
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'DOS15908_1st7.DAT'))
        self.parser = DostadParserRecovered(self.config, new_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)

        self.assert_result(result, [[234, 351, 1, 0], [351, 468, 1, 0], [468, 585, 1, 0],
	    [585, 702, 1, 0], [702, 819, 1, 0]],
            [[234, 6300]],
            self.particle_rb)
	
        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_rc)
        self.assertEqual(result[1], self.particle_rd)

        self.assert_state([[468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]],
	    [[468, 6300]])
        stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[[390, 507, 1, 0], [637, 754, 1, 0], [6131, 6248, 1, 0]],
            StateKey.UNPROCESSED_DATA:[ [390,6300]],
            StateKey.METADATA_SENT: True,
            StateKey.FILE_SIZE: 9400}
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, new_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)

        self.assert_result(result, [[637, 754, 1, 0], [6131, 6248, 1, 0]],
                           [[507,6300]],
                           self.particle_b)

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_c)
        self.assertEqual(result[1], self.particle_d)
        self.assert_state([],
            [[507,637], [754,6131], [6248, 6300]])
        self.assertEqual(self.publish_callback_value[-1], self.particle_d)
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start_recovered(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[[117, 234, 1, 0], [234, 351, 1, 0], [351, 468, 1, 0],
	    [468, 585, 1, 0],[585, 702, 1, 0], [702, 819, 1, 0]],
            StateKey.UNPROCESSED_DATA:[[117, 6300]],
            StateKey.METADATA_SENT: True,
            StateKey.FILE_SIZE: 9400}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'DOS15908_1st7.DAT'))
        self.parser = DostadParserRecovered(self.config, new_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)

        self.assert_result(result, [[234, 351, 1, 0], [351, 468, 1, 0], [468, 585, 1, 0],
	    [585, 702, 1, 0], [702, 819, 1, 0]],[[234, 6300]],
            self.particle_rb)

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_rc)
        self.assertEqual(result[1], self.particle_rd)
        self.assert_state([[468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]],[[468, 6300]])
        self.assertEqual(self.publish_callback_value[-1], self.particle_rd)
        self.assertEqual(self.exception_callback_value, None)


    def test_set_state(self):
        """
        test changing the state after initializing
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 1000]], StateKey.IN_PROCESS_DATA:[],
            StateKey.METADATA_SENT: False,
            StateKey.FILE_SIZE: 9400}
        new_state = {StateKey.UNPROCESSED_DATA:[[0,69],[944,6300]],
            StateKey.IN_PROCESS_DATA:[], StateKey.METADATA_SENT: True,
            StateKey.FILE_SIZE: 9400}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # there should only be 4 records, make sure we stop there
        result = self.parser.get_records(4)
        # 0-69 contains an incomplete block (end of a sample)
        self.assert_state([],
            [[0,69],[944,1000]])
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        stream_handle.close()
        # 0-69 contains an incomplete block (end of a sample)
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [],
                           [[0,69],[1329,1332], [2294,2363], [4092,4161], [4351, 4927],
                           [6248,6300]],
                           self.particle_d)
        self.assertEqual(self.exception_callback_value, None)


    def test_set_state_recovered(self):
        """
        test changing the state after initializing
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 351]], StateKey.IN_PROCESS_DATA:[],
            StateKey.METADATA_SENT: False,
            StateKey.FILE_SIZE: 9400}
        new_state = {StateKey.UNPROCESSED_DATA:[[351,6300]],
            StateKey.IN_PROCESS_DATA:[], StateKey.METADATA_SENT: True,
            StateKey.FILE_SIZE: 9400}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'DOS15908_1st7.DAT'))
        self.parser = DostadParserRecovered(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # there should only be 4 records, make sure we stop there
        result = self.parser.get_records(4)

        self.assert_state([],[])
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        stream_handle.close()

	print "IN"
	print self.parser._state[StateKey.IN_PROCESS_DATA]
	print "UN"
	print self.parser._state[StateKey.UNPROCESSED_DATA]


        self.assert_result(result, [[468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]],
                           [[468, 6300]],
                           self.particle_rd)
        self.assertEqual(self.exception_callback_value, None)


    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 6300]],
            StateKey.IN_PROCESS_DATA:[], StateKey.METADATA_SENT: False, StateKey.FILE_SIZE: 9400}
        # this file has a block of DO data replaced by 0s
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replaced.dat'))
        self.parser = DostadParser(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        # 0-69 contains an incomplete block (end of a sample)
        # 390-570 is the zeroed block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [[197,314,2,1], [637,754,1,0], [6131,6248,1,0]],
                           [[0,69], [197,314], [390,507], [637,754], [1329,1332], [2294,2363],
                            [4092,4161], [4351, 4927], [6131,6300]],
                            self.particle_metadata)
        result = self.parser.get_records(1)
        self.assert_result(result, [[637,754,1,0], [6131,6248,1,0]],
                           [[0,69], [390,507], [637,754], [1329,1332], [2294,2363],
                            [4092,4161], [4351, 4927], [6131,6300]],
                            self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, [[6131,6248,1,0]],
                           [[0,69], [390,507], [1329,1332], [2294,2363],
                            [4092,4161], [4351, 4927], [6131,6300]],
                            self.particle_c)
        stream_handle.close()

        next_state = self.parser._state
        # this file has the block of data that was missing in the previous file
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = DostadParser(self.config, next_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # first get the old 'in process' records from 6131-6248
        # Once those are done, the un processed data will be checked
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69], [390,507], [1329,1332], [2294,2363],
                            [4092,4161], [4351, 4927], [6248,6300]],
                            self.particle_d)

        # this should be the first of the newly filled in particles from 390-507
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69], [1329,1332], [2294,2363],
                            [4092,4161], [4351, 4927], [6248,6300]],
                           self.particle_b)
        stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)


    def test_update_recovered(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 6300]],
            StateKey.IN_PROCESS_DATA:[], StateKey.METADATA_SENT: False, StateKey.FILE_SIZE: 9400}
        # this file has a block of DO data replaced by 0s
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'DOS15908_1st7_replaced.DAT'))
        self.parser = DostadParserRecovered(self.config, state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

	result = self.parser.get_records(1)
	in_process = [[0, 117, 2, 1], [234, 351, 1, 0], [351, 468, 1, 0],
	    [468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[0, 6300]]	
	self.assert_result(result, in_process, unprocessed, self.particle_rmetadata)
	self.assertEqual(self.parser._state[StateKey.METADATA_SENT], True)
	
	# then get the first dosta data particle, this clears out the block from 197-314
	result = self.parser.get_records(1)
	in_process = [[234, 351, 1, 0], [351, 468, 1, 0], [468, 585, 1, 0],
	    [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[117, 6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_ra)
	self.assertEqual(self.parser._state[StateKey.METADATA_SENT], True)

	result = self.parser.get_records(1)
	in_process = [[351, 468, 1, 0], [468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[117, 234], [351, 6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_rc)

        stream_handle.close()

        next_state = self.parser._state
        # this file has the block of data that was missing in the previous file
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'DOS15908_1st7.DAT'))
        self.parser = DostadParserRecovered(self.config, next_state, stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # first get the old 'in process' records from 6131-6248
        # Once those are done, the un processed data will be checked
 	result = self.parser.get_records(1)
	in_process = [[468, 585, 1, 0], [585, 702, 1, 0], [702, 819, 1, 0]]
	unprocessed = [[117, 234], [468, 6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_rd)

        #  3 records remain, then the subsequent read should find the previously missing record
	result = self.parser.get_records(3)
	result = self.parser.get_records(1)
	in_process = []
	unprocessed = [[819, 6300]]
	self.assert_result(result, in_process, unprocessed, self.particle_rb)

        stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)
