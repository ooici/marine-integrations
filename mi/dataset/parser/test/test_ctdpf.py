#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_ctdpf Base dataset parser test code
@file mi/dataset/parser/test/test_ctdpf.py
@author Steve Foley
@brief Test code for a CTDPF data parser. There may be different flavors which
would lead to different subclasses of the test suites
"""

import gevent
from StringIO import StringIO
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.ctdpf import CtdpfParser, CtdpfParserDataParticle, StateKey

# Add a mixin here if needed

@attr('UNIT', group='mi')
class CtdpfParserUnitTestCase(ParserUnitTestCase):
    """
    CTDPF Parser unit test suite
    """
    TEST_DATA = """
* Sea-Bird SBE52 MP Data File *

*** Starting profile number 42 ***
10/01/2011 03:16:01
GPS1:
GPS2:
 42.2095, 13.4344,  143.63,   2830.2
 42.2102, 13.4346,  143.63,   2831.1
 42.2105, 13.4352,  143.63,   2830.6
 42.2110, 13.4350,  143.62,   2831.5
"""

    MID_TIMESTAMP_DATA = """
* Sea-Bird SBE52 MP Data File *

*** Starting profile number 42 ***
10/01/2011 03:16:01
GPS1:
GPS2:
 42.2095, 13.4344,  143.63,   2830.2
10/01/2011 03:17:01
 42.2102, 13.4346,  143.63,   2831.1
"""

    LONG_DATA = """
* Sea-Bird SBE52 MP Data File *

*** Starting profile number 42 ***
10/01/2011 03:16:01
GPS1:
GPS2:
 01.2095, 13.4344,  143.63,   2830.2
 02.2102, 13.4346,  143.63,   2831.1
 03.2105, 13.4352,  143.63,   2830.6
 04.2110, 13.4350,  143.62,   2831.5
 05.2095, 13.4344,  143.63,   2830.2
 06.2102, 13.4346,  143.63,   2831.1
 07.2105, 13.4352,  143.63,   2830.6
 08.2110, 13.4350,  143.62,   2831.5
 09.2095, 13.4344,  143.63,   2830.2
 10.2102, 13.4346,  143.63,   2831.1
 11.2105, 13.4352,  143.63,   2830.6
 12.2110, 13.4350,  143.62,   2831.5
 13.2095, 13.4344,  143.63,   2830.2
 14.2102, 13.4346,  143.63,   2831.1
 15.2105, 13.4352,  143.63,   2830.6
 16.2110, 13.4350,  143.62,   2831.5
 17.2095, 13.4344,  143.63,   2830.2
 18.2102, 13.4346,  143.63,   2831.1
 19.2105, 13.4352,  143.63,   2830.6
 20.2110, 13.4350,  143.62,   2831.5
 21.2095, 13.4344,  143.63,   2830.2
 22.2102, 13.4346,  143.63,   2831.1
 23.2105, 13.4352,  143.63,   2830.6
 24.2110, 13.4350,  143.62,   2831.5
 25.2095, 13.4344,  143.63,   2830.2
 26.2102, 13.4346,  143.63,   2831.1
 27.2105, 13.4352,  143.63,   2830.6
 28.2110, 13.4350,  143.62,   2831.5
 29.2095, 13.4344,  143.63,   2830.2
 30.2102, 13.4346,  143.63,   2831.1
 31.2105, 13.4352,  143.63,   2830.6
 32.2110, 13.4350,  143.62,   2831.5
 33.2095, 13.4344,  143.63,   2830.2
 34.2102, 13.4346,  143.63,   2831.1
 35.2105, 13.4352,  143.63,   2830.6
 36.2110, 13.4350,  143.62,   2831.5
 37.2095, 13.4344,  143.63,   2830.2
 38.2102, 13.4346,  143.63,   2831.1
 39.2105, 13.4352,  143.63,   2830.6
 40.2110, 13.4350,  143.62,   2831.5
 41.2095, 13.4344,  143.63,   2830.2
 42.2102, 13.4346,  143.63,   2831.1
 43.2105, 13.4352,  143.63,   2830.6
 11.1111, 22.2222,  333.33,   4444.4
"""
    BAD_TEST_DATA = """
* Sea-Bird SBE52 MP Data File *

*** Starting profile number 42 ***
10/01/2011 03:16:01
GPS1:
GPS2:
 42.2095, 13.4344,  143.63,   2830.2
 42.2102, 13.4346  143.63,   2831.1
 42.2105, 13.42,  143.63,   2830.6
 42.2110, 13.4350,  143.62,   2831.5
"""

    NO_TIME_TEST_DATA = """
* Sea-Bird SBE52 MP Data File *

*** Starting profile number 42 ***
GPS1:
GPS2:
 42.2095, 13.4344,  143.63,   2830.2
 42.2102, 13.4346,  143.63,   2831.1
 42.2105, 13.4252,  143.63,   2830.6
 42.2110, 13.4350,  143.62,   2831.5
"""
    def pos_callback(self, pos):
        """ Call back method to watch what comes in via the position callback """
        self.position_callback_value = pos

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub
    
    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpf',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'CtdpfParserDataParticle'
            }
        
        # not a DataSourceLocation...its just the parser
        self.position = {StateKey.POSITION:0, StateKey.TIMESTAMP:0.0}
        
        # Gonna need the test cases to make some of these
        # self.stream_handle = StringIO(TEST_DATA)        
        # self.parser = CtdpfParser(config, self.position, self.stream_handle) # last one is the link to the data source
        self.base_timestamp = 3526452961.0
        self.particle_a = CtdpfParserDataParticle(" 42.2095, 13.4344,  143.63,   2830.2",
                                                  internal_timestamp=self.base_timestamp)
        self.particle_b = CtdpfParserDataParticle(" 42.2102, 13.4346,  143.63,   2831.1",
                                                  internal_timestamp=self.base_timestamp+1)
        self.particle_c = CtdpfParserDataParticle(" 42.2105, 13.4352,  143.63,   2830.6",
                                                  internal_timestamp=self.base_timestamp+2)
        self.particle_d = CtdpfParserDataParticle(" 42.2110, 13.4350,  143.62,   2831.5",
                                                  internal_timestamp=self.base_timestamp+3)
        self.particle_e = CtdpfParserDataParticle(" 42.2102, 13.4346,  143.63,   2831.1",
                                                  internal_timestamp=self.base_timestamp+60)
        self.particle_z = CtdpfParserDataParticle(" 11.1111, 22.2222,  333.33,   4444.4",
                                                  internal_timestamp=self.base_timestamp+43)

        self.position_callback_value = None
        self.publish_callback_value = None

    def assert_result(self, result, position, timestamp, particle):
        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], position)
        self.assertEqual(self.position_callback_value[StateKey.TIMESTAMP], timestamp)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)
        
    def test_happy_path(self):
        """
        Test the happy path of operations where the parser takes the input
        and spits out a valid data particle given the stream.
        """
        self.stream_handle = StringIO(CtdpfParserUnitTestCase.TEST_DATA)
        self.parser = CtdpfParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
        self.assert_result(result, 137, self.base_timestamp, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, 174, self.base_timestamp+1, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 211, self.base_timestamp+2, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 248, self.base_timestamp+3, self.particle_d)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 248)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 248)
        self.assertEqual(self.position_callback_value[StateKey.TIMESTAMP],
                         self.base_timestamp+3)
        self.assert_(isinstance(self.publish_callback_value, list))        
        self.assertEqual(self.publish_callback_value[0], self.particle_d)
        
    def test_get_many(self):
        self.stream_handle = StringIO(CtdpfParserUnitTestCase.TEST_DATA)
        self.parser = CtdpfParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(2)
        self.assertEqual(result, [self.particle_a, self.particle_b])
        self.assertEqual(self.parser._state[StateKey.POSITION], 174)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 174)
        self.assertEqual(self.position_callback_value[StateKey.TIMESTAMP],
                         self.base_timestamp+1)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
               
    def test_bad_data(self):
        """ There's a bad sample in the data! Ack! Skip it! """
        self.stream_handle = StringIO(CtdpfParserUnitTestCase.BAD_TEST_DATA)
        self.parser = CtdpfParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
        self.assert_result(result, 137, self.base_timestamp, self.particle_a)
        
    def test_no_timestamp(self):
        """ There's no timestamp in the data! Ack! """
        self.stream_handle = StringIO(CtdpfParserUnitTestCase.NO_TIME_TEST_DATA)
        self.parser = CtdpfParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        with self.assertRaises(SampleException):
            self.parser.get_records(1)

    def test_long_stream(self):
        self.stream_handle = StringIO(CtdpfParserUnitTestCase.LONG_DATA)
        self.parser = CtdpfParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(44)
        self.assertEqual(result[-1], self.particle_z)
        self.assertEqual(self.parser._state[StateKey.POSITION], 1728)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 1728)
        self.assertEqual(self.position_callback_value[StateKey.TIMESTAMP],
                         self.base_timestamp+43)
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)

    def test_mid_state_start(self):
        new_state = {StateKey.POSITION:211, StateKey.TIMESTAMP:self.base_timestamp+2}
        self.stream_handle = StringIO(CtdpfParserUnitTestCase.TEST_DATA)
        self.parser = CtdpfParser(self.config, new_state, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, 248, self.base_timestamp+3, self.particle_d)

    def test_set_state(self):
        new_state = {StateKey.POSITION:174, StateKey.TIMESTAMP:self.base_timestamp+1}
        self.stream_handle = StringIO(CtdpfParserUnitTestCase.TEST_DATA)
        self.parser = CtdpfParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, 137, self.base_timestamp, self.particle_a)

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 212, self.base_timestamp+2, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 249, self.base_timestamp+3, self.particle_d)
        
    def test_mid_timestamp(self):
        self.stream_handle = StringIO(CtdpfParserUnitTestCase.MID_TIMESTAMP_DATA)
        self.parser = CtdpfParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
        self.assert_result(result, 137, self.base_timestamp, self.particle_a)

        result = self.parser.get_records(1)
        self.assert_result(result, 194, self.base_timestamp+60, self.particle_e)
