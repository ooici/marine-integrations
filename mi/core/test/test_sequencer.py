#!/usr/bin/env python

__author__ = 'Bill French'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger ; log = get_logger()

from nose.plugins.attrib import attr
from mi.core.unit_test import MiUnitTest
from mi.core.sequencer import Sequencer

@attr('UNIT', group='mi')
class TestSequencer(MiUnitTest):
    def test_timestamp(self):
        """
        Test the creation of a timestamp string but generation
        """
        sequencer = Sequencer()
        current = sequencer.get_sequence_id()

        log.debug("current seq_id: %s", sequencer.get_sequence_id())
        self.assertIsNotNone(current)

        self.assertEqual(sequencer.increment_sequence_index(), 0)
        self.assertEqual(sequencer.increment_sequence_index(), 1)
        self.assertEqual(sequencer.increment_sequence_index(), 2)
        self.assertEqual(sequencer.increment_sequence_index(), 3)
        self.assertEqual(sequencer.get_sequence_id(), current)

        sequencer.reset_sequence_id()
        log.debug("current seq_id: %s", sequencer.get_sequence_id())
        self.assertNotEqual(sequencer.get_sequence_id(), current)

