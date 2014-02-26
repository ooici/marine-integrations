#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_wfp_eng__stc_imodem
@file marine-integrations/mi/dataset/parser/test/test_wfp_eng__stc_imodem.py
@author Emily Hahn
@brief Test code for a Wfp_eng__stc_imodem data parser
"""
import ntplib
import struct
from StringIO import StringIO

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.WFP_E_file_common import StateKey
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodemParser
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodem_startParserDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodem_engineeringParserDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem import Wfp_eng__stc_imodem_statusParserDataParticle

@attr('UNIT', group='mi')
class Wfp_eng__stc_imodemParserUnitTestCase(ParserUnitTestCase):
    """
    Wfp_eng__stc_imodem Parser unit test suite
    """
    
    TEST_DATA_SHORT = "\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00R\x9d\xab\xa2R\x9d\xac\x19R\x9d\xac" \
        "\x1d\x00\x00\x00\x00A:6\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\x00h\x00NR\x9d\xac!C\t\xf2\xf7A9A!\x00\x00\x00" \
        "\x00\x00\x00\x00\x00\x00\xf2\x00c\x00OR\x9d\xac&C\xbc\x9f\xa7A7'\xbb\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x00^" \
        "\x00OR\x9d\xac*C\xc5\xad\x08A6\xd5\xd0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb4\x00n\x00O" 

    TEST_DATA = "\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00R\x9d\xab\xa2R\x9d\xac\x19R\x9d\xac\x1d\x00" \
        "\x00\x00\x00A:6\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\x00h\x00NR\x9d\xac!C\t\xf2\xf7A9A!\x00\x00\x00\x00" \
        "\x00\x00\x00\x00\x00\xf2\x00c\x00OR\x9d\xac&C\xbc\x9f\xa7A7'\xbb\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x00^" \
        "\x00OR\x9d\xac*C\xc5\xad\x08A6\xd5\xd0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb4\x00n\x00OR\x9d\xac/C\xb8COA6\xde" \
        "\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x9d\x00p\x00QR\x9d\xac3C\x98\xe5TA733\x00\x00\x00\x00\x00\x00\x00\x00" \
        "\x00\xa4\x00u\x00OR\x9d\xac8C\x9566A7!-\x00\x00\x00\x00\x00\x00\x00\x00\x00\x9a\x00o\x00OR\x9d\xac?C\xa1\xd7\xc3" \
        "A6\xa6LB\x8bG\xae\x00\x00\x00\x00\x00\xb6\x00v\x00PR\x9d\xacECsS\xfeA7e\xfeB\x88\x00\x00\x00\x00\x00\x00\x00" \
        "\x98\x00s\x00QR\x9d\xacKC\x89\x17\x8cA6\xe2\xecB\x84\x99\x9a\x00\x00\x00\x00\x00\xa4\x00\x81\x00PR\x9d\xacQC}\n" \
        "\xbfA7\x00hB\x81G\xae\x00\x00\x00\x00\x00\xa2\x00|\x00NR\x9d\xacWCyW\xc7A6\x97\x8dB{\xe1H\x00\x00\x00\x00\x00\x9a" \
        "\x00m\x00NR\x9d\xac]C\x8c!#A6\x9f\xbeBuQ\xec\x00\x00\x00\x00\x00\x97\x00s\x00QR\x9d\xaccC\x84!9A6h\nBn\x8f\\\x00" \
        "\x00\x00\x00\x00\x9f\x00v\x00NR\x9d\xaciCE\xa5UA6a|Bh=q\x00\x00\x00\x00\x00\x97\x00l\x00PR\x9d\xacoC\xa5\xa5\xad" \
        "A5\x94\xafBa\\)\x00\x00\x00\x00\x00\x9b\x00n\x00RR\x9d\xacuC\\\r\x08A6\x14{B[\n=\x00\x00\x00\x00\x00\x9a\x00s\x00" \
        "OR\x9d\xac{C\xa3\x0b\xb8A5F\nBT33\x00\x00\x00\x00\x00\x98\x00q\x00NR\x9d\xac\x81CO\xc0+A5\xd7\xdcBM\xd7\n\x00\x00" \
        "\x00\x00\x00\x97\x00n\x00PR\x9d\xac\x87Cxp\xd0A5#\xa3BGG\xae\x00\x00\x00\x00\x00\x9b\x00n\x00PR\x9d\xac\x8dC\x84" \
        "\xdd\xd9A5X\x10B@\xae\x14\x00\x00\x00\x00\x00\xa5\x00v\x00OR\x9d\xac\x93C\xa0\x85\x01A4j\x7fB:\x14{\x00\x00\x00\x00" \
        "\x00\x9c\x00t\x00QR\x9d\xac\x99Cq\xa4\xdbA5:\x92B3\xc2\x8f\x00\x00\x00\x00\x00\x9c\x00x\x00PR\x9d\xac\x9fCg\x07#A5" \
        "\x18+B-\x00\x00\x00\x00\x00\x00\x00\x9e\x00m\x00QR\x9d\xac\xa5C\x9bw\x96A4FtB&z\xe1\x00\x00\x00\x00\x00\xd7\x00s" \
        "\x00OR\x9d\xac\xabCmP5A4\x9dJB\x1f\xd7\n\x00\x00\x00\x00\x00\x99\x00s\x00PR\x9d\xac\xb1C\xad\x960A3\x8a\tB\x19" \
        "(\xf6\x00\x00\x00\x00\x00\x95\x00n\x00OR\x9d\xac\xb7C\x0c\xce]A5\x0f\xfaB\x12\xe1H\x00\x00\x00\x00\x00\x9c\x00u" \
        "\x00PR\x9d\xac\xbdC\xa1\xeb\x02A3Z\x85B\x0c=q\x00\x00\x00\x00\x00\x95\x00u\x00OR\x9d\xac\xc3C$\xafOA4\xa23B\x05" \
        "\xe1H\x00\x00\x00\x00\x00\x99\x00r\x00PR\x9d\xac\xc9C\xae\xddeA3\x0f(A\xfe(\xf6\x00\x00\x00\x00\x00\x9a\x00o\x00O" \
        "R\x9d\xac\xcfA\xfa\xb2:A5\x0b\x0fA\xf2\x8f\\\x00\x00\x00\x00\x00\xaf\x00m\x00P\xff\xff\xff\xff\x00\x00\x00\rR\x9d" \
        "\xac\xd4R\x9d\xadQ"

    # all flags set to zero
    TEST_DATA_BAD_FLAGS = "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00R\x9d\xab\xa2R\x9d\xac\x19R\x9d\xac\x1d" \
        "\x00\x00\x00\x00A:6\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\x00h\x00NR\x9d\xac!C\t\xf2\xf7A9A!\x00\x00\x00\x00\x00" \
        "\x00\x00\x00\x00\xf2\x00c\x00OR\x9d\xac&C\xbc\x9f\xa7A7'\xbb\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x00^\x00OR\x9d\xac" \
        "*C\xc5\xad\x08A6\xd5\xd0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb4\x00n\x00O"

    # took 5 bytes out of second engineering sample
    TEST_DATA_BAD_ENG = "\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00R\x9d\xab\xa2R\x9d\xac\x19R\x9d\xac\x1d" \
        "\x00\x00\x00\x00A:6\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\x00h\x00NR\x9d\xac!C\t!\x00\x00\x00\x00\x00" \
        "\x00\x00\x00\x00\xf2\x00c\x00OR\x9d\xac&C\xbc\x9f\xa7A7'\xbb\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x00^\x00OR\x9d\xac" \
        "*C\xc5\xad\x08A6\xd5\xd0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb4\x00n\x00O"

    
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.file_ingested = file_ingested
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng__stc_imodem',
            DataSetDriverConfigKeys.PARTICLE_CLASS: ['Wfp_eng__stc_imodem_statusParserDataParticle',
                                                     'Wfp_eng__stc_imodem_startParserDataParticle',
                                                     'Wfp_eng__stc_imodem_engineeringParserDataParticle']
            }

	self.start_state = {StateKey.POSITION: 0}

        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
        self.timestamp1_time = self.timestamp_to_ntp('R\x9d\xac\x19')
        self.particle_a_time = Wfp_eng__stc_imodem_startParserDataParticle(b'\x00\x01\x00\x00' \
            '\x00\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00R\x9d\xab\xa2R\x9d\xac\x19',
              internal_timestamp=self.timestamp1_time)

        self.timestamp1_eng = self.timestamp_to_ntp('R\x9d\xac\x1d')
        self.particle_a_eng = Wfp_eng__stc_imodem_engineeringParserDataParticle(b'R\x9d\xac\x1d' \
            '\x00\x00\x00\x00A:6\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\x00h\x00N',
            internal_timestamp=self.timestamp1_eng)

        self.timestamp2_eng = self.timestamp_to_ntp('R\x9d\xac!')
        self.particle_b_eng = Wfp_eng__stc_imodem_engineeringParserDataParticle(b'R\x9d\xac!C\t' \
            '\xf2\xf7A9A!\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf2\x00c\x00O',
            internal_timestamp=self.timestamp2_eng)

        self.timestamp3_eng = self.timestamp_to_ntp('R\x9d\xac&')
        self.particle_c_eng = Wfp_eng__stc_imodem_engineeringParserDataParticle(b"R\x9d\xac&C\xbc" \
            "\x9f\xa7A7'\xbb\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x00^\x00O",
            internal_timestamp=self.timestamp3_eng)

        self.timestamp4_eng = self.timestamp_to_ntp('R\x9d\xac*')
        self.particle_d_eng = Wfp_eng__stc_imodem_engineeringParserDataParticle(b'R\x9d\xac' \
            '*C\xc5\xad\x08A6\xd5\xd0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb4\x00n\x00O',
            internal_timestamp=self.timestamp4_eng)

        self.timestamp_last_eng = self.timestamp_to_ntp('R\x9d\xac\xcf')
        self.particle_last_eng = Wfp_eng__stc_imodem_engineeringParserDataParticle(b'R\x9d\xac\xcfA' \
            '\xfa\xb2:A5\x0b\x0fA\xf2\x8f\\\x00\x00\x00\x00\x00\xaf\x00m\x00P',
            internal_timestamp=self.timestamp_last_eng)

        self.timestamp1_stat = self.timestamp_to_ntp('R\x9d\xac\xd4')
        self.particle_a_stat = Wfp_eng__stc_imodem_statusParserDataParticle(b'\xff\xff\xff\xff' \
            '\x00\x00\x00\rR\x9d\xac\xd4R\x9d\xadQ',
            internal_timestamp=self.timestamp1_stat)

	# uncomment the following to generate particles in yml format for driver testing results files
	#self.particle_to_yml(self.particle_a_time)
	#self.particle_to_yml(self.particle_a_eng)
	#self.particle_to_yml(self.particle_b_eng)
	#self.particle_to_yml(self.particle_c_eng)
	#self.particle_to_yml(self.particle_d_eng)
        #self.particle_to_yml(self.particle_a_stat)

        self.file_ingested = False
        self.state_callback_value = None
        self.publish_callback_value = None

    def timestamp_to_ntp(self, hex_timestamp):
        fields = struct.unpack('>I', hex_timestamp)
        timestamp = int(fields[0])
        return ntplib.system_to_ntp_time(timestamp)

    def particle_to_yml(self, particle):
        """
        This is added as a testing helper, not actually as part of the parser tests. Since the same particles
        will be used for the driver test it is helpful to write them to .yml in the same form they need in the
        results.yml files here.
        """
        particle_dict = particle.generate_dict()
        # open write append, if you want to start from scratch manually delete this file
        fid = open('particle.yml', 'a')
        fid.write('  - _index: 0\n')
        fid.write('    internal_timestamp: %f\n' % particle_dict.get('internal_timestamp'))
        fid.write('    particle_object: %s\n' % particle.__class__.__name__)
        fid.write('    particle_type: %s\n' % particle_dict.get('stream_name'))
        for val in particle_dict.get('values'):
            if isinstance(val.get('value'), float):
                fid.write('    %s: %16.16f\n' % (val.get('value_id'), val.get('value')))
            else:
                fid.write('    %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()

    def assert_result(self, result, position, particle, ingested):
        self.assertEqual(result, [particle])
        self.assertEqual(self.file_ingested, ingested)

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(Wfp_eng__stc_imodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = Wfp_eng__stc_imodemParser(self.config, self.start_state, self.stream_handle,
                                                self.state_callback, self.pub_callback) # last one is the link to the data source

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_time, False)

        # next get engineering records
        result = self.parser.get_records(1)
        self.assert_result(result, 50, self.particle_a_eng, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 76, self.particle_b_eng, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng, True)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 128)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 128)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_d_eng)

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(Wfp_eng__stc_imodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = Wfp_eng__stc_imodemParser(self.config, self.start_state, self.stream_handle,
                                                self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_time, False)

        result = self.parser.get_records(4)
        self.assertEqual(result, [self.particle_a_eng, self.particle_b_eng, self.particle_c_eng, self.particle_d_eng])
        self.assertEqual(self.parser._state[StateKey.POSITION], 128)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 128)
        self.assertEqual(self.publish_callback_value[0], self.particle_a_eng)
        self.assertEqual(self.publish_callback_value[1], self.particle_b_eng)
        self.assertEqual(self.publish_callback_value[2], self.particle_c_eng)
        self.assertEqual(self.publish_callback_value[3], self.particle_d_eng)
	self.assertEqual(self.file_ingested, True)

    def test_long_stream(self):
        """
        Test a long stream of data
        """
        self.stream_handle = StringIO(Wfp_eng__stc_imodemParserUnitTestCase.TEST_DATA)
        self.parser = Wfp_eng__stc_imodemParser(self.config, self.start_state, self.stream_handle,
                                                self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_time, False)

        result = self.parser.get_records(32)
        self.assertEqual(result[0], self.particle_a_eng)
        self.assertEqual(result[-1], self.particle_last_eng)
        self.assertEqual(self.parser._state[StateKey.POSITION], 856)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 856)
        self.assertEqual(self.publish_callback_value[-1], self.particle_last_eng)

        result = self.parser.get_records(1)
        self.assert_result(result, 872, self.particle_a_stat, True)

    def test_after_header(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:24}
        self.stream_handle = StringIO(Wfp_eng__stc_imodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = Wfp_eng__stc_imodemParser(self.config, new_state, self.stream_handle,
                                                self.state_callback, self.pub_callback)

        # get engineering records
        result = self.parser.get_records(1)
        self.assert_result(result, 50, self.particle_a_eng, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 76, self.particle_b_eng, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng, True)

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:76}
        self.stream_handle = StringIO(Wfp_eng__stc_imodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = Wfp_eng__stc_imodemParser(self.config, new_state, self.stream_handle,
                                                self.state_callback, self.pub_callback)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng, True)

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION:76}
        self.stream_handle = StringIO(Wfp_eng__stc_imodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = Wfp_eng__stc_imodemParser(self.config, self.start_state, self.stream_handle,
                                                self.state_callback, self.pub_callback)
        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_time, False)

        # set the new state, the essentially skips engineering a and b
        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng, True)

    def test_bad_flags(self):
        """
        test that we don't parse any records when the flags are not what we expect
        """
        with self.assertRaises(SampleException):
            self.stream_handle = StringIO(Wfp_eng__stc_imodemParserUnitTestCase.TEST_DATA_BAD_FLAGS)
            self.parser = Wfp_eng__stc_imodemParser(self.config, self.start_state, self.stream_handle,
                                                    self.state_callback, self.pub_callback)

    def test_bad_data(self):
        """
        Ensure that missing data causes us to miss records
        TODO: This test should be improved if we come up with a more accurate regex for the data sample
        """
        self.stream_handle = StringIO(Wfp_eng__stc_imodemParserUnitTestCase.TEST_DATA_BAD_ENG)
        self.parser = Wfp_eng__stc_imodemParser(self.config, self.start_state, self.stream_handle,
                                                self.state_callback, self.pub_callback)

	# start with the start time record
	result = self.parser.get_records(1)
	self.assert_result(result, 24, self.particle_a_time, False)

	# next get engineering records
	result = self.parser.get_records(4)
	if len(result) == 4:
	    self.fail("We got 4 records, the bad data should only make 3")

