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
from mi.dataset.parser.glider import DostaParticleKey
from mi.dataset.parser.glider import FlordParticleKey
from mi.dataset.parser.glider import EngineeringParticleKey

from mi.dataset.parser.test.glider_test_results import positions, glider_test_data


HEADER="""dbd_label: DBD_ASC(dinkum_binary_data_ascii)file
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
4 8 8 4 4 4 4 4 8 8 4 8 8 4 4 8 4 4 4 4 4 4 4 8 4 4 4 4 4 """

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

ZERO_GPS_VALUE ="""
NaN 0 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

INT_GPS_VALUE ="""
NaN 2012 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

CHUNKER_TEST="""
0.273273 NaN NaN 0.335 149.608 0.114297 33.9352 -64.3506 NaN NaN NaN 5011.38113678061 -14433.5809717525 NaN 121546 1378349641.79871 NaN NaN NaN 0 NaN NaN NaN NaN NaN NaN NaN 11.00
3 NaN NaN NaN NaN NaN NaN NaN NaN NaN 1.23569 NaN NaN -0.0820305 121379 1378349475.09927 0.236869 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 1
"""

CTDGR_RECORD="""
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121147 1378349241.82962 NaN NaN NaN NaN NaN NaN 121147 1378349241.82962 NaN NaN 4.03096 0.021 15.3683
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121207 1378349302.10907 NaN NaN NaN NaN NaN NaN 121207 1378349302.10907 NaN NaN 4.03113 0.093 15.3703 """

DOSTA_RECORD="""
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121144 1378349238.77789 NaN NaN NaN NaN NaN NaN 121144 1378349238.77789 242.217 96.009 NaN NaN NaN
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121204 1378349299.09106 NaN NaN NaN NaN NaN NaN 121204 1378349299.09106 242.141 95.988 NaN NaN NaN """

FLORD_RECORD="""
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121140 1378349234.75079 NaN NaN NaN NaN 0.000298102 1.519 121140 1378349234.75079 NaN NaN NaN NaN NaN
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121321 1378349415.84534 NaN NaN NaN NaN 0.000327355 1.708 121321 1378349415.84534 NaN NaN NaN NaN NaN """

ENG_RECORD="""
0.273273 NaN NaN 0.335 149.608 0.114297 33.9352 -64.3506 NaN NaN NaN 5011.38113678061 -14433.5809717525 NaN 121546 1378349641.79871 NaN NaN NaN 0 NaN NaN NaN NaN NaN NaN NaN NaN NaN
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 1.23569 NaN NaN -0.0820305 121379 1378349475.09927 0.236869 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN """

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

    def set_data(self, *args):
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

    def set_data_file(self, filename):
        """
        Set test to read from a file.
        """
        self.test_data = open(filename, "r")

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
        self.set_data(HEADER)
        self.reset_parser()
        self.assert_state(1003)

        self.set_data(HEADER2)
        self.reset_parser()
        self.assert_state(1004)

    def test_exception(self):
        with self.assertRaises(SampleException):
            self.set_data("Foo")
            self.reset_parser()

    def test_chunker(self):
        """
        Verify the chunker is returning values we expect.
        """
        self.set_data(HEADER, CHUNKER_TEST)
        self.reset_parser()

        records = CHUNKER_TEST.strip("\n").split("\n")
        log.debug("Expected Records: %s", records)
        self.assertEqual(len(records), 2)

        # Load all data into the chunker
        self.parser.get_block(1024)

        self.assertEqual(CHUNKER_TEST.strip("\n"), self.parser._chunker.buffer.strip("\n"))

        (timestamp, data_record, start, end) = self.parser._chunker.get_next_data_with_index()
        log.debug("Data Record: %s", data_record)
        self.assertEqual(records[0]+"\n", data_record)

        (timestamp, data_record, start, end) = self.parser._chunker.get_next_data_with_index()
        self.assertEqual(records[1]+"\n", data_record)


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
        self.set_data(HEADER, CTDGR_RECORD)
        self.reset_parser()

        record_1 = {CtdgvParticleKey.SCI_WATER_TEMP: 15.3683}
        record_2 = {CtdgvParticleKey.SCI_WATER_TEMP: 15.3703}

        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_1, 1162)
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_2, 1321)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER, CTDGR_RECORD)
        self.reset_parser({StateKey.POSITION: 1162})
        self.assert_generate_particle(GgldrCtdgvDelayedDataParticle, record_2, 1321)
        self.assert_no_more_data()

    def test_gps(self):
        self.set_data(HEADER, ZERO_GPS_VALUE)
        self.reset_parser()
        records = self.parser.get_records(1)
        self.assertEqual(len(records), 0)

        self.set_data(HEADER, INT_GPS_VALUE)
        self.reset_parser()
        records = self.parser.get_records(1)
        self.assertEqual(len(records), 0)

@attr('UNIT', group='mi')
class DOSTAGliderTest(GliderParserUnitTestCase):
    """
    Test cases for dosta glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'GgldrDostaDelayedDataParticle',
    }

    def test_dosta_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        self.set_data(HEADER, DOSTA_RECORD)
        self.reset_parser()

        record_1 = {DostaParticleKey.SCI_OXY4_OXYGEN: 242.217, DostaParticleKey.SCI_OXY4_SATURATION: 96.009}
        record_2 = {DostaParticleKey.SCI_OXY4_OXYGEN: 242.141, DostaParticleKey.SCI_OXY4_SATURATION: 95.988}

        self.assert_generate_particle(GgldrDostaDelayedDataParticle, record_1, 1159)
        self.assert_generate_particle(GgldrDostaDelayedDataParticle, record_2, 1315)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER, DOSTA_RECORD)
        self.reset_parser({StateKey.POSITION: 1159})
        self.assert_generate_particle(GgldrDostaDelayedDataParticle, record_2, 1315)
        self.assert_no_more_data()

@attr('UNIT', group='mi')
class FLORDGliderTest(GliderParserUnitTestCase):
    """
    Test cases for dosta glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'GgldrFlordDelayedDataParticle',
    }

    def test_flord_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        self.set_data(HEADER, FLORD_RECORD)
        self.reset_parser()

        record_1 = {FlordParticleKey.SCI_FLBB_BB_UNITS: 0.000298102, FlordParticleKey.SCI_FLBB_CHLOR_UNITS: 1.519}
        record_2 = {FlordParticleKey.SCI_FLBB_BB_UNITS: 0.000327355, FlordParticleKey.SCI_FLBB_CHLOR_UNITS: 1.708}

        self.assert_generate_particle(GgldrDostaDelayedDataParticle, record_1, 1162)
        self.assert_generate_particle(GgldrDostaDelayedDataParticle, record_2, 1321)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER, FLORD_RECORD)
        self.reset_parser({StateKey.POSITION: 1162})
        self.assert_generate_particle(GgldrDostaDelayedDataParticle, record_2, 1321)
        self.assert_no_more_data()

@attr('UNIT', group='mi')
class ENGGliderTest(GliderParserUnitTestCase):
    """
    Test cases for eng glider data
    """
    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
        DataSetDriverConfigKeys.PARTICLE_CLASS: 'GgldrEngDelayedDataParticle',
    }

    def test_eng_particle(self):
        """
        Verify we publish particles as expected.  Ensure particle is published and
        that state is returned.
        """
        self.set_data(HEADER, ENG_RECORD)
        self.reset_parser()

        record_1 = {EngineeringParticleKey.M_BATTPOS: 0.335}
        record_2 = {EngineeringParticleKey.M_HEADING: 1.23569}

        self.assert_generate_particle(GgldrEngDelayedDataParticle, record_1, 1186)
        self.assert_generate_particle(GgldrEngDelayedDataParticle, record_2, 1335)
        self.assert_no_more_data()

        # Reset with the parser, but with a state this time
        self.set_data(HEADER, ENG_RECORD)
        self.reset_parser({StateKey.POSITION: 1186})
        self.assert_generate_particle(GgldrEngDelayedDataParticle, record_2, 1335)
        self.assert_no_more_data()
