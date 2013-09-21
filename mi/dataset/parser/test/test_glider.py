#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_glider Base dataset parser test code
@file mi/dataset/parser/test/test_glider.py
@author Chris Wingard & Stuart Pearce
@brief Test code for a Glider data parser.
"""

import gevent
from StringIO import StringIO
from nose.plugins.attrib import attr

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.glider import GliderParser, GgldrCtdgvDelayedDataParticle, StateKey


@attr('UNIT', group='mi')
class GliderParserUnitTestCase(ParserUnitTestCase):
    """
    Glider Parser unit test suite
    """
    TEST_DATA = """dbd_label: DBD_ASC(dinkum_binary_data_ascii)file
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
4 8 8 4 4 4 4 4 8 8 4 8 8 4 4 8 4 4 4 4 4 4 4 8 4 4 4 4 4 
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121032 1378349126.65387 NaN NaN NaN NaN 0 0 121032 1378349126.65387 0 0 0 0 0 
0.7 5004.23 -14448.95 0.682538 149.576 0.513297 0.05 260.038 5011.2933 -14433.6369 3.48019 5011.29330011781 -14433.6368999199 0.364774 121034 1378349130.18188 0.0935219 -0.0101841 0.0556645 5 NaN NaN NaN NaN NaN NaN NaN NaN NaN  5011.3705 -14433.592 NaN NaN NaN NaN 121121 1378349216.28339 NaN -0.0101765 0.0538197 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3702 -14433.5915 NaN NaN NaN NaN 121125 1378349221.01694 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3704 -14433.5914 NaN NaN NaN NaN 121130 1378349225.75677 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3706 -14433.5918 NaN NaN NaN NaN 121135 1378349230.71121 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121140 1378349234.75079 NaN NaN NaN NaN 0.000298102 1.519 121140 1378349234.75079 NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3712 -14433.5913 NaN NaN NaN NaN 121140 1378349235.40781 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121144 1378349238.77789 NaN NaN NaN NaN NaN NaN 121144 1378349238.77789 242.217 96.009 NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3714 -14433.5923 NaN NaN NaN NaN 121144 1378349240.05527 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121147 1378349241.82962 NaN NaN NaN NaN NaN NaN 121147 1378349241.82962 NaN NaN 4.03096 0.021 15.3683 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3727 -14433.5907 NaN NaN NaN NaN 121149 1378349244.68997 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3729 -14433.5897 NaN NaN NaN NaN 121154 1378349249.32614 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.373 -14433.5875 NaN NaN NaN NaN 121158 1378349253.96094 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3742 -14433.5884 NaN NaN NaN NaN 121163 1378349258.61444 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3754 -14433.5892 NaN NaN NaN NaN 121168 1378349263.24677 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3764 -14433.59 NaN NaN NaN NaN 121172 1378349267.91235 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.377 -14433.5902 NaN NaN NaN NaN 121181 1378349276.95468 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3901 -14433.6051 NaN NaN NaN NaN 121186 1378349281.60773 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3883 -14433.604 NaN NaN NaN NaN 121191 1378349286.31454 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN 5011.3896 -14433.6058 NaN NaN NaN NaN 121195 1378349290.97366 NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 
NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN NaN 121200 1378349295.07373 NaN NaN NaN NaN 0.000291137 1.533 121200 1378349295.07373 NaN NaN NaN NaN NaN 
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
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'GgldrCtdgvDelayedDataParticle'
            }

        # not a DataSourceLocation...its just the parser
        self.position = {StateKey.POSITION: 0}

        # Gonna need the test cases to make some of these
        self.stream_handle = StringIO(GliderParserUnitTestCase.TEST_DATA)
        self.parser = GliderParser(self.config, self.position, self.stream_handle,
                                   self.pos_callback, self.pub_callback)  # last one is the link to the data source

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
        self.stream_handle = StringIO(GliderParserUnitTestCase.TEST_DATA)
        self.parser = GliderParser(self.config, self.position, self.stream_handle,
                                   self.pos_callback, self.pub_callback)  # last one is the link to the data source
