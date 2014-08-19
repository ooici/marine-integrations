"""
@package mi.instrument.wetlabs.ac_s.ooicore.test.test_driver
@file marine-integrations/mi/instrument/wetlabs/ac_s/ooicore/driver.py
@author Rachel Manoni
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u [-t testname]
       $ bin/test_driver -i [-t testname]
       $ bin/test_driver -q [-t testname]
"""

__author__ = 'Rachel Manoni'
__license__ = 'Apache 2.0'

from mock import Mock
from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()
import unittest

from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from mi.idk.unit_test import DriverTestMixin
from mi.idk.unit_test import AgentCapabilityType

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverProtocolState, DriverParameter
from mi.core.instrument.instrument_driver import DriverEvent

from mi.core.instrument.port_agent_client import PortAgentClient

from mi.instrument.wetlabs.ac_s.ooicore.driver import InstrumentDriver
from mi.instrument.wetlabs.ac_s.ooicore.driver import DataParticleType
from mi.instrument.wetlabs.ac_s.ooicore.driver import ProtocolState
from mi.instrument.wetlabs.ac_s.ooicore.driver import ProtocolEvent
from mi.instrument.wetlabs.ac_s.ooicore.driver import Capability
from mi.instrument.wetlabs.ac_s.ooicore.driver import Protocol
from mi.instrument.wetlabs.ac_s.ooicore.driver import Prompt
from mi.instrument.wetlabs.ac_s.ooicore.driver import NEWLINE
from mi.instrument.wetlabs.ac_s.ooicore.driver import OptaaSampleDataParticleKey
from mi.instrument.wetlabs.ac_s.ooicore.driver import OptaaSampleDataParticle
from mi.instrument.wetlabs.ac_s.ooicore.driver import OptaaStatusDataParticleKey

from mi.core.exceptions import SampleException

from pyon.agent.agent import ResourceAgentState


InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.wetlabs.ac_s.ooicore.driver',
    driver_class="InstrumentDriver",
    instrument_agent_resource_id='DQPJJX',
    instrument_agent_name='wetlabs_ac_s_ooicore',
    instrument_agent_packet_config=DataParticleType(),
    driver_startup_config={}
)


def short_sample():
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
                           
    output = ''
    for value in short_sample_values.split():
        output += chr(int(value, 16))
    return output


OPTAA_SAMPLE_DATA = short_sample()


OPTAA_STATUS_DATA = \
    "AC-Spectra Version 1.10     (May 16 2005 09:40:13)" + NEWLINE +\
    "Persistor CF2 SN:12154   BIOS:2.28   PicoDOS:2.28" + NEWLINE + NEWLINE +\
    "14 A/D samples per bin into 20164 long buffers" + NEWLINE +\
    "Spinning up motor for 10 secs. Hit 'Q' to quit."


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
    """
    Mixin class used for storing data particle constants and common data assertion methods.
    """
    ###
    # Parameter and Type Definitions
    ###
    _driver_parameters = {}

    # particle data defined in the OPTAA Driver doc
    _sample_parameters = {
        OptaaSampleDataParticleKey.RECORD_LENGTH: {'type': int, 'value': 0x2a8},
        OptaaSampleDataParticleKey.PACKET_TYPE: {'type': int, 'value': 0x05},
        OptaaSampleDataParticleKey.METER_TYPE: {'type': int, 'value': 0x53},
        OptaaSampleDataParticleKey.SERIAL_NUMBER: {'type': int, 'value': 0x82},
        OptaaSampleDataParticleKey.A_REFERENCE_DARK_COUNTS: {'type': int, 'value': 0x1ce},
        OptaaSampleDataParticleKey.PRESSURE_COUNTS: {'type': int, 'value': 0xffff},
        OptaaSampleDataParticleKey.A_SIGNAL_DARK_COUNTS: {'type': int, 'value': 0x2b0},
        OptaaSampleDataParticleKey.EXTERNAL_TEMP_RAW: {'type': int, 'value': 0x6e47},
        OptaaSampleDataParticleKey.INTERNAL_TEMP_RAW: {'type': int, 'value': 0xa84f},
        OptaaSampleDataParticleKey.C_REFERENCE_DARK_COUNTS: {'type': int, 'value': 0x1d5},
        OptaaSampleDataParticleKey.C_SIGNAL_DARK_COUNTS: {'type': int, 'value': 0x2bd},
        OptaaSampleDataParticleKey.ELAPSED_RUN_TIME: {'type': int, 'value': 0x284d},
        OptaaSampleDataParticleKey.NUM_WAVELENGTHS: {'type': int, 'value': 0x51},
        OptaaSampleDataParticleKey.C_REFERENCE_COUNTS: {'type': list, 'value': [1391, 1632, 1889, 2168, 2473, 2817,
                                                                                3196, 3611, 4060, 4532,
                                                                                5020, 5530, 6058, 6645, 7292, 7964,
                                                                                8657, 9387, 10139, 10907,
                                                                                11687, 12495, 13313, 14139, 14990,
                                                                                15888, 16843, 17865, 18964, 20119,
                                                                                21298, 22437, 23526, 24538, 25494,
                                                                                26419, 27271, 28060, 28759, 29311,
                                                                                29941, 30478, 30928, 31284, 31536,
                                                                                31673, 31706, 31630, 31449, 31170,
                                                                                30786, 30326, 29767, 29146, 28508,
                                                                                27801, 27011, 26145, 25186, 23961,
                                                                                22897, 22027, 21024, 19988, 18945,
                                                                                17919, 16928, 15976, 15070, 14210,
                                                                                13386, 12602, 11856, 11145, 10493,
                                                                                9884, 9317, 8785, 8292, 7835,
                                                                                7418]},
        OptaaSampleDataParticleKey.A_REFERENCE_COUNTS: {'type': list, 'value': [1273, 1499, 1744, 2012, 2304, 2632,
                                                                                2995, 3395, 3825, 4283,
                                                                                4759, 5262, 5780, 6358, 7001, 7668,
                                                                                8360, 9089, 9848, 10630,
                                                                                11421, 12252, 13103, 13961, 14849,
                                                                                15792, 16786, 17853, 19000, 20216,
                                                                                21461, 22682, 23850, 24975, 26048,
                                                                                27059, 28020, 28925, 29739, 30363,
                                                                                31158, 31855, 32457, 32970, 33385,
                                                                                33680, 33849, 33911, 33858, 33705,
                                                                                33440, 33074, 32609, 32047, 31455,
                                                                                30828, 30101, 29283, 28383, 27271,
                                                                                26039, 25148, 24144, 23069, 21974,
                                                                                20877, 19811, 18773, 17771, 16822,
                                                                                15905, 15025, 14190, 13383, 12622,
                                                                                11927, 11270, 10655, 10081, 9547,
                                                                                9054]},
        OptaaSampleDataParticleKey.C_SIGNAL_COUNTS: {'type': list, 'value':    [1225, 1471, 1743, 2040, 2369, 2739,
                                                                                3159, 3616, 4118, 4652,
                                                                                5210, 5797, 6409, 7074, 7834, 8620,
                                                                                9436, 10292, 11191, 12109,
                                                                                13049, 14020, 15015, 16023, 17058,
                                                                                18145, 19307, 20544, 21881, 23294,
                                                                                24745, 26163, 27517, 28808, 29991,
                                                                                31187, 32273, 33304, 34225, 35010,
                                                                                35858, 36596, 37226, 37743, 38136,
                                                                                38389, 38509, 38499, 38352, 38088,
                                                                                37686, 37197, 36591, 35870, 35148,
                                                                                34353, 33438, 32425, 31315, 29877,
                                                                                28439, 27497, 26268, 24992, 23712,
                                                                                22441, 21210, 20025, 18889, 17816,
                                                                                16790, 15808, 14876, 13982, 13165,
                                                                                12405, 11693, 11025, 10408, 9838,
                                                                                9313]},
        OptaaSampleDataParticleKey.A_SIGNAL_COUNTS: {'type': list, 'value':    [918, 1159, 1419, 1696, 1994, 2325,
                                                                                2693, 3100, 3544, 4020,
                                                                                4524, 5059, 5620, 6249, 6953, 7691,
                                                                                8466, 9294, 10160, 11062,
                                                                                11989, 12968, 13982, 15017, 16095,
                                                                                17242, 18459, 19770, 21185, 22692,
                                                                                24244, 25782, 27277, 28734, 30144,
                                                                                31494, 32790, 34031, 35172, 36101,
                                                                                37239, 38270, 39191, 40009, 40707,
                                                                                41269, 41678, 41953, 42084, 42087,
                                                                                41950, 41680, 41279, 40748, 40160,
                                                                                39515, 38734, 37824, 36791, 35473,
                                                                                33988, 32910, 31676, 30340, 28963,
                                                                                27574, 26213, 24882, 23594, 22367,
                                                                                21182, 20041, 18950, 17898, 16905,
                                                                                15993, 15133, 14323, 13567, 12864,
                                                                                12217]}}
            
    _status_parameters = {
        OptaaStatusDataParticleKey.FIRMWARE_VERSION: {'type': unicode, 'value': '1.10'},
        OptaaStatusDataParticleKey.FIRMWARE_DATE: {'type': unicode, 'value': 'May 16 2005 09:40:13'},
        OptaaStatusDataParticleKey.PERSISTOR_CF_SERIAL_NUMBER: {'type': int, 'value': 12154},
        OptaaStatusDataParticleKey.PERSISTOR_CF_BIOS_VERSION: {'type': unicode, 'value': '2.28'},
        OptaaStatusDataParticleKey.PERSISTOR_CF_PICODOS_VERSION: {'type': unicode, 'value': '2.28'}}

    def assert_data_particle_sample(self, data_particle, verify_values=False):
        """
        Verify an optaa  sample data particle
        @param data_particle: OPTAAA_SampleDataParticle data particle
        @param verify_values: bool, should we verify parameter values
        """
        self.assert_data_particle_header(data_particle, DataParticleType.OPTAA_SAMPLE)
        self.assert_data_particle_parameters(data_particle, self._sample_parameters, verify_values)

    def assert_data_particle_status(self, data_particle, verify_values=False):
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

    def test_real_data(self):

        input_data3 = "\xff\x00\xff\x00\x02\xa8\x05\x01\x53\x00\x00\x82\x01\xd0\xff\xff\x02\xb1\x76\x3a\xae\x8b" \
                      "\x01\xd2\x02\xbc\x00\x00\x30\xa4\x01\x51\x00\x02\x00\x01\x00\x00\x00\x01\x00\x02\x00\x01" \
                      "\x00\x01\x00\x00\x00\x03\x00\x01\x00\x02\x00\x01\x00\x01\x00\x01\x00\x02\x00\x00\x00\x04" \
                      "\x00\x01\x00\x01\x00\x01\x00\x02\x00\x01\x00\x02\x00\x01\x00\x03\x00\x01\x00\x01\x00\x00" \
                      "\x00\x01\x00\x01\x00\x02\x00\x00\x00\x01\x00\x01\x00\x01\x00\x00\x00\x02\x00\x01\x00\x01" \
                      "\x00\x01\x00\x02\x00\x01\x00\x02\x00\x00\x00\x04\x00\x01\x00\x02\x00\x01\x00\x02\x00\x01" \
                      "\x00\x01\x00\x00\x00\x04\x00\x01\x00\x02\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x02" \
                      "\x00\x01\x00\x01\x00\x00\x00\x03\x00\x01\x00\x01\x00\x00\x00\x04\x00\x01\x00\x02\x00\x00" \
                      "\x00\x01\x00\x01\x00\x01\x00\x01\x00\x02\x00\x01\x00\x01\x00\x01\x00\x03\x00\x01\x00\x01" \
                      "\x00\x00\x00\x03\x00\x00\x00\x02\x00\x00\x00\x03\x00\x01\x00\x02\x00\x00\x00\x03\x00\x01" \
                      "\x00\x01\x00\x01\x00\x01\x00\x01\x00\x00\x00\x00\x00\x02\x00\x01\x00\x00\x00\x00\x00\x01" \
                      "\x00\x01\x00\x01\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\x02\x00\x01\x00\x02\x00\x00" \
                      "\x00\x02\x00\x00\x00\x01\x00\x00\x00\x02\x00\x01\x00\x01\x00\x00\x00\x02\x00\x01\x00\x02" \
                      "\x00\x01\x00\x02\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x02\x00\x01" \
                      "\x00\x01\x00\x00\x00\x02\x00\x01\x00\x01\x00\x01\x00\x03\x00\x01\x00\x02\x00\x00\x00\x04" \
                      "\x00\x00\x00\x03\x00\x00\x00\x00\x00\x01\x00\x02\x00\x00\x00\x03\x00\x01\x00\x02\x00\x01" \
                      "\x00\x03\x00\x01\x00\x00\x00\x00\x00\x01\x00\x01\x00\x02\x00\x00\x00\x00\x00\x01\x00\x01" \
                      "\x00\x00\x00\x04\x00\x01\x00\x01\x00\x01\x00\x01\x00\x01\x00\x00\x00\x00\x00\x04\x00\x00" \
                      "\x00\x00\x00\x01\x00\x02\x00\x00\x00\x01\x00\x01\x00\x04\x00\x01\x00\x01\x00\x00\x00\x02" \
                      "\x00\x01\x00\x03\x00\x01\x00\x01\x00\x01\x00\x01\x00\x00\x00\x03\x00\x01\x00\x00\x00\x00" \
                      "\x00\x03\x00\x01\x00\x03\x00\x00\x00\x03\x00\x01\x00\x01\x00\x01\x00\x00\x00\x01\x00\x03" \
                      "\x00\x00\x00\x03\x00\x01\x00\x00\x00\x00\x00\x03\x00\x01\x00\x03\x00\x01\x00\x05\x00\x01" \
                      "\x00\x02\x00\x01\x00\x03\x00\x01\x00\x02\x00\x00\x00\x02\x00\x01\x00\x02\x00\x00\x00\x02" \
                      "\x00\x00\x00\x01\x00\x01\x00\x02\x00\x00\x00\x02\x00\x01\x00\x04\x00\x00\x00\x02\x00\x00" \
                      "\x00\x00\x00\x00\x00\x01\x00\x01\x00\x03\x00\x00\x00\x01\x00\x00\x00\x03\x00\x01\x00\x01" \
                      "\x00\x01\x00\x02\x00\x01\x00\x02\x00\x01\x00\x04\x00\x01\x00\x02\x00\x01\x00\x01\x00\x01" \
                      "\x00\x00\x00\x01\x00\x05\x00\x01\x00\x02\x00\x01\x00\x02\x00\x01\x00\x02\x00\x00\x00\x02" \
                      "\x00\x01\x00\x02\x00\x00\x00\x04\x00\x01\x00\x01\x00\x02\x00\x02\x00\x01\x00\x01\x00\x00" \
                      "\x00\x03\x00\x01\x00\x02\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x03\x00\x01\x00\x02" \
                      "\x00\x01\x00\x04\x00\x01\x00\x01\x00\x00\x00\x01\x00\x01\x00\x02\x00\x00\x00\x00\x00\x01" \
                      "\x00\x01\x00\x01\x00\x04\x00\x01\x00\x01\x00\x00\x00\x01\x00\x00\x00\x01\x00\x01\x0d\x36" \
                      "\x00"

        particle = OptaaSampleDataParticle(input_data3)
        particle._build_parsed_values()

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the capabilities
        """

        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(DriverParameter())

        # Test capabilities for duplicates, them verify that capabilities is a subset of protocol events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, OPTAA_SAMPLE_DATA)
        self.assert_chunker_sample_with_noise(chunker, OPTAA_SAMPLE_DATA)
        self.assert_chunker_fragmented_sample(chunker, OPTAA_SAMPLE_DATA)
        self.assert_chunker_combined_sample(chunker, OPTAA_SAMPLE_DATA)

        self.assert_chunker_sample(chunker, OPTAA_STATUS_DATA)
        self.assert_chunker_sample_with_noise(chunker, OPTAA_STATUS_DATA)
        self.assert_chunker_fragmented_sample(chunker, OPTAA_STATUS_DATA)
        self.assert_chunker_combined_sample(chunker, OPTAA_STATUS_DATA)

    def test_corrupt_data_sample(self):
        """
        Verify corrupt data will throw error
        """
        particle = OptaaSampleDataParticle(OPTAA_SAMPLE_DATA.replace('\xff\x00\xff\x00', 'foo'))
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
        self.assert_particle_published(driver, OPTAA_STATUS_DATA, self.assert_data_particle_status, True)
        self.assert_particle_published(driver, OPTAA_SAMPLE_DATA, self.assert_data_particle_sample, True)

    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        mock_callback = Mock(spec=PortAgentClient)
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
            ProtocolState.UNKNOWN: [ProtocolEvent.DISCOVER],
            ProtocolState.COMMAND: [ProtocolEvent.GET,
                                    ProtocolEvent.SET,
                                    ProtocolEvent.START_AUTOSAMPLE,
                                    ProtocolEvent.START_DIRECT],
            ProtocolState.AUTOSAMPLE: [ProtocolEvent.STOP_AUTOSAMPLE],
            ProtocolState.DIRECT_ACCESS: [ProtocolEvent.STOP_DIRECT,
                                          ProtocolEvent.EXECUTE_DIRECT]}

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
class TestINT(InstrumentDriverIntegrationTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    @unittest.skip('Only enable and use when not running a batch')
    def test_status_particle_generation(self):
        """
        To test status particle instrument must be off and powered on while test is waiting
        The status particle is sent only once when the instrument is powered on.
        Cannot start the driver and instrument simultaneously, therefore need to start
        test with instrument off, start the driver, then power on the instrument to capture the
        status particle
        """
        #Test that we can generate particles when in autosample.
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        #NOTE: cannot timeout BEFORE reaching particle count or an error is thrown
        log.debug("turn off, then on the instrument")
        log.debug("waiting 30 seconds for 1 particle status")
        self.assert_async_particle_generation(DataParticleType.OPTAA_STATUS, self.assert_data_particle_status,
                                              particle_count=1, timeout=30)

    def test_autosample_particle_generation(self):

        #Test that we can generate particles when in autosample.
        self.assert_initialize_driver(DriverProtocolState.AUTOSAMPLE)

        log.debug("waiting 100 seconds for 50 particle samples")
        self.assert_async_particle_generation(DataParticleType.OPTAA_SAMPLE, self.assert_data_particle_sample,
                                              particle_count=50, timeout=100)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for doing final testing of ion      #
# integration.  The generally aren't used for instrument debugging and should #
# be tackled after all unit and integration tests are complete                #
###############################################################################
@attr('QUAL', group='mi')
class TestQUAL(InstrumentDriverQualificationTestCase, UtilMixin):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def test_direct_access_telnet_mode(self):
        """
        This test manually tests that the Instrument Driver properly supports direct
        access to the physical instrument.
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)
        self.assert_direct_access_stop_telnet()

    def test_discover(self):
        """
        Over-ridden because instrument doesn't actually have a command mode and therefore
        driver will always go to autosample mode during the discover process after a reset.
        Verify we can discover our instrument state from streaming and autosample.
        """
        # Verify the agent is in command mode
        self.assert_enter_command_mode()

        # Now reset and try to discover.  This will stop the driver and cause it to re-discover which
        # will always go back to autosample for this instrument
        self.assert_reset()
        self.assert_discover(ResourceAgentState.STREAMING)

    def test_get_capabilities(self):
        """
        Walk through all driver protocol states and verify capabilities
        returned by get_current_capabilities
        """
        self.assert_enter_command_mode()
        
        ##################
        #  Command Mode
        ##################
        capabilities = {
            AgentCapabilityType.AGENT_COMMAND: self._common_agent_commands(ResourceAgentState.COMMAND),
            AgentCapabilityType.AGENT_PARAMETER: self._common_agent_parameters(),
            AgentCapabilityType.RESOURCE_COMMAND: [DriverEvent.START_AUTOSAMPLE],
            AgentCapabilityType.RESOURCE_INTERFACE: None,
            AgentCapabilityType.RESOURCE_PARAMETER: self._driver_parameters.keys()}

        self.assert_capabilities(capabilities)

        ##################
        #  Streaming Mode
        ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.STREAMING)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = [DriverEvent.STOP_AUTOSAMPLE]

        self.assert_start_autosample()
        self.assert_capabilities(capabilities)
        self.assert_stop_autosample()

        ##################
        #  DA Mode
        ##################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.DIRECT_ACCESS)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = self._common_da_resource_commands()

        self.assert_direct_access_start_telnet()
        self.assert_capabilities(capabilities)
        self.assert_direct_access_stop_telnet()

        #######################
        #  Uninitialized Mode
        #######################
        capabilities[AgentCapabilityType.AGENT_COMMAND] = self._common_agent_commands(ResourceAgentState.UNINITIALIZED)
        capabilities[AgentCapabilityType.RESOURCE_COMMAND] = []
        capabilities[AgentCapabilityType.RESOURCE_INTERFACE] = []
        capabilities[AgentCapabilityType.RESOURCE_PARAMETER] = []

        self.assert_reset()
        self.assert_capabilities(capabilities)