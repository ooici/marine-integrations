#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_ctdmo
@file marine-integrations/mi/dataset/parser/test/test_ctdmo.py
@author Emily Hahn, Steve Myerson (recovered)
@brief Test code for a Ctdmo data parser
Recovered CO files:
  CTD02000.DAT
    1 CT block
    0 CO blocks
  CTD02001.DAT
    1 CT
    1 CO w/6 records, 5 valid IDs
  CTD02002.DAT
    1 CO w/4 records, 3 valid IDs
    1 CT
    1 CO w/6 records, 4 valid IDs
  CTD02004.DAT
    1 CT
    1 CO w/2 records, 0 valid IDs
    1 CO w/2 records, 1 valid ID
    1 CO w/5 records, 4 valid IDs
    1 CT
    1 CO w/10 records, 10 valid IDs
  CTD02100.DAT
    1 CT
    1 CO w/100 records, 100 valid IDs
    1 CO w/150 records, 150 valid IDs

Recovered CT files:
  SBE37-IM_20100000_2011_00_00.hex - 0 CT records
  SBE37-IM_20110101_2011_01_01.hex - 3 CT records
  SBE37-IM_20120314_2012_03_14.hex - 9 CT records
  SBE37-IM_20130704_2013_07_04.hex - 18 CT records
  SBE37-IM_20141231_2014_12_31.hex - 99 CT records
"""

import gevent
import unittest
import os
from nose.plugins.attrib import attr
from StringIO import StringIO

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase

from mi.dataset.parser.sio_mule_common import StateKey

from mi.dataset.parser.ctdmo import \
    CtdmoRecoveredCoParser, \
    CtdmoRecoveredCtParser, \
    CtdmoRecoveredInstrumentDataParticle, \
    CtdmoRecoveredOffsetDataParticle, \
    CtdmoTelemeteredParser, \
    CtdmoTelemeteredInstrumentDataParticle, \
    CtdmoTelemeteredOffsetDataParticle, \
    CtdmoStateKey

from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import DatasetParserException

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver',
                 'mflm', 'ctd', 'resource')

# Expected tuples for recovered CO data in file CTD02001.DAT
EXPECTED_CTD02001_1 = [
    ('51532002', '7', '\xff\xff\xff\xe7'),
    ('51532002', '7', '\xff\xff\xff\xf1'),
    ('51532002', '7', '\xff\xff\xff\xfb'),
    ('51532002', '7', '\x00\x00\x00\x0f'),
    ('51532002', '7', '\x00\x00\x00\x19')
]

# Expected tuples for recovered CO data in file CTD02002.DAT
EXPECTED_CTD02002_1 = [
    ('51532002', '7', '\xff\xff\xff\x88'),
    ('51532002', '7', '\xff\xff\xff\xa6'),
    ('51532002', '7', '\xff\xff\xff\xc4')
]
EXPECTED_CTD02002_2 = [
    ('51532004', '7', '\x00\x00\x00\x00'),
    ('51532004', '7', '\x00\x00\x00<'),
    ('51532004', '7', '\x00\x00\x00x'),
    ('51532004', '7', '\x00\x00\x00\x96')
]

# Expected tuples for recovered CO data in file CTD02004.DAT
EXPECTED_CTD02004_1 = []

EXPECTED_CTD02004_2 = [
    ('51532006', '7', '\xff\xff\xff\xe2')
]

EXPECTED_CTD02004_3 = [
    ('51532007', '7', '\x00\x00\x00\n'),
    ('51532007', '7', '\x00\x00\x00Z'),
    ('51532007', '7', '\x00\x00\x00\x82'),
    ('51532007', '7', '\x00\x00\x00\xaa')
]

EXPECTED_CTD02004_4 = [
    ('51532009', '7', '\x00\x00\x00\xd2'),
    ('51532009', '7', '\x00\x00\x00\xfa'),
    ('51532009', '7', '\x00\x00\x01"'),
    ('51532009', '7', '\x00\x00\x01J'),
    ('51532009', '7', '\x00\x00\x01r'),
    ('51532009', '7', '\x00\x00\x01\x9a'),
    ('51532009', '7', '\x00\x00\x01\xc2'),
    ('51532009', '7', '\x00\x00\x01\xea'),
    ('51532009', '7', '\x00\x00\x02\x12'),
    ('51532009', '7', '\x00\x00\x02:')
]

# List of all expected values for file CTD02004.DAT
EXPECTED_CTD02004 = [
    EXPECTED_CTD02004_1,
    EXPECTED_CTD02004_2,
    EXPECTED_CTD02004_3,
    EXPECTED_CTD02004_4
]

# Expected tuples for recovered CT data in SBE37-IM_20110101_2011_01_01.hex
EXPECTED_SBE20110101 = [
    (55, 20110101, '0186A1', '030D41', '0493E1', '9C41', '0016E36A'),
    (55, 20110101, '0186A2', '030D42', '0493E2', '9C42', '0016E36B'),
    (55, 20110101, '0186A3', '030D43', '0493E3', '9C43', '0016E36C')
]

# Expected tuples for recovered CT data in SBE37-IM_20120314_2012_03_14.hex
EXPECTED_SBE20120314 = [
    (55, 20120314, '030D42', '0493E2', '061A82', 'C352', '00186A14'),
    (55, 20120314, '031199', '049839', '061ED9', 'C7A9', '00186E6B'),
    (55, 20120314, '0315F0', '049C90', '062330', 'CC00', '001872C2'),
    (55, 20120314, '031A47', '04A0E7', '062787', 'D057', '00187719'),
    (55, 20120314, '031E9E', '04A53E', '062BDE', 'D4AE', '00187B70'),
    (55, 20120314, '0322F5', '04A995', '063035', 'D905', '00187FC7'),
    (55, 20120314, '03274C', '04ADEC', '06348C', 'DD5C', '0018841E'),
    (55, 20120314, '032BA3', '04B243', '0638E3', 'E1B3', '00188875'),
    (55, 20120314, '032FFA', '04B69A', '063D3A', 'E60A', '00188CCC')
]

# Expected tuples for recovered CT data in SBE37-IM_20130704_2013_07_04.hex
EXPECTED_SBE20130704 = [
    (55, 20130704, '0493F2', '061A92', '07A132', 'EA72', '006AD074'),
    (55, 20130704, '0494D0', '061B70', '07A210', 'EB50', '006AD152'),
    (55, 20130704, '0495AE', '061C4E', '07A2EE', 'EC2E', '006AD230'),
    (55, 20130704, '04968C', '061D2C', '07A3CC', 'ED0C', '006AD30E'),
    (55, 20130704, '04976A', '061E0A', '07A4AA', 'EDEA', '006AD3EC'),
    (55, 20130704, '049848', '061EE8', '07A588', 'EEC8', '006AD4CA'),
    (55, 20130704, '049926', '061FC6', '07A666', 'EFA6', '006AD5A8'),
    (55, 20130704, '049A04', '0620A4', '07A744', 'F084', '006AD686'),
    (55, 20130704, '049AE2', '062182', '07A822', 'F162', '006AD764'),
    (55, 20130704, '049BC0', '062260', '07A900', 'F240', '006AD842'),
    (55, 20130704, '049C9E', '06233E', '07A9DE', 'F31E', '006AD920'),
    (55, 20130704, '049D7C', '06241C', '07AABC', 'F3FC', '006AD9FE'),
    (55, 20130704, '049E5A', '0624FA', '07AB9A', 'F4DA', '006ADADC'),
    (55, 20130704, '049F38', '0625D8', '07AC78', 'F5B8', '006ADBBA'),
    (55, 20130704, '04A016', '0626B6', '07AD56', 'F696', '006ADC98'),
    (55, 20130704, '04A0F4', '062794', '07AE34', 'F774', '006ADD76'),
    (55, 20130704, '04A1D2', '062872', '07AF12', 'F852', '006ADE54'),
    (55, 20130704, '04A2B0', '062950', '07AFF0', 'F930', '006ADF32')

]

# Expected tuples for recovered CT data in SBE37-IM_20141231_2014_12_31.hex
EXPECTED_SBE20141231 = [
    (55, 20141231, '061AE3', '07A183', '092823', '2773', '0098967F'),
    (55, 20141231, '061B47', '07A1E7', '092887', '27D7', '009896E3'),
    (55, 20141231, '061BAB', '07A24B', '0928EB', '283B', '00989747'),
    (55, 20141231, '061C0F', '07A2AF', '09294F', '289F', '009897AB'),
    (55, 20141231, '061C73', '07A313', '0929B3', '2903', '0098980F'),
    (55, 20141231, '061CD7', '07A377', '092A17', '2967', '00989873'),
    (55, 20141231, '061D3B', '07A3DB', '092A7B', '29CB', '009898D7'),
    (55, 20141231, '061D9F', '07A43F', '092ADF', '2A2F', '0098993B'),
    (55, 20141231, '061E03', '07A4A3', '092B43', '2A93', '0098999F'),
    (55, 20141231, '061E67', '07A507', '092BA7', '2AF7', '00989A03'),
    (55, 20141231, '061ECB', '07A56B', '092C0B', '2B5B', '00989A67'),
    (55, 20141231, '061F2F', '07A5CF', '092C6F', '2BBF', '00989ACB'),
    (55, 20141231, '061F93', '07A633', '092CD3', '2C23', '00989B2F'),
    (55, 20141231, '061FF7', '07A697', '092D37', '2C87', '00989B93'),
    (55, 20141231, '06205B', '07A6FB', '092D9B', '2CEB', '00989BF7'),
    (55, 20141231, '0620BF', '07A75F', '092DFF', '2D4F', '00989C5B'),
    (55, 20141231, '062123', '07A7C3', '092E63', '2DB3', '00989CBF'),
    (55, 20141231, '062187', '07A827', '092EC7', '2E17', '00989D23'),
    (55, 20141231, '0621EB', '07A88B', '092F2B', '2E7B', '00989D87'),
    (55, 20141231, '06224F', '07A8EF', '092F8F', '2EDF', '00989DEB'),
    (55, 20141231, '0622B3', '07A953', '092FF3', '2F43', '00989E4F'),
    (55, 20141231, '062317', '07A9B7', '093057', '2FA7', '00989EB3'),
    (55, 20141231, '06237B', '07AA1B', '0930BB', '300B', '00989F17'),
    (55, 20141231, '0623DF', '07AA7F', '09311F', '306F', '00989F7B'),
    (55, 20141231, '062443', '07AAE3', '093183', '30D3', '00989FDF'),
    (55, 20141231, '0624A7', '07AB47', '0931E7', '3137', '0098A043'),
    (55, 20141231, '06250B', '07ABAB', '09324B', '319B', '0098A0A7'),
    (55, 20141231, '06256F', '07AC0F', '0932AF', '31FF', '0098A10B'),
    (55, 20141231, '0625D3', '07AC73', '093313', '3263', '0098A16F'),
    (55, 20141231, '062637', '07ACD7', '093377', '32C7', '0098A1D3'),
    (55, 20141231, '06269B', '07AD3B', '0933DB', '332B', '0098A237'),
    (55, 20141231, '0626FF', '07AD9F', '09343F', '338F', '0098A29B'),
    (55, 20141231, '062763', '07AE03', '0934A3', '33F3', '0098A2FF'),
    (55, 20141231, '0627C7', '07AE67', '093507', '3457', '0098A363'),
    (55, 20141231, '06282B', '07AECB', '09356B', '34BB', '0098A3C7'),
    (55, 20141231, '06288F', '07AF2F', '0935CF', '351F', '0098A42B'),
    (55, 20141231, '0628F3', '07AF93', '093633', '3583', '0098A48F'),
    (55, 20141231, '062957', '07AFF7', '093697', '35E7', '0098A4F3'),
    (55, 20141231, '0629BB', '07B05B', '0936FB', '364B', '0098A557'),
    (55, 20141231, '062A1F', '07B0BF', '09375F', '36AF', '0098A5BB'),
    (55, 20141231, '062A83', '07B123', '0937C3', '3713', '0098A61F'),
    (55, 20141231, '062AE7', '07B187', '093827', '3777', '0098A683'),
    (55, 20141231, '062B4B', '07B1EB', '09388B', '37DB', '0098A6E7'),
    (55, 20141231, '062BAF', '07B24F', '0938EF', '383F', '0098A74B'),
    (55, 20141231, '062C13', '07B2B3', '093953', '38A3', '0098A7AF'),
    (55, 20141231, '062C77', '07B317', '0939B7', '3907', '0098A813'),
    (55, 20141231, '062CDB', '07B37B', '093A1B', '396B', '0098A877'),
    (55, 20141231, '062D3F', '07B3DF', '093A7F', '39CF', '0098A8DB'),
    (55, 20141231, '062DA3', '07B443', '093AE3', '3A33', '0098A93F'),
    (55, 20141231, '062E07', '07B4A7', '093B47', '3A97', '0098A9A3'),
    (55, 20141231, '062E6B', '07B50B', '093BAB', '3AFB', '0098AA07'),
    (55, 20141231, '062ECF', '07B56F', '093C0F', '3B5F', '0098AA6B'),
    (55, 20141231, '062F33', '07B5D3', '093C73', '3BC3', '0098AACF'),
    (55, 20141231, '062F97', '07B637', '093CD7', '3C27', '0098AB33'),
    (55, 20141231, '062FFB', '07B69B', '093D3B', '3C8B', '0098AB97'),
    (55, 20141231, '06305F', '07B6FF', '093D9F', '3CEF', '0098ABFB'),
    (55, 20141231, '0630C3', '07B763', '093E03', '3D53', '0098AC5F'),
    (55, 20141231, '063127', '07B7C7', '093E67', '3DB7', '0098ACC3'),
    (55, 20141231, '06318B', '07B82B', '093ECB', '3E1B', '0098AD27'),
    (55, 20141231, '0631EF', '07B88F', '093F2F', '3E7F', '0098AD8B'),
    (55, 20141231, '063253', '07B8F3', '093F93', '3EE3', '0098ADEF'),
    (55, 20141231, '0632B7', '07B957', '093FF7', '3F47', '0098AE53'),
    (55, 20141231, '06331B', '07B9BB', '09405B', '3FAB', '0098AEB7'),
    (55, 20141231, '06337F', '07BA1F', '0940BF', '400F', '0098AF1B'),
    (55, 20141231, '0633E3', '07BA83', '094123', '4073', '0098AF7F'),
    (55, 20141231, '063447', '07BAE7', '094187', '40D7', '0098AFE3'),
    (55, 20141231, '0634AB', '07BB4B', '0941EB', '413B', '0098B047'),
    (55, 20141231, '06350F', '07BBAF', '09424F', '419F', '0098B0AB'),
    (55, 20141231, '063573', '07BC13', '0942B3', '4203', '0098B10F'),
    (55, 20141231, '0635D7', '07BC77', '094317', '4267', '0098B173'),
    (55, 20141231, '06363B', '07BCDB', '09437B', '42CB', '0098B1D7'),
    (55, 20141231, '06369F', '07BD3F', '0943DF', '432F', '0098B23B'),
    (55, 20141231, '063703', '07BDA3', '094443', '4393', '0098B29F'),
    (55, 20141231, '063767', '07BE07', '0944A7', '43F7', '0098B303'),
    (55, 20141231, '0637CB', '07BE6B', '09450B', '445B', '0098B367'),
    (55, 20141231, '06382F', '07BECF', '09456F', '44BF', '0098B3CB'),
    (55, 20141231, '063893', '07BF33', '0945D3', '4523', '0098B42F'),
    (55, 20141231, '0638F7', '07BF97', '094637', '4587', '0098B493'),
    (55, 20141231, '06395B', '07BFFB', '09469B', '45EB', '0098B4F7'),
    (55, 20141231, '0639BF', '07C05F', '0946FF', '464F', '0098B55B'),
    (55, 20141231, '063A23', '07C0C3', '094763', '46B3', '0098B5BF'),
    (55, 20141231, '063A87', '07C127', '0947C7', '4717', '0098B623'),
    (55, 20141231, '063AEB', '07C18B', '09482B', '477B', '0098B687'),
    (55, 20141231, '063B4F', '07C1EF', '09488F', '47DF', '0098B6EB'),
    (55, 20141231, '063BB3', '07C253', '0948F3', '4843', '0098B74F'),
    (55, 20141231, '063C17', '07C2B7', '094957', '48A7', '0098B7B3'),
    (55, 20141231, '063C7B', '07C31B', '0949BB', '490B', '0098B817'),
    (55, 20141231, '063CDF', '07C37F', '094A1F', '496F', '0098B87B'),
    (55, 20141231, '063D43', '07C3E3', '094A83', '49D3', '0098B8DF'),
    (55, 20141231, '063DA7', '07C447', '094AE7', '4A37', '0098B943'),
    (55, 20141231, '063E0B', '07C4AB', '094B4B', '4A9B', '0098B9A7'),
    (55, 20141231, '063E6F', '07C50F', '094BAF', '4AFF', '0098BA0B'),
    (55, 20141231, '063ED3', '07C573', '094C13', '4B63', '0098BA6F'),
    (55, 20141231, '063F37', '07C5D7', '094C77', '4BC7', '0098BAD3'),
    (55, 20141231, '063F9B', '07C63B', '094CDB', '4C2B', '0098BB37'),
    (55, 20141231, '063FFF', '07C69F', '094D3F', '4C8F', '0098BB9B'),
    (55, 20141231, '064063', '07C703', '094DA3', '4CF3', '0098BBFF'),
    (55, 20141231, '0640C7', '07C767', '094E07', '4D57', '0098BC63'),
    (55, 20141231, '06412B', '07C7CB', '094E6B', '4DBB', '0098BCC7')
]


@attr('UNIT', group='mi')
class CtdmoParserUnitTestCase(ParserUnitTestCase):

    def create_rec_co_parser(self, file_handle, new_state=None):
        """
        This function creates a Ctdmo parser for recovered CO data.
        """
        parser = CtdmoRecoveredCoParser(self.config_rec_co, file_handle,
            new_state, self.rec_state_callback, self.pub_callback,
            self.exception_callback)
        return parser

    def create_rec_ct_parser(self, file_handle, new_state=None):
        """
        This function creates a Ctdmo parser for recovered CT data.
        """
        parser = CtdmoRecoveredCtParser(self.config_rec_ct, file_handle,
            new_state, self.rec_state_callback, self.pub_callback,
            self.exception_callback)
        return parser

    def rec_state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.rec_state_callback_value = state
        self.file_ingested_value = file_ingested

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
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                ['CtdmoTelemeteredInstrumentDataParticle',
                 'CtdmoTelemeteredOffsetDataParticle'],
            CtdmoStateKey.INDUCTIVE_ID: 55
        }

        self.config_rec_co = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredOffsetDataParticle',
            CtdmoStateKey.INDUCTIVE_ID: 55
        }

        self.config_rec_ct = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredInstrumentDataParticle',
            CtdmoStateKey.INDUCTIVE_ID: 55,
            CtdmoStateKey.SERIAL_NUMBER: '03710261'
        }

        # all indices give in the comments are in actual file position, not escape sequence replace indices
        # packets have the same timestamp, the first has 3 data samples [394-467]
        self.particle_a = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF36D6',
             b'\x37',
             b'\x39\x4c\xe0\xc3\x54\xe6\x0a',
             b'\x81\xd5\x81\x19'))

        # this is the start of packet 2 [855:1045]
        self.particle_b = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF52F6',
             b'7',
             b'7\xf0\x00\xc3T\xe5\n',
             b'\xa1\xf1\x81\x19'))
        
        # this is the start of packet 3 [1433:1623]
        self.particle_c = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF6F16',
             b'7',
             b'6$p\xc3T\xe4\n',
             b'\xc1\r\x82\x19'))
        
        # this is the start of packet 4 [5354:5544]
        self.particle_d = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EF8B36',
             b'\x37',
             b'\x35\x8b\xe0\xc3T\xe5\n',
             b'\xe1)\x82\x19'))
        
        # this is the start of packet 5 [6321:6511]
        self.particle_e = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFC376',
             b'7',
             b'7\x17\xd6\x8eI;\x10',
             b'!b\x82\x19'))
        
        # start of packet 6 [6970-7160]
        self.particle_f = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFDF96',
             b'\x37',
             b'\x36\xe7\xe6\x89W9\x10',
             b'A~\x82\x19'))
        
        # packet 7 [7547-7737]
        self.particle_g = CtdmoTelemeteredInstrumentDataParticle(
            (b'51EFFBB6',
             b'\x37',
             b'\x32\t6F\x0c\xd5\x0f',
             b'a\x9a\x82\x19'))

        # first offset at 9543
        self.particle_a_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F05016', b'7', b'\x00\x00\x00\x00'))

        # in long file, starts at 13453
        self.particle_z = CtdmoTelemeteredInstrumentDataParticle(
            (b'51F0A476',
             b'7',
             b'3\xb9\xa6]\x93\xf2\x0f',
             b'!C\x83\x19'))

        # in longest file second offset at 19047
        self.particle_b_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F1A196', b'7', b'\x00\x00\x00\x00'))
        
        # third offset at 30596
        self.particle_c_offset = CtdmoTelemeteredOffsetDataParticle(
            (b'51F2F316', b'7', b'\x00\x00\x00\x00'))

        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None
        self.maxDiff = None

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
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                  'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            None, self.state_callback, self.pub_callback, self.exception_callback)

        log.debug('===== TEST SIMPLE GET RECORD 1 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
             [[853,1043,1,0], [1429,1619,1,0], [5349,5539,1,0],
                 [6313,6503,1,0], [6958,7148,1,0], [7534,7724,1,0]],
             [[0, 12], [336, 394], [853,1043], [1429,1619], [5349,5539],
                 [5924,5927], [6313,6503], [6889,7148], [7534,7985]],
             self.particle_a)

        log.debug('===== TEST SIMPLE GET RECORD 2 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[1429,1619,1,0], [5349,5539,1,0], [6313,6503,1,0],
                [6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [1429,1619], [5349,5539], [5924,5927],
                [6313,6503], [6889,7148], [7534,7985]],
            self.particle_b)

        log.debug('===== TEST SIMPLE GET RECORD 3 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0],
                [7534,7724,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7148], [7534,7985]],
            self.particle_c)

        log.debug('===== TEST SIMPLE GET RECORD 4 =====')
        result = self.parser.get_records(1)
        self.assert_result(result,
            [[6313,6503,1,0], [6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5924,5927], [6313,6503], [6889,7148],
                [7534,7985]],
            self.particle_d)

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_missing_inductive_id_config(self):
        """
        Make sure that the driver complains about a missing inductive ID in the config
        """
        self.state = {
            StateKey.UNPROCESSED_DATA:[[0, 8000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 8000
        }
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        bad_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoTelemeteredInstrumentDataParticle',
            }
        with self.assertRaises(DatasetParserException):
            self.parser = CtdmoTelemeteredParser(bad_config, self.stream_handle,
                self.state, self.state_callback,
                self.pub_callback, self.exception_callback)

    def test_get_many(self):
        """
        Read test data from the file and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        self.state = {
            StateKey.UNPROCESSED_DATA:[[0, 7500]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 8000
        }
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            self.state, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(5)
        self.stream_handle.close()
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c, self.particle_d, self.particle_e])
        self.assert_state([[6958,7148,1,0]],
                           [[0, 12], [336, 394], [5924,5927], [6889,7500]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_d)
        self.assertEqual(self.publish_callback_value[4], self.particle_e)
        self.assertEqual(self.exception_callback_value, None)

    def test_long_stream(self):
        self.state = {
            StateKey.UNPROCESSED_DATA:[[0, 14000]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 14000
        }
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_longer.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            self.state, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(13)
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[9], self.particle_a_offset)
        self.assertEqual(result[-1], self.particle_z)
        self.assert_state([],
            [[0, 12], [336, 394], [5924,5927],  [6889, 6958], [8687,8756], 
               [8946,9522], [13615, 14000]])
        self.assertEqual(self.publish_callback_value[-1], self.particle_z)
        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_longest_for_co(self):
        """
        Test an even longer file which contains more of the CO samples
        """
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_longest.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle, None,
            self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(36)
        self.assertEqual(result[0], self.particle_a)
        self.assertEqual(result[1], self.particle_b)
        self.assertEqual(result[2], self.particle_c)
        self.assertEqual(result[3], self.particle_d)
        self.assertEqual(result[9], self.particle_a_offset)
        self.assertEqual(result[12], self.particle_z)
        self.assertEqual(result[22], self.particle_b_offset)
        self.assertEqual(result[-1], self.particle_c_offset)

        self.assert_state([],
            [[0, 12], [336, 394], [5924,5927],  [6889, 6958], [8687,8756], 
             [8946,9522], [14576,14647], [16375,16444], [18173,18240],
             [20130,20199], [21927,21996], [29707,29776], [30648,30746]])

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_mid_state_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {
            StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [1429,7500]],
            StateKey.FILE_SIZE: 8000
        }
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            new_state, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7500]],
            self.particle_c)
        self.assertEqual(self.exception_callback_value, None)

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """
        new_state = {
            StateKey.IN_PROCESS_DATA:
                [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0],
                    [7534,7724,1,0]],
            StateKey.UNPROCESSED_DATA:
                [[0, 12], [336, 394], [5349,5539], [5924,5927],
                    [6313,6503], [6889,7148], [7534,7985]],
            StateKey.FILE_SIZE: 8000}

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            new_state, self.state_callback,
            self.pub_callback, self.exception_callback)

        result = self.parser.get_records(2)
        self.assertEqual(result[0], self.particle_d)
        self.assertEqual(result[-1], self.particle_e)
        self.assert_state([[6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5924,5927], [6889,7148], [7534,7985]])

        self.assertEqual(self.publish_callback_value[-1], self.particle_e)
        self.assertEqual(self.exception_callback_value, None)

    def test_set_state(self):
        """
        test changing the state after initializing
        """
        self.state = {
            StateKey.UNPROCESSED_DATA:[[0, 500]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 8000
        }

        new_state = {
            StateKey.UNPROCESSED_DATA:[[0, 12], [336, 394], [1429,7500]],
            StateKey.IN_PROCESS_DATA:[],
            StateKey.FILE_SIZE: 8000
        }

        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            self.state, self.state_callback,
            self.pub_callback, self.exception_callback)

        # there should only be 1 records, make sure we stop there
        result = self.parser.get_records(1)
        self.assertEqual(result[0], self.particle_a)
        result = self.parser.get_records(1)
        self.assertEqual(result, [])

        self.parser.set_state(new_state)
        result = self.parser.get_records(1)
        self.stream_handle.close()
        self.assert_result(result,
            [[5349,5539,1,0], [6313,6503,1,0], [6958,7148,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927],
                [6313,6503], [6889,7500]],
            self.particle_c)

        self.assertEqual(self.exception_callback_value, None)

    def test_update(self):
        """
        Test a file which has had a section of data replaced by 0s, as if a block of data has not been received yet,
        then using the returned state make a new parser with the test data that has the 0s filled in
        """
        # this file has a block of CT data replaced by 0s
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_replace.dat'))

        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle, None,
             self.state_callback, self.pub_callback, self.exception_callback)

        result = self.parser.get_records(4)

        # particle d has been replaced in this file with zeros
        self.assertEqual(result, [self.particle_a, self.particle_b, self.particle_c, self.particle_e])
        self.assert_state([[6958,7148,1,0], [7534,7724,1,0]],
            [[0, 12], [336, 394], [5349,5539], [5924,5927], [6889,7148],
                [7534,7985]])
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.publish_callback_value[1], self.particle_b)
        self.assertEqual(self.publish_callback_value[2], self.particle_c)
        self.assertEqual(self.publish_callback_value[3], self.particle_e)

        self.stream_handle.close()

        next_state = self.parser._state
        # this file has the block of CT data that was missing in the previous file
        self.stream_handle = open(os.path.join(RESOURCE_PATH,
                                               'node59p1_shorter.dat'))
        self.parser = CtdmoTelemeteredParser(self.config, self.stream_handle,
            next_state, self.state_callback,
            self.pub_callback, self.exception_callback)

        # first get the old 'in process' records from [6970-7160]
        # Once those are done, the un processed data will be checked
        result = self.parser.get_records(2)
        self.assertEqual(result, [self.particle_f, self.particle_g])
        self.assert_state([],
            [[0, 12], [336, 394], [5349,5539], [5924,5927], [6889,6958],
                [7724,7985]])

        self.assertEqual(self.publish_callback_value[0], self.particle_f)
        self.assertEqual(self.publish_callback_value[1], self.particle_g)

        # this should be the first of the newly filled in particles from [5354-5544]
        result = self.parser.get_records(1)
        self.assert_result(result,
            [],
            [[0, 12], [336, 394], [5924,5927], [6889,6958], [7724,7985]],
            self.particle_d)

        self.stream_handle.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_big_giant_input(self):
        """
        Read a large file and verify that all expected particles can be read.
        Verification is not done at this time, but will be done during
        integration and qualification testing.
        File used for this test has 250 total CO particles.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02100.DAT'))
        parser = self.create_rec_co_parser(in_file)

        number_expected_results = 250

        # In a single read, get all particles in this file.
        result = parser.get_records(number_expected_results)
        self.assertEqual(len(result), number_expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_get_many(self):
        """
        Read Recovered CO data and pull out multiple data particles at one time.
        Verify that the results are those we expected.
        File used for this test has 2 CO SIO blocks.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02002.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Generate a list of expected result particles.
        expected_results = []
        for record in range(0, len(EXPECTED_CTD02002_1)):
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02002_1[record])
            expected_results.append(particle)

        # In a single read, get all particles for this CO record.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        # Do it again for the other CO SIO block.
        expected_results = []
        for record in range(0, len(EXPECTED_CTD02002_2)):
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02002_2[record])
            expected_results.append(particle)

        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_invalid_state(self):
        """
        Make sure that an exception is raised when the state is not
        a dictionary.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02000.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Instead of a dictionary, use a list of dictionaries for the state.
        new_state = [{'POSITION': 0}, {'invalid key': 22}]
        with self.assertRaises(DatasetParserException):
            parser.set_state(new_state)

    def test_rec_co_long_stream(self):
        """
        Read test data and pull out all particles from a file at once.
        File used for this test has 3 CO SIO blocks and a total of 15 CO records.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02004.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Generate a list of expected result particles.
        expected_results = []

        for block in range(0, len(EXPECTED_CTD02004)):
            for record in range(0, len(EXPECTED_CTD02004[block])):
                particle = CtdmoRecoveredOffsetDataParticle(
                    EXPECTED_CTD02004[block][record])
                expected_results.append(particle)

        # In a single read, get all particles in this file.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_mid_state_start(self):
        """
        Test starting a recovered CO parser with a state in the
        middle of processing.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02002.DAT'))

        # Start at the second SIO block.
        initial_state = {
            StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[58, 146], [146, 216]],
            StateKey.FILE_SIZE: 216
        }

        parser = self.create_rec_co_parser(in_file, new_state=initial_state)

        # Generate the expected results.
        expected_results = []
        for record in range(0, len(EXPECTED_CTD02002_2)):
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02002_2[record])
            expected_results.append(particle)

        # Read the records from the CO SIO block.
        # Verify what we read is what we expect.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_missing_inductive_id_config(self):
        """
        Make sure that an exception is raised when building the
        Recovered CO parser if the inductive ID is missing in the config.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02000.DAT'))

        bad_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredOffsetDataParticle',
        }

        with self.assertRaises(DatasetParserException):
            CtdmoRecoveredCoParser(bad_config, in_file, None,
                self.state_callback, self.pub_callback, self.exception_callback)

    def test_rec_co_missing_state_key(self):
        """
        Make sure that an exception is raised when the POSITION state key
        is missing.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02000.DAT'))
        parser = self.create_rec_co_parser(in_file)

        new_state = {'Not a valid key': 18}
        with self.assertRaises(DatasetParserException):
            parser.set_state(new_state)

    def test_rec_co_no_records(self):
        """
        Read a Recovered CO data file that has no CO records.
        Verify that no particles are generated.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02000.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Not expecting any particles.
        expected_results = []

        # Try to get one particle and verify we didn't get any.
        result = parser.get_records(1)
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_set_state(self):
        """
        test changing the state after initializing
        File used for this test has 2 CO SIO blocks.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02002.DAT'))
        parser = self.create_rec_co_parser(in_file)

        # Read 1 record (of the 3 that are in the first SIO block).
        parser.get_records(1)

        # Skip ahead to the second SIO block.
        new_state = {
            StateKey.IN_PROCESS_DATA:[],
            StateKey.UNPROCESSED_DATA:[[58, 146], [146, 216]],
            StateKey.FILE_SIZE: 216
        }

        # Set the state.
        parser.set_state(new_state)

        # Generate the expected results.
        expected_results = []
        for record in range(0, len(EXPECTED_CTD02002_2)):
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02002_2[record])
            expected_results.append(particle)

        # Read the records from the CO SIO block.
        # Verify what we read is what we expect.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_co_simple(self):
        """
        Read Recovered CO data from the file and pull out data particles
        one at a time. Verify that the results are those we expected.
        """
        in_file = open(os.path.join(RESOURCE_PATH, 'CTD02001.DAT'))
        parser = self.create_rec_co_parser(in_file)

        for record in range(0, len(EXPECTED_CTD02001_1)):
            log.debug('===== TEST REC CO SIMPLE GET RECORD %d =====', record + 1)

            # Generate expected particle
            expected_results = []
            particle = CtdmoRecoveredOffsetDataParticle(
                EXPECTED_CTD02001_1[record])
            expected_results.append(particle)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_ct_invalid_state(self):
        """
        Make sure that an exception is raised when the state is not
        a dictionary.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20110101_2011_01_01.hex'))
        parser = self.create_rec_ct_parser(in_file)

        # Instead of a dictionary, use a list of dictionaries for the state.
        new_state = [{'POSITION': 0}, {'invalid key': 22}]
        with self.assertRaises(DatasetParserException):
            parser.set_state(new_state)

    def test_rec_ct_long_stream(self):
        """
        Read test data and pull out all particles from a file at once.
        """
        total_records = len(EXPECTED_SBE20141231)
        log.debug ('===== TEST REC CT LONG STREAM with %d records', total_records)
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20141231_2014_12_31.hex'))
        parser = self.create_rec_ct_parser(in_file)

        # Generate a list of expected result particles.
        expected_results = []

        for record in range(0, total_records):
            particle = CtdmoRecoveredInstrumentDataParticle(
                    EXPECTED_SBE20141231[record])
            expected_results.append(particle)

        # In a single read, get all particles in this file.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_ct_mid_state_start(self):
        """
        Test starting a recovered CT parser with a state in the
        middle of processing.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20120314_2012_03_14.hex'))

        # Start at the start of the 6th record of 9.
        initial_state = {
            CtdmoStateKey.END_CONFIG: True,
            CtdmoStateKey.POSITION: 0x12D,
            CtdmoStateKey.SERIAL_NUMBER: 20120314
        }

        parser = self.create_rec_ct_parser(in_file, new_state=initial_state)

        # Generate the expected results, skipping the first 5.
        expected_results = []
        for record in range(0, len(EXPECTED_SBE20120314)):
            if record > 4:
                particle = CtdmoRecoveredInstrumentDataParticle(
                    EXPECTED_SBE20120314[record])
                expected_results.append(particle)

        # Read the records from the CT file.
        # Verify what we read is what we expect.
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_ct_missing_end(self):
        """
        Read a Recovered CT data file that has no end configuration record.
        Verify that no particles are generated.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20110101_missing_end.hex'))
        parser = self.create_rec_ct_parser(in_file)

        # Not expecting any particles.
        expected_results = []

        # Try to get one particle and verify we didn't get any.
        result = parser.get_records(1)
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_ct_missing_inductive_id_config(self):
        """
        Make sure that an exception is raised when building the
        Recovered CT parser if the inductive ID is missing in the config.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20110101_2011_01_01.hex'))

        bad_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE:
                'mi.dataset.parser.ctdmo',
            DataSetDriverConfigKeys.PARTICLE_CLASS:
                'CtdmoRecoveredInstrumentDataParticle',
        }

        with self.assertRaises(DatasetParserException):
            CtdmoRecoveredCtParser(bad_config, in_file, None,
                self.state_callback, self.pub_callback, self.exception_callback)

    def test_rec_ct_missing_serial(self):
        """
        Read a Recovered CT data file that has no Serial record.
        Verify that no particles are generated.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20110101_missing_serial.hex'))
        parser = self.create_rec_ct_parser(in_file)

        # Not expecting any particles.
        expected_results = []

        # Try to get one particle and verify we didn't get any.
        result = parser.get_records(1)
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_ct_missing_state_key(self):
        """
        Make sure that an exception is raised when the POSITION state key
        is missing.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20110101_2011_01_01.hex'))
        parser = self.create_rec_ct_parser(in_file)

        new_state = {'Not a valid key': 18}
        with self.assertRaises(DatasetParserException):
            parser.set_state(new_state)

    def test_rec_ct_no_records(self):
        """
        Read a Recovered CT data file that has no CT records.
        Verify that no particles are generated.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20100000_2010_00_00.hex'))
        parser = self.create_rec_ct_parser(in_file)

        # Not expecting any particles.
        expected_results = []

        # Try to get one particle and verify we didn't get any.
        result = parser.get_records(1)
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_ct_set_state(self):
        """
        test changing the state after initializing
        File used for this test has 18 CT records.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20130704_2013_07_04.hex'))
        parser = self.create_rec_ct_parser(in_file)

        # Generate the expected results for the first 7 records.
        expected_results = []
        for record in range(0, 7):
            particle = CtdmoRecoveredInstrumentDataParticle(
                EXPECTED_SBE20130704[record])
            expected_results.append(particle)

        # Read the records.
        # Verify what we read is what we expect.
        log.debug('===== TEST REC CT SET STATE GROUP 1 =====')
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        # Skip ahead to the 15th record.
        new_state = {
            CtdmoStateKey.END_CONFIG: True,
            CtdmoStateKey.POSITION: 0x244,
            CtdmoStateKey.SERIAL_NUMBER: 20130704
        }

        # Set the state.
        parser.set_state(new_state)

        # Generate the expected results for the 15th record to the end.
        expected_results = []
        for record in range(14, len(EXPECTED_SBE20130704)):
            particle = CtdmoRecoveredInstrumentDataParticle(
                EXPECTED_SBE20130704[record])
            expected_results.append(particle)

        # Read the records.
        # Verify what we read is what we expect.
        log.debug('===== TEST REC CT SET STATE GROUP 2 =====')
        result = parser.get_records(len(expected_results))
        self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)

    def test_rec_ct_simple(self):
        """
        Read Recovered CT data from the file and pull out data particles
        one at a time. Verify that the results are those we expected.
        """
        in_file = open(os.path.join(RESOURCE_PATH,
                                    'SBE37-IM_20110101_2011_01_01.hex'))
        parser = self.create_rec_ct_parser(in_file)

        for record in range(0, len(EXPECTED_SBE20110101)):
            log.debug('===== TEST REC CT SIMPLE GET RECORD %d =====',
                      record + 1)

            # Generate expected particle
            expected_results = []
            particle = CtdmoRecoveredInstrumentDataParticle(
                EXPECTED_SBE20110101[record])
            expected_results.append(particle)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, expected_results)

        in_file.close()
        self.assertEqual(self.exception_callback_value, None)
