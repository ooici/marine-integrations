#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_issmcnsm_flortd
@file marine-integrations/mi/dataset/parser/test/test_issmcnsm_flortd.py
@author Emily Hahn
@brief Test code for a Issmcnsm_flortd data parser
"""

from nose.plugins.attrib import attr
from StringIO import StringIO
from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.issmcnsm_flortd import Issmcnsm_flortdParser, Issmcnsm_flortdParserDataParticle, StateKey

@attr('UNIT', group='mi')
class Issmcnsm_flortdParserUnitTestCase(ParserUnitTestCase):
    """
    Issmcnsm_flortd Parser unit test suite
    """
    TEST_DATA = """
2013/11/07 23:10:07.941 [flort:DLOGP2]:Instrument Started [Power On]
2013/11/07 23:10:43.394 [flort:DLOGP2]:mvs 1\r
2013/11/07 23:10:45.004 03/06/13\t23:08:51\t700\t4130\t695\t928\t460\t4130\t540\r
2013/11/07 23:10:46.136 03/06/13\t23:08:52\t700\t4130\t695\t929\t460\t4130\t540\r
2013/11/07 23:10:47.269 03/06/13\t23:08:53\t700\t4130\t695\t926\t460\t4130\t539\r
2013/11/07 23:10:48.401 03/06/13\t23:08:55\t700\t4130\t695\t927\t460\t4130\t539\r
"""

    BAD_TEST_DATA = """
2013/11/07 23:10:07.941 [flort:DLOGP2]:Instrument Started [Power On]
2013/11/07 23:10:43.394 [flort:DLOGP2]:mvs 1\r
2013/11/07 23:10:45.004 03/06/13\t23:08:51\t700\t4130\t695\t928\t460\t4130\t540\r
2013/11/07 23:10:46.136 03/06/13\t23:08:2\t80\t4130\t30\t929\t460\t4130\t540\r
2013/11/07 23:10:47.269 03/06/13\t23:08:53\t700\t4130\t695\t926\t460\t4130\t539\r
2013/11/07 23:10:48.401 03/06/13\t23:08:55\t700\t4130\t695\t927\t460\t4130\t539\r
"""

    NO_TIMESTAMP_TEST_DATA = """
2013/11/07 23:10:07.941 [flort:DLOGP2]:Instrument Started [Power On]
2013/11/07 23:10:43.394 [flort:DLOGP2]:mvs 1\r
2013/11/07 23:10:45.004 03/06/13\t23:08:51\t700\t4130\t695\t928\t460\t4130\t540\r
03/06/13\t23:08:52\t700\t4130\t300\t929\t460\t4130\t540\r
2013/11/07 23:10:47.269 03/06/13\t23:08:53\t700\t4130\t695\t926\t460\t4130\t539\r
2013/11/07 23:10:48.401 03/06/13\t23:08:55\t700\t4130\t695\t927\t460\t4130\t539\r
"""

    LONG_TEST_DATA = """
2013/11/07 23:05:07.973 [flort:DLOGP2]:Instrument Started [Power On]
2013/11/07 23:10:07.941 [flort:DLOGP2]:Instrument Started [Power On]
2013/11/07 23:10:43.394 [flort:DLOGP2]:mvs 1\r
2013/11/07 23:10:45.004 03/06/13\t23:08:51\t700\t4130\t695\t928\t460\t4130\t540\r
2013/11/07 23:10:46.136 03/06/13\t23:08:52\t700\t4130\t695\t929\t460\t4130\t540\r
2013/11/07 23:10:47.269 03/06/13\t23:08:53\t700\t4130\t695\t926\t460\t4130\t539\r
2013/11/07 23:10:48.401 03/06/13\t23:08:55\t700\t4130\t695\t927\t460\t4130\t539\r
2013/11/07 23:10:49.535 03/06/13\t23:08:56\t700\t4130\t695\t925\t460\t4130\t539\r
2013/11/07 23:10:50.667 03/06/13\t23:08:57\t700\t4130\t695\t927\t460\t4130\t539\r
2013/11/07 23:10:51.811 03/06/13\t23:08:58\t700\t4130\t695\t926\t460\t4130\t539\r
2013/11/07 23:10:52.931 03/06/13\t23:08:59\t700\t4130\t695\t926\t460\t4130\t539\r
2013/11/07 23:10:54.063 03/06/13\t23:09:00\t700\t4130\t695\t928\t460\t4130\t539\r
2013/11/07 23:10:55.196 03/06/13\t23:09:01\t700\t4130\t695\t926\t460\t4130\t539\r
2013/11/07 23:10:56.328 03/06/13\t23:09:02\t700\t4130\t695\t927\t460\t4130\t539\r
2013/11/07 23:10:57.460 03/06/13\t23:09:04\t700\t4130\t695\t928\t460\t4130\t538\r
2013/11/07 23:10:58.593 03/06/13\t23:09:05\t700\t4130\t695\t926\t460\t4130\t538\r
2013/11/07 23:10:59.725 03/06/13\t23:09:06\t700\t4130\t695\t925\t460\t4130\t539\r
2013/11/07 23:11:00.857 03/06/13\t23:09:07\t700\t4130\t695\t927\t460\t4130\t538\r
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
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.issmcnsm_flortd',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'Issmcnsm_flortdParserDataParticle'
	    }
	self.start_state = {StateKey.POSITION:0, StateKey.TIMESTAMP:0.0}
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
	self.timestamp1 = 3592854645.0039997
        self.particle_a = Issmcnsm_flortdParserDataParticle(
	    "2013/11/07 23:10:45.004 03/06/13\t23:08:51\t700\t4130\t695\t928\t460\t4130\t540\r",
            internal_timestamp=self.timestamp1)
	self.timestamp2 = 3592854646.136
        self.particle_b = Issmcnsm_flortdParserDataParticle(
	    "2013/11/07 23:10:46.136 03/06/13\t23:08:52\t700\t4130\t695\t929\t460\t4130\t540\r",
            internal_timestamp=self.timestamp2)
	self.timestamp3 = 3592854647.269
        self.particle_c = Issmcnsm_flortdParserDataParticle(
	    "2013/11/07 23:10:47.269 03/06/13\t23:08:53\t700\t4130\t695\t926\t460\t4130\t539\r",
            internal_timestamp=self.timestamp3)
	self.timestamp4 = 3592854648.401
        self.particle_d = Issmcnsm_flortdParserDataParticle(
	    "2013/11/07 23:10:48.401 03/06/13\t23:08:55\t700\t4130\t695\t927\t460\t4130\t539\r",
            internal_timestamp=self.timestamp4)

	self.timestamp_long = 3592854660.857
        self.particle_z = Issmcnsm_flortdParserDataParticle(
	    "2013/11/07 23:11:00.857 03/06/13\t23:09:07\t700\t4130\t695\t927\t460\t4130\t538\r",
            internal_timestamp=self.timestamp_long)

        self.state_callback_value = None
        self.publish_callback_value = None

    def assert_result(self, result, position, timestamp, particle):
        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)
	if self.state_callback_value[StateKey.TIMESTAMP] - timestamp > .0000001:
	    self.fail('Timestamp %s is not close enough to %s',
		      self.state_callback_value[StateKey.TIMESTAMP], timestamp)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
	Read test data and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
        self.stream_handle = StringIO(Issmcnsm_flortdParserUnitTestCase.TEST_DATA)
        self.parser = Issmcnsm_flortdParser(self.config, self.start_state, self.stream_handle,
					    self.state_callback, self.pub_callback)

	result = self.parser.get_records(1)
        self.assert_result(result, 188, self.timestamp1, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, 261, self.timestamp2, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 334, self.timestamp3, self.particle_c)
	result = self.parser.get_records(1)
        self.assert_result(result, 407, self.timestamp4, self.particle_d)

	# no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 407)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 407)
	if self.state_callback_value[StateKey.TIMESTAMP] - self.timestamp4 > .00001:
	    self.fail('Timestamp %s is not close enough to %s' %
		      (self.state_callback_value[StateKey.TIMESTAMP], self.timestamp4))
        self.assert_(isinstance(self.publish_callback_value, list))        
        self.assertEqual(self.publish_callback_value[0], self.particle_d)

    def test_get_many(self):
	"""
	Read test data and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
        self.stream_handle = StringIO(Issmcnsm_flortdParserUnitTestCase.TEST_DATA)
        self.parser = Issmcnsm_flortdParser(self.config, self.start_state, self.stream_handle,
					    self.state_callback, self.pub_callback)

        result = self.parser.get_records(3)
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c])
        self.assertEqual(self.parser._state[StateKey.POSITION], 334)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 334)
	if self.state_callback_value[StateKey.TIMESTAMP] - self.timestamp3 > .00001:
	    self.fail('Timestamp %s is not close enough to %s' %
		      (self.state_callback_value[StateKey.TIMESTAMP], self.timestamp3))
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
	self.assertEqual(self.publish_callback_value[2], self.particle_c)

    def test_long_stream(self):
	"""
	Test a long stream of data
	"""
	self.stream_handle = StringIO(Issmcnsm_flortdParserUnitTestCase.LONG_TEST_DATA)
        self.parser = Issmcnsm_flortdParser(self.config, self.start_state, self.stream_handle,
					    self.state_callback, self.pub_callback)
	result = self.parser.get_records(15)
	self.assertEqual(result[0], self.particle_a)
	self.assertEqual(result[-1], self.particle_z)
        self.assertEqual(self.parser._state[StateKey.POSITION], 1279)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 1279)
	if self.state_callback_value[StateKey.TIMESTAMP] - self.timestamp_long > .00001:
	    self.fail('Timestamp %s is not close enough to %s' %
		      (self.state_callback_value[StateKey.TIMESTAMP], self.timestamp_long))
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:261, StateKey.TIMESTAMP:self.timestamp2}
	self.stream_handle = StringIO(Issmcnsm_flortdParserUnitTestCase.TEST_DATA)
        self.parser = Issmcnsm_flortdParser(self.config, new_state, self.stream_handle,
					    self.state_callback, self.pub_callback)
	result = self.parser.get_records(1)
        self.assert_result(result, 334, self.timestamp3, self.particle_c)
	result = self.parser.get_records(1)
        self.assert_result(result, 407, self.timestamp4, self.particle_d)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION:261, StateKey.TIMESTAMP:self.timestamp2}
	self.stream_handle = StringIO(Issmcnsm_flortdParserUnitTestCase.TEST_DATA)
        self.parser = Issmcnsm_flortdParser(self.config, self.start_state, self.stream_handle,
					    self.state_callback, self.pub_callback)
	result = self.parser.get_records(1)
	self.assert_result(result, 188, self.timestamp1, self.particle_a)

	self.parser.set_state(new_state)
        result = self.parser.get_records(1)
	self.assert_result(result, 334, self.timestamp3, self.particle_c)
	result = self.parser.get_records(1)
        self.assert_result(result, 407, self.timestamp4, self.particle_d)

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        self.stream_handle = StringIO(Issmcnsm_flortdParserUnitTestCase.BAD_TEST_DATA)
        self.parser = Issmcnsm_flortdParser(self.config, self.start_state, self.stream_handle,
					    self.state_callback, self.pub_callback)
	result = self.parser.get_records(1)
        self.assert_result(result, 188, self.timestamp1, self.particle_a)
	result = self.parser.get_records(1)
        self.assert_result(result, 331, self.timestamp3, self.particle_c)

    def test_no_timestamp(self):
	"""
	A sample is missing a timestamp, skip that sample
	"""
	self.stream_handle = StringIO(Issmcnsm_flortdParserUnitTestCase.NO_TIMESTAMP_TEST_DATA)
        self.parser = Issmcnsm_flortdParser(self.config, self.start_state, self.stream_handle,
					    self.state_callback, self.pub_callback)
	result = self.parser.get_records(1)
        self.assert_result(result, 188, self.timestamp1, self.particle_a)
	result = self.parser.get_records(1)
        self.assert_result(result, 310, self.timestamp3, self.particle_c)

