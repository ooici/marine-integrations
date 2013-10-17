#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_glider Base dataset parser test code
@file mi/dataset/parser/test/test_glider.py
@author Chris Wingard & Stuart Pearce
@brief Test code for a Glider data parser.
"""

from StringIO import StringIO
import gevent
import os
import numpy as np
import ntplib
import unittest

from mi.core.log import get_logger
log = get_logger()

from nose.plugins.attrib import attr

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.glider import GliderParser, StateKey
from mi.dataset.parser.glider import GgldrCtdgvDelayedDataParticle, CtdgvParticleKey
from mi.dataset.parser.glider import GgldrDostaDelayedDataParticle
from mi.dataset.parser.glider import GgldrFlordDelayedDataParticle
from mi.dataset.parser.glider import GgldrEngDelayedDataParticle
from mi.dataset.parser.glider import DataParticleType
from mi.dataset.parser.glider import GliderParticle

from mi.dataset.parser.test.glider_test_results import positions, glider_test_data


HEADER="""dbd_label: DBD_ASC(dinkum_binary_data_ascii)file
encoding_ver: 2
num_ascii_tags: 14
all_sensors: 0
filename: unit_364-2013-225-11-0
the8x3_filename: 01400000
filename_extension: sbd
filename_label: unit_364-2013-225-11-0-sbd(01400000)
mission_name: TRANS59.MI
fileopen_time: Wed_Aug_14_20:03:48_2013
sensors_per_cycle: 28
num_label_lines: 3
num_segments: 1
segment_filename_0: unit_364-2013-225-11-0
c_battpos c_wpt_lat c_wpt_lon m_battpos m_coulomb_amphr_total m_coulomb_current m_depth m_de_oil_vol m_gps_lat m_gps_lon m_lat m_lon m_pitch m_present_secs_into_mission m_present_time m_speed m_water_vx m_water_vy x_low_power_status sci_flbb_bb_units sci_flbb_chlor_units sci_m_present_secs_into_mission sci_m_present_time sci_oxy4_oxygen sci_oxy4_saturation sci_water_cond sci_water_pressure sci_water_temp
in lat lon in amp-hrs amp m cc lat lon lat lon rad sec timestamp m/s m/s m/s nodim nodim ug/l sec timestamp um % s/m bar degc
4 8 8 4 4 4 4 4 8 8 8 8 4 4 8 4 4 4 4 4 4 4 8 4 4 4 4 4 """

# header from sample data in ctdgv driver test
HEADER2="""dbd_label: DBD_ASC(dinkum_binary_data_ascii)file
encoding_ver: 2
num_ascii_tags: 14
all_sensors: 0
filename: unit_363-2013-245-6-6
the8x3_filename: 01790006
filename_extension: sbd
filename_label: unit_363-2013-245-6-6-sbd(01790006)
mission_name: TRANS58.MI
fileopen_time: Thu_Sep__5_02:46:15_2013
sensors_per_cycle: 29
num_label_lines: 3
num_segments: 1
segment_filename_0: unit_363-2013-245-6-6
c_battpos c_wpt_lat c_wpt_lon m_battpos m_coulomb_amphr_total m_coulomb_current m_depth m_de_oil_vol m_gps_lat m_gps_lon m_heading m_lat m_lon m_pitch m_present_secs_into_mission m_present_time m_speed m_water_vx m_water_vy x_low_power_status sci_flbb_bb_units sci_flbb_chlor_units sci_m_present_secs_into_mission sci_m_present_time sci_oxy4_oxygen sci_oxy4_saturation sci_water_cond sci_water_pressure sci_water_temp
in lat lon in amp-hrs amp m cc lat lon rad lat lon rad sec timestamp m/s m/s m/s nodim nodim ug/l sec timestamp um % s/m bar degc
4 8 8 4 4 4 4 4 8 8 4 8 8 4 4 8 4 4 4 4 4 4 4 8 4 4 4 4 4  """

EMPTY_RECORD="""
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

CTDGR_RECORD="""
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 135.361 1376510712.36099 NaN NaN NaN NaN NaN NaN 135.361 1376510712.36099 NaN NaN 4.01713 0.006 15.2229
NaN NaN NaN NaN 0.000298102 NaN NaN NaN NaN NaN NaN NaN NaN NaN 256.162 1376510833.16202 NaN NaN NaN NaN NaN NaN 256.162 1376510833.16202 NaN NaN 4.01758 0.123 15.2283 """

"0.7 5004.24 -14447.88 0.702899 90.0873 0.669156 0 259.684 5002.9179 -14450.1677 5002.91790011739 -14450.1676999628 0.286234 5.609 1376510583.11807 0.343776 0.0102727 0.00906202 3 NaN NaN NaN NaN NaN NaN NaN NaN NaN "
"NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 114.106 1376510691.61636 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN "
"NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 127.32 1376510704.31973 NaN NaN NaN NaN 0.000215908 0.2808 127.32 1376510704.31973 NaN NaN NaN NaN NaN "
"NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 132.347 1376510709.3468 NaN NaN NaN NaN NaN NaN 132.347 1376510709.3468 238.585 94.319 NaN NaN NaN"
"NaN NaN NaN NaN NaN NaN NaN NaN 5002.9419 -14450.3282 NaN NaN NaN 132.997 1376510710.50647 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN "
"NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 187.852 1376510764.85187 NaN NaN NaN NaN 0.000197682 0.2952 187.852 1376510764.85187 NaN NaN NaN NaN NaN "
"NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 192.87 1376510769.86978 NaN NaN NaN NaN NaN NaN 192.87 1376510769.86978 238.022 94.094 NaN NaN NaN "
"NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 195.881 1376510772.88138 NaN NaN NaN NaN NaN NaN 195.881 1376510772.88138 NaN NaN 4.01675 0.006 15.2198 "
"NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 248.121 1376510825.12054 NaN NaN NaN NaN 0.000199084 0.3168 248.121 1376510825.12054 NaN NaN NaN NaN NaN "
"NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 253.148 1376510830.14764 NaN NaN NaN NaN NaN NaN 253.148 1376510830.14764 237.938 94.085 NaN NaN NaN "

@attr('UNIT', group='mi')
class GliderParserUnitTestCase(ParserUnitTestCase):
    """
    Glider Parser unit test base class and common tests.
    """
    config = {}

    def state_callback(self, state):
        """ Call back method to watch what comes in via the state callback """
        self.state_callback_values.append(state)

    def pub_callback(self, particle):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_values.append(particle)

    def setUp(self):
        ParserUnitTestCase.setUp(self)

    def set_test_data(self, *args):
        """
        Accept strings of data in args[] joined together and then a file handle
        to the concatenated string is returned.
        """
        io = StringIO()
        for count, data in enumerate(args):
            io.write(data)

        log.debug("Test data file: %s", io.getvalue())
        io.seek(0)
        self.test_data = io

    def reset_parser(self, state = {}):
        self.state_callback_values = []
        self.publish_callback_values = []
        self.parser = GliderParser(self.config, state, self.test_data,
                                   self.state_callback, self.pub_callback)

    def get_published_value(self):
        return self.publish_callback_values.pop(0)

    def get_state_value(self):
        return self.state_callback_values.pop(0)

    def assert_state(self, expected_position):
        """
        Verify the state
        """
        state = self.parser._read_state
        log.debug("Current state: %s", state)

        position = state.get(StateKey.POSITION)
        self.assertEqual(position, expected_position)

    def assert_no_more_data(self):
        """
        Verify we don't find any other records in the data file.
        """
        records = self.parser.get_records(1)
        self.assertEqual(len(records), 0)

    def assert_generate_particle(self, particle_type, values_dict = None, expected_position = None):
        """
        Verify that we can generate a particle of the correct type and that
        the state is set properly.
        @param particle_type type of particle we are producing
        @param values_dict key value pairs to test in the particle.
        @param expected_position upon publication of the particle, what should the state position indicate.
        """
        # ensure the callback queues are empty before we start
        self.assertEqual(len(self.publish_callback_values), 0)
        self.assertEqual(len(self.state_callback_values), 0)

        records = self.parser.get_records(1)

        self.assertIsNotNone(records)
        self.assertIsInstance(records, list)
        self.assertEqual(len(records), 1)

        self.assertEqual(len(self.publish_callback_values), 1)
        self.assertEqual(len(self.state_callback_values), 1)

        particles = self.get_published_value()
        self.assertEqual(len(particles), 1)

        # Verify the data
        if values_dict:
            self.assert_particle_values(particles[0], values_dict)

        # Verify the parser state
        state = self.get_state_value()
        log.debug("Published state: %s", state)

        if expected_position:
            position = state.get(StateKey.POSITION)
            self.assertEqual(position, expected_position)

    def assert_particle_values(self, particle, expected_values):
        """
        Verify the data in expected values is the data in the particle
        """
        data_dict = particle.generate_dict()
        log.debug("Data in particle: %s", data_dict)
        log.debug("Expected Data: %s", expected_values)

        for key in expected_values.keys():
            for value in data_dict['values']:
                if value['value_id'] == key:
                    self.assertEqual(value['value'], expected_values[key])

    def assert_type(self, records, particle_type):
        for particle in records:
            str_of_type = particle.type()
            self.assertEqual(particle_type, str_of_type)

    def assert_timestamp(self, ntp_timestamp, unix_timestamp):
        ntp_stamp = ntplib.system_to_ntp_time(unix_timestamp)
        assertion = np.allclose(ntp_timestamp, ntp_stamp)
        self.assertTrue(assertion)

    def test_init(self):
        """
        Verify we can initialize
        """
        self.set_test_data(HEADER)
        self.reset_parser()
        self.assert_state(990)

        self.set_test_data(HEADER2)
        self.reset_parser()
        self.assert_state(1004)

    def test_exception(self):
        with self.assertRaises(SampleException):
            self.set_test_data("Foo")
            self.reset_parser()


@attr('UNIT', group='mi')
class CTDGVGliderTest(GliderParserUnitTestCase):
    """
    Test cases for ctdgv glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'GgldrCtdgvDelayedDataParticle',
    }

    def test_ctdgv_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        self.set_test_data(HEADER, CTDGR_RECORD)
        self.reset_parser()

        record_1 = {CtdgvParticleKey.SCI_WATER_TEMP: 15.2229}
        record_2 = {CtdgvParticleKey.SCI_WATER_TEMP: 15.2283}

        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_1, 1146)
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_2, 1315)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_test_data(HEADER, CTDGR_RECORD)
        self.reset_parser({StateKey.POSITION: 1146})
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_2, 1315)
        self.assert_no_more_data()

        # Reset with the parser, but insert noise between records
        self.set_test_data(HEADER, "\nSome noise here!\n", CTDGR_RECORD)
        self.reset_parser()
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_1, 1164)
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_2, 1333)
        self.assert_no_more_data()

        self.set_test_data(HEADER, CTDGR_RECORD, "\nSome noise here!\n", CTDGR_RECORD)
        self.reset_parser()
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_1, 1146)
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_2, 1315)
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_1, 1489)
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_2, 1658)
        self.assert_no_more_data()

class OtherGliderTest(GliderParserUnitTestCase):
    def generic_particle_parse(self, particle_type, num_of_records, start_index=0):
        self.reset_parser()
        records = self.parser.get_records(num_of_records)
        while records:
            end_index = start_index + len(records)-1
            self.assertEqual(records, self.publish_callback_value)
            self.assert_type(records, particle_type)
            self.assert_particles(records, start_index, end_index)
            self.assertEqual(self.parser._state[StateKey.POSITION], positions[end_index])
            self.assertEqual(self.position_callback_value[StateKey.POSITION], positions[end_index])
            start_index += len(records)

            records = self.parser.get_records(num_of_records)



    def assert_particles(self, records, lower_index, upper_index):
        indexes = range(lower_index, upper_index + 1)
        index = indexes.pop(0)
        for particle in records:
            test_dict = particle.generate_dict()
            values = {}
            for value in test_dict['values']:
                values[value['value_id']] = value['value']
            for key in values:
                assertion = np.allclose(values[key], glider_test_data[key][index])
                self.assertTrue(assertion)
            self.assert_timestamp(test_dict['internal_timestamp'], values['m_present_time'])
            if indexes:
                index = indexes.pop(0)

    @unittest.skip("skip")
    def test_get_ctdgv_data(self):
        """
        Test the path of operations where the parser takes the input
        and spits out a valid ctdgv data particle.
        """
        self.config[DataSetDriverConfigKeys.PARTICLE_CLASS] = 'GgldrCtdgvDelayedDataParticle'
        particle_type = DataParticleType.GGLDR_CTDGV_DELAYED
        self.generic_particle_parse(particle_type, 1)
        self.generic_particle_parse(particle_type, 5)
        self.generic_particle_parse(particle_type, 12)

    @unittest.skip("skip")
    def test_get_dosta_data(self):
        """
        Test the path of operations where the parser takes the input
        and spits out a valid dosta data particle.
        """
        self.config[DataSetDriverConfigKeys.PARTICLE_CLASS] = 'GgldrDostaDelayedDataParticle'
        particle_type = DataParticleType.GGLDR_DOSTA_DELAYED
        self.generic_particle_parse(particle_type, 1)
        self.generic_particle_parse(particle_type, 5)
        self.generic_particle_parse(particle_type, 12)

    @unittest.skip("skip")
    def test_get_flord_data(self):
        """
        Test the path of operations where the parser takes the input
        and spits out a valid flord data particle.
        """
        self.config[DataSetDriverConfigKeys.PARTICLE_CLASS] = 'GgldrFlordDelayedDataParticle'
        particle_type = DataParticleType.GGLDR_FLORD_DELAYED
        self.generic_particle_parse(particle_type, 1)
        self.generic_particle_parse(particle_type, 5)
        self.generic_particle_parse(particle_type, 12)

    @unittest.skip("skip")
    def test_get_eng_data(self):
        """
        Test the path of operations where the parser takes the input
        and spits out a valid engineering data particle.
        """
        self.config[DataSetDriverConfigKeys.PARTICLE_CLASS] = 'GgldrEngDelayedDataParticle'
        particle_type = DataParticleType.GGLDR_ENG_DELAYED
        self.generic_particle_parse(particle_type, 1)
        self.generic_particle_parse(particle_type, 5)
        self.generic_particle_parse(particle_type, 12)

    @unittest.skip("skip")
    def test_set_state(self):
        self.config[DataSetDriverConfigKeys.PARTICLE_CLASS] = 'GgldrCtdgvDelayedDataParticle'
        particle_type = DataParticleType.GGLDR_CTDGV_DELAYED
        index = 3
        self.position[StateKey.POSITION] = positions[index]
        self.generic_particle_parse(particle_type, 1, start_index=index + 1)

    @unittest.skip("skip")
    def test_particle_exceptions(self):
        particle = GgldrCtdgvDelayedDataParticle("this is some data, not the expected dict")
        with self.assertRaises(SampleException):
            particle._build_parsed_values()
