#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_vel3d_l_wfp
@file marine-integrations/mi/dataset/parser/test/test_vel3d_l_wfp.py
@author Steve Myerson (Raytheon)
@brief Test code for a vel3d_l_wfp parser for recovered data
"""

from nose.plugins.attrib import attr

from mi.core.log import get_logger; log = get_logger()
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticleKey
from StringIO import StringIO

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

from mi.dataset.parser.vel3d_l_wfp import \
    Vel3dLWfpStateKey, \
    Vel3dLWfpParser, \
    Vel3dLWfpInstrumentParticle, \
    Vel3dLWfpMetadataParticle

# Recovered Record #1 has 1 instrument record.
REC_RECORD_1 = \
    '\x00\x00\x01\x46\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x01\x02\x03\x01\x02'  \
    '\xDD\x07\x00\x00\xCA\x42\x00\x00\x49\x43\x00\x80\x96\x43\x00\x40'  \
    '\x7A\x44\x00\x20\xFA\x44\x00\x90\x3B\x45\x00\x44\x1C\x46\x00\x42'  \
    '\x9C\x46\x00\x62\xEA\x46\x00\x41\x1C\x47\x52\xE6\x3C\x32\x52\xE6'  \
    '\x54\xDF'

# Recovered Record #2 has 2 instrument records.
REC_RECORD_2 = \
    '\x00\x00\x01\x75\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x02\x03\x04\x02\x03'  \
    '\xDD\x07\x00\x00\xCC\x42\x00\x00\x4A\x43\x00\x00\x97\x43\x00\x80'  \
    '\x7A\x44\x00\x40\xFA\x44\x00\xA0\x3B\x45\x00\x48\x1C\x46\x00\x44'  \
    '\x9C\x46\x00\x64\xEA\x46\x00\x42\x1C\x47\x03\x04\x05\x03\x04\xDD'  \
    '\x07\x00\x00\xCE\x42\x00\x00\x4B\x43\x00\x80\x97\x43\x00\xC0\x7A'  \
    '\x44\x00\x60\xFA\x44\x00\xB0\x3B\x45\x00\x4C\x1C\x46\x00\x46\x9C'  \
    '\x46\x00\x66\xEA\x46\x00\x43\x1C\x47\x52\xE6\x3C\x33\x52\xE6\x54'  \
    '\xE0'

# Recovered Record #3 has 3 instrument records.
REC_RECORD_3 = \
    '\x00\x00\x01\xA4\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x04\x05\x06\x04\x05'  \
    '\xDD\x07\x00\x00\xD0\x42\x00\x00\x4C\x43\x00\x00\x98\x43\x00\x00'  \
    '\x7B\x44\x00\x80\xFA\x44\x00\xC0\x3B\x45\x00\x50\x1C\x46\x00\x48'  \
    '\x9C\x46\x00\x68\xEA\x46\x00\x44\x1C\x47\x05\x06\x07\x05\x06\xDD'  \
    '\x07\x00\x00\xD2\x42\x00\x00\x4D\x43\x00\x80\x98\x43\x00\x40\x7B'  \
    '\x44\x00\xA0\xFA\x44\x00\xD0\x3B\x45\x00\x54\x1C\x46\x00\x4A\x9C'  \
    '\x46\x00\x6A\xEA\x46\x00\x45\x1C\x47\x06\x07\x08\x06\x07\xDD\x07'  \
    '\x00\x00\xD4\x42\x00\x00\x4E\x43\x00\x00\x99\x43\x00\x80\x7B\x44'  \
    '\x00\xC0\xFA\x44\x00\xE0\x3B\x45\x00\x58\x1C\x46\x00\x4C\x9C\x46'  \
    '\x00\x6C\xEA\x46\x00\x46\x1C\x47\x52\xE6\x3C\x34\x52\xE6\x54\xE1'

# Recovered Record #4 has 4 instrument records.
REC_RECORD_4 = \
    '\x00\x00\x01\xD3\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x07\x08\x09\x07\x08'  \
    '\xDD\x07\x00\x00\xD6\x42\x00\x00\x4F\x43\x00\x80\x99\x43\x00\xC0'  \
    '\x7B\x44\x00\xE0\xFA\x44\x00\xF0\x3B\x45\x00\x5C\x1C\x46\x00\x4E'  \
    '\x9C\x46\x00\x6E\xEA\x46\x00\x47\x1C\x47\x08\x09\x0A\x08\x09\xDD'  \
    '\x07\x00\x00\xD8\x42\x00\x00\x50\x43\x00\x00\x9A\x43\x00\x00\x7C'  \
    '\x44\x00\x00\xFB\x44\x00\x00\x3C\x45\x00\x60\x1C\x46\x00\x50\x9C'  \
    '\x46\x00\x70\xEA\x46\x00\x48\x1C\x47\x09\x0A\x0B\x09\x0A\xDD\x07'  \
    '\x00\x00\xDA\x42\x00\x00\x51\x43\x00\x80\x9A\x43\x00\x40\x7C\x44'  \
    '\x00\x20\xFB\x44\x00\x10\x3C\x45\x00\x64\x1C\x46\x00\x52\x9C\x46'  \
    '\x00\x72\xEA\x46\x00\x49\x1C\x47\x0A\x0B\x0C\x0A\x0B\xDD\x07\x00'  \
    '\x00\xDC\x42\x00\x00\x52\x43\x00\x00\x9B\x43\x00\x80\x7C\x44\x00'  \
    '\x40\xFB\x44\x00\x20\x3C\x45\x00\x68\x1C\x46\x00\x54\x9C\x46\x00'  \
    '\x74\xEA\x46\x00\x4A\x1C\x47\x52\xE6\x3C\x35\x52\xE6\x54\xE2'

# Recovered Record #10 has 10 instrument records.
REC_RECORD_10 = \
    '\x00\x00\x02\xED\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x01\x02\x03\x01\x02'  \
    '\xDD\x07\x00\x00\xCA\x42\x00\x00\x49\x43\x00\x80\x96\x43\x00\x40'  \
    '\x7A\x44\x00\x20\xFA\x44\x00\x90\x3B\x45\x00\x44\x1C\x46\x00\x42'  \
    '\x9C\x46\x00\x62\xEA\x46\x00\x41\x1C\x47\x02\x03\x04\x02\x03\xDD'  \
    '\x07\x00\x00\xCC\x42\x00\x00\x4A\x43\x00\x00\x97\x43\x00\x80\x7A'  \
    '\x44\x00\x40\xFA\x44\x00\xA0\x3B\x45\x00\x48\x1C\x46\x00\x44\x9C'  \
    '\x46\x00\x64\xEA\x46\x00\x42\x1C\x47\x03\x04\x05\x03\x04\xDD\x07'  \
    '\x00\x00\xCE\x42\x00\x00\x4B\x43\x00\x80\x97\x43\x00\xC0\x7A\x44'  \
    '\x00\x60\xFA\x44\x00\xB0\x3B\x45\x00\x4C\x1C\x46\x00\x46\x9C\x46'  \
    '\x00\x66\xEA\x46\x00\x43\x1C\x47\x04\x05\x06\x04\x05\xDD\x07\x00'  \
    '\x00\xD0\x42\x00\x00\x4C\x43\x00\x00\x98\x43\x00\x00\x7B\x44\x00'  \
    '\x80\xFA\x44\x00\xC0\x3B\x45\x00\x50\x1C\x46\x00\x48\x9C\x46\x00'  \
    '\x68\xEA\x46\x00\x44\x1C\x47\x05\x06\x07\x05\x06\xDD\x07\x00\x00'  \
    '\xD2\x42\x00\x00\x4D\x43\x00\x80\x98\x43\x00\x40\x7B\x44\x00\xA0'  \
    '\xFA\x44\x00\xD0\x3B\x45\x00\x54\x1C\x46\x00\x4A\x9C\x46\x00\x6A'  \
    '\xEA\x46\x00\x45\x1C\x47\x06\x07\x08\x06\x07\xDD\x07\x00\x00\xD4'  \
    '\x42\x00\x00\x4E\x43\x00\x00\x99\x43\x00\x80\x7B\x44\x00\xC0\xFA'  \
    '\x44\x00\xE0\x3B\x45\x00\x58\x1C\x46\x00\x4C\x9C\x46\x00\x6C\xEA'  \
    '\x46\x00\x46\x1C\x47\x07\x08\x09\x07\x08\xDD\x07\x00\x00\xD6\x42'  \
    '\x00\x00\x4F\x43\x00\x80\x99\x43\x00\xC0\x7B\x44\x00\xE0\xFA\x44'  \
    '\x00\xF0\x3B\x45\x00\x5C\x1C\x46\x00\x4E\x9C\x46\x00\x6E\xEA\x46'  \
    '\x00\x47\x1C\x47\x08\x09\x0A\x08\x09\xDD\x07\x00\x00\xD8\x42\x00'  \
    '\x00\x50\x43\x00\x00\x9A\x43\x00\x00\x7C\x44\x00\x00\xFB\x44\x00'  \
    '\x00\x3C\x45\x00\x60\x1C\x46\x00\x50\x9C\x46\x00\x70\xEA\x46\x00'  \
    '\x48\x1C\x47\x09\x0A\x0B\x09\x0A\xDD\x07\x00\x00\xDA\x42\x00\x00'  \
    '\x51\x43\x00\x80\x9A\x43\x00\x40\x7C\x44\x00\x20\xFB\x44\x00\x10'  \
    '\x3C\x45\x00\x64\x1C\x46\x00\x52\x9C\x46\x00\x72\xEA\x46\x00\x49'  \
    '\x1C\x47\x0A\x0B\x0C\x0A\x0B\xDD\x07\x00\x00\xDC\x42\x00\x00\x52'  \
    '\x43\x00\x00\x9B\x43\x00\x80\x7C\x44\x00\x40\xFB\x44\x00\x20\x3C'  \
    '\x45\x00\x68\x1C\x46\x00\x54\x9C\x46\x00\x74\xEA\x46\x00\x4A\x1C'  \
    '\x47\x52\xE6\x3C\x32\x52\xE6\x54\xDF'

# Recovered Record 2_3 has 2 SIO blocks, with 3 records in each block.
REC_RECORD_2_3 = \
    '\x00\x00\x01\xA4\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x01\x02\x03\x01\x02'  \
    '\xDD\x07\x00\x00\xCA\x42\x00\x00\x49\x43\x00\x80\x96\x43\x00\x40'  \
    '\x7A\x44\x00\x20\xFA\x44\x00\x90\x3B\x45\x00\x44\x1C\x46\x00\x42'  \
    '\x9C\x46\x00\x62\xEA\x46\x00\x41\x1C\x47\x02\x03\x04\x02\x03\xDD'  \
    '\x07\x00\x00\xCC\x42\x00\x00\x4A\x43\x00\x00\x97\x43\x00\x80\x7A'  \
    '\x44\x00\x40\xFA\x44\x00\xA0\x3B\x45\x00\x48\x1C\x46\x00\x44\x9C'  \
    '\x46\x00\x64\xEA\x46\x00\x42\x1C\x47\x03\x04\x05\x03\x04\xDD\x07'  \
    '\x00\x00\xCE\x42\x00\x00\x4B\x43\x00\x80\x97\x43\x00\xC0\x7A\x44'  \
    '\x00\x60\xFA\x44\x00\xB0\x3B\x45\x00\x4C\x1C\x46\x00\x46\x9C\x46'  \
    '\x00\x66\xEA\x46\x00\x43\x1C\x47\x52\xE6\x3C\x32\x52\xE6\x54\xDF'  \
    '\x00\x00\x01\xA4\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58'  \
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x04\x05\x06\x04\x05'  \
    '\xDD\x07\x00\x00\xD0\x42\x00\x00\x4C\x43\x00\x00\x98\x43\x00\x00'  \
    '\x7B\x44\x00\x80\xFA\x44\x00\xC0\x3B\x45\x00\x50\x1C\x46\x00\x48'  \
    '\x9C\x46\x00\x68\xEA\x46\x00\x44\x1C\x47\x05\x06\x07\x05\x06\xDD'  \
    '\x07\x00\x00\xD2\x42\x00\x00\x4D\x43\x00\x80\x98\x43\x00\x40\x7B'  \
    '\x44\x00\xA0\xFA\x44\x00\xD0\x3B\x45\x00\x54\x1C\x46\x00\x4A\x9C'  \
    '\x46\x00\x6A\xEA\x46\x00\x45\x1C\x47\x06\x07\x08\x06\x07\xDD\x07'  \
    '\x00\x00\xD4\x42\x00\x00\x4E\x43\x00\x00\x99\x43\x00\x80\x7B\x44'  \
    '\x00\xC0\xFA\x44\x00\xE0\x3B\x45\x00\x58\x1C\x46\x00\x4C\x9C\x46'  \
    '\x00\x6C\xEA\x46\x00\x46\x1C\x47\x52\xE6\x3C\x33\x52\xE6\x54\xE0'

# Expected results
EXPECTED_FIELDS_RECORD_1_1 = (1, 2, 3, 1, 2, 2013, 101.0, 201.0, 301.0,
                              1001.0, 2001.0, 3001.0,
                              10001.0, 20001.0, 30001.0, 40001.0)

EXPECTED_FIELDS_RECORD_1_META = (1390826719, 1390820402, 1390826719, 65535, 1)


EXPECTED_FIELDS_RECORD_2_1 = (2, 3, 4, 2, 3, 2013, 102.0, 202.0, 302.0,
                              1002.0, 2002.0, 3002.0,
                              10002.0, 20002.0, 30002.0, 40002.0)

EXPECTED_FIELDS_RECORD_2_2 = (3, 4, 5, 3, 4, 2013, 103.0, 203.0, 303.0,
                              1003.0, 2003.0, 3003.0,
                              10003.0, 20003.0, 30003.0, 40003.0)

EXPECTED_FIELDS_RECORD_2_META = (1390826720, 1390820403, 1390826720, 65535, 2)


EXPECTED_FIELDS_RECORD_3_1 = (4, 5, 6, 4, 5, 2013, 104.0, 204.0, 304.0,
                              1004.0, 2004.0, 3004.0,
                              10004.0, 20004.0, 30004.0, 40004.0)

EXPECTED_FIELDS_RECORD_3_2 = (5, 6, 7, 5, 6, 2013, 105.0, 205.0, 305.0,
                              1005.0, 2005.0, 3005.0,
                              10005.0, 20005.0, 30005.0, 40005.0)

EXPECTED_FIELDS_RECORD_3_3 = (6, 7, 8, 6, 7, 2013, 106.0, 206.0, 306.0,
                              1006.0, 2006.0, 3006.0,
                              10006.0, 20006.0, 30006.0, 40006.0)

EXPECTED_FIELDS_RECORD_3_META = (1390826721, 1390820404, 1390826721, 65535, 3)


EXPECTED_FIELDS_RECORD_4_1 = (7, 8, 9, 7, 8, 2013, 107.0, 207.0, 307.0,
                              1007.0, 2007.0, 3007.0,
                              10007.0, 20007.0, 30007.0, 40007.0)

EXPECTED_FIELDS_RECORD_4_2 = (8, 9, 10, 8, 9, 2013, 108.0, 208.0, 308.0,
                              1008.0, 2008.0, 3008.0,
                              10008.0, 20008.0, 30008.0, 40008.0)

EXPECTED_FIELDS_RECORD_4_3 = (9, 10, 11, 9, 10, 2013, 109.0, 209.0, 309.0,
                              1009.0, 2009.0, 3009.0,
                              10009.0, 20009.0, 30009.0, 40009.0)

EXPECTED_FIELDS_RECORD_4_4 = (10, 11, 12, 10, 11, 2013, 110.0, 210.0, 310.0,
                              1010.0, 2010.0, 3010.0,
                              10010.0, 20010.0, 30010.0, 40010.0)

EXPECTED_FIELDS_RECORD_4_META = (1390826722, 1390820405, 1390826722, 65535, 4)


EXPECTED_FIELDS_RECORD_10_1 = (1, 2, 3, 1, 2, 2013, 101.0, 201.0, 301.0,
                               1001.0, 2001.0, 3001.0,
                               10001.0, 20001.0, 30001.0, 40001.0)

EXPECTED_FIELDS_RECORD_10_2 = (2, 3, 4, 2, 3, 2013, 102.0, 202.0, 302.0,
                               1002.0, 2002.0, 3002.0,
                               10002.0, 20002.0, 30002.0, 40002.0)

EXPECTED_FIELDS_RECORD_10_3 = (3, 4, 5, 3, 4, 2013, 103.0, 203.0, 303.0,
                               1003.0, 2003.0, 3003.0,
                               10003.0, 20003.0, 30003.0, 40003.0)

EXPECTED_FIELDS_RECORD_10_4 = (4, 5, 6, 4, 5, 2013, 104.0, 204.0, 304.0,
                               1004.0, 2004.0, 3004.0,
                               10004.0, 20004.0, 30004.0, 40004.0)

EXPECTED_FIELDS_RECORD_10_5 = (5, 6, 7, 5, 6, 2013, 105.0, 205.0, 305.0,
                               1005.0, 2005.0, 3005.0,
                               10005.0, 20005.0, 30005.0, 40005.0)

EXPECTED_FIELDS_RECORD_10_6 = (6, 7, 8, 6, 7, 2013, 106.0, 206.0, 306.0,
                               1006.0, 2006.0, 3006.0,
                               10006.0, 20006.0, 30006.0, 40006.0)

EXPECTED_FIELDS_RECORD_10_7 = (7, 8, 9, 7, 8, 2013, 107.0, 207.0, 307.0,
                               1007.0, 2007.0, 3007.0,
                               10007.0, 20007.0, 30007.0, 40007.0)

EXPECTED_FIELDS_RECORD_10_8 = (8, 9, 10, 8, 9, 2013, 108.0, 208.0, 308.0,
                               1008.0, 2008.0, 3008.0,
                               10008.0, 20008.0, 30008.0, 40008.0)

EXPECTED_FIELDS_RECORD_10_9 = (9, 10, 11, 9, 10, 2013, 109.0, 209.0, 309.0,
                               1009.0, 2009.0, 3009.0,
                               10009.0, 20009.0, 30009.0, 40009.0)

EXPECTED_FIELDS_RECORD_10_10 = (10, 11, 12, 10, 11, 2013, 110.0, 210.0, 310.0,
                                1010.0, 2010.0, 3010.0,
                                10010.0, 20010.0, 30010.0, 40010.0)

EXPECTED_FIELDS_RECORD_10_META = (1390826719, 1390820402, 1390826719, 65535, 10)


EXPECTED_FIELDS_RECORD_2_3_1_1 = (1, 2, 3, 1, 2, 2013, 101.0, 201.0, 301.0,
                                  1001.0, 2001.0, 3001.0,
                                  10001.0, 20001.0, 30001.0, 40001.0)

EXPECTED_FIELDS_RECORD_2_3_1_2 = (2, 3, 4, 2, 3, 2013, 102.0, 202.0, 302.0,
                                  1002.0, 2002.0, 3002.0,
                                  10002.0, 20002.0, 30002.0, 40002.0)

EXPECTED_FIELDS_RECORD_2_3_1_3 = (3, 4, 5, 3, 4, 2013, 103.0, 203.0, 303.0,
                                  1003.0, 2003.0, 3003.0,
                                  10003.0, 20003.0, 30003.0, 40003.0)

EXPECTED_FIELDS_RECORD_2_3_META_1 = (1390826719, 1390820402, 1390826719, 65535, 3)


EXPECTED_FIELDS_RECORD_2_3_2_1 = (4, 5, 6, 4, 5, 2013, 104.0, 204.0, 304.0,
                                  1004.0, 2004.0, 3004.0,
                                  10004.0, 20004.0, 30004.0, 40004.0)

EXPECTED_FIELDS_RECORD_2_3_2_2 = (5, 6, 7, 5, 6, 2013, 105.0, 205.0, 305.0,
                                  1005.0, 2005.0, 3005.0,
                                  10005.0, 20005.0, 30005.0, 40005.0)

EXPECTED_FIELDS_RECORD_2_3_2_3 = (6, 7, 8, 6, 7, 2013, 106.0, 206.0, 306.0,
                                  1006.0, 2006.0, 3006.0,
                                  10006.0, 20006.0, 30006.0, 40006.0)

EXPECTED_FIELDS_RECORD_2_3_META_2 = (1390826720, 1390820403, 1390826720, 65535, 3)

# The list of generated tests are the suggested tests, but there may
# be other tests needed to fully test your parser

@attr('UNIT', group='mi')
class Vel3dLWfpParserUnitTestCase(ParserUnitTestCase):
    """
    vel3d_l_wfp Parser unit test suite
    """
    def create_expected_results(self):
        """
        This function creates the expected particle results.
        """

        self.expected_particle_1_1 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_1_1, internal_timestamp=3566106123.0)

        self.expected_particle_2_1 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_1, internal_timestamp=3568874584.0)

        self.expected_particle_2_2 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_2, internal_timestamp=3571383845.0)

        self.expected_particle_3_1 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_3_1, internal_timestamp=3574152306.0)

        self.expected_particle_3_2 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_3_2, internal_timestamp=3576834367.0)

        self.expected_particle_3_3 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_3_3, internal_timestamp=3579602828.0)

        self.expected_particle_4_1 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_4_1, internal_timestamp=3582284889.0)

        self.expected_particle_4_2 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_4_2, internal_timestamp=3585053350.0)

        self.expected_particle_4_3 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_4_3, internal_timestamp=3587821811.0)

        self.expected_particle_4_4 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_4_4, internal_timestamp=3590503872.0)

        self.expected_particle_10_1 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_1, internal_timestamp=3566106123.0)

        self.expected_particle_10_2 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_2, internal_timestamp=3568874584.0)

        self.expected_particle_10_3 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_3, internal_timestamp=3571383845.0)

        self.expected_particle_10_4 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_4, internal_timestamp=3574152306.0)

        self.expected_particle_10_5 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_5, internal_timestamp=3576834367.0)

        self.expected_particle_10_6 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_6, internal_timestamp=3579602828.0)

        self.expected_particle_10_7 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_7, internal_timestamp=3582284889.0)

        self.expected_particle_10_8 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_8, internal_timestamp=3585053350.0)

        self.expected_particle_10_9 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_9, internal_timestamp=3587821811.0)

        self.expected_particle_10_10=  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_10, internal_timestamp=3590503872.0)

        self.expected_particle_1_meta = Vel3dLWfpMetadataParticle(
            EXPECTED_FIELDS_RECORD_1_META, internal_timestamp=3599815519.0)

        self.expected_particle_2_meta = Vel3dLWfpMetadataParticle(
            EXPECTED_FIELDS_RECORD_2_META, internal_timestamp=3583891131.0)

        self.expected_particle_3_meta = Vel3dLWfpMetadataParticle(
            EXPECTED_FIELDS_RECORD_3_META, internal_timestamp=3599815521.0)

        self.expected_particle_4_meta = Vel3dLWfpMetadataParticle(
            EXPECTED_FIELDS_RECORD_4_META, internal_timestamp=3599815522.0)

        self.expected_particle_10_meta = Vel3dLWfpMetadataParticle(
            EXPECTED_FIELDS_RECORD_10_META, internal_timestamp=3599815519.0)
        
        # The following are for the multiple block file.
        self.expected_particle_2_3_1_1 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_1_1, internal_timestamp=3566106123.0)
        
        self.expected_particle_2_3_1_2 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_1_2, internal_timestamp=3568874584.0)

        self.expected_particle_2_3_1_3 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_1_3, internal_timestamp=3571383845.0)

        self.expected_particle_2_3_2_1 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_2_1, internal_timestamp=3574152306.0)

        self.expected_particle_2_3_2_2 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_2_2, internal_timestamp=3576834367.0)

        self.expected_particle_2_3_2_3 =  Vel3dLWfpInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_2_3, internal_timestamp=3579602828.0)

        self.expected_particle_2_3_meta_1 = Vel3dLWfpMetadataParticle(
            EXPECTED_FIELDS_RECORD_2_3_META_1, internal_timestamp=3599815519.0)

        self.expected_particle_2_3_meta_2 = Vel3dLWfpMetadataParticle(
            EXPECTED_FIELDS_RECORD_2_3_META_2, internal_timestamp=3599815520.0)

    def create_parser(self, file_handle, new_state):
        """
        This function creates a Vel3d_l_Wfp parser.
        """
        if new_state is None:
            new_state = self.state
        parser = Vel3dLWfpParser(self.config, new_state, file_handle,
            self.state_callback, self.pub_callback, self.exception_callback)
        return parser

    def exception_callback(self, exception):
        """ Callback method to watch what comes in via the exception callback """
        self.exception_callback_value = exception
        log.info("EXCEPTION RECEIVED %s", exception)

    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
	        DataSetDriverConfigKeys.PARTICLE_MODULE:\
                'mi.dataset.parser.vel3d_l_wfp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: \
                ['Vel3dLWfpInstrumentParticle',
                 'Vel3dLWfpMetadataParticle']
	    }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None
        self.state = None
        self.maxDiff = None
        self.create_expected_results()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        log.info("=================== START MANY ======================")
        log.info("Many length %d", len(REC_RECORD_4))
        input_file = StringIO(REC_RECORD_4)
        self.parser = self.create_parser(input_file, self.state)

        log.info("MANY VERIFY RECORDS 1-4")
        result = self.parser.get_records(4)
        self.assertEqual(result, [self.expected_particle_4_1,
                                  self.expected_particle_4_2,
                                  self.expected_particle_4_3,
                                  self.expected_particle_4_4])

        self.assertEqual(self.publish_callback_value[0],
            self.expected_particle_4_1)

        self.assertEqual(self.publish_callback_value[1],
            self.expected_particle_4_2)

        self.assertEqual(self.publish_callback_value[2],
            self.expected_particle_4_3)

        self.assertEqual(self.publish_callback_value[3],
            self.expected_particle_4_4)

        log.info("MANY VERIFY METADATA RECORD")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_4_meta)

        log.info("=================== END MANY ======================")

    def test_long_stream(self):
        """
        Test a long stream
        """
        log.info("============== START LONG STREAM ==================")
        log.info("Long Stream length %d", len(REC_RECORD_10))
        input_file = StringIO(REC_RECORD_10)
        self.parser = self.create_parser(input_file, self.state)

        result = self.parser.get_records(10)
        self.assertEqual(result, [self.expected_particle_10_1,
                                  self.expected_particle_10_2,
                                  self.expected_particle_10_3,
                                  self.expected_particle_10_4,
                                  self.expected_particle_10_5,
                                  self.expected_particle_10_6,
                                  self.expected_particle_10_7,
                                  self.expected_particle_10_8,
                                  self.expected_particle_10_9,
                                  self.expected_particle_10_10])

        log.info("LONG STREAM VERIFY METADATA RECORD")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_10_meta)

        self.assertEqual(self.exception_callback_value, None)

        log.info("============== END LONG STREAM ==================")

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        log.info("============== START MID STATE START ==================")
        log.info("Mid State length %d", len(REC_RECORD_2_3))
        input_file = StringIO(REC_RECORD_2_3)

        # Skip past the first block.
        new_state = {Vel3dLWfpStateKey.POSITION: 432,
                     Vel3dLWfpStateKey.TIMESTAMP: 0.0}
        self.parser = self.create_parser(input_file, new_state)

        log.info("MID STATE VERIFY BLOCK 2, RECORDS 1-3 and METADATA")
        result = self.parser.get_records(4)
        self.assertEqual(result, [self.expected_particle_2_3_2_1,
                                  self.expected_particle_2_3_2_2,
                                  self.expected_particle_2_3_2_3,
                                  self.expected_particle_2_3_meta_2])

        log.info("MID STATE VERIFY STATE")
        self.assertEqual(self.parser._state[Vel3dLWfpStateKey.POSITION], 864)

        log.info("============== END MID STATE START ==================")

    def test_multiple_blocks(self):
        """
        This function verifies that multiple blocks can be read.
        """
        log.info("============== START MULTIPLE BLOCKS ==================")
        log.info("Multiple Blocks length %d", len(REC_RECORD_2_3))
        input_file = StringIO(REC_RECORD_2_3)
        self.parser = self.create_parser(input_file, self.state)

        result = self.parser.get_records(8)
        self.assertEqual(result, [self.expected_particle_2_3_1_1,
                                  self.expected_particle_2_3_1_2,
                                  self.expected_particle_2_3_1_3,
                                  self.expected_particle_2_3_meta_1,
                                  self.expected_particle_2_3_2_1,
                                  self.expected_particle_2_3_2_2,
                                  self.expected_particle_2_3_2_3,
                                  self.expected_particle_2_3_meta_2])

        log.info("============== END MULTIPLE BLOCKS ==================")

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and
        reading data, as if new data has been found and the state has
        changed
        """
        log.info("============== START SET STATE ==================")
        log.info("Set State length %d", len(REC_RECORD_2_3))
        input_file = StringIO(REC_RECORD_2_3)
        self.parser = self.create_parser(input_file, self.state)

        log.info("SET STATE VERIFY BLOCK 1 RECORDS 1-2")
        result = self.parser.get_records(2)
        self.assertEqual(result, [self.expected_particle_2_3_1_1,
                                      self.expected_particle_2_3_1_2])

        # Skip past the other records in block 1.
        log.info("SET STATE RESET STATE")
        new_state = {Vel3dLWfpStateKey.POSITION: 432,
                     Vel3dLWfpStateKey.TIMESTAMP: 0.0}
        self.parser.set_state(new_state)

        log.info("SET STATE VERIFY BLOCK 2 ALL RECORDS")
        result = self.parser.get_records(4)
        self.assertEqual(result, [self.expected_particle_2_3_2_1,
                                  self.expected_particle_2_3_2_2,
                                  self.expected_particle_2_3_2_3,
                                  self.expected_particle_2_3_meta_2])

        log.info("SET STATE VERIFY STATE")
        self.assertEqual(self.parser._state[Vel3dLWfpStateKey.POSITION], 864)

        log.info("============== END SET STATE ==================")

    def test_simple_no_decimation(self):
        """
	    Read test data and pull out data particles one at a time.
	    Assert that the results are those we expected.
	    """
        log.info("============== START SIMPLE WITHOUT DECIMATION ==================")
        log.info("Simple length %d", len(REC_RECORD_3))
        input_file = StringIO(REC_RECORD_3)
        self.parser = self.create_parser(input_file, self.state)

        log.info("SIMPLE WITHOUT DECIMATION VERIFY RECORD 1")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_3_1)

        log.info("SIMPLE WITHOUT DECIMATION VERIFY RECORD 2")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_3_2)

        log.info("SIMPLE WITHOUT DECIMATION VERIFY RECORD 3")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_3_3)

        log.info("SIMPLE WITHOUT DECIMATION VERIFY METADATA RECORD")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_3_meta)

        log.info("============== END SIMPLE WITHOUT DECIMATION ==================")

    def verify_contents(self, actual_particle, expected_particle_):
        self.assertEqual(actual_particle, [expected_particle_])
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], expected_particle_)
