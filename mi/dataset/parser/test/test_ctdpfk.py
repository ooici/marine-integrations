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
from mi.dataset.parser.ctdpfk import CtdpfkParser, CtdpfkParserDataParticle, StateKey

# Add a mixin here if needed

@attr('UNIT', group='mi')
class CtdpfkParserUnitTestCase(ParserUnitTestCase):
    """
    CTDPFK Parser unit test suite
    """
    TEST_DATA = """
  CTD turned on at 04/16/2013 01:00:02
  CTD turned off at 04/16/2013 01:05:16
 Profile 181

mmho/cm,Celsius,dbars,hz

1.5370,16.3184,12.630, 3122
1.5370,16.3174,12.640, 3127
1.5371,16.3170,12.640, 3132
1.5371,16.3171,12.640, 3137

 Profile 181
"""

    LONG_DATA = """
  CTD turned on at 04/16/2013 01:00:02
  CTD turned off at 04/16/2013 01:05:16

 Profile 181

mmho/cm,Celsius,dbars,hz

1.5370,16.3184,12.630, 3122
1.5370,16.3174,12.640, 3127
1.5371,16.3170,12.640, 3132
1.5371,16.3171,12.640, 3137
1.5371,16.3169,12.640, 3141
1.5371,16.3160,12.640, 3146
1.5372,16.3160,12.640, 3151
1.5372,16.3152,12.640, 3157
1.5372,16.3145,12.640, 3161
1.5372,16.3143,12.640, 3165
1.5372,16.3139,12.640, 3170
1.5373,16.3139,12.640, 3175
1.5373,16.3132,12.640, 3180
1.5373,16.3132,12.640, 3184
1.5373,16.3125,12.640, 3187
1.5373,16.3121,12.640, 3192
1.5373,16.3127,12.640, 3196
1.5373,16.3118,12.630, 3200
1.5374,16.3117,12.640, 3205
1.5374,16.3108,12.640, 3209
1.5374,16.3111,12.630, 3213
1.5374,16.3102,12.630, 3217
1.5374,16.3106,12.640, 3221
1.5375,16.3095,12.640, 3226
1.5374,16.3096,12.640, 3229
1.5375,16.3097,12.640, 3234
1.5375,16.3092,12.640, 3237
1.5375,16.3086,12.640, 3242
1.5375,16.3079,12.640, 3246
1.5376,16.3081,12.640, 3249
1.5376,16.3081,12.640, 3253
1.5376,16.3077,12.640, 3256
1.5376,16.3072,12.640, 3260
1.5376,16.3069,12.640, 3264
1.5376,16.3072,12.640, 3268
1.5376,16.3059,12.640, 3272
1.5376,16.3067,12.640, 3275
1.5377,16.3063,12.640, 3279
1.5377,16.3057,12.640, 3282
1.5377,16.3058,12.640, 3286
1.5377,16.3053,12.640, 3289
1.5377,16.3052,12.640, 3294
1.5377,16.3045,12.640, 3297
1.5371,16.3160,12.640, 3146

 Profile 181
"""
    LEFTOVER = """
1.5377,16.3051,12.640, 3303
1.5377,16.3042,12.640, 3307
1.5377,16.3041,12.640, 3310
1.5377,16.3034,12.640, 3313
1.5377,16.3039,12.640, 3317
1.5377,16.3038,12.640, 3319
1.5377,16.3036,12.640, 3322
1.5378,16.3030,12.640, 3326
1.5378,16.3030,12.640, 3329
1.5378,16.3028,12.640, 3332
1.5378,16.3029,12.640, 3336
1.5378,16.3026,12.640, 3340
1.5378,16.3020,12.640, 3343
1.5379,16.3026,12.640, 3345
1.5379,16.3018,12.640, 3349
1.5378,16.3017,12.640, 3352
1.5378,16.3017,12.640, 3355
1.5379,16.3010,12.640, 3358
1.5378,16.3016,12.640, 3361
1.5379,16.3006,12.640, 3363
1.5379,16.3009,12.640, 3367
1.5378,16.3009,12.640, 3369
1.5378,16.3008,12.640, 3372
1.5379,16.3006,12.640, 3374
1.5379,16.3005,12.640, 3377
1.5379,16.3002,12.640, 3379
1.5379,16.3007,12.640, 3382
1.5379,16.2999,12.640, 3383
1.5379,16.2998,12.640, 3385
1.5379,16.2995,12.630, 3388
1.5379,16.3002,12.640, 3391
1.5371,16.3160,12.640, 3146
"""

    BAD_TEST_DATA = """
  CTD turned on at 04/16/2013 01:00:02
  CTD turnfed off at 04/16/2013 01:05:16
 Profile 181

mmho/cm,Celsius,dbars,hz


1.5283,1f6.3574,0.970, 2739
1.5283,16.3596,x0.970, 2745
1.5370,16.3184,12.630, 3122
1.5282,16.3604,0.970, 2f752

 Profiled 181.3
"""

    NO_TIME_TEST_DATA = """
 Profile 181

mmho/cm,Celsius,dbars,hz

1.5282,16.3541,0.970, 2724
1.5283,16.3574,0.970, 2739
1.5283,16.3596,0.970, 2745
1.5283,16.3603,0.970, 2749
1.5282,16.3604,0.970, 2752
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
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpfk',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'CtdpfkParserDataParticle'
            }

        # not a DataSourceLocation...its just the parser
        self.position = {StateKey.POSITION:0, StateKey.TIMESTAMP:0.0}

        # Gonna need the test cases to make some of these
        # self.stream_handle = StringIO(TEST_DATA)        
        # self.parser = CtdpfParser(config, self.position, self.stream_handle) # last one is the link to the data source
        self.base_timestamp = 3575062802.0
        self.particle_a = CtdpfkParserDataParticle("1.5370,16.3184,12.630, 3122",
                                                  internal_timestamp=self.base_timestamp)
        self.particle_b = CtdpfkParserDataParticle("1.5370,16.3174,12.640, 3127",
                                                  internal_timestamp=self.base_timestamp+1)
        self.particle_c = CtdpfkParserDataParticle("1.5371,16.3170,12.640, 3132",
                                                  internal_timestamp=self.base_timestamp+2)
        self.particle_d = CtdpfkParserDataParticle("1.5371,16.3171,12.640, 3137",
                                                  internal_timestamp=self.base_timestamp+3)
        self.particle_e = CtdpfkParserDataParticle("1.5371,16.3169,12.640, 3141",
                                                  internal_timestamp=self.base_timestamp+60)
        self.particle_z = CtdpfkParserDataParticle("1.5371,16.3160,12.640, 3146",
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
        self.stream_handle = StringIO(CtdpfkParserUnitTestCase.TEST_DATA)
        self.parser = CtdpfkParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)

        self.assert_result(result, 147, self.base_timestamp, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, 175, self.base_timestamp+1, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 203, self.base_timestamp+2, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 231, self.base_timestamp+3, self.particle_d)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 231)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 231)
        self.assertEqual(self.position_callback_value[StateKey.TIMESTAMP],
                         self.base_timestamp+3)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_d)

    def test_get_many(self):
        self.stream_handle = StringIO(CtdpfkParserUnitTestCase.TEST_DATA)
        self.parser = CtdpfkParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(2)
        self.assertEqual(result, [self.particle_a, self.particle_b])
        self.assertEqual(self.parser._state[StateKey.POSITION], 175)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 175)
        self.assertEqual(self.position_callback_value[StateKey.TIMESTAMP],
                         self.base_timestamp+1)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)

    def test_bad_data(self):
        """ There's a bad sample in the data! Ack! Skip it! """
        self.stream_handle = StringIO(CtdpfkParserUnitTestCase.BAD_TEST_DATA)
        self.parser = CtdpfkParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
        self.assert_result(result, 205, self.base_timestamp, self.particle_a)

    def test_no_timestamp(self):
        """ There's no timestamp in the data! Ack! """
        self.stream_handle = StringIO(CtdpfkParserUnitTestCase.NO_TIME_TEST_DATA)
        self.parser = CtdpfkParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        with self.assertRaises(SampleException):
            self.parser.get_records(1)

    def test_long_stream(self):
        self.stream_handle = StringIO(CtdpfkParserUnitTestCase.LONG_DATA)
        self.parser = CtdpfkParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(44)
        self.assertEqual(result[-1], self.particle_z)
        self.assertEqual(self.parser._state[StateKey.POSITION], 1352)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 1352)
        self.assertEqual(self.position_callback_value[StateKey.TIMESTAMP],
                         self.base_timestamp+43)
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)

    def test_mid_state_start(self):
        new_state = {StateKey.POSITION:203, StateKey.TIMESTAMP:self.base_timestamp+2}
        self.stream_handle = StringIO(CtdpfkParserUnitTestCase.TEST_DATA)
        self.parser = CtdpfkParser(self.config, new_state, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, 231, self.base_timestamp+3, self.particle_d)

    def test_set_state(self):
        new_state = {StateKey.POSITION:174, StateKey.TIMESTAMP:self.base_timestamp+1}
        self.stream_handle = StringIO(CtdpfkParserUnitTestCase.TEST_DATA)
        self.parser = CtdpfkParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source
        result = self.parser.get_records(1)
        self.assert_result(result, 147, self.base_timestamp, self.particle_a)

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 218, self.base_timestamp+2, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 246, self.base_timestamp+3, self.particle_d)
