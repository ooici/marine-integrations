#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_wfp_eng__stc_imodem
@file marine-integrations/mi/dataset/parser/test/test_wfp_eng__stc_imodem.py
@author Emily Hahn
@brief Test code for a Wfp_eng__stc_imodem data parser
"""

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodemParser, StateKey
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodem_engineeringParserDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodem_profileParserDataParticle

@attr('UNIT', group='mi')
class Wfp_eng__stc_imodemParserUnitTestCase(ParserUnitTestCase):
    """
    Wfp_eng__stc_imodem Parser unit test suite
    """
    
TEST_DATA = '\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00R\x9d\xab\xa2R\x9d\xac\x19R\x9d\xac\x1d' \ 
    '\x00\x00\x00\x00A:6\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\x00h\x00NR\x9d\xac!C\t\xf2\xf7A9A!\x00\x00\x00\x00\x00' \
    '\x00\x00\x00\x00\xf2\x00c\x00OR\x9d\xac&C\xbc\x9f\xa7A7\'\xbb\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x00^\x00OR\x9d\xac' \
    '*C\xc5\xad\x08A6\xd5\xd0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb4\x00n\x00OR\x9d\xac/C\xb8COA6\xde\x01\x00\x00\x00\x00' \
    '\x00\x00\x00\x00\x00\x9d\x00p\x00QR\x9d\xac3C\x98\xe5TA733\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa4\x00u\x00OR\x9d\xac' \
    '8C\x9566A7!-\x00\x00\x00\x00\x00\x00\x00\x00\x00\x9a\x00o\x00OR\x9d\xac?C\xa1\xd7\xc3A6\xa6LB\x8bG\xae\x00\x00\x00\x00' \
    '\x00\xb6\x00v\x00PR\x9d\xacECsS\xfeA7e\xfeB\x88\x00\x00\x00\x00\x00\x00\x00\x98\x00s\x00QR\x9d\xacKC\x89\x17\x8cA6\xe2' \
    '\xecB\x84\x99\x9a\x00\x00\x00\x00\x00\xa4\x00\x81\x00PR\x9d\xacQC}\n\xbfA7\x00hB\x81G\xae\x00\x00\x00\x00\x00\xa2\x00|' \
    '\x00NR\x9d\xacWCyW\xc7A6\x97\x8dB{\xe1H\x00\x00\x00\x00\x00\x9a\x00m\x00NR\x9d\xac]C\x8c!#A6\x9f\xbeBuQ\xec\x00\x00\x00' \
    '\x00\x00\x97\x00s\x00QR\x9d\xaccC\x84!9A6h\nBn\x8f\\\x00\x00\x00\x00\x00\x9f\x00v\x00NR\x9d\xaciCE\xa5UA6a|Bh=q\x00\x00' \
    '\x00\x00\x00\x97\x00l\x00PR\x9d\xacoC\xa5\xa5\xadA5\x94\xafBa\\)\x00\x00\x00\x00\x00\x9b\x00n\x00RR\x9d\xacuC\\\r\x08A6' \
    '\x14{B[\n=\x00\x00\x00\x00\x00\x9a\x00s\x00OR\x9d\xac{C\xa3\x0b\xb8A5F\nBT33\x00\x00\x00\x00\x00\x98\x00q\x00NR\x9d\xac' \
    '\x81CO\xc0+A5\xd7\xdcBM\xd7\n\x00\x00\x00\x00\x00\x97\x00n\x00PR\x9d\xac\x87Cxp\xd0A5#\xa3BGG\xae\x00\x00\x00\x00\x00\x9b' \
    '\x00n\x00PR\x9d\xac\x8dC\x84\xdd\xd9A5X\x10B@\xae\x14\x00\x00\x00\x00\x00\xa5\x00v\x00OR\x9d\xac\x93C\xa0\x85\x01A4j\x7f' \
    'B:\x14{\x00\x00\x00\x00\x00\x9c\x00t\x00QR\x9d\xac\x99Cq\xa4\xdbA5:\x92B3\xc2\x8f\x00\x00\x00\x00\x00\x9c\x00x\x00PR\x9d' \
    '\xac\x9fCg\x07#A5\x18+B-\x00\x00\x00\x00\x00\x00\x00\x9e\x00m\x00QR\x9d\xac\xa5C\x9bw\x96A4FtB&z\xe1\x00\x00\x00\x00\x00' \
    '\xd7\x00s\x00OR\x9d\xac\xabCmP5A4\x9dJB\x1f\xd7\n\x00\x00\x00\x00\x00\x99\x00s\x00PR\x9d\xac\xb1C\xad\x960A3\x8a\tB\x19' \
    '(\xf6\x00\x00\x00\x00\x00\x95\x00n\x00OR\x9d\xac\xb7C\x0c\xce]A5\x0f\xfaB\x12\xe1H\x00\x00\x00\x00\x00\x9c\x00u\x00PR\x9d' \
    '\xac\xbdC\xa1\xeb\x02A3Z\x85B\x0c=q\x00\x00\x00\x00\x00\x95\x00u\x00OR\x9d\xac\xc3C$\xafOA4\xa23B\x05\xe1H\x00\x00\x00\x00' \
    '\x00\x99\x00r\x00PR\x9d\xac\xc9C\xae\xddeA3\x0f(A\xfe(\xf6\x00\x00\x00\x00\x00\x9a\x00o\x00OR\x9d\xac\xcfA\xfa\xb2:A5\x0b'
    '\x0fA\xf2\x8f\\\x00\x00\x00\x00\x00\xaf\x00m\x00P\xff\xff\xff\xff\x00\x00\x00\rR\x9d\xac\xd4R\x9d\xadQ'

    
    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
	ParserUnitTestCase.setUp(self)
	self.config = {
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng__stc_imodem',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'Wfp_eng__stc_imodem_engineeringParserDataParticle'
	    }
	
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
	self.timestamp1_eng = 0
	self.particle_a_eng = Wfp_eng__stc_imodem_engineeringParserDataParticle(b'',
              internal_timestamp=self.timestamp1_eng)
	
	self.timestamp2_eng = 0
	self.particle_b_eng = Wfp_eng__stc_imodem_engineeringParserDataParticle(b'',
              internal_timestamp=self.timestamp2_eng)
	
	self.timestamp3_eng = 0
	self.particle_c_eng = Wfp_eng__stc_imodem_engineeringParserDataParticle(b'',
              internal_timestamp=self.timestamp3_eng)
	
    	self.timestamp1_prof = 0
	self.particle_a_prof = Wfp_eng__stc_imodem_profileParserDataParticle(b'',
              internal_timestamp=self.timestamp1_prof)
	
	self.timestamp2_prof = 0
	self.particle_b_prof = Wfp_eng__stc_imodem_profileParserDataParticle(b'',
              internal_timestamp=self.timestamp2_prof)
	
	self.timestamp3_prof = 0
	self.particle_c_prof = Wfp_eng__stc_imodem_profileParserDataParticle(b'',
              internal_timestamp=self.timestamp3_prof)

        self.state_callback_value = None
        self.publish_callback_value = None
	
    def assert_result(self, result, position, particle):
        self.assertEqual(result, [particle])

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], position)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
	Read test data and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
        self.stream_handle = StringIO(WfpParserUnitTestCase.TEST_DATA)
        self.parser = WfpParser(self.config, self.position, self.stream_handle,
                                  self.pos_callback, self.pub_callback) # last one is the link to the data source

        result = self.parser.get_records(1)
        self.assert_result(result, 213, self.particle_a)
        result = self.parser.get_records(1)
        self.assert_result(result, 262, self.particle_b)
        result = self.parser.get_records(1)
        self.assert_result(result, 311, self.particle_c)
        result = self.parser.get_records(1)
        self.assert_result(result, 360, self.particle_d)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 360)
        self.assertEqual(self.position_callback_value[StateKey.POSITION], 360)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_d)

    def test_get_many(self):
	"""
	Read test data and pull out multiple data particles at one time.
	Assert that the results are those we expected.
	"""
        pass

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        pass

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        pass

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        pass
