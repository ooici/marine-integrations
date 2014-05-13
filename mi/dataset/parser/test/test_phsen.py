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
        # starts file index 367
        self.particle_a = PhsenParserDataParticle('51EFC1C1^0A\r*2BE70ACE15724007EF0C5'
            '707A208AA09E10C5F07A008AD09E10C6007A108AB09E00C5907A408AA09E10C6007A408AA'
            '09E00C5C07A308A809E00C5B07A108A609E00C62079E08AC09D80C5E076808A809720C5E0'
            '6ED08AA088D0C5C067508A907B70C5E062F08AC073F0C5F061808AA071C0C5E062908A907'
            '360C5D064C08AB07720C5B067808A707BC0C5906A608A7080F0C6006D008A808590C5C06F'
            '608AA089E0C61071708AB08D90C5C072F08A909070C60074408A7092F0C5E075508AA0950'
            '0C5E076408A8096B0C5B076E08A8097F0C5C077A08AA09910C5D077E08AC099B00000C2807EF17\r')
        # starts file index 1107
        self.particle_b = PhsenParserDataParticle('51F01621^0A\r*2BE70AC\x8515C69F083'
            'C0C6607A608CB0A0D0C6507A708CC0A0C0C6A07A808CF0A0C0C6A07A508D10A0A0C6607A'
            '908CF0A0F0C6B07A908D10A0D0C6807A708C90A0D0C6C07A708D10A0D0C6707A808CE0A0'
            'E0C6607A608CF0A0D0C6807A808CD0A0B0C6907A708CD0A0B0C6707A508CF0A0B0C6707A'
            '808CC0A0C0C6C07A608D20A0B0C6A07A808CD0A0C0C6907A708CE0A0C0C6A07A808CD0A0'
            'D0C6807A708CB0A0C0C6807A808CD0A0D0C6807A808CE0A0E0C6307A708C90A0B0C6607A7'
            '08CD0A0A0C6507A708C80A0D0C6907A708CA0A0B0C6807A708CE0A0C0C6607A708CF0A0B0'
            '0000C27083D64\r')
        # starts file index 1805
        self.particle_c = PhsenParserDataParticle('51F06A81^0A\r*2BE70ACE161AFF07FE0C6507AB' \
            '08B609F90C5D07A808B709F70C6207AA08B709F50C5F07A908B809F70C6207A808B709' \
            'F60C6107A808B409F40C60079508B309D00C6006BC08B708400C6504D708B5052B0C64' \
            '031D08B802D50C62022308B601B80C6501BC08B901520C5F01AE08B601430C6001D708' \
            'B701680C62022708B501BA0C62029708B902300C60031708B902C50C5903A008B20371' \
            '0C63042908B804290C6404AA08B804E20C64052008B405930C63058808B706360C6405' \
            'E308BA06CA0C63062E08B707490C61066D08B607B50C6506A408B708140C6206D008B5' \
            '086200000C2807FF24\r')
        # starts file index 13742
        self.particle_d = PhsenParserDataParticle('51F0BEE1^0A\r*2BE70ACE1\x9e6F5F081' \
            '50C6E07AD08DC0A1E0C6D07AE08DA0A210C6C07AB08DC0A1E0C6D07AD08D70A1E0C6C07A' \
            'E08DA0A210C6B07AD08D50A1F0C6A07A708D60A120C6D075508D509730C6B061308D8073' \
            '40C6D046F08D904A20C6B035508D903220C6B02DB08D7028A0C6F02CC08D702760C6B02F' \
            '708D502A90C6E034708D8030C0C6B03AC08D4038D0C65041A08D504230C6B048608D404C' \
            '10C6F04F508DB05640C6F055A08D806000C6905B508D406920C6D060508D5071A0C6E064' \
            'B08D407910C67068408D507F60C6F06B708D808510C6C06DD08D608970C70070108DB08D' \
            '500000C260816B2\r')
        # starts file index 14171
        self.particle_e = PhsenParserDataParticle('51F11341^0A\r*2BE70ACE16C3BF07FC0C6007A70' \
            '8B609F70C6107A708B509F50C6107A608B609F50C6307A808BB09F60C5D07A908B709F5' \
            '0C6107A908B809F60C65079208B809CF0C6106A408BA08250C61049708B804E70C6302D' \
            '308B702930C5D01F508B3019F0C6001AD08B901500C6301B008B201500C5E01E208B301' \
            '800C62023708B701DB0C6302A408B702500C65031C08B902DC0C63039A08B5037A0C630' \
            '41808B804240C5C048F08B104CD0C64050208B805720C63056508B6060D0C6305BF08B5' \
            '069C0C64060B08B7071A0C61064D08B507890C61068408B307E70C6306B308B60837000' \
            '00C2708002A\r')

        self.particle_f = PhsenParserDataParticle('51F167A0^0A\r*2BE70ACE17181F07E70C6207AA08' \
            'C50A0A0C6907AC08CA0A0B0C6207AB08C50A0B0C6607A908C60A0A0C6807A908BF0A080C' \
            '6B07AA08C70A0A0C67079208C509DC0C6906B908C808520C6404BD08C3051C0C63033D08' \
            'C5030C0C6D028708C8022E0C66024D08C301EA0C69025C08C801FC0C67029808C9023D0C' \
            '6402F008C102A10C65035308C4031C0C6703C008C703A70C67043008C8043F0C68049B08' \
            'C904D80C6C050308C705740C68055E08C506070C6605B608C506910C67060308C6070C0C' \
            '67064308C4077A0C66067A08C707D70C6706A708C508280C6706CD08C2086E00000C2507' \
            'E88D\r')

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
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 9000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.parser = PhsenParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, [[1106, 1610, 1, 0], [1804, 2308, 1, 0]],
                           [[0, 172], [1106, 1610], [1804, 2308], [4100, 4171],
                            [5899, 5968], [7697, 7764], [8636, 9000]], 
                           self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, [[1804, 2308, 1, 0]],
                           [[0, 172], [1804, 2308], [4100, 4171],
                            [5899, 5968], [7697, 7764], [8636, 9000]],
                           self.particle_b)
        self.stream_handle.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 17600]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(6)
        self.stream_handle.close()
        self.assertEqual(result,
                         [self.particle_a, self.particle_b, self.particle_c,
                          self.particle_d, self.particle_e, self.particle_f])
        # the remaining in process data is actually a particle with a bad sample
        self.assert_state([[15536, 16040, 1, 0], [16301, 16805, 1, 0], [16998, 17502, 1, 0]],
            [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764],[9654,9723], 
             [11451,11520], [15536, 16040], [16301, 16805], [16998, 17600]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_d)
        self.assertEqual(self.publish_callback_value[4], self.particle_e)
        self.assertEqual(self.publish_callback_value[5], self.particle_f)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0, 172], [4100, 4171], [5899, 5968],
                [7697, 7764], [8636, 16000]]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, [[14142, 14646, 1, 0], [14839, 15343, 1, 0]],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14142,14646], [14839,15343], [15536, 16000]],
                           self.particle_d)
        result = self.parser.get_records(1)
        self.assert_result(result, [[14839, 15343, 1, 0]],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14839,15343], [15536, 16000]],
                           self.particle_e)
        self.stream_handle.close()

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[[1804, 2308, 1, 0]],
            StateKey.UNPROCESSED_DATA:[[0, 172], [1804, 2308], [4100, 4171], [5899, 5968],
                                       [7697, 7764], [8636, 16000]]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [8636, 16000]],
                           self.particle_c)

        result = self.parser.get_records(1)
        self.assert_result(result, [[14142, 14646, 1, 0], [14839, 15343, 1, 0]],
                        [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14142,14646], [14839,15343], [15536, 16000]],
                        self.particle_d)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 9000]], StateKey.IN_PROCESS_DATA:[]}
        new_state = {StateKey.UNPROCESSED_DATA:[[0, 172], [4100, 4171], [5899, 5968],
                                                [7697, 7764], [8636, 14700]],
                     StateKey.IN_PROCESS_DATA:[]}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # there should only be 3 records, make sure we stop there
        result = self.parser.get_records(3)
        self.assert_state([], [[0, 172], [4100, 4171], [5899, 5968],
                                [7697, 7764], [8636, 9000]])
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result, [[14142, 14646, 1, 0]],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14142,14700]],
                           self.particle_d)

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        log.debug('Starting test_update')
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 14700]],
            StateKey.IN_PROCESS_DATA:[]}
        # this file has a block of FL data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replaced.dat'))
        self.parser = PhsenParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(3)
        self.assertEqual(result, [self.particle_b, self.particle_c, self.particle_d])
        self.assert_state([[14142, 14646, 1, 0]],
            [[0, 172], [367,911], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14142,14700]])
        # was b and c
        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = PhsenParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        
        # get last in process record
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [367,911], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14646,14700]],
                           self.particle_e)
        # now get the filled in record
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0, 172], [4100, 4171], [5899, 5968], [7697, 7764], [9654, 9723],
                            [11451, 11520], [14646,14700]],
                           self.particle_a)
        self.stream_handle.close()
