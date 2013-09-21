#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_adcpa Base dataset parser test code
@file mi/dataset/parser/test/test_adcpa.py
@author Christopher Wingard
@brief Test code for a ADCPA data parser. There may be different flavors which
would lead to different subclasses of the test suites
"""

import gevent
from nose.plugins.attrib import attr

from mi.core.log import get_logger

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.adcpa import AdcpaParser, ADCPA_PD0_PARSED_DataParticle, StateKey

log = get_logger()


@attr('UNIT', group='mi')
class AdcpaParserUnitTestCase(ParserUnitTestCase):
    """
    ADCPA Parser unit test suite
    """
    def pos_callback(self, pos):
        """ Call back method to watch what comes in via the position callback """
        self.position_callback_value = pos

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)

        # configure parser for testing
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcpa',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'ADCPA_PD0_PARSED_DataParticle'
        }
        self.position = {StateKey.POSITION: 0}
        self.stream_handle = StringIO(AdcpaParserUnitTestCase.TEST_DATA)
        self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        self.position_callback_value = None
        self.publish_callback_value = None

        # set known values for key elements of the particle to validate parsing against
        rt_clock
        velocity
        correlation
        percent_good
        position

    def assert_result(self, result, position, values):
        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], position)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_get_data(self):
        """
        Test that the parser will read the data from a file and return valid
        particles and values within the particles.
        """
        # grab 1 particle at a time
        result = self.parser.get_records(1)
        self.assert_result(result, 137, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, 174, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 211, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 248, self.particle_d)

        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], position)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

        # grab multiple particles at once
        result = self.parser.get_records(2)
        self.assertEqual(result, [self.particle_a, self.particle_b])
        self.assertEqual(self.parser._state[StateKey.POSITION], 174)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 174)
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)

    def test_set_state(self):
        """
        Test that the parser will start up at some mid-point in the file, and
        read the data from a file, returning valid particles and values within
        the particles.

        This tests the ability to set the POSITION state and have the parser
        pick up from there.
        """
        new_state = {StateKey.POSITION: 211}
        self.stream_handle = StringIO(AdcpaParserUnitTestCase.TEST_DATA)
        self.parser = AdcpaParser(self.config, new_state, self.stream_handle,
                                  self.pos_callback, self.pub_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 248, self.base_timestamp+3, self.particle_d)
