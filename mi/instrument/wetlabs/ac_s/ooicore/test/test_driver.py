"""
@package mi.instrument.wetlabs.ac_s.ooicore.test.test_driver
@file marine-integrations/mi/instrument/wetlabs/ac_s/ooicore/driver.py
@author Lytle Johnson
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Lytle Johnson'
__license__ = 'Apache 2.0'

import unittest

from nose.plugins.attrib import attr
from mock import Mock
from mi.core.common import BaseEnum
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import ParameterTestConfigKey

from interface.objects import AgentCommand

from mi.core.instrument.logger_client import LoggerClient

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue

from mi.instrument.wetlabs.ac_s.ooicore.driver import InstrumentDriver
from mi.instrument.wetlabs.ac_s.ooicore.driver import DataParticleType
from mi.instrument.wetlabs.ac_s.ooicore.driver import InstrumentCommand
from mi.instrument.wetlabs.ac_s.ooicore.driver import ProtocolState
from mi.instrument.wetlabs.ac_s.ooicore.driver import ProtocolEvent
from mi.instrument.wetlabs.ac_s.ooicore.driver import Capability
from mi.instrument.wetlabs.ac_s.ooicore.driver import Parameter
from mi.instrument.wetlabs.ac_s.ooicore.driver import Protocol
from mi.instrument.wetlabs.ac_s.ooicore.driver import Prompt
from mi.instrument.wetlabs.ac_s.ooicore.driver import NEWLINE
from mi.instrument.wetlabs.ac_s.ooicore.driver import OPTAA_SampleDataParticleKey
from mi.instrument.wetlabs.ac_s.ooicore.driver import OPTAA_SampleDataParticle
from mi.instrument.wetlabs.ac_s.ooicore.driver import OPTAA_StatusDataParticleKey
from mi.instrument.wetlabs.ac_s.ooicore.driver import OPTAA_StatusDataParticle

from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException, InstrumentCommandException
from interface.objects import AgentCommand

from struct import pack

def ShortSample():
    short_sample_values = "FF 00 FF 00  02 A8 05 01  53 00 00 82  01 CE FF FF \
                           02 B0 6E 47  A8 4F 01 D5  02 \
                           BD 00 00 28  4D 01 51 05  6F 04 F9 04  C9 03 96 06 \
                           60 05 DB 05  BF 04 87 07  61 06 D0 06  CF 05 8B 08 \
                           78 07 DC 07  F8 06 A0 09  A9 09 00 09  41 07 CA 0B \
                           01 0A 48 0A  B3 09 15 0C  7C 0B B3 0C  57 0A 85 0E \
                           1B 0D 43 0E  20 0C 1C 0F  DC 0E F1 10  16 0D D8 11 \
                           B4 10 BB 12  2C 0F B4 13  9C 12 97 14  5A 11 AC 15 \
                           9A 14 8E 16  A5 13 C3 17  AA 16 94 19  09 15 F4 19 \
                           F5 18 D6 1B  A2 18 69 1C  7C 1B 59 1E  9A 1B 29 1F \
                           1C 1D F4 21  AC 1E 0B 21  D1 20 A8 24  DC 21 12 24 \
                           AB 23 81 28  34 24 4E 27  9B 26 78 2B  B7 27 B0 2A \
                           9B 29 86 2F  4D 2B 36 2D  A7 2C 9D 32  F9 2E D5 30 \
                           CF 2F DC 36  C4 32 A8 34  01 33 2F 3A  A7 36 9E 37 \
                           3B 36 89 3E  97 3A A9 3A  8E 3A 01 42  A2 3E DF 3E \
                           10 3D B0 46  E1 43 5A 41  CB 41 92 4B  6B 48 1B 45 \
                           C9 45 BD 50  40 4D 3A 4A  14 4A 38 55  79 52 C1 4E \
                           97 4E F8 5A  FE 58 A4 53  32 53 D5 60  A9 5E B4 57 \
                           A5 58 9A 66  33 64 B6 5B  E6 5D 2A 6B  7D 6A 8D 5F \
                           DA 61 8F 70  88 70 3E 63  96 65 C0 75  27 75 C0 67 \
                           33 69 B3 79  D3 7B 06 6A  87 6D 74 7E  11 80 16 6D \
                           9C 70 FD 82  18 84 EF 70  57 74 2B 85  B1 89 64 72 \
                           7F 76 9B 88  C2 8D 05 74  F5 79 B6 8C  12 91 77 77 \
                           0E 7C 6F 8E  F4 95 7E 78  D0 7E C9 91  6A 99 17 7A \
                           34 80 CA 93  6F 9C 49 7B  30 82 69 94  F8 9F 03 7B \
                           B9 83 90 95  F5 A1 35 7B  DA 84 39 96  6D A2 CE 7B \
                           8E 84 77 96  63 A3 E1 7A  D9 84 42 95  D0 A4 64 79 \
                           C2 83 A9 94  C8 A4 67 78  42 82 A0 93  36 A3 DE 76 \
                           76 81 32 91  4D A2 D0 74  47 7F 61 8E  EF A1 3F 71 \
                           DA 7D 2F 8C  1E 9F 2C 6F  5C 7A DF 89  4C 9C E0 6C \
                           99 78 6C 86  31 9A 5B 69  83 75 95 82  9E 97 4E 66 \
                           21 72 63 7E  A9 93 C0 62  62 6E DF 7A  53 8F B7 5D \
                           99 6A 87 74  B5 8A 91 59  71 65 B7 6F  17 84 C4 56 \
                           0B 62 3C 6B  69 80 8E 52  20 5E 50 66  9C 7B BC 4E \
                           14 5A 1D 61  A0 76 84 4A  01 55 D6 5C  A0 71 23 45 \
                           FF 51 8D 57  A9 6B B6 42  20 \
                           4D 63 52 DA  66 65 3E 68  49 55 4E 39  61 32 3A DE \
                           45 6B 49 C9  5C 2A 37 82  41 B6 45 98  57 5F 34 4A \
                           3E 21 41 96  52 BE 31 3A  3A B1 3D C0  4E 49 2E 50 \
                           37 6E 3A 1C  4A 06 2B 89  34 47 36 9E  45 EA 28 FD \
                           31 4E 33 6D  42 09 26 9C  2E 97 30 75  3E 79 24 65 \
                           2C 06 2D AD  3B 1D 22 51  29 9F 2B 11  37 F3 20 64 \
                           27 61 28 A8  34 FF 1E 9B  25 4B 26 6E  32 40 1C FA \
                           23 5E 24 61  2F B9 11 0A  00"
                           
    short_sample = ''
    for value in short_sample_values.split():
        short_sample += chr(int(value, 16))
    return short_sample

raw_sample_1 = pack('200B',\
0xff,0x00,0xff,0x00,0x02,0xb8,0x05,0x01,0x53,0x00,0x00,0x7b,0x01,0xc4,0xff,0xff,0x02,0xb6,0x6d,0xba,\
0xa5,0x67,0x01,0xc4,0x02,0xb1,0xca,0x67,0x51,0x4f,0x01,0x53,0x04,0x51,0x03,0x63,0x04,0x54,0x02,0xff,\
0x05,0x0d,0x04,0x06,0x05,0x29,0x03,0xb6,0x05,0xd9,0x04,0xbc,0x06,0x19,0x04,0x80,0x06,0xb6,0x05,0x80,\
0x07,0x1e,0x05,0x5b,0x07,0xa2,0x06,0x57,0x08,0x3e,0x06,0x4e,0x08,0xa7,0x07,0x44,0x09,0x7c,0x07,0x5a,\
0x09,0xc5,0x08,0x4b,0x0a,0xdc,0x08,0x85,0x0a,0xfe,0x09,0x6b,0x0c,0x63,0x09,0xd3,0x0c,0x49,0x0a,0x7c,\
0x0e,0x09,0x0b,0x0d,0x81,0x0b,0xc9,0x0f,0x90,0x0c,0x9c,0x0f,0x1c,0x0d,0x46,0x8d,0x0e,0x5b,0x10,0xaf,\
0x0e,0xae,0xa0,0x10,0x10,0x12,0x41,0x10,0x24,0x15,0xa3,0xdd,0xe5,0xb8,0x17,0xc3,0xce,0x15,0xaa,0x68,\
0x1a,0x0b,0x15,0xe9,0x17,0x92,0x15,0x3a,0x1c,0x87,0x18,0x34,0x19,0x9c,0x17,0x29,0x1f,0x2e,0x1a,0xa5,\
0x1b,0xc0,0x19,0x3d,0x21,0xfe,0x1d,0x4b,0x1e,0x0b,0x1b,0x76,0x24,0xfe,0x20,0x26,0x20,0x80,0x1d,0xd4,\
0x28,0x3a,0x23,0x32,0x23,0x16,0x20,0x4f,0x2b,0xa7,0x26,0x6e,0x25,0xc8,0x22,0xe6,0x2f,0x3e,0x29,0xd2)

raw_sample_2 = pack('200B',\
0x28,0x98,0x25,0x88,0x32,0xfd,0x2d,0x56,0x2b,0x74,0x28,0x34,0x36,0xd6,0x30,0xef,0x2e,0x50,0x2a,0xe1,\
0x3a,0xb5,0x34,0x98,0x31,0x38,0x2d,0x9b,0x3e,0xa2,0x38,0x59,0x34,0x2d,0x30,0x71,0x42,0xa2,0x3c,0x49,\
0x37,0x44,0x33,0x78,0x46,0xcd,0x40,0x7e,0x3a,0x8e,0x36,0xb1,0x4b,0x3c,0x44,0xf9,0x3e,0x3a,0x22,0x4f,\
0xfa,0x49,0xc7,0x41,0xd8,0x3d,0xb5,0x55,0x15,0x4e,0xd0,0x45,0xb7,0x41,0x43,0x5a,0x6b,0x53,0xdc,0x49,\
0x73,0x44,0xa4,0x5f,0xa0,0x58,0xbb,0x4d,0x1f,0x48,0x05,0x64,0x9c,0x5d,0xa7,0x50,0xd3,0x4b,0x31,0x69,\
0xcc,0x62,0x58,0x54,0x48,0x4e,0x2e,0x6e,0xaa,0x66,0xd2,0x57,0x8a,0x50,0xf8,0x73,0x3e,0x6b,0x0a,0x5a,\
0x95,0x53,0x9d,0x77,0x8d,0x6f,0x19,0x5d,0x70,0x56,0x06,0x7b,0xa2,0x72,0xd9,0x60,0x1b,0x58,0x3d,0x7f,\
0x73,0x76,0x5d,0x62,0x91,0x5a,0x45,0x83,0x04,0x79,0xa6,0x64,0xd3,0x5c,0x1d,0x86,0x4e,0x7c,0xa8,0x67,\
0x18,0x5e,0x1e,0x89,0x3e,0x80,0x12,0x69,0x15,0x5f,0x9a,0x8c,0x35,0x82,0xad,0x6a,0xce,0x60,0xd2,0x8e,\
0xdb,0x84,0xf4,0x6c,0x46,0x61,0xc5,0x91,0x27,0x86,0xdd,0x6d,0x80,0x62,0x6b,0x93,0x22,0x88,0x5b,0x6e)

raw_sample_3 = pack('200B',\
0x66,0x62,0xbf,0x94,0xb2,0x89,0x69,0x6e,0xed,0x62,0xc2,0x95,0xc5,0x89,0xff,0x6f,0x1a,0x62,0x74,0x96,\
0x57,0x8a,0x25,0x6e,0xf6,0x61,0xdd,0x96,0x81,0x89,0xe0,0x6e,0x7f,0x60,0xfa,0x96,0x35,0x89,0x2b,0x6d,\
0xb5,0x5f,0xcf,0x95,0x74,0x88,0x0d,0x6c,0x9b,0x5e,0x73,0x94,0x46,0x86,0xa9,0x6b,0x49,0x5c,0xe5,0x92,\
0xc3,0x84,0xf2,0x69,0xc6,0x5b,0x24,0x90,0xfd,0x82,0xee,0x68,0x06,0x59,0x25,0x8e,0xdf,0x80,0x86,0x66,\
0x14,0x56,0xfd,0x8c,0x79,0x7d,0xd9,0x63,0xe6,0x54,0xa1,0x89,0xc1,0x7a,0xda,0x61,0x75,0x51,0xfb,0x86,\
0xb5,0x77,0x66,0x5e,0xae,0x4f,0x37,0x83,0x19,0x73,0xbb,0x5b,0xcd,0x4c,0x4d,0x7f,0x52,0x6f,0xc7,0x58,\
0xf6,0x49,0x3c,0x7b,0x72,0x6b,0x94,0x56,0x46,0x25,0x77,0xff,0x67,0x47,0x52,0x3e,0x43,0x06,0x72,0xb2,\
0x62,0xe7,0x4e,0xbb,0x3f,0xec,0x6d,0xe9,0x5e,0x83,0x4b,0x4c,0x3c,0xe2,0x69,0x43,0x5a,0x28,0x47,0xe4,\
0x39,0xe9,0x64,0x95,0x55,0xe0,0x44,0x99,0x37,0x05,0x60,0x0e,0x51,0xb2,0x41,0x60,0x34,0x3e,0x5b,0xa3,\
0x4d,0xac,0x3e,0x3e,0x31,0x8f,0x57,0x4b,0x49,0xca,0x3b,0x38,0x2e,0xff,0x53,0x19,0x46,0x0f,0x38,0x4f)

raw_sample_4 = pack('99B',\
0x2c,0x88,0x4f,0x0c,0x42,0x7c,0x35,0x81,0x2a,0x32,0x4b,0x27,0x3f,0x10,0x32,0xd6,0x27,0xf2,0x47,0x6f,\
0x3b,0xc7,0x30,0x49,0x25,0xad,0x43,0xe2,0x38,0x74,0x2d,0xc0,0x23,0xc9,0x40,0x6f,0x35,0xaa,0x2b,0x68,\
0x22,0x1a,0x3c,0xf3,0x33,0x2c,0x29,0x7a,0x20,0x68,0x3a,0x53,0x30,0xb1,0x27,0x83,0x1e,0xcd,0x37,0x99,\
0x2e,0x51,0x25,0xa1,0x1d,0x49,0x34,0xf2,0x2c,0x15,0x23,0xd8,0x1b,0xdd,0x32,0x71,0x29,0xfb,0x22,0x25,\
0x19,0x43,0x30,0x26,0x0c,0x73,0x00,0xfe,0x00,0xfe,0x00,0x02,0xb8,0x05,0x01,0x53,0x0f,0x29,0x00)

OPTAA_SAMPLE = raw_sample_1 + raw_sample_2 + raw_sample_3 + raw_sample_4

OPTAA_STATUS_DATA = \
"AC-Spectra Version 1.10     (May 16 2005 09:40:13)" + NEWLINE +\
"Persistor CF2 SN:12154   BIOS:2.28   PicoDOS:2.28" + NEWLINE + NEWLINE +\
"14 A/D samples per bin into 20164 long buffers" + NEWLINE +\
"Spinning up motor for 10 secs. Hit 'Q' to quit."

# Globals
raw_stream_received = False
parsed_stream_received = False

###
#   Driver parameters for the tests
###
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.wetlabs.ac_s.ooicore.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id = 'DQPJJX',
    instrument_agent_name = 'wetlabs_ac_s_ooicore',
    instrument_agent_packet_config = DataParticleType(),
    driver_startup_config = {}
)



 #################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################

###
#   Driver constant definitions
###

###############################################################################
#                           DATA PARTICLE TEST MIXIN                          #
#     Defines a set of assert methods used for data particle verification     #
#                                                                             #
#  In python mixin classes are classes designed such that they wouldn't be    #
#  able to stand on their own, but are inherited by other classes generally   #
#  using multiple inheritance.                                                #
#                                                                             #
# This class defines a configuration structure for testing and common assert  #
# methods for validating data particles.
###############################################################################
class UtilMixin(DriverTestMixin):
    '''
    Mixin class used for storing data particle constants and common data assertion methods.
    '''
    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {}

    ###
    # Data Particle Parameters
    ### 
    _sample_parameters = {
        # particle data defined in the OPTAA Driver doc
        OPTAA_SampleDataParticleKey.RECORD_LENGTH : {'type': int, 'value': 680 },
        OPTAA_SampleDataParticleKey.PACKET_TYPE : {'type': int, 'value': 5 },
        OPTAA_SampleDataParticleKey.METER_TYPE : {'type': int, 'value': 83 },
        OPTAA_SampleDataParticleKey.SERIAL_NUMBER : {'type': int, 'value': 130},
        OPTAA_SampleDataParticleKey.A_REFERENCE_DARK_COUNTS : {'type': int, 'value': 0x1ce },
        OPTAA_SampleDataParticleKey.PRESSURE_COUNTS : {'type': int, 'value': 0xffff },
        OPTAA_SampleDataParticleKey.A_SIGNAL_DARK_COUNTS : {'type': int, 'value': 0x2b0 },
        OPTAA_SampleDataParticleKey.EXTERNAL_TEMP_RAW : {'type': int, 'value': 0x6e47 },
        OPTAA_SampleDataParticleKey.INTERNAL_TEMP_RAW : {'type': int, 'value': 0xa84f },
        OPTAA_SampleDataParticleKey.C_REFERENCE_DARK_COUNTS : {'type': int, 'value': 0x1d5 },
        OPTAA_SampleDataParticleKey.C_SIGNAL_DARK_COUNTS : {'type': int, 'value': 0x2bd },
        OPTAA_SampleDataParticleKey.ELAPSED_RUN_TIME : {'type': int, 'value': 0x0000284d },
        OPTAA_SampleDataParticleKey.NUM_WAVELENGTHS : {'type': int, 'value': 81 },
        OPTAA_SampleDataParticleKey.C_REFERENCE_COUNTS : {'type': list, 'value': [1391, 1632, 1889, 2168, 2473, 2817, 3196, 3611, 4060, 4532, 
                                                                                  5020, 5530, 6058, 6645, 7292, 7964, 8657, 9387, 10139, 10907, 
                                                                                  11687, 12495, 13313, 14139, 14990, 15888, 16843, 17865, 18964, 20119, 
                                                                                  21298, 22437, 23526, 24538, 25494, 26419, 27271, 28060, 28759, 29311, 
                                                                                  29941, 30478, 30928, 31284, 31536, 31673, 31706, 31630, 31449, 31170, 
                                                                                  30786, 30326, 29767, 29146, 28508, 27801, 27011, 26145, 25186, 23961, 
                                                                                  22897, 22027, 21024, 19988, 18945, 17919, 16928, 15976, 15070, 14210, 
                                                                                  13386, 12602, 11856, 11145, 10493, 9884, 9317, 8785, 8292, 7835, 
                                                                                  7418]},
        OPTAA_SampleDataParticleKey.A_REFERENCE_COUNTS : {'type': list, 'value': [1273, 1499, 1744, 2012, 2304, 2632, 2995, 3395, 3825, 4283, 
                                                                                  4759, 5262, 5780, 6358, 7001, 7668, 8360, 9089, 9848, 10630, 
                                                                                  11421, 12252, 13103, 13961, 14849, 15792, 16786, 17853, 19000, 20216, 
                                                                                  21461, 22682, 23850, 24975, 26048, 27059, 28020, 28925, 29739, 30363, 
                                                                                  31158, 31855, 32457, 32970, 33385, 33680, 33849, 33911, 33858, 33705, 
                                                                                  33440, 33074, 32609, 32047, 31455, 30828, 30101, 29283, 28383, 27271, 
                                                                                  26039, 25148, 24144, 23069, 21974, 20877, 19811, 18773, 17771, 16822, 
                                                                                  15905, 15025, 14190, 13383, 12622, 11927, 11270, 10655, 10081, 9547,
                                                                                   9054]},
        OPTAA_SampleDataParticleKey.C_SIGNAL_COUNTS : {'type': list, 'value':    [1225, 1471, 1743, 2040, 2369, 2739, 3159, 3616, 4118, 4652, 
                                                                                  5210, 5797, 6409, 7074, 7834, 8620, 9436, 10292, 11191, 12109, 
                                                                                  13049, 14020, 15015, 16023, 17058, 18145, 19307, 20544, 21881, 23294, 
                                                                                  24745, 26163, 27517, 28808, 29991, 31187, 32273, 33304, 34225, 35010, 
                                                                                  35858, 36596, 37226, 37743, 38136, 38389, 38509, 38499, 38352, 38088, 
                                                                                  37686, 37197, 36591, 35870, 35148, 34353, 33438, 32425, 31315, 29877, 
                                                                                  28439, 27497, 26268, 24992, 23712, 22441, 21210, 20025, 18889, 17816, 
                                                                                  16790, 15808, 14876, 13982, 13165, 12405, 11693, 11025, 10408, 9838, 
                                                                                  9313]},
        OPTAA_SampleDataParticleKey.A_SIGNAL_COUNTS : {'type': list, 'value':    [918, 1159, 1419, 1696, 1994, 2325, 2693, 3100, 3544, 4020, 
                                                                                  4524, 5059, 5620, 6249, 6953, 7691, 8466, 9294, 10160, 11062, 
                                                                                  11989, 12968, 13982, 15017, 16095, 17242, 18459, 19770, 21185, 22692, 
                                                                                  24244, 25782, 27277, 28734, 30144, 31494, 32790, 34031, 35172, 36101, 
                                                                                  37239, 38270, 39191, 40009, 40707, 41269, 41678, 41953, 42084, 42087, 
                                                                                  41950, 41680, 41279, 40748, 40160, 39515, 38734, 37824, 36791, 35473, 
                                                                                  33988, 32910, 31676, 30340, 28963, 27574, 26213, 24882, 23594, 22367, 
                                                                                  21182, 20041, 18950, 17898, 16905, 15993, 15133, 14323, 13567, 12864, 
                                                                                  12217]}
        }   
            
    _short_sample_parameters = {
        # particle data defined in the OPTAA Driver doc
        OPTAA_SampleDataParticleKey.RECORD_LENGTH : {'type': int, 'value': 696 },
        OPTAA_SampleDataParticleKey.PACKET_TYPE : {'type': int, 'value': 5 },
        OPTAA_SampleDataParticleKey.METER_TYPE : {'type': int, 'value': 83 },
        OPTAA_SampleDataParticleKey.SERIAL_NUMBER : {'type': int, 'value': 123},
        OPTAA_SampleDataParticleKey.A_REFERENCE_DARK_COUNTS : {'type': int, 'value': 0x1c4 },
        OPTAA_SampleDataParticleKey.PRESSURE_COUNTS : {'type': int, 'value': 0xffff },
        OPTAA_SampleDataParticleKey.A_SIGNAL_DARK_COUNTS : {'type': int, 'value': 0x2b6 },
        OPTAA_SampleDataParticleKey.EXTERNAL_TEMP_RAW : {'type': int, 'value': 0x6dba },
        OPTAA_SampleDataParticleKey.INTERNAL_TEMP_RAW : {'type': int, 'value': 0xa567 },
        OPTAA_SampleDataParticleKey.C_REFERENCE_DARK_COUNTS : {'type': int, 'value': 0x1c4 },
        OPTAA_SampleDataParticleKey.C_SIGNAL_DARK_COUNTS : {'type': int, 'value': 0x2b1 },
        OPTAA_SampleDataParticleKey.ELAPSED_RUN_TIME : {'type': int, 'value': 0xca67514f },
        OPTAA_SampleDataParticleKey.NUM_WAVELENGTHS : {'type': int, 'value': 83 },
        OPTAA_SampleDataParticleKey.C_REFERENCE_COUNTS : {'type': list, 'value': [1105, 1293, 1497, 1718, 1954, 2215, 2501, 2814, 3145, 33035, 
                                                                                  7181, 3758, 9237, 52757, 6034, 6556, 7104, 7691, 8320, 8982, 
                                                                                  9672, 10392, 11124, 11856, 12600, 13357, 14148, 14990, 15930, 55357, 
                                                                                  46913, 29508, 8008, 54091, 18510, 35408, 38227, 28758, 7000, 37210, 
                                                                                  54108, 6238, 5471, 52832, 18017, 32866, 26210, 60770, 6754, 63073, 
                                                                                  32608, 46431, 39774, 18780, 50779, 1625, 5206, 58964, 30033, 44623, 
                                                                                  52556, 63049, 17957, 17158, 16364, 15586, 14825, 14085, 13374, 12687, 
                                                                                  12031, 11400, 10802, 10226, 9645, 9161, 8730, 8296, 7885, 7497, 
                                                                                  7133, 6467, 254]},
        OPTAA_SampleDataParticleKey.A_REFERENCE_COUNTS : {'type': list, 'value': [867, 1030, 1212, 1408, 1623, 1860, 2123, 2411, 2684, 51471, 
                                                                                  18061, 40976, 41949, 43624, 5434, 5929, 6461, 7030, 7636, 8271, 
                                                                                  8934, 9608, 10292, 10977, 11675, 12401, 13176, 14001, 8783, 46421, 
                                                                                  17242, 42079, 1380, 12649, 11886, 63603, 40311, 1659, 15743, 17795, 
                                                                                  7558, 7817, 39564, 53902, 50577, 27539, 49044, 49813, 29846, 56726, 
                                                                                  64150, 53141, 29588, 58770, 9360, 9614, 64908, 41353, 64390, 14211, 
                                                                                  19839, 15483, 30719, 29362, 28137, 26947, 25749, 24590, 23459, 22347, 
                                                                                  21273, 20236, 19239, 18287, 17378, 16495, 15603, 14931, 14233, 13554, 
                                                                                  12913, 12326, 2]},
        OPTAA_SampleDataParticleKey.C_SIGNAL_COUNTS : {'type': list, 'value':    [1108, 1321, 1561, 1822, 2110, 2428, 2780, 3171, 3593, 36876, 
                                                                                  3675, 4114, 58808, 6667, 7303, 7982, 8702, 9470, 10298, 11175, 
                                                                                  12094, 13053, 14038, 15029, 16034, 17058, 18125, 19260, 64073, 5454, 
                                                                                  27475, 41048, 40029, 52322, 43622, 15979, 36207, 41586, 29558, 1145, 
                                                                                  20092, 16000, 13698, 56196, 10118, 8840, 45705, 50569, 22410, 33161, 
                                                                                  13705, 29832, 18054, 50052, 64898, 57216, 31101, 49530, 46455, 6515, 
                                                                                  21103, 29291, 26439, 25319, 24195, 23080, 21984, 20914, 19884, 18890, 
                                                                                  17935, 17020, 16144, 15303, 14452, 13738, 13100, 12465, 11857, 11285, 
                                                                                  10747, 3187, 47109]},
        OPTAA_SampleDataParticleKey.A_SIGNAL_COUNTS : {'type': list, 'value':    [767, 950, 1152, 1371, 1614, 1882, 2181, 2515, 2829, 39951, 
                                                                                  4271, 16656, 6083, 5609, 6196, 6821, 7499, 8230, 9010, 9838, 
                                                                                  10706, 11606, 12527, 13464, 14425, 15433, 16510, 17657, 51009, 53317, 
                                                                                  56393, 47949, 42832, 22612, 53847, 2650, 6493, 55648, 23906, 42596, 
                                                                                  43111, 4713, 44394, 62572, 56685, 23406, 26990, 65391, 9582, 57454, 
                                                                                  11117, 3436, 43371, 62057, 61032, 34406, 55651, 55905, 26206, 47963, 
                                                                                  51032, 37974, 21054, 20155, 19276, 18404, 17561, 16736, 15934, 15160, 
                                                                                  14415, 13697, 13014, 12361, 11712, 11112, 10618, 10115, 9633, 9176, 
                                                                                  8741, 254, 339]}
        }   
            
    _status_parameters = {
        OPTAA_StatusDataParticleKey.FIRMWARE_VERSION : {'type': unicode, 'value': '1.10'},
        OPTAA_StatusDataParticleKey.FIRMWARE_DATE : {'type': unicode, 'value': 'May 16 2005 09:40:13' },
        OPTAA_StatusDataParticleKey.PERSISTOR_CF_SERIAL_NUMBER : {'type': int, 'value': 12154 },
        OPTAA_StatusDataParticleKey.PERSISTOR_CF_BIOS_VERSION : {'type': unicode, 'value': '2.28'},
        OPTAA_StatusDataParticleKey.PERSISTOR_CF_PICODOS_VERSION : {'type': unicode, 'value': '2.28'},
        }

# Driver Parameter Methods
    ###
    def assert_driver_parameters(self, current_parameters, verify_values = False):
        """
        Verify that all driver parameters are correct and potentially verify values.
        @param current_parameters: driver parameters read from the driver instance
        @param verify_values: should we verify values against definition?
        """
        self.assert_parameters(current_parameters, self._driver_parameters, verify_values)

    ###
    # Data Particle Parameters Methods
    ### 
    def assert_sample_data_particle(self, data_particle):
        '''
        Verify a particle is a known particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unknown type produced by the driver
        '''
        if (isinstance(data_particle, OPTAA_SampleDataParticle)):
            self.assert_data_particle_sample(data_particle)
        if (isinstance(data_particle, OPTAA_StatusDataParticle)):
            self.assert_data_particle_status(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_data_particle_sample(self, data_particle, verify_values = False):
        '''
        Verify an optaa sample data particle
        @param data_particle: OPTAAA_SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.OPTAA_SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_data_particle_short_sample(self, data_particle, verify_values = False):
        '''
        Verify an optaa short sample data particle
        @param data_particle: OPTAAA_SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.OPTAA_SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._short_sample_parameters, verify_values)

    def assert_data_particle_status(self, data_particle, verify_values = False):
        """
        Verify an optaa status data particle
        @param data_particle: OPTAAA_StatusDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_header(data_particle, DataParticleType.OPTAA_STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_parameters, verify_values)
        
###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
#                                                                             #
#   These tests are especially useful for testing parsers and other data      #
#   handling.  The tests generally focus on small segments of code, like a    #
#   single function call, but more complex code using Mock objects.  However  #
#   if you find yourself mocking too much maybe it is better as an            #
#   integration test.                                                         #
#                                                                             #
#   Unit tests do not start up external processes like the port agent or      #
#   driver process.                                                           #
###############################################################################
@attr('UNIT', group='mi')
class TestUNIT(InstrumentDriverUnitTestCase, UtilMixin):
    
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)


    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """

        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())
        self.assert_enum_has_no_duplicates(InstrumentCommand())

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        #self.assert_enum_complete(Capability(), ProtocolEvent())  Capability is empty, so this test fails


    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, ShortSample())
        self.assert_chunker_sample_with_noise(chunker, ShortSample())
        self.assert_chunker_fragmented_sample(chunker, ShortSample())
        self.assert_chunker_combined_sample(chunker, ShortSample())

        self.assert_chunker_sample(chunker, OPTAA_SAMPLE)
        self.assert_chunker_sample_with_noise(chunker, OPTAA_SAMPLE)
        self.assert_chunker_fragmented_sample(chunker, OPTAA_SAMPLE)
        self.assert_chunker_combined_sample(chunker, OPTAA_SAMPLE)

        self.assert_chunker_sample(chunker, OPTAA_STATUS_DATA)
        self.assert_chunker_sample_with_noise(chunker, OPTAA_STATUS_DATA)
        self.assert_chunker_fragmented_sample(chunker, OPTAA_STATUS_DATA)
        self.assert_chunker_combined_sample(chunker, OPTAA_STATUS_DATA)


    def test_corrupt_data_sample(self):
        # garbage is not okay
        particle = OPTAA_SampleDataParticle(OPTAA_SAMPLE.replace('\x00\x00\x7b', 'foo'),
                                            port_timestamp = 3558720820.531179)
        with self.assertRaises(SampleException):
            particle.generate()
         
    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        self.assert_raw_particle_published(driver, True)

        # validating data particles
        """
        self.assert_particle_published(driver, OPTAA_STATUS_DATA, self.assert_data_particle_status, True)
        self.assert_particle_published(driver, OPTAA_SAMPLE, self.assert_data_particle_sample, True)
        """
        self.assert_particle_published(driver, ShortSample(), self.assert_data_particle_sample, True)


    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, mock_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(sorted(driver_capabilities),
                          sorted(protocol._filter_capabilities(test_capabilities)))

    def test_capabilities(self):
        """
        Verify the FSM reports capabilities as expected.  All states defined in this dict must
        also be defined in the protocol FSM.
        """
        capabilities = {
            ProtocolState.UNKNOWN: ['DRIVER_EVENT_DISCOVER'],
            ProtocolState.AUTOSAMPLE: []
        }

        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_capabilities(driver, capabilities)

###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class DriverIntegrationTest(InstrumentDriverIntegrationTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    def test_autosample_particle_generation(self):
        """
        Test that we can generate particles when in autosample
        """
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)


        self.assert_async_particle_generation(DataParticleType.OPTAA_SAMPLE, self.assert_sample_data_particle, timeout=120)

###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class DriverQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        ###
        #   Add instrument specific code here.
        ###

        self.assert_direct_access_stop_telnet()

    def test_get_capabilities(self):
        """
        @brief Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()
