#!/usr/bin/env python

import gevent
import unittest
import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.mflm import StateKey
from mi.dataset.parser.flortd import FlortdParser, FlortdParserDataParticle
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

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
	ParserUnitTestCase.setUp(self)
	self.config = {
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flortd',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlortdParserDataParticle'
	    }

	# first FL tag
	self.timestamp1 = 3583610106.0
	self.particle_a = FlortdParserDataParticle(
	    '07/23/13	23:15:06	700	50	695	50	460	53	545',
              internal_timestamp=self.timestamp1, new_sequence=True)

	self.timestamp2 = 3583612806.0
	self.particle_b = FlortdParserDataParticle(
	    '07/24/13	00:00:06	700	85	695	50	460	51	548',
              internal_timestamp=self.timestamp2, new_sequence=False)
	self.particle_b_new = FlortdParserDataParticle(
	    '07/24/13	00:00:06	700	85	695	50	460	51	548',
              internal_timestamp=self.timestamp2, new_sequence=True)

	self.timestamp3 = 3583634405.0
	self.particle_c = FlortdParserDataParticle(
	    '07/24/13	06:00:05	700	78	695	72	460	51	553',
              internal_timestamp=self.timestamp3, new_sequence=False)
	self.particle_c_new = FlortdParserDataParticle(
	    '07/24/13	06:00:05	700	78	695	72	460	51	553',
              internal_timestamp=self.timestamp3, new_sequence=True)

	self.timestamp4 = 3583656006.0
	self.particle_d = FlortdParserDataParticle(
	    '07/24/13	12:00:06	700	169	695	127	460	58	553',
              internal_timestamp=self.timestamp4, new_sequence=True)

	self.timestamp5 = 3583677606.0
	self.particle_e = FlortdParserDataParticle(
	    '07/24/13	18:00:06	700	262	695	84	460	55	555',
              internal_timestamp=self.timestamp5, new_sequence=False)

	self.timestamp6 = 3583699206.0
	self.particle_f = FlortdParserDataParticle(
	    '07/25/13	00:00:06	700	159	695	95	460	59	554',
              internal_timestamp=self.timestamp6, new_sequence=False)

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
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP], timestamp)

    def test_simple(self):
	"""
	Read test data from the file and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
	self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
	# NOTE: using the unprocessed data state of 0,1000 limits the file to reading
	# just 1000 bytes, so even though the file is longer it only reads the first
	# 1000
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	self.parser = FlortdParser(self.config, self.state, self.stream_handle,
				  self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
	self.assert_result(result,
			   [[314,390,1,0,0], [561,637,1,0,0]],
			   [[0,69],[314,390],[561,637],[944,1000]], 
			   self.timestamp3, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[561,637,1,0,0]],
			   [[0,69],[561,637],[944,1000]],
			   self.timestamp3, self.particle_b)
	result = self.parser.get_records(1)
	self.assert_result(result, [],
			   [[0,69],[944,1000]], 
			   self.timestamp3, self.particle_c)

	self.stream_handle.close()

    def test_get_many(self):
	"""
	Read test data from the file and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 1000]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(3)
	self.stream_handle.close()
        self.assertEqual(result,
			 [self.particle_a, self.particle_b, self.particle_c])
	self.assert_state([],
			[[0,69],[944,1000]],
			self.timestamp3)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
	self.assertEqual(self.publish_callback_value[2], self.particle_c)

    def test_long_stream(self):
	self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
	data = self.stream_handle.read()
	data_len = len(data)
	self.stream_handle.seek(0)
	self.state = {StateKey.UNPROCESSED_DATA:[[0, data_len]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(6)
	self.stream_handle.close()
	self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
	self.assertEqual(result[2], self.particle_c)
	self.assertEqual(result[-3], self.particle_d)
	self.assertEqual(result[-2], self.particle_e)
	self.assertEqual(result[-1], self.particle_f)
	self.assert_state([],
	    [[0, 69], [944, 2370], [2560, 2947], [3137, 4173], [4363, 5437], [5683, 6072], [8273, 9400]],
	    self.timestamp6)
	self.assertEqual(self.publish_callback_value[-2], self.particle_e)
        self.assertEqual(self.publish_callback_value[-1], self.particle_f)

    def test_mid_state_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
        new_state = {StateKey.IN_PROCESS_DATA:[],
	    StateKey.UNPROCESSED_DATA:[[0,69], [197,1000]],
	    StateKey.TIMESTAMP:self.timestamp1}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, [[561,637,1,0,0]],
			   [[0,69],[561,637],[944,1000]],
			   self.timestamp3, self.particle_b_new)
	result = self.parser.get_records(1)
        self.assert_result(result, [],
			   [[0,69],[944,1000]],
			   self.timestamp3, self.particle_c)

	self.stream_handle.close()

    def test_in_process_start(self):
	"""
	test starting a parser with a state in the middle of processing
	"""
        new_state = {StateKey.IN_PROCESS_DATA:[[314,390,1,0,0], [561,637,1,0,0]],
	    StateKey.UNPROCESSED_DATA:[[0,69],[314,390],[561,637],[944,6150]],
	    StateKey.TIMESTAMP:self.timestamp3}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)

	# even though the state says this particle is not a new sequence, since it is the
	# first after setting the state it will be new
        self.assert_result(result, [[561,637,1,0,0]],
			   [[0,69],[561,637],[944,6150]],
			   self.timestamp2, self.particle_b_new)

	result = self.parser.get_records(2)
	self.assertEqual(result[0], self.particle_c)
	self.assertEqual(result[1], self.particle_d)
	self.assert_state([],
	    [[0,69],[944, 2370], [2560, 2947], [3137, 4173], [4363, 5437], [5683, 6072]],
	    self.timestamp4)
	self.assertEqual(self.publish_callback_value[-1], self.particle_d)

    def test_set_state(self):
	"""
	test changing the state after initializing
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 1000]], StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:0.0}
        new_state = {StateKey.UNPROCESSED_DATA:[[0,69],[944,6150]],
	    StateKey.IN_PROCESS_DATA:[],
	    StateKey.TIMESTAMP:self.timestamp2}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source
	# there should only be 3 records, make sure we stop there
        result = self.parser.get_records(3)
	self.assert_state([],
	    [[0,69],[944,1000]],
	    self.timestamp3)
	result = self.parser.get_records(1)
	self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
	self.stream_handle.close()
        self.assert_result(result, [],
			   [[0,69],[944, 2370], [2560, 2947], [3137, 4173], [4363, 5437], [5683, 6072]],
			   self.timestamp4, self.particle_d)

    def test_update(self):
	"""
	Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
	then using the returned state make a new parser with the test data that has the 0s filled in
	"""
	self.state = {StateKey.UNPROCESSED_DATA:[[0, 6150]],
	    StateKey.IN_PROCESS_DATA:[], StateKey.TIMESTAMP:0.0}
	# this file has a block of FL data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_replaced.dat'))
        self.parser = FlortdParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
	self.assert_result(result, [[561,637,1,0,1], [6072,6150,1,0,1]],
			   [[0,69],[314,390],[561,637],[944, 2370], [2560, 2947], [3137, 4173], [4363, 5437], [5683, 6150]],
			   self.timestamp4, self.particle_a)
	result = self.parser.get_records(1)
	self.assert_result(result, [[6072,6150,1,0,1]],
			   [[0,69], [314,390], [944, 2370], [2560, 2947], [3137, 4173], [4363, 5437], [5683, 6150]],
			   self.timestamp4, self.particle_c_new)
	self.stream_handle.close()

	next_state = self.parser._state
	# this file has the block of data that was missing in the previous file
	self.stream_handle = open(os.path.join(RESOURCE_PATH,
					       'node59p1_shorter.dat'))
	self.parser = FlortdParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) # last one is the link to the data source

	# first get the old 'in process' records
	# Once those are done, the un processed data will be checked
	result = self.parser.get_records(1)
	self.assert_result(result, [],
			   [[0,69], [314,390], [944, 2370], [2560, 2947], [3137, 4173], [4363, 5437], [5683, 6072]],
			   self.timestamp4, self.particle_d)

	# this should be the first of the newly filled in particles from
        result = self.parser.get_records(1)
        self.assert_result(result, [],
			   [[0,69], [944, 2370], [2560, 2947], [3137, 4173], [4363, 5437], [5683, 6072]],
			   self.timestamp2, self.particle_b_new)
	self.stream_handle.close()
