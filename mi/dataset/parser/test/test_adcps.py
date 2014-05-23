#!/usr/bin/env python

import gevent
import unittest
import os
import copy
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.parser.adcps import AdcpsParser, AdcpsParserDataParticle
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'mflm',
			     'adcp', 'resource')

# store frequently used states
A_IN_PROC = [[868,1254,1,0],[1444,1830,1,0],[2020,2406,1,0],[2665,3050,1,0],[3240,3627,1,0],[3817,4204,1,0],[4461,4847,1,0]]
A_UN_PROC = [[0,32],[607,678],[868,1254],[1444,1830],[2020,2475],[2665,3050],[3240,3627],[3817,4271],[4461,5000]]
B_IN_PROC = [[1444,1830,1,0],[2020,2406,1,0],[2665,3050,1,0],[3240,3627,1,0],[3817,4204,1,0],[4461,4847,1,0]]
B_UN_PROC = [[0,32], [607,678],[1444,1830],[2020,2475],[2665,3050],[3240,3627],[3817,4271],[4461,5000]]
C_IN_PROC = [[2020,2406,1,0],[2665,3050,1,0],[3240,3627,1,0],[3817,4204,1,0],[4461,4847,1,0]]
C_UN_PROC = [[0,32],[607,678],[2020,2475],[2665,3050],[3240,3627],[3817,4271],[4461,5000]]
D_IN_PROC = [[2665,3050,1,0],[3240,3627,1,0],[3817,4204,1,0],[4461,4847,1,0]]
D_UN_PROC = [[0,32],[607,678],[2406,2475],[2665,3050],[3240,3627],[3817,4271],[4461,5000]]

@attr('UNIT', group='mi')
class AdcpsParserUnitTestCase(ParserUnitTestCase):

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcps',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpsParserDataParticle'
            }

        # first AD tag 223-609
        self.particle_a = AdcpsParserDataParticle(b'51F0C39Bn\x7f\x02\x01k\x00\x00\x00\x002(\xdd\x07\x07\x19\x05' \
            '\x1a\x10a]\x0bg\xff\n\x00m\x01\x2b(\x00\x00/\x01\x1c\xcf\xff$\x00\x0f\x00\xff\xff\x07\x00\x00\x00\xa4' \
            '\xff\xcf\xff\xcb\xff\xce\xff\xbc\xff\xf2\xff\xd9\xff\xb6\xff\x9a\xff\xb0\xff\x10\x00\x1f\x00\xd0\xff' \
            '\xbe\xff\xa5\xff\x9b\xffd\x00\x1c\x03\x9b\x020\x00\x14\x00y\xff\xd2\xff\x04\x00\xe0\xff\xc4\xff\xdf' \
            '\xff\xdb\xff\xa3\xff\xa3\xff\xbf\xff\xa5\xff\xa3\xff\x98\xffm\xfft\xff\x95\xff\x8c\xff\xc2\xffx\xff]' \
            '\xffk\xff\x0e\xffS\xffm\xff\n\xfd\x1e\xfd\x98\xffT\xff\xb2\xfe\x01\x00\x03\x00\x10\x00\x06\x00\xfe\xff' \
            '\x05\x00\x0f\x00\x05\x00\xf3\xff\x04\x00\x05\x00\t\x00\x08\x00\x07\x00\r\x00\x18\x00\x1f\x00\x14\x00' \
            '\x0b\x00\x05\x00\x14\x00\x0c\x00\xfc\xff\x1e\x00\xf0\xff\xf9\xff\xec\xff\xcb\xff\x15\x00\xe6\xff\xbf' \
            '\xff\x05\x00\x17\x00\x13\x00\x0c\x00\x1e\x00\x00\x00\x01\x00\x1a\x00\xf3\xff\xe6\xff\xdd\xff\xe5\xff' \
            '\xf7\xff\xf6\xff\xf3\xff\xfd\xff\xe2\xff\x02\x00\x11\x00\xde\xff\xf8\xff\xcc\x00 \x00\xa0\x00\x00\x80\x13y')
        # first AD tag from 871-1257 (there is 1 previous AD but the data is corrupted in it)
        self.particle_b = AdcpsParserDataParticle(b'51F0DFBBn\x7f\x02\x01m\x00\x00\x00\x002(\xdd\x07\x07\x19\x07\x1a' \
            '\x10aE#c\xff\r\x00m\x01\\(\x00\x00/\x01\x1c\xc9\xff\x1e\x00\xf9\xff\xca\xff\xd0\xff\xb5\xff\x8a' \
            '\xff\xa7\xff~\xff\x92\xff\x96\xff\xa1\xff]\xffc\xff\x86\xff_\xff\xd4\xff\xa5\xff\x95\xff\x87\xff' \
            '\x0c\xffO\xff\xc8\xfff\x00\xaa\x00\xdb\xff\xa6\xffn\xff\r\x00*\x00\xfd\xff\x17\x00\xf8\xff\xf9' \
            '\xff-\x006\x00:\x00\x1f\x00\xf1\xff\x03\x00\xea\xff\xf1\xff\x06\x00\x08\x00\xca\xff\xa3\xff\x08' \
            '\x00\x1d\x00\xf1\xff\xfd\xff\xc7\xff\x06\xfe\xd1\xfcr\xfd3\xfe\xa5\xff\xfa\xff\x02\x00\xff\xff' \
            '\xfe\xff\x00\x00\xfc\xff\xfc\xff\xf6\xff\xfd\xff\x01\x00\xfd\xff\xf6\xff\xf9\xff\xfe\xff\xf5\xff' \
            '\xf1\xff\x05\x00\xfb\xff\xf1\xff\xf0\xff\xfa\xff\xed\xff\x01\x00\xdb\xff\xe7\xff\xf2\xff\x14\x00' \
            '\x1f\x00\x0e\x00\x01\x00\xde\xff0\x00\x04\x00\x07\x00\x00\x00\xfa\xff\xed\xff\x1b\x00\x0f\x007' \
            '\x00\xe1\xff\x10\x00\xf5\xff\xf1\xff\xe2\xff\x0f\x00\x17\x00 \x00\x12\x00\xe3\xff\xf0\xff}\x00-' \
            '\x00L\x00\x0e\x00\x00\x80\x91\x89')
        # second AD block from 1447-1833
        self.particle_c = AdcpsParserDataParticle(b'51F0FBDBn\x7f\x02\x01o\x00\x00\x00\x002(\xdd\x07\x07\x19\t\x1a' \
            '\x10a\x7f:a\xff\n\x00m\x01[(\x00\x00/\x01\x1c\xea\xff\xe4\xff\xe8\xff\xb0\xff\xbf\xff\x98\xff' \
            '\xc2\xff\xdd\xff\xce\xff\xd7\xff\xaa\xff\x91\xff\x8a\xff\x96\xff\x83\xff\xda\xff\x81\xff\xb6' \
            '\xff\xca\xff\\\xffK\xff\x85\xff;\x00\xbc\x00\n\x00\x94\x00\xc7\xff \x00\x10\x00\x15\x00A\x009' \
            '\x00 \x00\x1b\x00\x7f\x00R\x00c\x00S\x00D\x00a\x00X\x00t\x00\xa8\x003\x00\x1c\x00J\x00s\x00]' \
            '\x00\x8d\x00D\x00a\xff\xf0\xfb\xcd\xfa\x9d\xfb\xb0\xfd\x05\xff\xfe\xff\xf9\xff\xf6\xff\x05' \
            '\x00\xfe\xff\x05\x00\x02\x00\x14\x00\x0c\x00\n\x00\x13\x00\t\x00\x06\x00\n\x00\x13\x00\x0c' \
            '\x00\r\x00\x19\x00\x0b\x00\x11\x00\x0c\x00\x04\x00%\x00\xec\xff\xd8\xff\xcb\xff!\x00%\x00' \
            '\xfa\xff\xf7\xff\xf4\xff\xff\xff\xee\xff\xf1\xff\x03\x00\xe2\xff\xe0\xff\x12\x00\xe5\xff\xf3' \
            '\xff\xdd\xff\xe1\xff\x03\x00\t\x00\x05\x00\x12\x00\x0b\x00\x02\x00\xec\xff\x16\x00\xc0\x00G' \
            '\x00\xf7\xff\xd0\xff\xd5\xff\x00\x801n')
        # AD block 2025-2412
        self.particle_d = AdcpsParserDataParticle(b'51F117FBn\x7f\x02\x01q\x00\x00\x00\x002(\xdd\x07\x07\x19' \
            '\x0b\x1a\x10a\xf9#^\xff\x05\x00n\x01a(\x00\x00/\x01\x1c\xd1\xff\xfd\xff\xdf\xff\x0f\x00\xdb\xff' \
            '#\x00=\x00.\x00\x08\x00\x05\x00)\x00\x01\x00\x04\x00\x00\x00\xfb\xff\xee\xff\xac\xff\x99\xff\xd2' \
            '\xff\x90\xff\xd9\xff\x93\xff\xba\xff\x13\x00\xd9\xffS\xffY\xffD\xff\x13\x00G\x000\x00J\x00?\x00_' \
            '\x00=\x00>\x002\x00d\x00`\x00\x8b\x00~\x00\xa9\x00\x90\x00\x06\x00\x0b\x00\x12\x00\xfb\xff\x0e' \
            '\x00\x1b\x00\xf9\xff\xd9\xff\x16\xfe\xb7\xfdM\xff\xe5\xffW\x00\x11\x00\x00\x00\xfd\xff\xf7\xff' \
            '\xfb\xff\xf9\xff\xfe\xff\xfc\xff\xfe\xff\x03\x00\xf6\xff\xf7\xff\x01\x00\xf6\xff\xfd\xff\x02\x00' \
            '\x06\x00\xf1\xff\xf9\xff\x05\x00\xfe\xff\xff\xff\x10\x00\xff\xff\xfa\xff\x04\x00\xf8\xff\xf0\xff' \
            '\x10\x00\xec\xff\xf4\xff\x1e\x00\xf8\xff\x06\x00\xf5\xff\xdf\xff\xf2\xff\x03\x00\xf3\xff\xef\xff' \
            '\t\x00\x1f\x00\xcd\xff\xf3\xff\xe1\xff\x18\x00\x06\x00\xfc\xff\xe6\xff\x1d\x00B\x00\xb3\xff\xb7' \
            '\xff\x11\x00\xa3\x00\x00\x80\x9bz')
        # AD block 2673-3058
        self.particle_e = AdcpsParserDataParticle(b'51F1341Bn\x7f\x02\x01s\x00\x00\x00\x002(\xdd\x07\x07\x19' \
            '\r\x1a\x10a\xd10R\xff\x06\x00k\x01E(\x00\x00/\x01\x1c\x1b\x00\x1c\x00\x05\x00\x15\x00%\x00&\x002' \
            '\x00;\x00_\x00R\x00#\x00K\x00M\x00i\x00Z\x00V\x00\x11\x00\x1c\x00F\x00\x1f\x00L\x00\xdc\xff&\x00' \
            '\x8b\x01{\x01\xcc\x00\x06\x01\xe6\x00\xf0\xff\xd0\xff\xd5\xff\xf8\xff\xd9\xff\xdd\xff\xc5\xff\xb6' \
            '\xff\xc9\xff\xec\xff\xf0\xff\xf6\xff\x01\x00:\x001\x00"\x006\x00\xf3\xff\xe0\xff\xc6\xff\xa0\xff' \
            '\xd6\xffx\xff!\xfdG\xfc\xed\xfcr\xfd\xd1\xfe\t\x00\n\x00\xfb\xff\xf9\xff\xfe\xff\xf9\xff\xfe\xff' \
            '\x00\x00\xf6\xff\x01\x00\xfe\xff\xf3\xff\xf7\xff\xf8\xff\xdd\xff\xd2\xff\xea\xff\x02\x00\x02\x00' \
            '\r\x00\x17\x00\x0f\x00\x1c\x00\xf5\xff\x01\x00\xf2\xff\x1e\x00\x16\x00\xf1\xff\xe6\xff\xf9\xff\xef' \
            '\xff\xf0\xff\xff\xff\xe6\xff\xfc\xff\xf4\xff!\x00\x03\x00\xfa\xff\xe7\xff\xee\xff\x0c\x00\x10\x00' \
            '\xf4\xff\x18\x00\x08\x00\x13\x00\xed\xff\x10\x00J\x00\xfe\xff\x12\x00j\xff\x8a\xff\x00\x80^x')
        # 7 AD block 3827-4214
        self.particle_g = AdcpsParserDataParticle(b'51F16C5Bn\x7f\x02\x01w\x00\x00\x00\x002(\xdd\x07\x07\x19' \
            '\x11\x1a\x10a\xc9\x06d\xff\x04\x00m\x01!(\x00\x00/\x01\x1cZ\x00\xf8\xff\x0f\x00\xef\xff\xe8' \
            '\xff\xd7\xff\xe9\xff\xae\xff\xa2\xff\xd1\xff\xba\xff\xd3\xff\xf0\xff\xda\xff\xe7\xff\x05\x00' \
            '\xf6\xff\xd2\xff\xa6\xff\x8e\xff\xa1\xff\x92\xff\x16\x00\x8b\x00\xd2\x00\xad\x00\xd2\xffw\xff' \
            '\xc6\xff\xc9\xff\xdc\xff\xac\xff\xc4\xff\x9d\xffl\xffl\xffr\xff\x8b\xff\x94\xff\xbc\xff\x8d' \
            '\xffr\xff\x97\xff\x98\xff\xbf\xff\xd0\xff\xe5\xff\x92\xffr\xff\x8c\xff7\xffA\xfb\x8d\xfa$\xfb' \
            '\r\xfd7\xfe\x06\x00\x00\x00\x01\x00\t\x00\x01\x00\xfa\xff\x00\x00\xfb\xff\xff\xff\x02\x00\x06' \
            '\x00\x05\x00\x01\x00\x02\x00\x00\x00\xf6\xff\xfd\xff\x04\x00\x02\x00\xfb\xff\x01\x00\x01\x00' \
            '\x02\x00(\x00\x12\x00*\x00L\x00\x17\x00\x12\x00\x02\x00\xff\xff\xf5\xff\t\x00\xf1\xff\xfd\xff ' \
            '\x00\xee\xff\x0c\x00\xef\xff\x1c\x00\xfb\xff\xfd\xff\xd4\xff\xd8\xff\xe0\xff\x10\x00\xe4\xff-' \
            '\x00\xe6\xff\xf5\xff\xd4\xff\xce\xff\xf6\xffl\x00-\x00\x00\x80\x9b\x88')
        # fourth AD block 4471-4857
        self.particle_h = AdcpsParserDataParticle(b'51F1887Bn\x7f\x02\x01y\x00\x00\x00\x002(\xdd\x07\x07\x19\x13\x1a' \
            '\x10a\x9d\x1ba\xff\x06\x00m\x01$(\x00\x00/\x01\x1c\xf7\xff\xfa\xff\xd5\xff\xc5\xff\xb5\xff\x90' \
            '\xffb\xffn\xff\x90\xffq\xff\x9e\xff\x8c\xff\x93\xff\x80\xff\xa6\xff\x82\xff\xa9\xff\xa8\xff\xb4' \
            '\xfff\xffu\xff\x94\xffg\xff\t\xff\x08\xff\x13\xff\x1c\xffx\xff\x07\x00\x1b\x00\xe8\xff\x07\x00' \
            '\x04\x00\x10\x00\x0e\x008\x00;\x00"\x00#\x00\xe6\xff\xf5\xff\xf6\xff\xce\xff\xc4\xff\xec\xff\xc4' \
            '\xff\xd0\xff\xb9\xff\x9f\xff\xca\xff8\xff|\xfbC\xfa2\xfb\x1d\xfeJ\xff\x02\x00\xfe\xff\x00\x00' \
            '\xfd\xff\xf8\xff\x01\x00\xff\xff\xfc\xff\n\x00\r\x00\x06\x00\x06\x00\xfe\xff\x04\x00\x04\x00\x05' \
            '\x00\x04\x00\x08\x00\t\x00\x08\x00\x03\x00\x0f\x00\xea\xff\xf8\xff\xf7\xff(\x00\x17\x00\xef\xff)' \
            '\x00\x13\x00\x03\x00\xf7\xff\x13\x00\xff\xff\xe9\xff\xf9\xff\x1a\x00\x12\x00\xdc\xff-\x00\xfe' \
            '\xff\xed\xff\xfa\xff\xf2\xff\x08\x00\xe0\xff\n\x00\x01\x00!\x00\x17\x00\xd0\xff\xd9\xff\xda\xff' \
            '\x88\x00\x8e\x00\x00\x80\x1e\x7f')
        # second to last AD, 20938
        self.particle_before_end = AdcpsParserDataParticle(b'51F3BAFBn\x7f\x02\x01\xa1\x00\x00\x00\x002(\xdd' \
            '\x07\x07\x1b\x0b\x1a\x10a\xffB[\xff\n\x00n\x01N(\x00\x00/\x01\x1c\xfd\xff\xd6\xff\xb1\xff\xb7' \
            '\xff\xda\xff\xd3\xff\xc6\xff\xe4\xff\xea\xff\xd2\xff\xbf\xff\xc9\xff\xe6\xff\xf0\xff\xaf\xff\xba' \
            '\xff\xd1\xff\x06\x00\xe3\xff\xd5\xff\xc0\xff\xc8\xff\x8a\xff\xdd\xfe\xda\xfe\xb9\xff/\x00\xf3\xff' \
            '\'\x00G\x00H\x005\x00f\x00c\x00U\x00x\x00\x9d\x00\x9c\x00}\x00\x96\x00\xa3\x00\x96\x00\x80\x00G' \
            '\x00\x05\x00\xd9\xff\x16\x00\x0b\x00\x04\x00<\x00\xc1\x00\x88\x02>\x03G\x01e\x00\xfc\x00\x0b\x00' \
            '\x10\x00\x08\x00\t\x00\x00\x00\r\x00\x05\x00\r\x00\r\x00\x02\x00\t\x00\n\x00\x0e\x00\n\x00\x07\x00' \
            '\xf3\xff\xff\xff\t\x00\xff\xff\x0b\x00\x07\x00\x00\x00\xf0\xff\x1e\x00\x18\x00N\x00\x18\x00\x14' \
            '\x00\x00\x00\x17\x00\x0e\x00\xfb\xff\n\x003\x00\xd9\xff\xeb\xff\x06\x00\xe6\xff\x13\x00\xef\xff' \
            '\x15\x00%\x00\x1d\x00\x14\x00\x01\x00\x1e\x00\xf9\xff\x0b\x006\x00"\x00\xe1\xff\xba\xff\x87\xff' \
            'O\x01#\x00\x00\x80\xfe^')
        # last, 29th, AD block 21587-21975
        self.particle_end = AdcpsParserDataParticle(b"51F3D71Bn\x7f\x02\x01\xa3\x00\x00\x00\x002(\xdd\x07\x07" \
            "\x1b\r\x1a\x10a\xcb,T\xff\n\x00m\x01Z(\x00\x00/\x01\x1c\xff\xff\xf8\xff\xd6\xff\xe9\xff\x1f\x00" \
            "\xfd\xff0\x003\x00C\x00R\x00Z\x00J\x00\t\x00\xf1\xff\x0b\x00\x12\x00\xff\xff\xf8\xff\x18\x00\xc0" \
            "\xff\xc0\xff\xc2\xff\xd8\xff5\x00u\x00\x06\x01\xfb\x00/\x00\xe0\xff\xf4\xff5\x00\x17\x00!\x00d\x00B" \
            "\x00'\x00\x14\x00\x1e\x00B\x00/\x007\x004\x00\x9d\x00B\x00\xc2\xff\x8f\xff\xc0\xff\x99\xff\x15\x00" \
            "\xdf\xffJ\x00n\x02%\x03\x81\x02Y\x01\x1c\x00\x03\x00\x00\x00\x04\x00\xfb\xff\x03\x00\xfd\xff\xfe\xff" \
            "\x01\x00\x07\x00\x07\x00\x07\x00\xfc\xff\x05\x00\xe4\xff\xdd\xff\xd4\xff\xf1\xff\x16\x00\x16\x00\x13" \
            "\x00\x16\x00\t\x00\x08\x00\x0b\x00\x02\x00\x03\x00\x0b\x00\x1f\x00\x01\x00\x00\x00\xe7\xff\xfa\xff\xfb" \
            "\xff\xf8\xff%\x00\xe6\xff\xd1\xff\xca\xff\x05\x00\x00\x00\x0f\x00\x06\x00\x08\x00\xf7\xff\xf0\xff\x11" \
            "\x00\xf7\xff\xf9\xff\xf3\xff\xfb\xff\xd9\xff&\x00\x1b\x00r\x00\xc8\xff\x00\x80ra")

        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def assert_result(self, result, in_process_data, unprocessed_data, particle):
        self.assertEqual(result, [particle])
        self.assert_state(in_process_data, unprocessed_data)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def assert_state(self, in_process_data, unprocessed_data):
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)

    def test_simple(self):
        """
        Read test data from the file and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        log.debug('Starting test_simple')
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        # NOTE: using the unprocessed data state of 0,5000 limits the file to reading
        # just 5000 bytes, so even though the file is longer it only reads the first
        # 5000
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle, 
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, A_IN_PROC, A_UN_PROC, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, B_IN_PROC, B_UN_PROC, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, C_IN_PROC, C_UN_PROC, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, D_IN_PROC, D_UN_PROC, self.particle_d)
        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        log.debug('Starting test_get_many')
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
            StateKey.IN_PROCESS_DATA:[]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle, 
                                  self.state_callback, self.pub_callback, self.exception_callback) 

        result = self.parser.get_records(5)
        self.stream_handle.close()
        self.assertEqual(result,
                         [self.particle_a, self.particle_b, self.particle_c, self.particle_d,
                          self.particle_e])
        self.assert_state([[3240,3627,1,0],[3817,4204,1,0],[4461,4847,1,0]],
                        [[0,32],[607,678],[2406,2475],[3240,3627],[3817,4271],[4461,5000]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_d)
        self.assertEqual(self.publish_callback_value[4], self.particle_e)
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream(self):
        log.debug('Starting test_long_stream')
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        data = self.stream_handle.read()
        data_len = len(data)
        self.stream_handle.seek(0)
        self.state = {StateKey.UNPROCESSED_DATA:[[0, data_len]],
            StateKey.IN_PROCESS_DATA:[]}
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(29)
        self.stream_handle.close()
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[-2], self.particle_before_end)
        self.assertEqual(result[-1], self.particle_end)
        self.assert_state([],
            [[0, 32], [607, 678], [2406, 2475], [4204, 4271], [6161, 6230], [7958,8027], [15738, 15807],
                [17697, 17766], [19495,19564], [21292, 21361], [21938, 22000]])
        self.assertEqual(self.publish_callback_value[-2], self.particle_before_end)
        self.assertEqual(self.publish_callback_value[-1], self.particle_end)
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        log.debug('Starting test_mid_state_start')
        new_state = {StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0,32], [607, 678], [1444,5000]]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, C_IN_PROC, C_UN_PROC, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, D_IN_PROC, D_UN_PROC, self.particle_d)
        
        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        log.debug('Starting test_in_process_start')
        new_state = {StateKey.IN_PROCESS_DATA: [[868,1254,1,0],[1444,1830,1,0],[2020,2406,1,0],
            [2665,3050,1,0],[3240,3627,1,0],[3817,4204,1,0],[4461,4847,1,0]],
            StateKey.UNPROCESSED_DATA: [[0,32],[607,678],[868,1254],[1444,1830],
                [2020,2475],[2665,3050],[3240,3627],[3817,4271],[4461,5000]]}
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, new_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(1)
        
        self.assert_result(result, B_IN_PROC, B_UN_PROC, self.particle_b)
        
        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_c)
        self.assertEqual(result[1], self.particle_d)
        self.assert_state(D_IN_PROC, D_UN_PROC)
        self.assertEqual(self.publish_callback_value[-1], self.particle_d)
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state(self):
        """
        test changing the state after initializing
        """
        log.debug('Starting test_set_state')
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 3800]], StateKey.IN_PROCESS_DATA:[]}
        # add in c particle as unprocessed
        new_state = {StateKey.UNPROCESSED_DATA:[[0,32],[607,678],[1444,1830],[2406,2475],[2665,3050],[3800,5000]],
            StateKey.IN_PROCESS_DATA:[]}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)
        # there should only be 6 records, make sure we stop there
        result = self.parser.get_records(6)
        self.assert_state([],
            [[0,32],[607,678],[2406,2475],[3627,3800]])
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,32],[607,678],[2406,2475],[2665,3050],[3800,5000]],
                           self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,32],[607,678],[2406,2475],[3800,5000]],
                           self.particle_e)
        self.assertEqual(self.exception_callback_value, None)
        self.stream_handle.close()

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        log.debug('Starting test_update')
        self.state = {StateKey.UNPROCESSED_DATA:[[0, 5000]],
            StateKey.IN_PROCESS_DATA:[]}
        # this file has a block of AD data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replaced.dat'))
        self.parser = AdcpsParser(self.config, self.state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, [[868,1254,1,0],[1444,1830,1,0],[2020,2406,1,0],[2665,3050,1,0],[3240,3627,1,0],[4461,4847,1,0]],
                           [[0,32],[607,678],[868,1254],[1444,1830],[2020,2475],[2665,3050],[3240,3627],[3817,4271],[4461,5000]],
                           self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, [[1444,1830,1,0],[2020,2406,1,0],[2665,3050,1,0],[3240,3627,1,0],[4461,4847,1,0]],
                           [[0,32], [607,678],[1444,1830],[2020,2475],[2665,3050],[3240,3627],[3817,4271],[4461,5000]],
                           self.particle_b)
        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of CT data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = AdcpsParser(self.config, next_state, self.stream_handle,
                                  self.state_callback, self.pub_callback, self.exception_callback)

        # first get the old 'in process' records
        # Once those are done, the un processed data will be checked
        result = self.parser.get_records(5)
        self.assertEqual(result[0], self.particle_c)
        self.assertEqual(result[1], self.particle_d)
        self.assertEqual(result[2], self.particle_e)
        self.assert_state([],[[0,32],[607,678],[2406,2475],[3817,4271],[4847,5000]])
        # this should be the first of the newly filled in particles from
        result = self.parser.get_records(1)
        self.assert_result(result, [],
                           [[0,32],[607,678],[2406,2475],[4204,4271],[4847,5000]],
                           self.particle_g)
        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

