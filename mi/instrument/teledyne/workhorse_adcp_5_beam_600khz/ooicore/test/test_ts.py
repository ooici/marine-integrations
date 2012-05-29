#!/usr/bin/env python

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'

"""
@package mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.test.test_ts
@file    ion/services/mi/drivers/vadcp/test/test_ts.py
@author Carlos Rueda
@brief Unit tests for timestamp related functions
"""


from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.ts_filter import _partial_match
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.ts_filter import TS_OPEN_STRING
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.ts_filter import TS_OPEN_SAFE_SIZE
from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.util.ts_filter import TS_CLOSE_STRING

from unittest import TestCase
from nose.plugins.attrib import attr


@attr('UNIT', group='mi')
class Test(TestCase):
    """
    Unit tests for timestamp related functions
    """

    def test_partial_match_open(self):
        pairs = [
            (('123456', ''), "123456"),
            (('123456', '<'), "123456<"),
            (('123456', '<OO'), "123456<OO"),
            (('123456', '<OOI-TS'), "123456<OOI-TS"),
            (('', '<OOI-TS'), "<OOI-TS"),
            (('', '<OOI-'), "<OOI-"),
            (('', '<'), "<"),
            (('', '<OOI-TS 2012-05-22T'), "<OOI-TS 2012-05-22T"),
            (('foo bar ', '<OOI-TS 2012-05-'), "foo bar <OOI-TS 2012-05-"),
        ]
        for expected, input in pairs:
            returned = _partial_match(input, TS_OPEN_STRING, TS_OPEN_SAFE_SIZE)
#            print "%40s ==> %s" % ("'" + input + "'", returned)
            self.assertEqual(expected, returned)

    def test_partial_match_close(self):
        pairs = [
                (('123456', ''), "123456"),
                (('123456', '<'), "123456<"),
                (('123456', '<\\00I'), "123456<\\00I"),
                (('123456', '<\\00I-TS>\r\n'), "123456<\\00I-TS>\r\n"),
                (('', '<\\00I-TS>\r\n'), "<\\00I-TS>\r\n"),
                (('', '<\\00I-'), "<\\00I-"),
                (('', '<'), "<"),
                (('foo bar ', '<\\00I-TS>'), "foo bar <\\00I-TS>"),
        ]
        for expected, input in pairs:
            returned = _partial_match(input, TS_CLOSE_STRING,
                                      len(TS_CLOSE_STRING))
#            print "%40s ==> %s" % ("'" + input + "'", returned)
            self.assertEqual(expected, returned)
