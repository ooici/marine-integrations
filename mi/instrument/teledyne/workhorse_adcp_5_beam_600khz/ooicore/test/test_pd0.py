#!/usr/bin/env python

__author__ = "Carlos Rueda"
__license__ = 'Apache 2.0'

"""
"""


from mi.instrument.teledyne.workhorse_adcp_5_beam_600khz.ooicore.pd0 import PD0DataStructure

from mi.core.unit_test import MiUnitTest
from nose.plugins.attrib import attr


def _read_sample(filename='mi/instrument/teledyne'
                          '/workhorse_adcp_5_beam_600khz/ooicore/resource'
                          '/pd0_sample.bin'):
    sample = file(filename, 'r')
    data = sample.read()
    sample.close()
    print "len(data) = %d" % len(data)
    return data


@attr('UNIT', group='mi')
class Test(MiUnitTest):
    """
    Unit tests for PD0DataStructure
    """

    def test_pd0(self):
        data = _read_sample()
        
        pd0 = PD0DataStructure(data)

        print "PD0 = %s" % pd0

        s = pd0.getNumberOfBytesInEnsemble()
        self.assertEqual(s, 952)

        no_data_types = pd0.getNumberOfDataTypes()
        self.assertEqual(no_data_types, 6)

        header_len = pd0.getHeaderLength()
        self.assertEqual(header_len, 6 + 2*no_data_types)

