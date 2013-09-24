#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_adcpa Base dataset parser test code
@file mi/dataset/parser/test/test_adcpa.py
@author Christopher Wingard
@brief Test code for a ADCPA data parser. There may be different flavors which
would lead to different subclasses of the test suites
"""

import collections
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

    # Set the source of the test data to a known file that has been opened and
    # parsed with the Teledyne RDI WinADCP application. Comparisons of certain
    # parameters between the results of this parser and the vendor provided
    # utiltiy will be used to validate the parser. Use a data file collected
    # during the PVT testing off the Oregon coast in 2011. This file contains
    # both regular ensembles and bottom-tracking data (starts about 2/3 of the
    # way through the file).
    TEST_DATA = '/tmp/dsatest/adcpa/LA101636.PD0'

    def setUp(self):
        ParserUnitTestCase.setUp(self)

        # configure parser for testing
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcpa',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'ADCPA_PD0_PARSED_DataParticle'
        }
        self.stream_handle = open(AdcpaParserUnitTestCase.TEST_DATA, 'rb')
        self.position_callback_value = None
        self.publish_callback_value = None

        # Set known values for key elements of the particle to validate against
        ### Test 1, Read first 3 particles, one at a time, and compare results
        ### to values below.
        self.test01 = {}
        self.test01['byte_count'] = []
        self.test01['internal_timestamp'] = []
        self.test01['ensemble_start_time'] = []
        self.test01['offset_data_types'] = []
        self.test01['echo_intensity_beam1'] = []
        self.test01['correlation_magnitude_beam1'] = []
        self.test01['percent_bad_beams'] = []
        self.test01['water_velocity_east'] = []
        self.test01['water_velocity_north'] = []
        self.test01['water_velocity_up'] = []
        self.test01['error_velocity'] = []

        ### Test 2, Read first 10 particles all at once and compare results to
        ### values below.
        self.test02 = {}
        self.test02['byte_count'] = []
        self.test02['internal_timestamp'] = []
        self.test02['ensemble_start_time'] = []
        self.test02['offset_data_types'] = []
        self.test02['echo_intensity_beam1'] = []
        self.test02['correlation_magnitude_beam1'] = []
        self.test02['percent_bad_beams'] = []
        self.test02['water_velocity_east'] = []
        self.test02['water_velocity_north'] = []
        self.test02['water_velocity_up'] = []
        self.test02['error_velocity'] = []

        ### Test 3, Skip ahead 25 records (11150 bytes), get 3 records and
        ### compare results to values below.
        self.test03 = {}
        self.test03['byte_count'] = []
        self.test03['internal_timestamp'] = []
        self.test03['ensemble_start_time'] = []
        self.test03['offset_data_types'] = []
        self.test03['echo_intensity_beam1'] = []
        self.test03['correlation_magnitude_beam1'] = []
        self.test03['percent_bad_beams'] = []
        self.test03['water_velocity_east'] = []
        self.test03['water_velocity_north'] = []
        self.test03['water_velocity_up'] = []
        self.test03['error_velocity'] = []

        ### Test 4, Skip ahead to records containing bottom-tracking. Read 2
        ### particles prior to bottom tracking and three after, one at a time
        ### and compare results to values below.
        self.test04 = {}
        self.test04['byte_count'] = []
        self.test04['internal_timestamp'] = []
        self.test04['ensemble_start_time'] = []
        self.test04['offset_data_types'] = []
        self.test04['echo_intensity_beam1'] = []
        self.test04['correlation_magnitude_beam1'] = []
        self.test04['percent_bad_beams'] = []
        self.test04['water_velocity_east'] = []
        self.test04['water_velocity_north'] = []
        self.test04['water_velocity_up'] = []
        self.test04['error_velocity'] = []
        self.test04['beam1_ref_layer_velocity'] = []
        self.test04['beam2_ref_layer_velocity'] = []
        self.test04['beam3_ref_layer_velocity'] = []
        self.test04['beam4_ref_layer_velocity'] = []

    def tearDown(self):
        self.stream_handle.close()

    def pos_callback(self, pos):
        """ Call back method to watch what comes in via the position callback """
        self.position_callback_value = pos

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def parse_particles(self, particles):
        """
        Parse a particle to get at some of the data for comparison purposes
        """
        self.parsed_data = collections.defaultdict(list)

        for i in range(0, len(particles)):
            data = particles[i].generate_dict()

            # parse the values from the dictionary
            values = {}
            for value in data['values']:
                values[value['value_id']] = value['value']

            # start extracting the data for use -- all ensembles
            self.parsed_data['byte_count'].append(self.position_callback_value['position'])
            self.parsed_data['internal_timestamp'].append(data['internal_timestamp'])
            self.parsed_data['ensemble_start_time'].append(values['ensemble_start_time'])
            self.parsed_data['echo_intensity_beam1'].append(values['echo_intensity_beam1'])
            self.parsed_data['correlation_magnitude_beam1'].append(values['correlation_magnitude_beam1'])
            self.parsed_data['error_velocity'].append(values['error_velocity'])
            self.parsed_data['offset_data_types'].append(values['offset_data_types'])
            self.parsed_data['percent_bad_beams'].append(values['percent_bad_beams'])
            self.parsed_data['water_velocity_east'].append(values['water_velocity_east'])
            self.parsed_data['water_velocity_north'].append(values['water_velocity_north'])
            self.parsed_data['water_velocity_up'].append(values['water_velocity_up'])
            # ensembles containing bottom-tracking data
            if 'beam1_ref_layer_velocity' in values:
                self.parsed_data['beam1_ref_layer_velocity'].append(values['beam1_ref_layer_velocity'])
                self.parsed_data['beam2_ref_layer_velocity'].append(values['beam2_ref_layer_velocity'])
                self.parsed_data['beam3_ref_layer_velocity'].append(values['beam3_ref_layer_velocity'])
                self.parsed_data['beam4_ref_layer_velocity'].append(values['beam4_ref_layer_velocity'])

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
        # reset the parser
        self.stream_handle.seek(0)
        self.position = {StateKey.POSITION: 0}
        self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        # get three records from the parser, one at a time, and compare to expected values
        log.debug('##### TEST_GET_DATA #####')
        particle = self.parser.get_records(1)
        self.parse_particles(particle)
        log.debug(self.parsed_data)

        particle = self.parser.get_records(1)
        self.parse_particles(particle)
        log.debug(self.parsed_data)

        particle = self.parser.get_records(1)
        self.parse_particles(particle)
        log.debug(self.parsed_data)

    def test_get_multi(self):
        """
        Test that the parser will read the data from a file and return multiple
        valid particles and values within the particles.
        """
        # reset the parser
        self.stream_handle.seek(0)
        self.position = {StateKey.POSITION: 0}
        self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        # get 3 records from the parser, and compare to expected values
        particles = self.parser.get_records(3)
        self.parse_particles(particles)
        log.debug('##### TEST_GET_MULTI #####')
        log.debug(self.parsed_data)

    def test_set_state(self):
        """
        Test that the parser will start up at some mid-point in the file, and
        continue reading data from a file, returning valid particles and values
        within the particles.

        This tests the ability to set the POSITION state and have the parser
        pick up from there.
        """
        # reset the parser
        self.stream_handle.seek(0)
        self.position = {StateKey.POSITION: 11150}
        self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        # get 3 records from the parser, and compare to expected values
        particles = self.parser.get_records(3)
        self.parse_particles(particles)
        log.debug('##### TEST_SET_STATE #####')
        log.debug(self.parsed_data)

    def test_get_bottom(self):
        """
        """
        # reset the parser
        self.stream_handle.seek(0)
        self.position = {StateKey.POSITION: 91067}
        self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        # get 3 records from the parser, and compare to expected values
        particles = self.parser.get_records(3)
        self.parse_particles(particles)
        log.debug('##### TEST_GET_BOTTOM #####')
        log.debug(self.parsed_data)
