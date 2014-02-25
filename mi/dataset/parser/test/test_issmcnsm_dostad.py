#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_issmcnsm_dostad
@file marine-integrations/mi/dataset/parser/test/test_issmcnsm_dostad.py
@author Emily Hahn
@brief Test code for a Issmcnsm_dostad data parser
"""

from nose.plugins.attrib import attr
from StringIO import StringIO
from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.issmcnsm_dostad import Issmcnsm_dostadParser, Issmcnsm_dostadParserDataParticle, StateKey

@attr('UNIT', group='mi')
class Issmcnsm_dostadParserUnitTestCase(ParserUnitTestCase):
    """
    Issmcnsm_dostad Parser unit test suite
    """
    TEST_DATA = """
2013/10/12 00:00:14.878 [dosta:DLOGP4]:Instrument Started on second attempt [Power On]
2013/10/12 00:00:17.862 4831\t135\t323.144\t101.137\t14.337\t31.580\t31.580\t40.363\t8.783\t1079.2\t1070.5\t245.4\r
2013/10/12 00:00:19.861 4831\t135\t323.140\t101.135\t14.337\t31.581\t31.581\t40.362\t8.781\t1079.1\t1068.5\t245.4\r
2013/10/12 00:00:21.862 4831\t135\t323.141\t101.136\t14.337\t31.581\t31.581\t40.362\t8.781\t1078.9\t1067.3\t245.4\r
2013/10/12 00:00:23.862 4831\t135\t323.126\t101.131\t14.337\t31.581\t31.581\t40.363\t8.782\t1078.8\t1066.3\t245.4\r
"""

    BAD_TEST_DATA = """
2013/10/12 00:00:14.878 [dosta:DLOGP4]:Instrument Started on second attempt [Power On]
2013/10/12 00:00:17.862 4831\t135\t323.144\t101.137\t14.337\t31.580\t31.580\t40.363\t8.783\t1079.2\t1070.5\t245.4\r
2013/10/12 00:00:19.861 48\t135\t323.140\t101.135\t14.337\t31.581\t31.581\t40.362\t8.781\t\t1068.5\t245.4\r
2013/10/12 00:00:21.862 4831\t135\t323.141\t101.136\t14.337\t31.581\t31.581\t40.362\t8.781\t1078.9\t1067.3\t245.4\r
"""

    NO_TIMESTAMP_TEST_DATA = """
2013/10/12 00:00:14.878 [dosta:DLOGP4]:Instrument Started on second attempt [Power On]
2013/10/12 00:00:17.862 4831\t135\t323.144\t101.137\t14.337\t31.580\t31.580\t40.363\t8.783\t1079.2\t1070.5\t245.4\r
4831\t135\t323.140\t101.135\t14.337\t31.581\t31.581\t40.362\t8.781\t1079.1\t1068.5\t245.4\r
2013/10/12 00:00:21.862 4831\t135\t323.141\t101.136\t14.337\t31.581\t31.581\t40.362\t8.781\t1078.9\t1067.3\t245.4\r
"""

    LONG_TEST_DATA = """
2013/10/12 00:00:14.878 [dosta:DLOGP4]:Instrument Started on second attempt [Power On]
2013/10/12 00:00:17.862 4831\t135\t323.144\t101.137\t14.337\t31.580\t31.580\t40.363\t8.783\t1079.2\t1070.5\t245.4\r
2013/10/12 00:00:19.861 4831\t135\t323.140\t101.135\t14.337\t31.581\t31.581\t40.362\t8.781\t1079.1\t1068.5\t245.4\r
2013/10/12 00:00:21.862 4831\t135\t323.141\t101.136\t14.337\t31.581\t31.581\t40.362\t8.781\t1078.9\t1067.3\t245.4\r
2013/10/12 00:00:23.862 4831\t135\t323.126\t101.131\t14.337\t31.581\t31.581\t40.363\t8.782\t1078.8\t1066.3\t245.4\r
2013/10/12 00:00:25.862 4831\t135\t323.109\t101.126\t14.337\t31.582\t31.582\t40.363\t8.782\t1078.7\t1065.4\t245.3\r
2013/10/12 00:00:27.862 4831\t135\t323.082\t101.119\t14.338\t31.582\t31.582\t40.365\t8.782\t1078.6\t1064.5\t245.3\r
2013/10/12 00:00:29.862 4831\t135\t323.129\t101.134\t14.338\t31.581\t31.581\t40.364\t8.784\t1078.4\t1063.8\t245.3\r
2013/10/12 00:00:31.862 4831\t135\t323.105\t101.128\t14.339\t31.581\t31.581\t40.365\t8.784\t1078.3\t1063.2\t245.3\r
2013/10/12 00:00:33.862 4831\t135\t323.080\t101.122\t14.340\t31.582\t31.582\t40.367\t8.785\t1078.3\t1062.6\t245.3\r
2013/10/12 00:00:35.862 4831\t135\t323.017\t101.104\t14.340\t31.584\t31.584\t40.369\t8.786\t1078.2\t1061.9\t245.2\r
2013/10/12 00:00:37.862 4831\t135\t323.065\t101.121\t14.341\t31.581\t31.581\t40.369\t8.788\t1078.2\t1061.6\t245.2\r
2013/10/12 00:00:39.862 4831\t135\t323.070\t101.125\t14.342\t31.581\t31.581\t40.370\t8.789\t1078.1\t1061.0\t245.2\r
2013/10/12 00:00:41.862 4831\t135\t323.038\t101.118\t14.344\t31.581\t31.581\t40.370\t8.789\t1077.8\t1060.2\t245.1\r
2013/10/12 00:00:43.862 4831\t135\t322.991\t101.106\t14.345\t31.582\t31.582\t40.373\t8.791\t1077.8\t1059.5\t245.1\r
2013/10/12 00:00:45.863 4831\t135\t323.009\t101.115\t14.346\t31.581\t31.581\t40.373\t8.791\t1077.7\t1059.0\t245.0\r
2013/10/12 00:00:47.862 4831\t135\t322.874\t101.076\t14.348\t31.585\t31.585\t40.376\t8.791\t1077.5\t1058.5\t245.0\r
2013/10/12 00:00:49.862 4831\t135\t322.919\t101.093\t14.349\t31.583\t31.583\t40.377\t8.794\t1077.5\t1058.0\t245.0\r
2013/10/12 00:00:51.861 4831\t135\t322.889\t101.087\t14.351\t31.583\t31.583\t40.380\t8.796\t1077.4\t1057.4\t244.9\r
"""

    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
	ParserUnitTestCase.setUp(self)
	self.config = {
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.issmcnsm_dostad',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'Issmcnsm_dostadParserDataParticle'
	    }

	self.start_state = {StateKey.POSITION:0, StateKey.TIMESTAMP:0.0}
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
	self.timestamp1 = 3590524817.862
        self.particle_a = Issmcnsm_dostadParserDataParticle(
	    "2013/10/12 00:00:17.862 4831\t135\t323.144\t101.137\t14.337\t31.580\t31.580\t40.363\t8.783\t1079.2\t1070.5\t245.4\r",
            internal_timestamp=self.timestamp1)
	self.timestamp2 = 3590524819.861
	self.particle_b = Issmcnsm_dostadParserDataParticle(
	    "2013/10/12 00:00:19.861 4831\t135\t323.140\t101.135\t14.337\t31.581\t31.581\t40.362\t8.781\t1079.1\t1068.5\t245.4\r",
            internal_timestamp=self.timestamp2)
    	self.timestamp3 = 3590524821.862
	self.particle_c = Issmcnsm_dostadParserDataParticle(
	    "2013/10/12 00:00:21.862 4831\t135\t323.141\t101.136\t14.337\t31.581\t31.581\t40.362\t8.781\t1078.9\t1067.3\t245.4\r",
            internal_timestamp=self.timestamp3)
	self.timestamp4 = 3590524823.862
	self.particle_d = Issmcnsm_dostadParserDataParticle(
	    "2013/10/12 00:00:23.862 4831\t135\t323.126\t101.131\t14.337\t31.581\t31.581\t40.363\t8.782\t1078.8\t1066.3\t245.4\r",
            internal_timestamp=self.timestamp4)
	self.timestamp_last = 3590524851.861
	self.particle_z = Issmcnsm_dostadParserDataParticle(
	    "2013/10/12 00:00:51.861 4831\t135\t322.889\t101.087\t14.351\t31.583\t31.583\t40.380\t8.796\t1077.4\t1057.4\t244.9\r",
            internal_timestamp=self.timestamp_last)

        self.state_callback_value = None
        self.publish_callback_value = None

    def assert_result(self, result, position, timestamp, particle):
        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP], timestamp)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
	Read test data and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
        self.stream_handle = StringIO(Issmcnsm_dostadParserUnitTestCase.TEST_DATA)
        self.parser = Issmcnsm_dostadParser(self.config, self.start_state, self.stream_handle,
					    self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
        self.assert_result(result, 191, self.timestamp1, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, 295, self.timestamp2, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 399, self.timestamp3, self.particle_c)
	result = self.parser.get_records(1)
        self.assert_result(result, 503, self.timestamp4, self.particle_d)

	# no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 503)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 503)
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP],
                         self.timestamp4)
        self.assert_(isinstance(self.publish_callback_value, list))        
        self.assertEqual(self.publish_callback_value[0], self.particle_d)

    def test_get_many(self):
	"""
	Read test data and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
        self.stream_handle = StringIO(Issmcnsm_dostadParserUnitTestCase.TEST_DATA)
        self.parser = Issmcnsm_dostadParser(self.config, self.start_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) 

        result = self.parser.get_records(3)
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c])
        self.assertEqual(self.parser._state[StateKey.POSITION], 399)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 399)
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP],
                         self.timestamp3)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
	self.assertEqual(self.publish_callback_value[2], self.particle_c)

    def test_bad_data(self):
	"""
	There is a bad sample, make sure we skip it and read the next sample
	"""
	self.stream_handle = StringIO(Issmcnsm_dostadParserUnitTestCase.BAD_TEST_DATA)
        self.parser = Issmcnsm_dostadParser(self.config, self.start_state, self.stream_handle,
                                  self.state_callback, self.pub_callback)
	result = self.parser.get_records(1)
	self.assert_result(result, 191, self.timestamp1, self.particle_a)
	result = self.parser.get_records(1)
        self.assert_result(result, 391, self.timestamp3, self.particle_c)

    def test_no_timestamp(self):
	"""
	A sample is missing a timestamp, skip that sample
	"""
	self.stream_handle = StringIO(Issmcnsm_dostadParserUnitTestCase.NO_TIMESTAMP_TEST_DATA)
        self.parser = Issmcnsm_dostadParser(self.config, self.start_state, self.stream_handle,
                                  self.state_callback, self.pub_callback)
	result = self.parser.get_records(1)
	self.assert_result(result, 191, self.timestamp1, self.particle_a)
	result = self.parser.get_records(1)
        self.assert_result(result, 375, self.timestamp3, self.particle_c)

    def test_long_stream(self):
	"""
	Test a long stream of data
	"""
	self.stream_handle = StringIO(Issmcnsm_dostadParserUnitTestCase.LONG_TEST_DATA)
        self.parser = Issmcnsm_dostadParser(self.config, self.start_state, self.stream_handle,
                                  self.state_callback, self.pub_callback) 

        result = self.parser.get_records(18)
	self.assertEqual(result[-1], self.particle_z)
        self.assertEqual(self.parser._state[StateKey.POSITION], 1959)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 1959)
        self.assertEqual(self.state_callback_value[StateKey.TIMESTAMP],
                         self.timestamp_last)
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:294, StateKey.TIMESTAMP:self.timestamp2}
	self.stream_handle = StringIO(Issmcnsm_dostadParserUnitTestCase.TEST_DATA)
        self.parser = Issmcnsm_dostadParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback)
	result = self.parser.get_records(1)
        self.assert_result(result, 399, self.timestamp3, self.particle_c)
	result = self.parser.get_records(1)
        self.assert_result(result, 503, self.timestamp4, self.particle_d)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION:295, StateKey.TIMESTAMP:self.timestamp2}
	self.stream_handle = StringIO(Issmcnsm_dostadParserUnitTestCase.TEST_DATA)
        self.parser = Issmcnsm_dostadParser(self.config, self.start_state, self.stream_handle,
                                  self.state_callback, self.pub_callback)
	result = self.parser.get_records(1)
	self.assert_result(result, 191, self.timestamp1, self.particle_a)

	self.parser.set_state(new_state)
        result = self.parser.get_records(1)
	self.assert_result(result, 399, self.timestamp3, self.particle_c)
	result = self.parser.get_records(1)
        self.assert_result(result, 503, self.timestamp4, self.particle_d)
