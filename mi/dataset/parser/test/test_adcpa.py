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

    # Set the source of the test data to a known file (collected during the PVT
    # testing off the Oregon coast in 2011). This file contains both regular
    # ensembles and bottom-tracking data (starts about 2/3 of the way through
    # the file).
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
        # Matlab using a function called PD0decoder provided by Jerry Mullison
        # <jmullison@teledyne.com> of Teledyne RD Instruments. Results of
        # decoding the file using that file are compared to the results of this
        # parser to confirm functionality.

        ### Test 1 and 2, Read first 3 ensembles, either one at a time or all
        ### at once, and compare results to values below.
        self.test01 = {}
        self.test01['internal_timestamp'] = [
            3535202174.300002,
            3535202175.940005,
            3535202177.479998
        ]
        self.test01['ensemble_start_time'] = [
            1326213374.300002,
            1326213375.940005,
            1326213377.479998,
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
            [23, 23, 45, 110, 68, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-94, -94, -167, -454, -176, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-42, -42, -76, -184, -121, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test01['water_velocity_north'] = [
            [-62, -62, -53, -27, -17, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [252, 252, 222, 105, 41, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [111, 111, 97, 42, 28, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test01['water_velocity_up'] = [
            [84, 84, 84, 86, 53, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-339, -339, -341, -348, -136, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-150, -150, -151, -141, -93, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test01['error_velocity'] = [
            [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
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
            1326213413.179996,
            1326213414.900003,
            1326213416.600004
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
            [22, 22, 110, 107, 360, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-77, -77, -268, -372, -349, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-37, -37, -88, -166, -432, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test03['water_velocity_north'] = [
            [-59, -59, -23, -24, -82, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [206, 206, 128, 85, 80, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [98, 98, 78, 38, 100, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test03['water_velocity_up'] = [
            [79, 79, 81, 81, 275, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-277, -277, -282, -285, -267, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [-133, -133, -134, -127, -331, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test03['error_velocity'] = [
            [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
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
        self.test04['byte_count'] = [93017, 93017, 93017, 93017, 93017]
        self.test04['internal_timestamp'] = [
            3535202503.630000,
            3535202505.349996,
            3535202506.880003,
            3535202509.079999,
            3535202514.970000
        ]
        self.test04['ensemble_start_time'] = [
            1326213703.630000,
            1326213705.349996,
            1326213706.880002,
            1326213709.079999,
            1326213714.970000
        ]
        self.test04['echo_intensity_beam1'] = [
            [95, 86, 80, 79, 76, 71, 74, 86, 76, 67, 66, 66, 66, 66, 67],
            [91, 92, 84, 79, 74, 72, 76, 86, 75, 67, 66, 67, 66, 66, 67],
            [94, 88, 84, 80, 76, 71, 74, 76, 69, 67, 67, 71, 72, 71, 69],
            [101, 88, 83, 78, 74, 72, 77, 75, 70, 69, 69, 69, 71, 74, 71],
            [100, 91, 85, 77, 75, 79, 76, 72, 73, 74, 71, 72, 69, 68, 66]
        ]
        self.test04['correlation_magnitude_beam1'] = [
            [128, 118, 104, 109, 95, 74, 80, 109, 73, 21, 13, 12, 12, 11, 9],
            [118, 125, 113, 107, 86, 76, 82, 109, 70, 19, 12, 11, 10, 13, 13],
            [119, 119, 115, 113, 94, 70, 69, 63, 35, 12, 18, 33, 36, 41, 30],
            [124, 119, 115, 107, 85, 73, 74, 57, 39, 27, 26, 26, 40, 45, 38],
            [126, 121, 115, 98, 88, 93, 73, 48, 38, 48, 36, 35, 29, 22, 13]
        ]
        self.test04['percent_good_3beam'] = [
            [0, 0, 0, 0, 0, 90, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 40, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 10, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 50, 60, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 50, 0, 0, 0, 0, 0, 10, 10, 0, 0]
        ]
        self.test04['water_velocity_east'] = [
            [32, 32, 32, 32, 32, 43, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [29, 29, 29, 29, 29, 36, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [27, 27, 27, 27, 28, 80, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [33, 33, 33, 33, 37, 58, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [35, 35, 35, 35, 35, 58, -32768, -32768, -32768, -32768, -32768, 43, 40, -32768, -32768]
        ]
        self.test04['water_velocity_north'] = [
            [8, 8, 8, 8, 8, -115, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [7, 7, 7, 7, 7, -55, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [6, 6, 6, 6, -2, -20, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [7, 7, 7, 7, -49, -93, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [7, 7, 7, 7, 7, -68, -32768, -32768, -32768, -32768, -32768, -115, -107, -32768, -32768]
        ]
        self.test04['water_velocity_up'] = [
            [127, 127, 127, 127, 127, 138, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [113, 113, 113, 113, 113, 123, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [106, 106, 106, 106, 107, 79, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [130, 130, 130, 130, 132, 128, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [127, 127, 127, 127, 127, 125, -32768, -32768, -32768, -32768, -32768, 133, 123, -32768, -32768]
        ]
        self.test04['error_velocity'] = [
            [0, 0, 0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, 0, 0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, 0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, 0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768],
            [0, 0, 0, 0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        ]
        self.test04['eastward_bt_velocity'] = [-32768, -550, -356]
        self.test04['northward_bt_velocity'] = [-32768, -200, -195]
        self.test04['upward_bt_velocity'] = [-32768, 316, 273]
        self.test04['error_bt_velocity'] = [-32768, -32768, -32768]

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

    def assert_result(self, test, parsed, particle, index=-1):
        """
        Suite of tests to run against each returned particle and the parsed
        data from same.
        """
        self.assertEqual(self.publish_callback_value[:], particle[:])
        self.assert_(isinstance(self.publish_callback_value, list))

        # compare each key in the test and parsed dictionaries
        for key in test:
            # modify the test data to account for using only 1 index for
            # test_get_data versus all three indexs for test_set_state.
            if index == -1:
                tdata = test[key]
            else:
                if len(test[key]) >= 1:
                    tdata = [test[key][index]]
                else:
                    tdata = test[key]

            # test the keys
            if 'internal_timestamp' in key or 'ensemble_start_time' in key:
                # slightly different test for these values as they are floats.
                # this asserts that the difference between these values is less
                # than 0.1 milliseconds.
                compare = np.abs(np.array(tdata) - np.array(parsed[key])) <= 1e-5
                self.assertTrue(compare.all())
            else:
                # otherwise they are all ints and should be exactly equal
                self.assertEqual(tdata, parsed[key])

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
            self.assert_result(self.test01, self.parsed_data, particle, i)

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
        self.assert_result(self.test03, self.parsed_data, particles)

    def test_get_bottom(self):
        """
        Test that the parser will start up at some mid-point in the file, and
        continue reading data from a file, returning valid particles and values
        within the particles.

        This duplicates test_set_state above, and extends it by grabbing the
        additional bottom-tracking (BT) data that will appear at this point in
        the file. This validates that the parser will correctly start adding
        the BT data when it is encountered. The first 2 particles will not have
        BT data, while the last three will.
        """
        # reset the parser
        self.stream_handle.seek(0)
        self.position = {StateKey.POSITION: 90538}
        self.parser = AdcpaParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback)

        # get 3 records from the parser, and compare to expected values
        particles = self.parser.get_records(5)
        self.parse_particles(particles)
        self.assert_result(self.test04, self.parsed_data, particles)
