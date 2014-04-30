#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_vel3d_l_wfp
@file marine-integrations/mi/dataset/parser/test/test_vel3d_l_wfp.py
@author Steve Myerson (Raytheon)
@brief Test code for a vel3d_l_wfp data parser
"""

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticleKey
from StringIO import StringIO

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.parser.vel3d_l_wfp_sio_mule import \
    Vel3dLWfpSioMuleParser, \
    Vel3dLWfpSioMuleInstrumentParticle, \
    Vel3dLWfpSioMuleMetadataParticle

# SIO Record #1 has 1 instrument record.
SIO_RECORD_1 = \
    '\x01\x57\x41\x31\x32\x33\x34\x35\x36\x39\x5F\x30\x31\x35\x32\x48'  \
    '\x35\x31\x46\x33\x35\x38\x33\x42\x5F\x30\x31\x5F\x41\x39\x30\x34'  \
    '\x02\x52\x01\x00\x00\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58'  \
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
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x01\x02\x03\x01'  \
    '\x02\xDD\x07\x00\x00\x20\x41\x00\x00\xA0\x41\x00\x00\xF0\x41\x00'  \
    '\x00\xCA\x42\x00\x00\x49\x43\x00\x80\x96\x43\x00\x40\x7A\x44\x00'  \
    '\x20\xFA\x44\x00\x90\x3B\x45\x00\x10\x7A\x45\x52\xE6\x3C\x32\x52'  \
    '\xE6\x54\xDF\x03'

# SIO Record #2 has 2 instrument records.
SIO_RECORD_2 = \
    '\x01\x57\x41\x31\x32\x33\x34\x35\x36\x39\x5F\x30\x31\x38\x33\x48'  \
    '\x35\x31\x46\x33\x35\x38\x33\x42\x5F\x30\x32\x5F\x41\x31\x44\x32'  \
    '\x02\x83\x01\x00\x00\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58'  \
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
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x02\x03\x04\x02'  \
    '\x03\xDD\x07\x00\x00\x30\x41\x00\x00\xA8\x41\x00\x00\xF8\x41\x00'  \
    '\x00\xCC\x42\x00\x00\x4A\x43\x00\x00\x97\x43\x00\x80\x7A\x44\x00'  \
    '\x40\xFA\x44\x00\xA0\x3B\x45\x00\x20\x7A\x45\x03\x04\x05\x03\x04'  \
    '\xDD\x07\x00\x00\x40\x41\x00\x00\xB0\x41\x00\x00\x00\x42\x00\x00'  \
    '\xCE\x42\x00\x00\x4B\x43\x00\x80\x97\x43\x00\xC0\x7A\x44\x00\x60'  \
    '\xFA\x44\x00\xB0\x3B\x45\x00\x30\x7A\x45\x52\xE6\x3C\x33\x52\xE6'  \
    '\x54\xE0\x00\x0B\x03'

# SIO Record #3 has 3 instrument records.
SIO_RECORD_3 = \
    '\x01\x57\x41\x31\x32\x33\x34\x35\x36\x39\x5F\x30\x31\x42\x30\x48'  \
    '\x35\x31\x46\x33\x35\x38\x33\x42\x5F\x30\x33\x5F\x43\x31\x32\x36'  \
    '\x02\xB0\x01\x00\x00\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58'  \
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
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x04\x05\x06\x04'  \
    '\x05\xDD\x07\x00\x00\x50\x41\x00\x00\xB8\x41\x00\x00\x04\x42\x00'  \
    '\x00\xD0\x42\x00\x00\x4C\x43\x00\x00\x98\x43\x00\x00\x7B\x44\x00'  \
    '\x80\xFA\x44\x00\xC0\x3B\x45\x00\x40\x7A\x45\x05\x06\x07\x05\x06'  \
    '\xDD\x07\x00\x00\x60\x41\x00\x00\xC0\x41\x00\x00\x08\x42\x00\x00'  \
    '\xD2\x42\x00\x00\x4D\x43\x00\x80\x98\x43\x00\x40\x7B\x44\x00\xA0'  \
    '\xFA\x44\x00\xD0\x3B\x45\x00\x50\x7A\x45\x06\x07\x08\x06\x07\xDD'  \
    '\x07\x00\x00\x70\x41\x00\x00\xC8\x41\x00\x00\x0C\x42\x00\x00\xD4'  \
    '\x42\x00\x00\x4E\x43\x00\x00\x99\x43\x00\x80\x7B\x44\x00\xC0\xFA'  \
    '\x44\x00\xE0\x3B\x45\x00\x60\x7A\x45\x52\xE6\x3C\x34\x52\xE6\x54'  \
    '\xE1\x03'

# SIO Record #4 has 4 instrument records.
SIO_RECORD_4 = \
    '\x01\x57\x41\x31\x32\x33\x34\x35\x36\x39\x5F\x30\x31\x45\x31\x48'  \
    '\x35\x31\x46\x33\x35\x38\x33\x42\x5F\x30\x34\x5F\x30\x36\x42\x39'  \
    '\x02\xE1\x01\x00\x00\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58'  \
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
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x07\x08\x09\x07'  \
    '\x08\xDD\x07\x00\x00\x80\x41\x00\x00\xD0\x41\x00\x00\x10\x42\x00'  \
    '\x00\xD6\x42\x00\x00\x4F\x43\x00\x80\x99\x43\x00\xC0\x7B\x44\x00'  \
    '\xE0\xFA\x44\x00\xF0\x3B\x45\x00\x70\x7A\x45\x08\x09\x0A\x08\x09'  \
    '\xDD\x07\x00\x00\x88\x41\x00\x00\xD8\x41\x00\x00\x14\x42\x00\x00'  \
    '\xD8\x42\x00\x00\x50\x43\x00\x00\x9A\x43\x00\x00\x7C\x44\x00\x00'  \
    '\xFB\x44\x00\x00\x3C\x45\x00\x80\x7A\x45\x09\x0A\x0B\x09\x0A\xDD'  \
    '\x07\x00\x00\x90\x41\x00\x00\xE0\x41\x00\x00\x18\x42\x00\x00\xDA'  \
    '\x42\x00\x00\x51\x43\x00\x80\x9A\x43\x00\x40\x7C\x44\x00\x20\xFB'  \
    '\x44\x00\x10\x3C\x45\x00\x90\x7A\x45\x0A\x0B\x0C\x0A\x0B\xDD\x07'  \
    '\x00\x00\x98\x41\x00\x00\xE8\x41\x00\x00\x1C\x42\x00\x00\xDC\x42'  \
    '\x00\x00\x52\x43\x00\x00\x9B\x43\x00\x80\x7C\x44\x00\x40\xFB\x44'  \
    '\x00\x20\x3C\x45\x00\xA0\x7A\x45\x52\xE6\x3C\x35\x52\xE6\x54\xE2'  \
    '\x00\x0D\x03'

# SIO Record #10 has 10 instrument records.
SIO_RECORD_10 = \
    '\x01\x57\x41\x31\x32\x33\x34\x35\x36\x39\x5F\x30\x32\x46\x42\x48'  \
    '\x35\x31\x46\x33\x35\x38\x33\x42\x5F\x30\x31\x5F\x31\x30\x43\x41'  \
    '\x02\xFB\x02\x00\x00\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58'  \
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
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x01\x02\x03\x01'  \
    '\x02\xDD\x07\x00\x00\x20\x41\x00\x00\xA0\x41\x00\x00\xF0\x41\x00'  \
    '\x00\xCA\x42\x00\x00\x49\x43\x00\x80\x96\x43\x00\x40\x7A\x44\x00'  \
    '\x20\xFA\x44\x00\x90\x3B\x45\x00\x10\x7A\x45\x02\x03\x04\x02\x03'  \
    '\xDD\x07\x00\x00\x30\x41\x00\x00\xA8\x41\x00\x00\xF8\x41\x00\x00'  \
    '\xCC\x42\x00\x00\x4A\x43\x00\x00\x97\x43\x00\x80\x7A\x44\x00\x40'  \
    '\xFA\x44\x00\xA0\x3B\x45\x00\x20\x7A\x45\x03\x04\x05\x03\x04\xDD'  \
    '\x07\x00\x00\x40\x41\x00\x00\xB0\x41\x00\x00\x00\x42\x00\x00\xCE'  \
    '\x42\x00\x00\x4B\x43\x00\x80\x97\x43\x00\xC0\x7A\x44\x00\x60\xFA'  \
    '\x44\x00\xB0\x3B\x45\x00\x30\x7A\x45\x04\x05\x06\x04\x05\xDD\x07'  \
    '\x00\x00\x50\x41\x00\x00\xB8\x41\x00\x00\x04\x42\x00\x00\xD0\x42'  \
    '\x00\x00\x4C\x43\x00\x00\x98\x43\x00\x00\x7B\x44\x00\x80\xFA\x44'  \
    '\x00\xC0\x3B\x45\x00\x40\x7A\x45\x05\x06\x07\x05\x06\xDD\x07\x00'  \
    '\x00\x60\x41\x00\x00\xC0\x41\x00\x00\x08\x42\x00\x00\xD2\x42\x00'  \
    '\x00\x4D\x43\x00\x80\x98\x43\x00\x40\x7B\x44\x00\xA0\xFA\x44\x00'  \
    '\xD0\x3B\x45\x00\x50\x7A\x45\x06\x07\x08\x06\x07\xDD\x07\x00\x00'  \
    '\x70\x41\x00\x00\xC8\x41\x00\x00\x0C\x42\x00\x00\xD4\x42\x00\x00'  \
    '\x4E\x43\x00\x00\x99\x43\x00\x80\x7B\x44\x00\xC0\xFA\x44\x00\xE0'  \
    '\x3B\x45\x00\x60\x7A\x45\x07\x08\x09\x07\x08\xDD\x07\x00\x00\x80'  \
    '\x41\x00\x00\xD0\x41\x00\x00\x10\x42\x00\x00\xD6\x42\x00\x00\x4F'  \
    '\x43\x00\x80\x99\x43\x00\xC0\x7B\x44\x00\xE0\xFA\x44\x00\xF0\x3B'  \
    '\x45\x00\x70\x7A\x45\x08\x09\x0A\x08\x09\xDD\x07\x00\x00\x88\x41'  \
    '\x00\x00\xD8\x41\x00\x00\x14\x42\x00\x00\xD8\x42\x00\x00\x50\x43'  \
    '\x00\x00\x9A\x43\x00\x00\x7C\x44\x00\x00\xFB\x44\x00\x00\x3C\x45'  \
    '\x00\x80\x7A\x45\x09\x0A\x0B\x09\x0A\xDD\x07\x00\x00\x90\x41\x00'  \
    '\x00\xE0\x41\x00\x00\x18\x42\x00\x00\xDA\x42\x00\x00\x51\x43\x00'  \
    '\x80\x9A\x43\x00\x40\x7C\x44\x00\x20\xFB\x44\x00\x10\x3C\x45\x00'  \
    '\x90\x7A\x45\x0A\x0B\x0C\x0A\x0B\xDD\x07\x00\x00\x98\x41\x00\x00'  \
    '\xE8\x41\x00\x00\x1C\x42\x00\x00\xDC\x42\x00\x00\x52\x43\x00\x00'  \
    '\x9B\x43\x00\x80\x7C\x44\x00\x40\xFB\x44\x00\x20\x3C\x45\x00\xA0'  \
    '\x7A\x45\x52\xE6\x3C\x32\x52\xE6\x54\xDF\x00\x0A\x03'

# SIO Record 2_3 has 2 SIO blocks, with 3 records in each block.
SIO_RECORD_2_3 = \
    '\x01\x57\x41\x31\x32\x33\x34\x35\x36\x39\x5F\x30\x31\x42\x32\x48'  \
    '\x35\x31\x46\x33\x35\x38\x33\x42\x5F\x30\x31\x5F\x44\x31\x31\x32'  \
    '\x02\xB2\x01\x00\x00\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58'  \
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
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x01\x02\x03\x01'  \
    '\x02\xDD\x07\x00\x00\x20\x41\x00\x00\xA0\x41\x00\x00\xF0\x41\x00'  \
    '\x00\xCA\x42\x00\x00\x49\x43\x00\x80\x96\x43\x00\x40\x7A\x44\x00'  \
    '\x20\xFA\x44\x00\x90\x3B\x45\x00\x10\x7A\x45\x02\x03\x04\x02\x03'  \
    '\xDD\x07\x00\x00\x30\x41\x00\x00\xA8\x41\x00\x00\xF8\x41\x00\x00'  \
    '\xCC\x42\x00\x00\x4A\x43\x00\x00\x97\x43\x00\x80\x7A\x44\x00\x40'  \
    '\xFA\x44\x00\xA0\x3B\x45\x00\x20\x7A\x45\x03\x04\x05\x03\x04\xDD'  \
    '\x07\x00\x00\x40\x41\x00\x00\xB0\x41\x00\x00\x00\x42\x00\x00\xCE'  \
    '\x42\x00\x00\x4B\x43\x00\x80\x97\x43\x00\xC0\x7A\x44\x00\x60\xFA'  \
    '\x44\x00\xB0\x3B\x45\x00\x30\x7A\x45\x52\xE6\x3C\x32\x52\xE6\x54'  \
    '\xDF\x00\x0A\x03' \
    '\x01\x57\x41\x31\x32\x33\x34\x35\x36\x39\x5F\x30\x31\x42\x30\x48'  \
    '\x35\x31\x46\x33\x35\x38\x33\x42\x5F\x30\x32\x5F\x45\x30\x37\x33'  \
    '\x02\xB0\x01\x00\x00\x31\x32\x33\xFF\xFF\x00\x00\x58\x58\x58\x58'  \
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
    '\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x58\x04\x05\x06\x04'  \
    '\x05\xDD\x07\x00\x00\x50\x41\x00\x00\xB8\x41\x00\x00\x04\x42\x00'  \
    '\x00\xD0\x42\x00\x00\x4C\x43\x00\x00\x98\x43\x00\x00\x7B\x44\x00'  \
    '\x80\xFA\x44\x00\xC0\x3B\x45\x00\x40\x7A\x45\x05\x06\x07\x05\x06'  \
    '\xDD\x07\x00\x00\x60\x41\x00\x00\xC0\x41\x00\x00\x08\x42\x00\x00'  \
    '\xD2\x42\x00\x00\x4D\x43\x00\x80\x98\x43\x00\x40\x7B\x44\x00\xA0'  \
    '\xFA\x44\x00\xD0\x3B\x45\x00\x50\x7A\x45\x06\x07\x08\x06\x07\xDD'  \
    '\x07\x00\x00\x70\x41\x00\x00\xC8\x41\x00\x00\x0C\x42\x00\x00\xD4'  \
    '\x42\x00\x00\x4E\x43\x00\x00\x99\x43\x00\x80\x7B\x44\x00\xC0\xFA'  \
    '\x44\x00\xE0\x3B\x45\x00\x60\x7A\x45\x52\xE6\x3C\x33\x52\xE6\x54'  \
    '\xE0\x03'

# Expected results
EXPECTED_FIELDS_RECORD_1_1 = (1, 2, 3, 1, 2, 2013, 10.0, 20.0, 30.0,
                              101.0, 201.0, 301.0, 1001.0, 2001.0, 3001.0, 4001.0)

EXPECTED_FIELDS_RECORD_1_META = (1390820402, 1390826719, None, 65535, 1, 1374902331)

EXPECTED_FIELDS_RECORD_2_1 = (2, 3, 4, 2, 3, 2013, 11.0, 21.0, 31.0,
                              102.0, 202.0, 302.0, 1002.0, 2002.0, 3002.0, 4002.0)

EXPECTED_FIELDS_RECORD_2_2 = (3, 4, 5, 3, 4, 2013, 12.0, 22.0, 32.0,
                              103.0, 203.0, 303.0, 1003.0, 2003.0, 3003.0, 4003.0)

EXPECTED_FIELDS_RECORD_2_META = (1390820403, 1390826720, 11, 65535, 2, 1374902331)

EXPECTED_FIELDS_RECORD_3_1 = (4, 5, 6, 4, 5, 2013, 13.0, 23.0, 33.0,
                              104.0, 204.0, 304.0, 1004.0, 2004.0, 3004.0, 4004.0)

EXPECTED_FIELDS_RECORD_3_2 = (5, 6, 7, 5, 6, 2013, 14.0, 24.0, 34.0,
                              105.0, 205.0, 305.0, 1005.0, 2005.0, 3005.0, 4005.0)

EXPECTED_FIELDS_RECORD_3_3 = (6, 7, 8, 6, 7, 2013, 15.0, 25.0, 35.0,
                              106.0, 206.0, 306.0, 1006.0, 2006.0, 3006.0, 4006.0)

EXPECTED_FIELDS_RECORD_3_META = (1390820404, 1390826721, None, 65535, 3, 1374902331)

EXPECTED_FIELDS_RECORD_4_1 = (7, 8, 9, 7, 8, 2013, 16.0, 26.0, 36.0,
                              107.0, 207.0, 307.0, 1007.0, 2007.0, 3007.0, 4007.0)

EXPECTED_FIELDS_RECORD_4_2 = (8, 9, 10, 8, 9, 2013, 17.0, 27.0, 37.0,
                              108.0, 208.0, 308.0, 1008.0, 2008.0, 3008.0, 4008.0)

EXPECTED_FIELDS_RECORD_4_3 = (9, 10, 11, 9, 10, 2013, 18.0, 28.0, 38.0,
                              109.0, 209.0, 309.0, 1009.0, 2009.0, 3009.0, 4009.0)

EXPECTED_FIELDS_RECORD_4_4 = (10, 11, 12, 10, 11, 2013, 19.0, 29.0, 39.0,
                             110.0, 210.0, 310.0, 1010.0, 2010.0, 3010.0, 4010.0)

EXPECTED_FIELDS_RECORD_4_META = (1390820405, 1390826722, 13, 65535, 4, 1374902331)

EXPECTED_FIELDS_RECORD_10_1 = (1, 2, 3, 1, 2, 2013, 10.0, 20.0, 30.0,
                              101.0, 201.0, 301.0, 1001.0, 2001.0, 3001.0, 4001.0)

EXPECTED_FIELDS_RECORD_10_2 = (2, 3, 4, 2, 3, 2013, 11.0, 21.0, 31.0,
                              102.0, 202.0, 302.0, 1002.0, 2002.0, 3002.0, 4002.0)

EXPECTED_FIELDS_RECORD_10_3 = (3, 4, 5, 3, 4, 2013, 12.0, 22.0, 32.0,
                              103.0, 203.0, 303.0, 1003.0, 2003.0, 3003.0, 4003.0)

EXPECTED_FIELDS_RECORD_10_4 = (4, 5, 6, 4, 5, 2013, 13.0, 23.0, 33.0,
                              104.0, 204.0, 304.0, 1004.0, 2004.0, 3004.0, 4004.0)

EXPECTED_FIELDS_RECORD_10_5 = (5, 6, 7, 5, 6, 2013, 14.0, 24.0, 34.0,
                              105.0, 205.0, 305.0, 1005.0, 2005.0, 3005.0, 4005.0)

EXPECTED_FIELDS_RECORD_10_6 = (6, 7, 8, 6, 7, 2013, 15.0, 25.0, 35.0,
                              106.0, 206.0, 306.0, 1006.0, 2006.0, 3006.0, 4006.0)

EXPECTED_FIELDS_RECORD_10_7 = (7, 8, 9, 7, 8, 2013, 16.0, 26.0, 36.0,
                              107.0, 207.0, 307.0, 1007.0, 2007.0, 3007.0, 4007.0)

EXPECTED_FIELDS_RECORD_10_8 = (8, 9, 10, 8, 9, 2013, 17.0, 27.0, 37.0,
                              108.0, 208.0, 308.0, 1008.0, 2008.0, 3008.0, 4008.0)

EXPECTED_FIELDS_RECORD_10_9 = (9, 10, 11, 9, 10, 2013, 18.0, 28.0, 38.0,
                              109.0, 209.0, 309.0, 1009.0, 2009.0, 3009.0, 4009.0)

EXPECTED_FIELDS_RECORD_10_10 = (10, 11, 12, 10, 11, 2013, 19.0, 29.0, 39.0,
                               110.0, 210.0, 310.0, 1010.0, 2010.0, 3010.0, 4010.0)

EXPECTED_FIELDS_RECORD_10_META = (1390820402, 1390826719, 10, 65535, 10, 1374902331)

EXPECTED_FIELDS_RECORD_2_3_1_1 = (1, 2, 3, 1, 2, 2013, 10.0, 20.0, 30.0,
                                 101.0, 201.0, 301.0, 1001.0, 2001.0, 3001.0, 4001.0)

EXPECTED_FIELDS_RECORD_2_3_1_2 = (2, 3, 4, 2, 3, 2013, 11.0, 21.0, 31.0,
                                  102.0, 202.0, 302.0, 1002.0, 2002.0, 3002.0, 4002.0)

EXPECTED_FIELDS_RECORD_2_3_1_3 = (3, 4, 5, 3, 4, 2013, 12.0, 22.0, 32.0,
                                  103.0, 203.0, 303.0, 1003.0, 2003.0, 3003.0, 4003.0)

EXPECTED_FIELDS_RECORD_2_3_2_1 = (4, 5, 6, 4, 5, 2013, 13.0, 23.0, 33.0,
                                  104.0, 204.0, 304.0, 1004.0, 2004.0, 3004.0, 4004.0)

EXPECTED_FIELDS_RECORD_2_3_2_2 = (5, 6, 7, 5, 6, 2013, 14.0, 24.0, 34.0,
                                  105.0, 205.0, 305.0, 1005.0, 2005.0, 3005.0, 4005.0)

EXPECTED_FIELDS_RECORD_2_3_2_3 = (6, 7, 8, 6, 7, 2013, 15.0, 25.0, 35.0,
                                  106.0, 206.0, 306.0, 1006.0, 2006.0, 3006.0, 4006.0)

EXPECTED_FIELDS_RECORD_2_3_META_1 = (1390820402, 1390826719, 10, 65535, 3, 1374902331)

EXPECTED_FIELDS_RECORD_2_3_META_2 = (1390820403, 1390826720, None, 65535, 3, 1374902331)

# The list of generated tests are the suggested tests, but there may
# be other tests needed to fully test your parser

@attr('UNIT', group='mi')
class Vel3dLWfpSioMuleParserUnitTestCase(ParserUnitTestCase):
    """
    vel3d_l_wfp Parser unit test suite
    """
    def create_expected_results(self):
        """
        This function creates the expected particle results.
        """
        # The first number refers to the SIO record number.
        # The second number refers to the FSI record within the SIO block.
        self.expected_particle_1_1 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_1_1, internal_timestamp=3566106123.0)

        self.expected_particle_2_1 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_1, internal_timestamp=3568874584.0)

        self.expected_particle_2_2 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_2, internal_timestamp=3571383845.0)

        self.expected_particle_3_1 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_3_1, internal_timestamp=3574152306.0)

        self.expected_particle_3_2 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_3_2, internal_timestamp=3576834367.0)

        self.expected_particle_3_3 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_3_3, internal_timestamp=3579602828.0)

        self.expected_particle_4_1 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_4_1, internal_timestamp=3582284889.0)

        self.expected_particle_4_2 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_4_2, internal_timestamp=3585053350.0)

        self.expected_particle_4_3 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_4_3, internal_timestamp=3587821811.0)

        self.expected_particle_4_4 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_4_4, internal_timestamp=3590503872.0)

        self.expected_particle_10_1 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_1, internal_timestamp=3566106123.0)

        self.expected_particle_10_2 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_2, internal_timestamp=3568874584.0)

        self.expected_particle_10_3 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_3, internal_timestamp=3571383845.0)

        self.expected_particle_10_4 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_4, internal_timestamp=3574152306.0)

        self.expected_particle_10_5 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_5, internal_timestamp=3576834367.0)

        self.expected_particle_10_6 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_6, internal_timestamp=3579602828.0)

        self.expected_particle_10_7 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_7, internal_timestamp=3582284889.0)

        self.expected_particle_10_8 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_8, internal_timestamp=3585053350.0)

        self.expected_particle_10_9 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_9, internal_timestamp=3587821811.0)

        self.expected_particle_10_10= Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_10_10, internal_timestamp=3590503872.0)

        self.expected_particle_1_meta = Vel3dLWfpSioMuleMetadataParticle(
            EXPECTED_FIELDS_RECORD_1_META, internal_timestamp=3583891131.0)

        self.expected_particle_2_meta = Vel3dLWfpSioMuleMetadataParticle(
            EXPECTED_FIELDS_RECORD_2_META, internal_timestamp=3583891131.0)

        self.expected_particle_3_meta = Vel3dLWfpSioMuleMetadataParticle(
            EXPECTED_FIELDS_RECORD_3_META, internal_timestamp=3583891131.0)

        self.expected_particle_4_meta = Vel3dLWfpSioMuleMetadataParticle(
            EXPECTED_FIELDS_RECORD_4_META, internal_timestamp=3583891131.0)

        self.expected_particle_10_meta = Vel3dLWfpSioMuleMetadataParticle(
            EXPECTED_FIELDS_RECORD_10_META, internal_timestamp=3583891131.0)
        
        # The following are for the multiple SIO block file.
        self.expected_particle_2_3_1_1 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_1_1, internal_timestamp=3566106123.0)
        
        self.expected_particle_2_3_1_2 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_1_2, internal_timestamp=3568874584.0)

        self.expected_particle_2_3_1_3 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_1_3, internal_timestamp=3571383845.0)

        self.expected_particle_2_3_2_1 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_2_1, internal_timestamp=3574152306.0)

        self.expected_particle_2_3_2_2 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_2_2, internal_timestamp=3576834367.0)

        self.expected_particle_2_3_2_3 = Vel3dLWfpSioMuleInstrumentParticle(
            EXPECTED_FIELDS_RECORD_2_3_2_3, internal_timestamp=3579602828.0)

        self.expected_particle_2_3_meta_1 = Vel3dLWfpSioMuleMetadataParticle(
            EXPECTED_FIELDS_RECORD_2_3_META_1, internal_timestamp=3583891131.0)

        self.expected_particle_2_3_meta_2 = Vel3dLWfpSioMuleMetadataParticle(
            EXPECTED_FIELDS_RECORD_2_3_META_2, internal_timestamp=3583891131.0)

    def create_parser(self, file_handle, new_state):
        """
        This function creates a Vel3d_l_Wfp_Sio_Mule parser.
        """
        if new_state is None:
            new_state = self.state
        parser = Vel3dLWfpSioMuleParser(self.config, new_state, file_handle,
            self.state_callback, self.pub_callback, self.exception_callback)
        return parser

    def exception_callback(self, exception):
        """ Callback method to watch what comes in via the exception callback """
        self.exception_callback_value = exception
        log.info("EXCEPTION RECEIVED %s", exception)

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        #self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
	        DataSetDriverConfigKeys.PARTICLE_MODULE:\
            'mi.dataset.parser.vel3d_l_wfp_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: \
                ['Vel3dLWfpSioMuleInstrumentParticle',
                 'Vel3dLWfpSioMuleMetadataParticle']
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
        log.info("Many length %d", len(SIO_RECORD_4))
        input_file = StringIO(SIO_RECORD_4)
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
        log.info("Long Stream length %d", len(SIO_RECORD_10))
        input_file = StringIO(SIO_RECORD_10)
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
        log.info("Mid State length %d", len(SIO_RECORD_2_3))
        input_file = StringIO(SIO_RECORD_2_3)

        # Skip past the first SIO block and
        # the first 2 instrument records in SIO block 2.
        new_state = {
            StateKey.UNPROCESSED_DATA: [[468, 934]],
            StateKey.IN_PROCESS_DATA: [[468, 934, 4, 2]],
            StateKey.TIMESTAMP: 0.0}
        self.parser = self.create_parser(input_file, new_state)

        log.info("MID STATE VERIFY RECORD 2_3")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_2_3_2_3)

        log.info("MID STATE VERIFY STATE")
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA],
                        [[468, 934, 4, 3]])
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA],
                         [[468, 934]])

        log.info("============== END MID STATE START ==================")

    def test_multiple_sio_blocks(self):
        """
        This function verifies that multiple SIO blocks can be read.
        """
        log.info("============== START MULTIPLE SIO BLOCKS ==================")
        log.info("Multiple SIO Blocks length %d", len(SIO_RECORD_2_3))
        input_file = StringIO(SIO_RECORD_2_3)
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

        log.info("============== END MULTIPLE SIO BLOCKS ==================")

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and
        reading data, as if new data has been found and the state has
        changed
        """
        log.info("============== START SET STATE ==================")
        log.info("Set State length %d", len(SIO_RECORD_2_3))
        input_file = StringIO(SIO_RECORD_2_3)
        self.parser = self.create_parser(input_file, self.state)

        log.info("SET STATE VERIFY RECORD 1_1")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_2_3_1_1)

        # Skip past the other 2 instrument records in SIO block 1.
        # The next record that will be read is the metadata record.
        new_state = {
            StateKey.UNPROCESSED_DATA: [[0, 934]],
            StateKey.IN_PROCESS_DATA: [[0, 468, 4, 3], [468, 934, 4, 0]],
            StateKey.TIMESTAMP: 0.0}
        self.parser.set_state(new_state)

        log.info("SET STATE VERIFY RECORD 1_META")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_2_3_meta_1)

        # Skip past the first instrument record in SIO block 2.
        new_state = {
            StateKey.UNPROCESSED_DATA: [[468, 934]],
            StateKey.IN_PROCESS_DATA: [[468, 934, 4, 1]],
            StateKey.TIMESTAMP: 0.0}
        self.parser.set_state(new_state)

        log.info("SET STATE VERIFY RECORD 2_2")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_2_3_2_2)

        log.info("SET STATE VERIFY STATE")
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA],
                        [[468, 934, 4, 2]])
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA],
                         [[468, 934]])

        log.info("============== END SET STATE ==================")

    def test_simple_no_decimation(self):
        """
	    Read test data and pull out data particles one at a time.
	    Assert that the results are those we expected.
	    This test verifies that a missing decimation factor is handled correctly.
	    """
        log.info("============== START SIMPLE NO DECIMATION ==================")
        log.info("Simple length %d", len(SIO_RECORD_1))
        input_file = StringIO(SIO_RECORD_1)
        self.parser = self.create_parser(input_file, self.state)

        log.info("SIMPLE NO DECIMATION VERIFY RECORD 1")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_1_1)

        log.info("SIMPLE NO DECIMATION VERIFY METADATA RECORD")
        result = self.parser.get_records(1)
        self.verify_contents(result, self.expected_particle_1_meta)

        log.info("============== END SIMPLE NO DECIMATION ==================")

    def test_simple_with_decimation(self):
        """
	    Read test data and pull out data particles one at a time.
	    Assert that the results are those we expected.
	    This test verifies that a decimation factor is handled correctly.
	    """
        log.info("============== START SIMPLE WITH DECIMATION ==================")
        log.info("Simple length %d", len(SIO_RECORD_2))
        input_file = StringIO(SIO_RECORD_2)
        self.parser = self.create_parser(input_file, self.state)

        log.info("SIMPLE WITH DECIMATION VERIFY RECORD 1")
        result = self.parser.get_records(1)
        #log.info("ACT %s %f", result[0].raw_data,
        #    result[0].contents[DataParticleKey.INTERNAL_TIMESTAMP])
        #log.info("EXP %s %f", self.expected_particle_2_1.raw_data,
        #    self.expected_particle_2_1.contents[DataParticleKey.INTERNAL_TIMESTAMP])
        self.verify_contents(result, self.expected_particle_2_1)

        log.info("SIMPLE WITH DECIMATION VERIFY RECORD 2")
        result = self.parser.get_records(1)
        #log.info("ACT %s %f", result[0].raw_data,
        #    result[0].contents[DataParticleKey.INTERNAL_TIMESTAMP])
        #log.info("EXP %s %f", self.expected_particle_2_2.raw_data,
        #    self.expected_particle_2_2.contents[DataParticleKey.INTERNAL_TIMESTAMP])
        self.verify_contents(result, self.expected_particle_2_2)

        log.info("SIMPLE WITH DECIMATION VERIFY METADATA RECORD")
        result = self.parser.get_records(1)
        #log.info("ACT %s %f", result[0].raw_data,
        #    result[0].contents[DataParticleKey.INTERNAL_TIMESTAMP])
        #log.info("EXP %s %f", self.expected_particle_2_meta.raw_data,
        #    self.expected_particle_2_meta.contents[DataParticleKey.INTERNAL_TIMESTAMP])
        self.verify_contents(result, self.expected_particle_2_meta)

        log.info("============== END SIMPLE WITH DECIMATION ==================")

    def verify_contents(self, actual_particle, expected_particle_):
        self.assertEqual(actual_particle, [expected_particle_])
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], expected_particle_)
