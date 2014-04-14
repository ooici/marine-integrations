#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_phsen
@file marine-integrations/mi/dataset/parser/test/test_phsen.py
@author Emily Hahn
@brief Test code for a Phsen data parser
"""
import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.phsen import PhsenParser, PhsenParserDataParticle

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'mflm',
			     'phsen', 'resource')

@attr('UNIT', group='mi')
class PhsenParserUnitTestCase(ParserUnitTestCase):
    """
    Phsen Parser unit test suite
    """
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
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.phsen',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'PhsenParserDataParticle'
            }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results

        self.timestamp1 = 3583656000.0
        self.particle_a = PhsenParserDataParticle('^0A\r*2BE70ACE15724007EF0C5707A' \
            '208AA09E10C5F07A008AD09E10C6007A108AB09E00C5907A408AA09E10C6007A408AA' \
            '09E00C5C07A308A809E00C5B07A108A609E00C62079E08AC09D80C5E076808A809720' \
            'C5E06ED08AA088D0C5C067508A907B70C5E062F08AC073F0C5F061808AA071C0C5E06' \
            '2908A907360C5D064C08AB07720C5B067808A707BC0C5906A608A7080F0C6006D008A' \
            '808590C5C06F608AA089E0C61071708AB08D90C5C072F08A909070C60074408A7092F' \
            '0C5E075508AA09500C5E076408A8096B0C5B076E08A8097F0C5C077A08AA09910C5D0' \
            '77E08AC099B00000C2807EF17\r',
            internal_timestamp=self.timestamp1)

        self.timestamp2 = 3583699199.0
        self.particle_b = PhsenParserDataParticle('^0A\r*2BE70ACE161AFF07FE0C6507AB' \
            '08B609F90C5D07A808B709F70C6207AA08B709F50C5F07A908B809F70C6207A808B709' \
            'F60C6107A808B409F40C60079508B309D00C6006BC08B708400C6504D708B5052B0C64' \
            '031D08B802D50C62022308B601B80C6501BC08B901520C5F01AE08B601430C6001D708' \
            'B701680C62022708B501BA0C62029708B902300C60031708B902C50C5903A008B20371' \
            '0C63042908B804290C6404AA08B804E20C64052008B405930C63058808B706360C6405' \
            'E308BA06CA0C63062E08B707490C61066D08B607B50C6506A408B708140C6206D008B5' \
            '086200000C2807FF24\r',
            internal_timestamp=self.timestamp2)

	self.timestamp3 = 3583742399.0
	self.particle_c = PhsenParserDataParticle('^0A\r*2BE70ACE16C3BF07FC0C6007A70' \
	    '8B609F70C6107A708B509F50C6107A608B609F50C6307A808BB09F60C5D07A908B709F5' \
	    '0C6107A908B809F60C65079208B809CF0C6106A408BA08250C61049708B804E70C6302D' \
	    '308B702930C5D01F508B3019F0C6001AD08B901500C6301B008B201500C5E01E208B301' \
	    '800C62023708B701DB0C6302A408B702500C65031C08B902DC0C63039A08B5037A0C630' \
	    '41808B804240C5C048F08B104CD0C64050208B805720C63056508B6060D0C6305BF08B5' \
            '069C0C64060B08B7071A0C61064D08B507890C61068408B307E70C6306B308B60837000' \
            '00C2708002A\r',
            internal_timestamp=self.timestamp3)

        self.timestamp4 = 3583763999.0
        self.particle_d = PhsenParserDataParticle('^0A\r*2BE70ACE17181F07E70C6207AA08' \
            'C50A0A0C6907AC08CA0A0B0C6207AB08C50A0B0C6607A908C60A0A0C6807A908BF0A080C' \
            '6B07AA08C70A0A0C67079208C509DC0C6906B908C808520C6404BD08C3051C0C63033D08' \
            'C5030C0C6D028708C8022E0C66024D08C301EA0C69025C08C801FC0C67029808C9023D0C' \
            '6402F008C102A10C65035308C4031C0C6703C008C703A70C67043008C8043F0C68049B08' \
            'C904D80C6C050308C705740C68055E08C506070C6605B608C506910C67060308C6070C0C' \
            '67064308C4077A0C66067A08C707D70C6706A708C508280C6706CD08C2086E00000C2507' \
            'E88D\r',
            internal_timestamp=self.timestamp4)

        self.timestamp5 = 3583545055.0
        # the particle associated with this timestamp is bad, but we still read the
        # timestamp before discovering the particle is bad

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
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 9000]],
            StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.parser = PhsenParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, [[1804, 2308, 1, 0]],
			   [[0, 172], [1804, 2308], [2373, 3532], [3722, 4371],
			    [5333, 6558], [6748, 7327], [7714, 7781], [8547, 9000]], 
			   self.timestamp2, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [],
			   [[0, 172], [2373, 3532], [3722, 4371],
			    [5333, 6558], [6748, 7327], [7714, 7781], [8547, 9000]],
			   self.timestamp2, self.particle_b)
	self.stream_handle.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 17600]],
            StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(4)
        self.stream_handle.close()
        self.assertEqual(result,
                         [self.particle_a, self.particle_b, self.particle_c,
                          self.particle_d])
        # the remaining in process data is actually a particle with a bad sample
        self.assert_state([[16329, 16833, 1, 0]], [[0, 172], [2373, 3532], [3722, 4371],
                        [5333, 6558], [6748, 7327], [7714, 7781], [8547, 8653],
                        [9039, 9230], [9286, 9933], [10509, 10896],
                        [11086, 12700], [16329,16833], [17530, 17600]],
                        self.timestamp5)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_d)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0, 172], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781], [8547, 16000]],
            StateKey.TIMESTAMP:self.timestamp2}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, [[14867, 15371, 1, 0]],
                           [[0, 172], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781], 
                            [8547, 8653], [9039, 9230], [9286, 9933], 
                            [10509, 10896], [11086, 12700], [14867, 15371],
                            [15564, 16000]],
                           self.timestamp4, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781], 
                            [8547, 8653], [9039, 9230], [9286, 9933], 
                            [10509, 10896], [11086, 12700], [15564, 16000]],
                           self.timestamp4, self.particle_d)
        self.stream_handle.close()

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[[1804, 2308, 1, 0]],
            StateKey.UNPROCESSED_DATA:[[0, 172], [1804, 2308], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781], [8547, 14700]],
            StateKey.TIMESTAMP:self.timestamp1}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)

        # even though the state says this particle is not a new sequence, since it is the
        # first after setting the state it will be new
        self.assert_result(result, [],
                           [[0, 172], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781], [8547, 14700]],
                           self.timestamp2, self.particle_b)

        result = self.parser.get_records(1)
        self.assertEqual(result[0], self.particle_c)
        self.assert_state([],
                        [[0, 172], [2373, 3532], [3722, 4371],
                        [5333, 6558], [6748, 7327], [7714, 7781],
                        [8547, 8653], [9039, 9230], [9286, 9933], 
                        [10509, 10896], [11086, 12700], [14674,14700]],
                        self.timestamp3)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 9000]], StateKey.IN_PROCESS_DATA:[],
            StateKey.TIMESTAMP:0.0}
        new_state = {StateKey.UNPROCESSED_DATA:[[0, 172], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781], [8547, 14700]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.TIMESTAMP:self.timestamp2}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # there should only be 2 records, make sure we stop there
        result = self.parser.get_records(2)
        self.assert_state([], [[0, 172], [2373, 3532], [3722, 4371],
            [5333, 6558], [6748, 7327], [7714, 7781], [8547, 9000]],
            self.timestamp2)
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result, [],
                           [[0, 172], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781],
                            [8547, 8653], [9039, 9230], [9286, 9933], 
                            [10509, 10896], [11086, 12700], [14674,14700]],
                           self.timestamp3, self.particle_c)

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        log.debug('Starting test_update')
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 14700]],
            StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        # this file has a block of FL data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replaced.dat'))
        self.parser = PhsenParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, [[14170,14674,1,0]],
                           [[0, 172], [367,911], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781],
                            [8547, 8653], [9039, 9230], [9286, 9933], 
                            [10509, 10896], [11086, 12700], [14170,14700]],
                           self.timestamp3, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [367,911], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781],
                            [8547, 8653], [9039, 9230], [9286, 9933], 
                            [10509, 10896], [11086, 12700], [14674,14700]],
                           self.timestamp3, self.particle_c)
        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # now get the filled in record
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [2373, 3532], [3722, 4371],
                            [5333, 6558], [6748, 7327], [7714, 7781],
                            [8547, 8653], [9039, 9230], [9286, 9933], 
                            [10509, 10896], [11086, 12700], [14674,14700]],
                           self.timestamp1, self.particle_a)
        self.stream_handle.close()
