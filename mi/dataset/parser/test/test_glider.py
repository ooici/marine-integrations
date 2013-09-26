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
from mi.dataset.parser.glider import GliderParser, GgldrCtdgvDelayedDataParticle, StateKey

import os

from mi.core.log import get_logger
log = get_logger()

positions = [
    {'position': 1124},
    {'position': 1340},
    {'position': 1506},
    {'position': 1650},
    {'position': 1789},
    {'position': 1945},
    {'position': 2097},
    {'position': 2241},
    {'position': 2398},
    {'position': 2556},
    {'position': 2708},
    {'position': 2852},
    {'position': 3009},
    {'position': 3153},
    {'position': 3311},
    {'position': 3465},
    {'position': 3609},
    {'position': 3766},
    {'position': 3909},
    {'position': 4036},
    {'position': 4194},
    {'position': 4348},
    {'position': 4504},
    {'position': 4661},
    {'position': 4815},
    {'position': 4972},
    {'position': 5129}]




@attr('UNIT', group='mi')
class GliderParserUnitTestCase(ParserUnitTestCase):
    """
    Glider Parser unit test suite
    """
    #log.debug('###########!! PWD is %s !!##########' % os.getcwd())
    test_file = open('mi/dataset/parser/test/test_glider_data.mrg', 'r')

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

    def assert_result(self, result, position, timestamp, particle):
        self.assertEqual(result, [particle])
        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], position)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_ctdgv_particle(self):
        """
        Test the path of operations where the parser takes the input
        and spits out a valid ctdgv data particle.
        """

        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.glider',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'GgldrCtdgvDelayedDataParticle'}

        self.parser = GliderParser(self.config, self.position, self.test_file,
                                   self.pos_callback, self.pub_callback)
        record = self.parser.get_records(1)
        self.assertIs(record[0].type(), 'ggldr_ctdgv_delayed')
        self.

