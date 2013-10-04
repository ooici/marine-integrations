#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_glider Base dataset parser test code
@file mi/dataset/parser/test/test_glider.py
@author Chris Wingard & Stuart Pearce
@brief Test code for a Glider data parser.
"""

import gevent
from nose.plugins.attrib import attr

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.glider import GliderParser, StateKey
from mi.dataset.parser.glider import GgldrCtdgvDelayedDataParticle
from mi.dataset.parser.glider import GgldrDostaDelayedDataParticle
from mi.dataset.parser.glider import GgldrFlordDelayedDataParticle
from mi.dataset.parser.glider import GgldrEngDelayedDataParticle
from mi.dataset.parser.glider import DataParticleType
from mi.dataset.parser.glider import GliderParticle

from mi.dataset.parser.test.glider_test_results import positions, glider_test_data

import os
import numpy as np
import ntplib

from mi.core.log import get_logger
log = get_logger()


@attr('UNIT', group='mi')
class GliderParserUnitTestCase(ParserUnitTestCase):
    """
    Glider Parser unit test suite
    """
    #log.debug('###########!! PWD is %s !!##########' % os.getcwd())
    test_file = open('mi/dataset/parser/test/test_glider_data.mrg', 'r')

    config = {
        DataSetDriverConfigKeys.PARTICLE_MODULE:
        'mi.dataset.parser.glider'}

    def pos_callback(self, pos):
        """ Call back method to watch what comes in via the position callback """
        self.position_callback_value = pos

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)

        # not a DataSourceLocation...its just the parser
        self.position = {StateKey.POSITION: 0}

        # take that, rewind it back ...
        self.test_file.seek(0)

        self.position_callback_value = None
        self.publish_callback_value = None

    def reset_parser(self):
        self.test_file.seek(0)
        self.position_callback_value = None
        self.publish_callback_value = None
        self.parser = GliderParser(self.config, self.position, self.test_file,
                                   self.pos_callback, self.pub_callback)

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

    def assert_type(self, records, particle_type):
        for particle in records:
            str_of_type = particle.type()
            self.assertEqual(particle_type, str_of_type)

    def assert_timestamp(self, ntp_timestamp, unix_timestamp):
        ntp_stamp = ntplib.system_to_ntp_time(unix_timestamp)
        assertion = np.allclose(ntp_timestamp, ntp_stamp)
        self.assertTrue(assertion)

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

    def test_set_state(self):
        self.config[DataSetDriverConfigKeys.PARTICLE_CLASS] = 'GgldrCtdgvDelayedDataParticle'
        particle_type = DataParticleType.GGLDR_CTDGV_DELAYED
        index = 3
        self.position[StateKey.POSITION] = positions[index]
        self.generic_particle_parse(particle_type, 1, start_index=index + 1)

    def test_particle_exceptions(self):
        self.assertRaises(
            SampleException, GliderParticle,
            'this is testing that GliderParticle raises a SampleException')
        self.assertRaises(
            SampleException, GgldrCtdgvDelayedDataParticle,
            'this is testing that Ctdgv Particle raises a SampleException')
        self.assertRaises(
            SampleException, GgldrDostaDelayedDataParticle,
            'this is testing that Ctdgv Particle raises a SampleException')
        self.assertRaises(
            SampleException, GgldrFlordDelayedDataParticle,
            'this is testing that Ctdgv Particle raises a SampleException')
        self.assertRaises(
            SampleException, GgldrEngDelayedDataParticle,
            'this is testing that Ctdgv Particle raises a SampleException')
