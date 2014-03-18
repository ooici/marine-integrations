#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_wfp_parser Base dataset parser test code
@file mi/dataset/parser/test/test_wfp_parser.py
@author Steve Foley/Roger Unwin
@brief Test code for a WFP data parser. There may be different flavors which
would lead to different subclasses of the test suites
"""

import gevent
from StringIO import StringIO
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.wfp_parser import WfpParser, WfpParticle, WfpFlortkDataParticle, WfpParadkDataParticle, StateKey

# Add a mixin here if needed

@attr('UNIT', group='mi')
class WfpParserUnitTestCase(ParserUnitTestCase):
    """
    WFP Parser unit test suite
    """
    TEST_DATA = """

 Profile 152

 Sensors were turned on at  04/15/2013 14:20:02
 Vehicle began profiling at 04/15/2013 14:22:02

Date,[mA],[V],[dbar],Par[mV],scatSig,chlSig,CDOMSig
04/15/2013 14:22:02,-2,10.8,0.000,0.00,117,52,94
04/15/2013 14:22:10,61,10.6,0.000,0.00,114,52,97
04/15/2013 14:23:02,155,10.6,1.520,3.00,114,52,94
04/15/2013 14:23:08,720,9.7,0.850,27.00,114,53,90

 Ramp exit:    SMOOTH RUNNING
 Profile exit: TOP PRESSURE

 Vehicle motion stopped at 04/15/2013 14:23:17
 Sensor logging stopped at 04/15/2013 14:25:28
"""

    LONG_DATA = """

 Profile 152

 Sensors were turned on at  04/15/2013 14:20:02
 Vehicle began profiling at 04/15/2013 14:22:02

Date,[mA],[V],[dbar],Par[mV],scatSig,chlSig,CDOMSig
04/15/2013 14:22:02,-2,10.8,0.000,0.00,117,52,94
04/15/2013 14:22:10,61,10.6,0.000,0.00,114,52,97
04/15/2013 14:22:17,187,10.4,0.000,0.00,116,52,94
04/15/2013 14:22:24,189,10.5,0.000,0.00,113,53,94
04/15/2013 14:22:30,187,10.5,0.000,0.00,113,53,93
04/15/2013 14:22:37,204,10.5,7.630,0.00,113,51,94
04/15/2013 14:22:43,168,10.5,6.110,0.00,114,53,96
04/15/2013 14:22:50,161,10.6,4.590,0.00,113,52,91
04/15/2013 14:22:56,153,10.5,3.060,1.00,113,50,93
04/15/2013 14:23:02,155,10.6,1.520,3.00,114,52,94
04/15/2013 14:23:08,720,9.7,0.850,27.00,114,53,90

 Ramp exit:    SMOOTH RUNNING
 Profile exit: TOP PRESSURE

 Vehicle motion stopped at 04/15/2013 14:23:17
 Sensor logging stopped at 04/15/2013 14:25:28
"""

    BAD_TEST_DATA = """

 Profile 152

 Sensors were turned on at  04/15/2013 14:20:02
 Vehicle began profiling at 04/15/2013 14:22:02

Date,[mA],[V],[dbar],Par[mV],scatSig,chlSig,CDOMSig
,-2,10.8,0.000,0.00,117,52,94
04/15/2013 14:22:10,61,10.6,0.000,0.00,114,52,97
04/15/2013 14:23:08,720,9.7,o.850,27.00,114,53,90

 Ramp exit:    SILENT RUNNING
 Profile exit: TOP GUN

 Vehicle motion stopped at FE/15/2013 14:23:17
 Sensor logging stopped at D0/0D/2013 14:25:28
"""


    def pos_callback(self, pos, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.file_ingested = file_ingested
        self.position_callback_value = pos

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        log.error("SETTING publish_callback_value to " + str(pub))
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_parser',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'WfpParticle'
            }

        # not a DataSourceLocation...its just the parser
        self.position = {StateKey.POSITION:0}

        self.base_timestamp = 3575024522.0
        self.particle_a = WfpParticle("04/15/2013 14:22:02,-2,10.8,0.000,0.00,117,52,94",
                                                  internal_timestamp=self.base_timestamp)
        self.particle_b = WfpParticle("04/15/2013 14:22:10,61,10.6,0.000,0.00,114,52,97",
                                                  internal_timestamp=self.base_timestamp+1)
        self.particle_c = WfpParticle("04/15/2013 14:23:02,155,10.6,1.520,3.00,114,52,94",
                                                  internal_timestamp=self.base_timestamp+2)
        self.particle_d = WfpParticle("04/15/2013 14:23:08,720,9.7,0.850,27.00,114,53,90",
                                                  internal_timestamp=self.base_timestamp+3)
        self.particle_e = WfpParticle("1.5371,16.3169,12.640, 3141",
                                                  internal_timestamp=self.base_timestamp+60)
        self.particle_z = WfpParticle("04/15/2013 14:23:08,720,9.7,0.850,27.00,114,53,90",
                                                  internal_timestamp=self.base_timestamp+43)

        self.position_callback_value = None
        self.publish_callback_value = None

    def assert_result(self, result, position, particle):
        self.assertEqual(result, [particle])

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], position)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_happy_path(self):
        """
        Test the happy path of operations where the parser takes the input
        and spits out a valid data particle given the stream.
        """
        self.stream_handle = StringIO(WfpParserUnitTestCase.TEST_DATA)
        self.parser = WfpParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
        self.assert_result(result, 213, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, 262, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 311, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 360, self.particle_d)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 360)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 360)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_d)

    def test_get_many(self):
        self.stream_handle = StringIO(WfpParserUnitTestCase.TEST_DATA)
        self.parser = WfpParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        result = self.parser.get_records(2)
        self.assertEqual(result, [self.particle_a, self.particle_b])
        self.assertEqual(self.parser._state[StateKey.POSITION], 262)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 262)

        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)

    def test_bad_data(self):
        """ There's a bad sample in the data! Ack! Skip it! """
        self.stream_handle = StringIO(WfpParserUnitTestCase.BAD_TEST_DATA)
        self.parser = WfpParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        result = self.parser.get_records(1)
        log.error("RESULT = " + str(result))
        self.assert_result(result, 243, self.particle_b)

    def test_long_stream(self):
        self.stream_handle = StringIO(WfpParserUnitTestCase.LONG_DATA)
        self.parser = WfpParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        result = self.parser.get_records(44)
        self.assertEqual(result[-1], self.particle_z)
        self.assertEqual(self.parser._state[StateKey.POSITION], 703)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 703)
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)

    def test_mid_state_start(self):
        new_state = {StateKey.POSITION: 313}
        self.stream_handle = StringIO(WfpParserUnitTestCase.TEST_DATA)
        self.parser = WfpParser(self.config, new_state, self.stream_handle,
                                  self.pos_callback, self.pub_callback)
        #
        # Oddly the position is off by 1 after repositioning.
        # puzzling, but seems harmless.
        #

        result = self.parser.get_records(1)
        self.assert_result(result, 362, self.particle_d)

    def test_set_state(self):
        new_state = {StateKey.POSITION:262}

        self.stream_handle = StringIO(WfpParserUnitTestCase.TEST_DATA)
        self.parser = WfpParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, 213, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, 262, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 311, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 360, self.particle_d)

        self.parser.set_state(new_state)
        #
        # Oddly the position is off by 1 after repositioning.
        # puzzling, but seems harmless.
        #

        result = self.parser.get_records(1)
        self.assert_result(result, 312, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 362, self.particle_d)

