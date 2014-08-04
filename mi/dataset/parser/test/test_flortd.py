#!/usr/bin/env python

import gevent
import unittest
import os
import time
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.parser.flortd import FlortdParser, FlortdRecoveredParser, \
                                     FlortdParserDataParticle, \
                                     FlortdRecoveredParserDataParticle
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'mflm',
			     'flort', 'resource')

@attr('UNIT', group='mi')
class FlortdParserUnitTestCase(ParserUnitTestCase):

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def state_callback_recovered(self, state, ingested):
        """ Call back method to watch what comes in via the position callback for the recovered parser"""
        self.state_callback_recov_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.telem_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flortd',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlortdParserDataParticle'
            }

        self.recov_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flortd',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlortdRecoveredParserDataParticle'
            }

        # first FL tag
        self.particle_a = FlortdParserDataParticle(
            '51EF0E7507/23/13\t23:15:06\t700\t50\t695\t50\t460\t53\t545')
        self.particle_a_dash = FlortdParserDataParticle(
            '51EF0E7507/23/13\t23:15:06\t700\t50\t--\t50\t460\t53\t545')
        self.particle_b = FlortdParserDataParticle(
            '51EF190107/24/13\t00:00:06\t700\t85\t695\t50\t460\t51\t548')
        self.particle_c = FlortdParserDataParticle(
            '51EF6D6107/24/13\t06:00:05\t700\t78\t695\t72\t460\t51\t553')
        self.particle_d = FlortdParserDataParticle(
            '51EFC1C207/24/13\t12:00:06\t700\t169\t695\t127\t460\t58\t553')
        self.particle_e = FlortdParserDataParticle(
            '51F0162207/24/13\t18:00:06\t700\t262\t695\t84\t460\t55\t555')
        self.particle_f = FlortdParserDataParticle(
            '51F06A8207/25/13\t00:00:06\t700\t159\t695\t95\t460\t59\t554')

	# particles from FLO15908.DAT and FLO_short.DAT
	self.particle_a_recov = FlortdRecoveredParserDataParticle(
	    '51EC760117/12/13\t00:00:05\t700\t4130\t695\t700\t460\t4130\t547')
	self.particle_b_recov = FlortdRecoveredParserDataParticle(
	    '51EC798517/12/13\t00:15:04\t700\t4130\t695\t708\t460\t4130\t548')
	self.particle_c_recov = FlortdRecoveredParserDataParticle(
	    '51EC7D0917/12/13\t00:30:04\t700\t4130\t695\t702\t460\t4130\t548')
	self.particle_d_recov = FlortdRecoveredParserDataParticle(
	    '51EC808D17/12/13\t00:45:04\t700\t4130\t695\t710\t460\t4130\t548')
	self.particle_e_recov = FlortdRecoveredParserDataParticle(
	    '51EC841117/12/13\t01:00:04\t700\t4130\t695\t708\t460\t4130\t548')
	self.particle_f_recov = FlortdRecoveredParserDataParticle(
	    '51EC879517/12/13\t01:15:04\t700\t4130\t695\t700\t460\t4130\t548')

	# particles from FLO15908.DAT
	self.particle_long_before_last = FlortdRecoveredParserDataParticle(
	    '51EDC07917/12/13\t23:30:05\t700\t4130\t695\t677\t460\t4130\t545')
	self.particle_long_last = FlortdRecoveredParserDataParticle(
	    '51EDC3FD17/12/13\t23:45:05\t700\t4130\t695\t674\t460\t4130\t545')

	self.stream_handle = None
        self.state_callback_value = None
        self.state_callback_recov_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def assert_result(self, result, in_process_data, unprocessed_data, particle, recov_flag=False):
        self.assertEqual(result, [particle])
        self.assert_state(in_process_data, unprocessed_data, recov_flag)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def assert_state(self, in_process_data, unprocessed_data, recov_flag=False):
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        if not recov_flag:
            self.assertEqual(self.state_callback_value[StateKey.IN_PROCESS_DATA], in_process_data)
            self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)
        else:
            self.assertEqual(self.state_callback_recov_value[StateKey.IN_PROCESS_DATA], in_process_data)
            self.assertEqual(self.state_callback_recov_value[StateKey.UNPROCESSED_DATA], unprocessed_data)

    def build_telem_parser(self, state=None):
        """
        Build a telemetered parser, storing it in self.parser
        @param state initial parser state defaults to None
        """
        if self.stream_handle is None:
            self.fail("Must set stream handle before building telemetered parser")
        self.parser = FlortdParser(self.telem_config, state, self.stream_handle,
                                   self.state_callback, self.pub_callback, self.exception_callback)

    def build_recov_parser(self, state=None):
        """
        Build a telemetered parser, storing it in self.parser
        This requires stream handle to be set before calling it
        @param state initial parser state defaults to None
        """
        if self.stream_handle is None:
            self.fail("Must set stream handle before building recovered parser")
        self.parser = FlortdRecoveredParser(self.recov_config, state, self.stream_handle,
                                            self.state_callback_recovered, self.pub_callback,
                                            self.exception_callback)

    def test_simple(self):
        """
        Read test data from the file and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'node59p1_shorter.dat'))
        # NOTE: using the unprocessed data state of 0,1000 limits the file to reading
        # just 1000 bytes, so even though the file is longer it only reads the first
        # 1000
        state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 9400}
        self.build_telem_parser(state)

        result = self.parser.get_records(1)
        # 0-69, 944-1000 are incomplete samples, 314-390 and 561-637 are samples that have
        # parsed but not yet returned (in_process)
        self.assert_result(result,
                           [[314,390,1,0], [561,637,1,0]],
                           [[0,69],[314,390],[561,637],[944,1000]], self.particle_a)
        result = self.parser.get_records(1)
        # 0-69, 944-1000 are incomplete samples, 561-637 is parsed but not yet 
        # returned (in_process)
        self.assert_result(result, [[561,637,1,0]],
                           [[0,69],[561,637],[944,1000]], self.particle_b)
        result = self.parser.get_records(1)
        # all three samples that were parsed have been returned, no more in process
        self.assert_result(result, [],
                           [[0,69],[944,1000]], self.particle_c)

	# make sure there were no exceptions
	self.assertEqual(self.exception_callback_value, None)

        self.stream_handle.close()

    def test_simple_recov(self):
        """
        Test that we can pull out data particles one at a time from for a recovered
        parser and file.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'FLO_short.DAT'))
        self.build_recov_parser()

	# get all 6 records in this file one at a time, comparing the state and particle
	result = self.parser.get_records(1)
	self.assert_result(result, [[81,162,1,0], [162,243,1,0], [243,324,1,0], [324,405,1,0], [405,486,1,0]],
			   [[81,486]], self.particle_a_recov, recov_flag=True)
	result = self.parser.get_records(1)
	self.assert_result(result, [[162,243,1,0], [243,324,1,0], [324,405,1,0], [405,486,1,0]],
			   [[162,486]], self.particle_b_recov, recov_flag=True)
	result = self.parser.get_records(1)
	self.assert_result(result, [[243,324,1,0], [324,405,1,0], [405,486,1,0]],
			   [[243,486]], self.particle_c_recov, recov_flag=True)
	result = self.parser.get_records(1)
	self.assert_result(result, [[324,405,1,0], [405,486,1,0]], [[324,486]],
			   self.particle_d_recov, recov_flag=True)
	result = self.parser.get_records(1)
	self.assert_result(result, [[405,486,1,0]], [[405,486]], self.particle_e_recov,
			   recov_flag=True)
	result = self.parser.get_records(1)
	self.assert_result(result, [], [], self.particle_f_recov, recov_flag=True)

	# make sure there are no more records
	result = self.parser.get_records(1)
	self.assertEqual(result, [])

	# make sure there were no exceptions
	self.assertEqual(self.exception_callback_value, None)

	self.stream_handle.close()

    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 9400}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.build_telem_parser(state)

        result = self.parser.get_records(3)
        self.stream_handle.close()
        self.assertEqual(result,
                         [self.particle_a, self.particle_b, self.particle_c])
        # 0-69, 944-1000 are incomplete samples
        self.assert_state([],
                        [[0,69],[944,1000]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_get_many_recov(self):
        """
        Read recovered test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'FLO_short.DAT'))
        self.build_recov_parser()

        # get all 6 records
        result = self.parser.get_records(6)
        # compare returned particles
        self.assertEqual(result,
                         [self.particle_a_recov,
                          self.particle_b_recov,
                          self.particle_c_recov,
                          self.particle_d_recov,
                          self.particle_e_recov,
                          self.particle_f_recov])
        # no more in process or unprocessed data
        self.assert_state([], [], recov_flag=True)
        # compare particles in published callback
        self.assertEqual(self.publish_callback_value[0], self.particle_a_recov)
        self.assertEqual(self.publish_callback_value[1], self.particle_b_recov)
        self.assertEqual(self.publish_callback_value[2], self.particle_c_recov)
        self.assertEqual(self.publish_callback_value[3], self.particle_d_recov)
        self.assertEqual(self.publish_callback_value[4], self.particle_e_recov)
        self.assertEqual(self.publish_callback_value[5], self.particle_f_recov)

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_dash(self):
        """
        Test that the particle with a field replaced by dashes is found
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_dash.dat'))
        self.build_telem_parser()

        result = self.parser.get_records(1)
        self.assert_result(result,
                           [[313,389,1,0]],
                           [[0,69],[313,499]], self.particle_a_dash)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69],[389,499]], self.particle_b)

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream(self):
        data_len = os.path.getsize(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        state = {StateKey.UNPROCESSED_DATA:[[0, data_len]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: data_len}
        self.build_telem_parser(state)

        result = self.parser.get_records(6)
        self.stream_handle.close()
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[4], self.particle_e)
        self.assertEqual(result[5], self.particle_f)
        # 0-69 contains an incomplete block (end of a sample)
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_state([],
            [[0, 69], [1329,1332],[2294,2363],[4092,4161],[4351,4927], [9020,9400]])
        self.assertEqual(self.publish_callback_value[4], self.particle_e)
        self.assertEqual(self.publish_callback_value[5], self.particle_f)

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream_recov(self):
        """
        test that a longer file can be read and compare the end particles
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'FLO15908.DAT'))
        self.build_recov_parser()

        result = self.parser.get_records(96)
        # compare returned particles at the start of the file
        self.assertEqual(result[0], self.particle_a_recov)
        self.assertEqual(result[1], self.particle_b_recov)
        self.assertEqual(result[2], self.particle_c_recov)
        # compare returned particles at the end of the file
        self.assertEqual(result[-2], self.particle_long_before_last)
        self.assertEqual(result[-1], self.particle_long_last)
        # no more in process and unprocessed state
        self.assert_state([],[], recov_flag=True)
        # compare particles in published callback
        self.assertEqual(self.publish_callback_value[0], self.particle_a_recov)
        self.assertEqual(self.publish_callback_value[1], self.particle_b_recov)
        self.assertEqual(self.publish_callback_value[2], self.particle_c_recov)
        self.assertEqual(self.publish_callback_value[-2], self.particle_long_before_last)
        self.assertEqual(self.publish_callback_value[-1], self.particle_long_last)

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0,69], [197,1000]],
            StateKey.FILE_SIZE: 9400}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.build_telem_parser(new_state)

        # 0-69, 944-1000 are incomplete samples
        result = self.parser.get_records(1)
        self.assert_result(result, [[561,637,1,0]],
                           [[0,69],[561,637],[944,1000]],
                           self.particle_b)
        result = self.parser.get_records(1)
        # 0-69, 944-1000 are incomplete samples
        self.assert_result(result, [],
                           [[0,69],[944,1000]],
                           self.particle_c)

        self.stream_handle.close()

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {StateKey.IN_PROCESS_DATA:[[314,390,1,0], [561,637,1,0]],
            StateKey.UNPROCESSED_DATA:[[0,69],[314,390],[561,637],[944,6150]],
            StateKey.FILE_SIZE: 9400}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.build_telem_parser(new_state)
        result = self.parser.get_records(1)

        self.assert_result(result, [[561,637,1,0]],
                           [[0,69],[561,637],[944,6150]],
                           self.particle_b)

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_c)
        self.assertEqual(result[1], self.particle_d)
        # 0-69, 6131-6150 contains an incomplete block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_state([],
            [[0,69],[1329,1332],[2294,2363],[4092,4161],[4351,4927], [6131,6150]])
        self.assertEqual(self.publish_callback_value[-1], self.particle_d)

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start_recov(self):
        """
        test starting a parser with a state in the middle of processing
        """
        # start after having read the first 3 particles, so we expect d to be next
        new_state = {StateKey.IN_PROCESS_DATA:[[243,324,1,0], [324,405,1,0], [405,486,1,0]],
            StateKey.UNPROCESSED_DATA:[[243,486]],
            StateKey.FILE_SIZE: 486}
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'FLO_short.DAT'))
        self.build_recov_parser(new_state)

        result = self.parser.get_records(1)
        # ensure we get the correct particle
        self.assert_result(result,[[324,405,1,0], [405,486,1,0]], [[324,486]],
            self.particle_d_recov, recov_flag=True)

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state(self):
        """
        test changing the state after initializing
        """
        start_state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 9400}
        new_state = {StateKey.UNPROCESSED_DATA:[[0,69],[944,6150]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 9400}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.build_telem_parser(start_state)

        # there should only be 3 records, make sure we stop there
        result = self.parser.get_records(3)
        self.assert_state([],
            [[0,69],[944,1000]])
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.stream_handle.close()
        # 0-69, 6131-6150 contains an incomplete block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [],
                           [[0,69], [1329,1332],[2294,2363],[4092,4161],[4351,4927], [6131,6150]],
                           self.particle_d)

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state_recov(self):
        """
        test changing the state for a recovered parser after initializing
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH, 'FLO_short.DAT'))
        self.build_recov_parser()

        result = self.parser.get_records(2)
        # confirm the state after reading 2 particles
        self.assert_state([[162,243,1,0], [243,324,1,0], [324,405,1,0], [405,486,1,0]],
                           [[162,486]], recov_flag=True)

        # pretend we have skipped the middle 2 particles, set the state to start so we will
        # just read the last two
        new_state = {StateKey.UNPROCESSED_DATA:[[324,486]],
            StateKey.IN_PROCESS_DATA:[[324,405,1,0], [405,486,1,0]],
            StateKey.FILE_SIZE: 486}
        self.parser.set_state(new_state)

        result = self.parser.get_records(2)
        # assert that the last 2 particles are the ones we read
        self.assertEqual(result, [self.particle_e_recov, self.particle_f_recov])
        # assert the state shows no more in process and unprocessed data
        self.assert_state([],[], recov_flag=True)
        self.assertEqual(self.publish_callback_value[-2], self.particle_e_recov)
        self.assertEqual(self.publish_callback_value[-1], self.particle_f_recov)

        # ensure there are no more particles
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)

        self.stream_handle.close()

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        state = {StateKey.UNPROCESSED_DATA:[[0, 6150]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 9400}
        # this file has a block of FL data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replaced.dat'))
        self.build_telem_parser(state)


        result = self.parser.get_records(1)
        self.assert_result(result, [[561,637,1,0], [6053,6131,1,0]],
                           [[0,69],[314,390],[561,637],[1329,1332],[2294,2363],[4092,4161],[4351,4927],[6053,6150]],
                           self.particle_a)
        result = self.parser.get_records(1)
        # 0-69, 6131-6150 contains an incomplete block
        # 314-390 is the zeroed block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [[6053,6131,1,0]],
                           [[0,69],[314,390],[1329,1332],[2294,2363],[4092,4161],[4351,4927],[6053,6150]],
                           self.particle_c)
        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.build_telem_parser(next_state)

        # first get the old 'in process' records from 6053-6131
        # Once those are done, the un processed data will be checked
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,69], [314,390], [1329,1332],[2294,2363],[4092,4161],[4351,4927],[6131,6150]],
                           self.particle_d)

        # this should be the first of the newly filled in particles from 314-390
        result = self.parser.get_records(1)
        # 0-69, 6131-6150 contains an incomplete block
        # 1329-1332 there are 3 extra \n's between sio blocks
        # 2294-2363, and 4092-4161 contains an error text string in between two sio blocks
        # 4351-4927 has a bad AD then CT message where the size from the header does not line up with
        # the final \x03
        self.assert_result(result, [],
                           [[0,69], [1329,1332],[2294,2363],[4092,4161],[4351,4927],[6131,6150]],
                           self.particle_b)
        self.stream_handle.close()

        # make sure there were no exceptions
        self.assertEqual(self.exception_callback_value, None)
