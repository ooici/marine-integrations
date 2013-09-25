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
import numpy as np
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

        # Set known values for key elements of the particle to validate
        # against. These values were created by opening the test data file in
        # WinADCP (an RD Instruments utility), and exporting the data to
        # Matlab, where they were then copied and pasted into this code. The
        # intent is to compare this parser to a standard utility provided by
        # the vendor.

        ### Test 1 and 2, Read first 3 ensembles, either one at a time or all
        ### at once, and compare results to values below.
        self.test01 = {}
        self.test01['byte_count'] = []
        self.test01['internal_timestamp'] = [
            3535202174.300002,
            3535202175.940005,
            3535202177.479998
        ]
        self.test01['ensemble_start_time'] = [
            3535202174.300002,
            3535202175.940005,
            3535202177.479998
        ]
        self.test01['echo_intensity_beam1'] = [
            [114, 96, 84, 74, 73, 71, 68, 68, 68, 68, 67, 67, 67, 66, 66],
            [113, 95, 81, 76, 72, 71, 70, 68, 68, 68, 68, 67, 67, 66, 67],
            [117, 93, 82, 77, 74, 72, 69, 69, 68, 68, 68, 67, 67, 67, 67]
        ]
        self.test01['correlation_magnitude_beam1'] = [
            [106, 126, 106, 89, 66, 49, 40, 34, 24, 17, 15, 12, 0, 0, 0],
            [105, 121, 101, 99, 65, 51, 40, 33, 29, 19, 15, 13, 0, 0, 0],
            [106, 118, 105, 97, 72, 52, 45, 38, 22, 21, 20, 16, 0, 0, 0]
        ]
        self.test01['percent_good_3beam'] = [
            [0, 0, 20, 100, 40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 20, 100, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 20,  80, 50, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        ]
        self.test01['water_velocity_east'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test01['water_velocity_north'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test01['water_velocity_up'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test01['error_velocity'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test01['eastward_bt_velocity'] = []
        self.test01['northward_bt_velocity'] = []
        self.test01['upward_bt_velocity'] = []
        self.test01['error_bt_velocity'] = []

        ### Test 3, Skip ahead 25 ensembles (11150 bytes), get 3 records and
        ### compare results to values below.
        self.test03 = {}
        self.test03['byte_count'] = [12042, 12042, 12042]
        self.test03['internal_timestamp'] = [
            3535202213.179996,
            3535202214.900003,
            3535202216.600003
        ]
        self.test03['ensemble_start_time'] = [
            3535202213.179996,
            3535202214.900003,
            3535202216.600003
        ]
        self.test03['echo_intensity_beam1'] = [
            [123, 94, 84, 80, 72, 69, 70, 69, 68, 68, 67, 67, 67, 67, 67],
            [123, 93, 83, 76, 71, 71, 69, 69, 69, 67, 67, 67, 67, 67, 67],
            [127, 89, 80, 76, 73, 71, 71, 69, 68, 69, 68, 67, 67, 68, 67]
        ]
        self.test03['correlation_magnitude_beam1'] = [
            [96, 123, 107, 106, 55, 55, 41, 25, 20, 15, 18, 14, 0, 0, 0],
            [97, 117, 114, 91, 71, 52, 44, 34, 16, 16, 15, 13, 0, 0, 0],
            [92, 113, 109, 94, 72, 61, 37, 36, 22, 16, 13, 17, 0, 0, 0]
        ]
        self.test03['percent_good_3beam'] = [
            [0, 0, 60, 100, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 60, 100, 40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 40, 90, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        ]
        self.test03['water_velocity_east'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test03['water_velocity_north'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test03['water_velocity_up'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test03['error_velocity'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test03['eastward_bt_velocity'] = []
        self.test03['northward_bt_velocity'] = []
        self.test03['upward_bt_velocity'] = []
        self.test03['error_bt_velocity'] = []

        ### Test 4, Skip ahead to records containing bottom-tracking. Read 2
        ### ensembles prior to bottom tracking and three after (ensembles
        ### 204-208, byte 90984), all at once and compare results to values
        ### below.
        self.test04 = {}
        self.test04['byte_count'] = []
        self.test04['internal_timestamp'] = [
            3535202503.630000,
            3535202505.349996,
            3535202506.880003,
            3535202634.730003,
            3535202638.000001
        ]
        self.test04['ensemble_start_time'] = [
            3535202503.630000,
            3535202505.349996,
            3535202506.880003,
            3535202634.730003,
            3535202638.000001
        ]
        self.test04['echo_intensity_beam1'] = [
            [95, 86, 80, 79, 76, 71, 74, 86, 76, 67, 66, 66, 66, 66, 67],
            [91, 92, 84, 79, 74, 72, 76, 86, 75, 67, 66, 67, 66, 66, 67],
            [94, 88, 84, 80, 76, 71, 74, 76, 69, 67, 67, 71, 72, 71, 69],
            [82, 72, 69, 68, 67, 67, 67, 66, 66, 66, 67, 66, 66, 69, 72],
            [81, 73, 68, 68, 67, 67, 67, 66, 67, 67, 67, 67, 66, 69, 78]
        ]
        self.test04['correlation_magnitude_beam1'] = [
            [128, 118, 104, 109, 95, 74, 80, 109, 73, 21, 13, 12, 12, 11, 9],
            [118, 125, 113, 107, 86, 76, 82, 109, 70, 19, 12, 11, 10, 13, 13],
            [119, 119, 115, 113, 94, 70, 69, 63, 35, 12, 18, 33, 36, 41, 30],
            [106, 77, 48, 36, 30, 25, 22, 14, 19, 16, 19, 19, 19, 44, 68],
            [103, 76, 39, 35, 26, 24, 21, 16, 19, 17, 22, 19, 19, 61, 72]
        ]
        self.test04['percent_good_3beam'] = [
            [0, 0, 0, 0, 0, 90, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 10, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [10, 50, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        ]
        self.test04['water_velocity_east'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [297, 318, 443, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [352, 366, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test04['water_velocity_north'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-53, -77, -41, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-89, -89, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test04['water_velocity_up'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-68, -72, -61, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-105, -112, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test04['water_velocity_error'] = [
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-5, -5, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test04['eastward_bt_velocity'] = [0, 0, -32768, 269, 322]
        self.test04['northward_bt_velocity'] = [0, 0, -32768, -55, -95]
        self.test04['upward_bt_velocity'] = [0, 0, -32768, -177, -216]
        self.test04['error_bt_velocity'] = [0, 0, -32768, 0, -5]

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
            self.parsed_data['percent_good_3beam'].append(values['percent_good_3beam'])
            self.parsed_data['water_velocity_east'].append(values['water_velocity_east'])
            self.parsed_data['water_velocity_north'].append(values['water_velocity_north'])
            self.parsed_data['water_velocity_up'].append(values['water_velocity_up'])
            self.parsed_data['error_velocity'].append(values['error_velocity'])
            # ensembles containing bottom-tracking data
            if 'eastward_bt_velocity' in values:
                self.parsed_data['eastward_bt_velocity'].append(values['eastward_bt_velocity'])
                self.parsed_data['northward_bt_velocity'].append(values['northward_bt_velocity'])
                self.parsed_data['upward_bt_velocity'].append(values['upward_bt_velocity'])
                self.parsed_data['error_bt_velocity'].append(values['error_bt_velocity'])
            else:
                self.parsed_data['eastward_bt_velocity'] = []
                self.parsed_data['northward_bt_velocity'] = []
                self.parsed_data['upward_bt_velocity'] = []
                self.parsed_data['error_bt_velocity'] = []

    def assert_result(self, test, parsed, particle):
        self.assertEqual(self.publish_callback_value[:], particle[:])
        self.assert_(isinstance(self.publish_callback_value, list))

        for key in test:
            if 'internal_timestamp' in key:
                self.assertTrue(np.allclose(parsed['internal_timestamp'], parsed['ensemble_start_time'],
                                            rtol=1e2, atol=1e2))
            else:
                self.assertEqual(test[key], parsed[key])
                log.debug(key)

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
        self.test01['byte_count'] = [446, 892, 1338]

        # get three records from the parser, one at a time, and compare to expected values
        for i in range(0, 2):
            particle = self.parser.get_records(1)
            self.parse_particles(particle)
            log.debug('\n\n\n\n\n')
            log.debug('##### TEST_GET_DATA #####')
            log.debug(self.test01)
            log.debug(self.parsed_data)
            log.debug('\n\n\n\n\n')
            self.assert_result(self.test01, self.parsed_data, particle)

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
        self.test01['byte_count'] = [1338, 1338, 1338]

        # get 3 records from the parser, and compare to expected values
        particles = self.parser.get_records(3)
        self.parse_particles(particles)
        log.debug('\n\n\n\n\n')
        log.debug('##### TEST_GET_MULTI #####')
        log.debug(self.test01)
        log.debug(self.parsed_data)
        log.debug('\n\n\n\n\n')
        self.assert_result(self.test01, self.parsed_data, particles)

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
        self.position = {StateKey.POSITION: 10704}
        self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        # get 3 records from the parser, and compare to expected values
        particles = self.parser.get_records(3)
        self.parse_particles(particles)
        log.debug('\n\n\n\n\n')
        log.debug('##### TEST_SET_STATE #####')
        log.debug(self.test03)
        log.debug(self.parsed_data)
        log.debug('\n\n\n\n\n')
        self.assert_result(self.test03, self.parsed_data, particles)

    def test_get_bottom(self):
        """
        Test that the parser will start up at some mid-point in the file, and
        continue reading data from a file, returning valid particles and values
        within the particles.

        This duplicates test_set_state and extends by grabbing bottom-tracking
        data that will appear at this point in the file.
        """
        # reset the parser
        self.stream_handle.seek(0)
        self.position = {StateKey.POSITION: 90984}
        self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        # get 3 records from the parser, and compare to expected values
        particles = self.parser.get_records(3)
        self.parse_particles(particles)
        log.debug('\n\n\n\n\n')
        log.debug('##### TEST_GET_BOTTOM #####')
        log.debug(self.test04)
        log.debug(self.parsed_data)
        log.debug('\n\n\n\n\n')
        self.assert_result(self.test04, self.parsed_data, particles)
