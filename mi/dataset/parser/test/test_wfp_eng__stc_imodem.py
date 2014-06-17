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

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.driver.WFP_ENG.STC_IMODEM.driver import DataTypeKey
from mi.dataset.parser.WFP_E_file_common import StateKey
from mi.dataset.parser.wfp_eng__stc_imodem import WfpEngStcImodemParser
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStartRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStatusRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemEngineeringRecoveredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStartTelemeteredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemStatusTelemeteredDataParticle
from mi.dataset.parser.wfp_eng__stc_imodem_particles import WfpEngStcImodemEngineeringTelemeteredDataParticle

import os
from mi.idk.config import Config

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'WFP_ENG', 'wfp', 'resource')


@attr('UNIT', group='mi')
class WfpEngStcImodemParserUnitTestCase(ParserUnitTestCase):
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
            DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED: {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng__stc_imodem_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'status_data_particle_class': WfpEngStcImodemStatusRecoveredDataParticle,
                    'start_data_particle_class': WfpEngStcImodemStartRecoveredDataParticle,
                    'engineering_data_particle_class': WfpEngStcImodemEngineeringRecoveredDataParticle
                }
            },
            DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED: {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng__stc_imodem_particles',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    'status_data_particle_class': WfpEngStcImodemStatusTelemeteredDataParticle,
                    'start_data_particle_class': WfpEngStcImodemStartTelemeteredDataParticle,
                    'engineering_data_particle_class': WfpEngStcImodemEngineeringTelemeteredDataParticle
                }
            },
        }

        self.start_state = {StateKey.POSITION: 0}

        # Define test data particles and their associated timestamps which will be
        # compared with returned results
        timestamp1_time = self.timestamp_to_ntp('R\x9d\xac\x19')
        self.particle_a_start_time_recov = WfpEngStcImodemStartRecoveredDataParticle(
            b'\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00R\x9d\xab\xa2R\x9d\xac\x19',
            internal_timestamp=timestamp1_time)
        self.particle_a_start_time_telem = WfpEngStcImodemStartTelemeteredDataParticle(
            b'\x00\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00R\x9d\xab\xa2R\x9d\xac\x19',
            internal_timestamp=timestamp1_time)

        timestamp1_eng = self.timestamp_to_ntp('R\x9d\xac\x1d')
        self.particle_a_eng_recov = WfpEngStcImodemEngineeringRecoveredDataParticle(
            b'R\x9d\xac\x1d\x00\x00\x00\x00A:6\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\x00h\x00N',
            internal_timestamp=timestamp1_eng)
        self.particle_a_eng_telem = WfpEngStcImodemEngineeringTelemeteredDataParticle(
            b'R\x9d\xac\x1d\x00\x00\x00\x00A:6\xe3\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\x00h\x00N',
            internal_timestamp=timestamp1_eng)

        timestamp2_eng = self.timestamp_to_ntp('R\x9d\xac!')
        self.particle_b_eng_recov = WfpEngStcImodemEngineeringRecoveredDataParticle(
            b'R\x9d\xac!C\t\xf2\xf7A9A!\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf2\x00c\x00O',
            internal_timestamp=timestamp2_eng)
        self.particle_b_eng_telem = WfpEngStcImodemEngineeringTelemeteredDataParticle(
            b'R\x9d\xac!C\t\xf2\xf7A9A!\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf2\x00c\x00O',
            internal_timestamp=timestamp2_eng)

        timestamp3_eng = self.timestamp_to_ntp('R\x9d\xac&')
        self.particle_c_eng_recov = WfpEngStcImodemEngineeringRecoveredDataParticle(
            b"R\x9d\xac&C\xbc\x9f\xa7A7'\xbb\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x00^\x00O",
            internal_timestamp=timestamp3_eng)
        self.particle_c_eng_telem = WfpEngStcImodemEngineeringTelemeteredDataParticle(
            b"R\x9d\xac&C\xbc\x9f\xa7A7'\xbb\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc2\x00^\x00O",
            internal_timestamp=timestamp3_eng)

        timestamp4_eng = self.timestamp_to_ntp('R\x9d\xac*')
        self.particle_d_eng_recov = WfpEngStcImodemEngineeringRecoveredDataParticle(
            b'R\x9d\xac*C\xc5\xad\x08A6\xd5\xd0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb4\x00n\x00O',
            internal_timestamp=timestamp4_eng)
        self.particle_d_eng_telem = WfpEngStcImodemEngineeringTelemeteredDataParticle(
            b'R\x9d\xac*C\xc5\xad\x08A6\xd5\xd0\x00\x00\x00\x00\x00\x00\x00\x00\x00\xb4\x00n\x00O',
            internal_timestamp=timestamp4_eng)

        timestamp_last_eng = self.timestamp_to_ntp('R\x9d\xac\xcf')
        self.particle_last_eng_recov = WfpEngStcImodemEngineeringRecoveredDataParticle(
            b'R\x9d\xac\xcfA\xfa\xb2:A5\x0b\x0fA\xf2\x8f\\\x00\x00\x00\x00\x00\xaf\x00m\x00P',
            internal_timestamp=timestamp_last_eng)
        self.particle_last_eng_telem = WfpEngStcImodemEngineeringTelemeteredDataParticle(
            b'R\x9d\xac\xcfA\xfa\xb2:A5\x0b\x0fA\xf2\x8f\\\x00\x00\x00\x00\x00\xaf\x00m\x00P',
            internal_timestamp=timestamp_last_eng)

        timestamp1_status = self.timestamp_to_ntp('R\x9d\xac\xd4')
        self.particle_a_status_recov = WfpEngStcImodemStatusRecoveredDataParticle(
            b'\xff\xff\xff\xff\x00\x00\x00\rR\x9d\xac\xd4R\x9d\xadQ',
            internal_timestamp=timestamp1_status)
        self.particle_a_status_telem = WfpEngStcImodemStatusTelemeteredDataParticle(
            b'\xff\xff\xff\xff\x00\x00\x00\rR\x9d\xac\xd4R\x9d\xadQ',
            internal_timestamp=timestamp1_status)

        # uncomment the following to generate particles in yml format for driver testing results files
        #self.particle_to_yml(self.particle_a_start_time_recov)
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

    def assert_result(self, result, position, particle, ingested):
        self.assertEqual(result, [particle])
        self.assertEqual(self.file_ingested, ingested)

        self.assertEqual(self.parser._state[StateKey.POSITION], position)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], position)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple_recovered(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)

        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_start_time_recov, False)

        # next get engineering records
        result = self.parser.get_records(1)
        self.assert_result(result, 50, self.particle_a_eng_recov, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 76, self.particle_b_eng_recov, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng_recov, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng_recov, True)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 128)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 128)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_d_eng_recov)

    def test_simple_telemetered(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)

        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_start_time_telem, False)

        # next get engineering records
        result = self.parser.get_records(1)
        self.assert_result(result, 50, self.particle_a_eng_telem, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 76, self.particle_b_eng_telem, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng_telem, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng_telem, True)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.parser._state[StateKey.POSITION], 128)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 128)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_d_eng_telem)

    def test_get_many_recovered(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_start_time_recov, False)

        result = self.parser.get_records(4)
        self.assertEqual(result, [self.particle_a_eng_recov,
                                  self.particle_b_eng_recov,
                                  self.particle_c_eng_recov,
                                  self.particle_d_eng_recov])
        self.assertEqual(self.parser._state[StateKey.POSITION], 128)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 128)
        self.assertEqual(self.publish_callback_value[0], self.particle_a_eng_recov)
        self.assertEqual(self.publish_callback_value[1], self.particle_b_eng_recov)
        self.assertEqual(self.publish_callback_value[2], self.particle_c_eng_recov)
        self.assertEqual(self.publish_callback_value[3], self.particle_d_eng_recov)
        self.assertEqual(self.file_ingested, True)

    def test_get_many_telemetered(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_start_time_telem, False)

        result = self.parser.get_records(4)
        self.assertEqual(result, [self.particle_a_eng_telem,
                                  self.particle_b_eng_telem,
                                  self.particle_c_eng_telem,
                                  self.particle_d_eng_telem])
        self.assertEqual(self.parser._state[StateKey.POSITION], 128)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 128)
        self.assertEqual(self.publish_callback_value[0], self.particle_a_eng_telem)
        self.assertEqual(self.publish_callback_value[1], self.particle_b_eng_telem)
        self.assertEqual(self.publish_callback_value[2], self.particle_c_eng_telem)
        self.assertEqual(self.publish_callback_value[3], self.particle_d_eng_telem)
        self.assertEqual(self.file_ingested, True)

    def test_long_stream_recovered(self):
        """
        Test a long stream of data
        """
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA)

        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)

        self.assert_result(result, 24, self.particle_a_start_time_recov, False)

        result = self.parser.get_records(32)
        self.assertEqual(result[0], self.particle_a_eng_recov)
        self.assertEqual(result[-1], self.particle_last_eng_recov)
        self.assertEqual(self.parser._state[StateKey.POSITION], 856)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 856)
        self.assertEqual(self.publish_callback_value[-1], self.particle_last_eng_recov)

        result = self.parser.get_records(1)
        self.assert_result(result, 872, self.particle_a_status_recov, True)

    def test_long_stream_telemetered(self):
        """
        Test a long stream of data
        """
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA)

        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)

        self.assert_result(result, 24, self.particle_a_start_time_telem, False)

        result = self.parser.get_records(32)
        self.assertEqual(result[0], self.particle_a_eng_telem)
        self.assertEqual(result[-1], self.particle_last_eng_telem)
        self.assertEqual(self.parser._state[StateKey.POSITION], 856)
        self.assertEqual(self.state_callback_value[StateKey.POSITION], 856)
        self.assertEqual(self.publish_callback_value[-1], self.particle_last_eng_telem)

        result = self.parser.get_records(1)
        self.assert_result(result, 872, self.particle_a_status_telem, True)

    def test_after_header_recovered(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION: 24}
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED), new_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # get engineering records
        result = self.parser.get_records(1)
        self.assert_result(result, 50, self.particle_a_eng_recov, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 76, self.particle_b_eng_recov, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng_recov, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng_recov, True)

    def test_after_header_telemetered(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION: 24}
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED), new_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # get engineering records
        result = self.parser.get_records(1)
        self.assert_result(result, 50, self.particle_a_eng_telem, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 76, self.particle_b_eng_telem, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng_telem, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng_telem, True)

    def test_mid_state_start_recovered(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:76}
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED), new_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng_recov, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng_recov, True)

    def test_mid_state_start_telemetered(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        new_state = {StateKey.POSITION:76}
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED), new_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng_telem, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng_telem, True)

    def test_set_state_recovered(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION: 76}
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_start_time_recov, False)

        # set the new state, the essentially skips engineering a and b
        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng_recov, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng_recov, True)

    def test_set_state_telemetered(self):
        """
        Test changing to a new state after initializing the parser and
        reading data, as if new data has been found and the state has
        changed
        """
        new_state = {StateKey.POSITION: 76}
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_SHORT)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_start_time_telem, False)

        # set the new state, the essentially skips engineering a and b
        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.assert_result(result, 102, self.particle_c_eng_telem, False)
        result = self.parser.get_records(1)
        self.assert_result(result, 128, self.particle_d_eng_telem, True)

    def test_bad_flags_recovered(self):
        """
        test that we don't parse any records when the flags are not what we expect
        """
        with self.assertRaises(SampleException):
            self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_BAD_FLAGS)
            self.parser = WfpEngStcImodemParser(
                self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED), self.start_state, self.stream_handle,
                self.state_callback, self.pub_callback)

    def test_bad_flags_telemetered(self):
        """
        test that we don't parse any records when the flags are not what we expect
        """
        with self.assertRaises(SampleException):
            self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_BAD_FLAGS)
            self.parser = WfpEngStcImodemParser(
                self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED), self.start_state, self.stream_handle,
                self.state_callback, self.pub_callback)

    def test_bad_data_recovered(self):
        """
        Ensure that missing data causes us to miss records
        TODO: This test should be improved if we come up with a more accurate regex for the data sample
        """
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_BAD_ENG)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_RECOVERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_start_time_recov, False)

        # next get engineering records
        result = self.parser.get_records(4)
        if len(result) == 4:
            self.fail("We got 4 records, the bad data should only make 3")

    def test_bad_data_telemetered(self):
        """
        Ensure that missing data causes us to miss records
        TODO: This test should be improved if we come up with a more accurate regex for the data sample
        """
        self.stream_handle = StringIO(WfpEngStcImodemParserUnitTestCase.TEST_DATA_BAD_ENG)
        self.parser = WfpEngStcImodemParser(
            self.config.get(DataTypeKey.WFP_ENG_STC_IMODEM_TELEMETERED), self.start_state, self.stream_handle,
            self.state_callback, self.pub_callback)

        # start with the start time record
        result = self.parser.get_records(1)
        self.assert_result(result, 24, self.particle_a_start_time_telem, False)

        # next get engineering records
        result = self.parser.get_records(4)
        if len(result) == 4:
            self.fail("We got 4 records, the bad data should only make 3")

    def particle_to_yml(self, particles, filename, mode='w'):
        """
        This is added as a testing helper, not actually as part of the parser tests. Since the same particles
        will be used for the driver test it is helpful to write them to .yml in the same form they need in the
        results.yml fids here.
        """
        # open write append, if you want to start from scratch manually delete this fid
        fid = open(os.path.join(RESOURCE_PATH, filename), mode)

        fid.write('header:\n')
        fid.write("    particle_object: 'MULTIPLE'\n")
        fid.write("    particle_type: 'MULTIPLE'\n")
        fid.write('data:\n')

        for i in range(0, len(particles)):
            particle_dict = particles[i].generate_dict()

            fid.write('  - _index: %d\n' %(i+1))

            fid.write('    particle_object: %s\n' % particles[i].__class__.__name__)
            fid.write('    particle_type: %s\n' % particle_dict.get('stream_name'))
            fid.write('    internal_timestamp: %f\n' % particle_dict.get('internal_timestamp'))

            for val in particle_dict.get('values'):
                if isinstance(val.get('value'), float):
                    fid.write('    %s: %16.16f\n' % (val.get('value_id'), val.get('value')))
                else:
                    fid.write('    %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()
