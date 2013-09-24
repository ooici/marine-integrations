#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_adcpa Base dataset parser test code
@file mi/dataset/parser/test/test_adcpa.py
@author Christopher Wingard
@brief Test code for a ADCPA data parser. There may be different flavors which
would lead to different subclasses of the test suites
"""

import gevent
import json
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

    # Set the source of the test data to a known file that has been opened and
    # parsed with the Teledyne RDI WinADCP application. Comparisons of certain
    # parameters between the results of this parser and the vendor provided
    # utiltiy will be used to validate the parser. Use a data file collected
    # during the PVT testing off the Oregon coast in 2011. This file contains
    # both regular ensembles and bottom-tracking data (starts about 2/3 of the
    # way through the file).
    TEST_DATA = '/tmp/dsatest/adcpa/LA101636.PD0'

    def setUpModule(self):
        ParserUnitTestCase.setUp(self)

        # configure parser for testing
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcpa',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'ADCPA_PD0_PARSED_DataParticle'
        }
        self.position = {StateKey.POSITION: 0}

        self.position_callback_value = None
        self.publish_callback_value = None

        # set known values for key elements of the particle to validate against
        ### Test 1, Read first
        self.internal_timestamp = []
        self.ensemble_start_time = []
        self.offset_data_types = []
        self.echo_intensity_beam1 = []
        self.correlation_magnitude_beam1 = []
        self.percent_bad_beams = []
        self.water_velocity_east = []
        self.water_velocity_north = []
        self.water_velocity_up = []
        self.error_velocity = []

    def pos_callback(self, pos):
        """ Call back method to watch what comes in via the position callback """
        self.position_callback_value = pos

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

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
        with open(AdcpaParserUnitTestCase.TEST_DATA, 'rb') as self.stream_handle:

            self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                      self.pos_callback, self.pub_callback)

            # grab 1 particle at a time -- repeated 5 times
            i = 1
            while i <= 5:
                result = self.parser.get_records(1)
                print result.generate_dict()
                print self.position_callback_value
                print self.publish_callback_value
                i += 1

    def test_set_state(self):
        """
        Test that the parser will start up at some mid-point in the file, and
        continue reading data from a file, returning valid particles and values
        within the particles.

        This tests the ability to set the POSITION state and have the parser
        pick up from there.
        """
        pass
