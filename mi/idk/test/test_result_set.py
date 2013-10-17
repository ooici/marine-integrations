#!/usr/bin/env python

"""
@package mi.idk.test.test_result_set
@file mi.idk/test/test_result_set.py
@author Bill French
@brief Read a result set file and test the verification methods
"""

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

import os
import re

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.common import BaseEnum
from mi.core.unit_test import MiUnitTest
from mi.idk.result_set import ResultSet
from mi.core.instrument.data_particle import DataParticle, DataParticleKey

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.metadata import Metadata

from mi.core.exceptions import SampleException

TIME_REGEX = r'\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{1,2}:\d{1,2}'
TIME_MATCHER = re.compile(TIME_REGEX, re.DOTALL)

DATA_REGEX = r'^\s*(\d*\.\d*),\s*(\d*\.\d*),\s*(\d*\.\d*),\s*(\d*\.\d)'
DATA_MATCHER = re.compile(DATA_REGEX, re.DOTALL)

class CtdpfParserDataParticleKey(BaseEnum):
    TEMPERATURE = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    OXYGEN = "oxygen"

class CtdpfParserDataParticle(DataParticle):
    """
    Class for parsing data from the CTDPF instrument on a HYPM SP platform node
    """

    _data_particle_type = 'ctdpf_parsed'

    def _build_parsed_values(self):
        """
        Take something in the data format CSV delimited values and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("CtdParserDataParticle: No regex match of parsed sample data: [%s]", self.raw_data)
        try:
            temp = float(match.group(2))
            cond = float(match.group(1))
            press = float(match.group(3))
            o2 = float(match.group(4))
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]" % (ex, self.raw_data))

        result = [{DataParticleKey.VALUE_ID: CtdpfParserDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temp},
                  {DataParticleKey.VALUE_ID: CtdpfParserDataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: cond},
                  {DataParticleKey.VALUE_ID: CtdpfParserDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: press},
                  {DataParticleKey.VALUE_ID: CtdpfParserDataParticleKey.OXYGEN,
                   DataParticleKey.VALUE: o2}]
        log.debug('CtdpfParserDataParticle: particle=%s', result)
        return result


@attr('UNIT', group='mi')
class TestResultSet(MiUnitTest):
    """
    Test the metadata object
    """
    def _get_result_set_file(self, filename):
        """
        return the full path to the result_set_file in
        the same directory as the test file.
        """
        test_dir = os.path.dirname(__file__)
        return os.path.join(test_dir, filename)

    def setUp(self):
        """
        Setup the test case
        """

    def test_ntp_conversion(self):
        rs = ResultSet(self._get_result_set_file("record_set_files/test_data_1.txt.result.yml"))
        ts = rs._string_to_ntp_date_time("1970-01-01T00:00:00.00Z")
        self.assertEqual(ts, 2208988800.0)

        ts = rs._string_to_ntp_date_time("1970-01-01T00:01:00.101Z")
        self.assertEqual(ts, 2208988860.101)

        ts = rs._string_to_ntp_date_time("09/05/2013 02:47:21.82962Z")
        self.assertEqual(ts, 3587338041.829620)

    def test_simple_result_set(self):
        """
        Try the first result set with a single record.
        """
        rs = ResultSet(self._get_result_set_file("record_set_files/test_data_1.txt.result.yml"))

        # Test the happy path
        base_timestamp = 3583886463.0
        particle_a = CtdpfParserDataParticle("10.5914,  4.1870,  161.06,   2693.0",
                                             internal_timestamp=base_timestamp, new_sequence=True)
        particle_b = CtdpfParserDataParticle("10.5915,  4.1871,  161.07,   2693.1",
                                             internal_timestamp=base_timestamp+1)

        self.assertTrue(rs.verify([particle_a, particle_b]))
        self.assertIsNone(rs.report())

        # test record count mismatch
        self.assertFalse(rs.verify([particle_a]))
        self.assertIsNotNone(rs.report())

        # test out of order record
        self.assertFalse(rs.verify([particle_b, particle_a]))
        self.assertIsNotNone(rs.report())

        # test bad data record
        self.assertFalse(rs.verify([particle_a, particle_a]))
        self.assertIsNotNone(rs.report())

        # multiple data types in result
        self.assertFalse(rs.verify([particle_a, 'foo']))
        self.assertIsNotNone(rs.report())

        # stream name mismatch
        particle_a._data_particle_type = 'foo'
        particle_b._data_particle_type = 'foo'
        self.assertFalse(rs.verify([particle_a, particle_b]))
        self.assertIsNotNone(rs.report())

        # internal timestamp mismatch
        particle_a = CtdpfParserDataParticle("10.5914,  4.1870,  161.06,   2693.0",
                                             internal_timestamp=base_timestamp+1, new_sequence=True)
        particle_b = CtdpfParserDataParticle("10.5915,  4.1871,  161.07,   2693.1",
                                             internal_timestamp=base_timestamp+2)
        self.assertFalse(rs.verify([particle_a, particle_a]))
        self.assertIsNotNone(rs.report())


    def test_simple_result_set_as_dict(self):
        """
        Try the first result set with a single record from dict.
        """
        rs = ResultSet(self._get_result_set_file("record_set_files/test_data_1.txt.result.yml"))

        # Test the happy path
        base_timestamp = 3583886463.0
        particle_a = CtdpfParserDataParticle("10.5914,  4.1870,  161.06,   2693.0",
                                             internal_timestamp=base_timestamp, new_sequence=True).generate_dict()
        particle_b = CtdpfParserDataParticle("10.5915,  4.1871,  161.07,   2693.1",
                                             internal_timestamp=base_timestamp+1).generate_dict()

        self.assertTrue(rs.verify([particle_a, particle_b]))
        self.assertIsNone(rs.report())

        # test record count mismatch
        self.assertFalse(rs.verify([particle_a]))
        self.assertIsNotNone(rs.report())

        # test out of order record
        self.assertFalse(rs.verify([particle_b, particle_a]))
        self.assertIsNotNone(rs.report())

        # test bad data record
        self.assertFalse(rs.verify([particle_a, particle_a]))
        self.assertIsNotNone(rs.report())
