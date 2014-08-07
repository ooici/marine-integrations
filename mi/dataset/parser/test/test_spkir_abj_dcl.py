#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_spkir_abj_dcl
@file marine-integrations/mi/dataset/parser/test/test_spkir_abj_dcl.py
@author Steve Myerson
@brief Test code for a spkir_abj_dcl data parser

In the following files, Metadata consists of 4 records.
There is 1 group of Sensor Data records for each set of metadata.

Files used for testing:

20010101.spkir1.log
  Metadata - 1 set,  Sensor Data - 0 records

20020113.spkir2.log
  Metadata - 1 set,  Sensor Data - 13 records

20030208.spkir3.log
  Metadata - 2 sets,  Sensor Data - 8 records

20040305.spkir4.log
  Metadata - 3 sets,  Sensor Data - 5 records

20050403.spkir5.log
  Metadata - 4 sets,  Sensor Data - 3 records

20061220.spkir6.log
  Metadata - 1 set,  Sensor Data - 400 records

20071225.spkir7.log
  Metadata - 2 sets,  Sensor Data - 250 records

20080401.spkir8.log
  This file contains a boatload of invalid sensor data records.
  See metadata in file for a list of the errors.
"""

import unittest
import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

from mi.dataset.parser.spkir_abj_dcl import \
    SpkirAbjDclRecoveredParser, \
    SpkirAbjDclTelemeteredParser, \
    SpkirAbjDclRecoveredInstrumentDataParticle, \
    SpkirAbjDclTelemeteredInstrumentDataParticle, \
    SpkirStateKey

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver',
                 'spkir_abj', 'dcl', 'resource')

# Expected tuples for data in file 20010101.spkir1.log
# This file has no sensor data records and should not produce any particles.

# Expected tuples for data in file 20020113.spkir2.log
EXPECTED_20020113_spkir2 = [
    ('2002/01/13 03:07:07.338', '2002', '01', '13', '03', '07', '07',
        'SATDI1', '0001', '0000000.00', -32768,
        [0, 1, 2, 3, 4, 5, 6],
        0, 0, 0, 0, 1),
    ('2002/01/13 03:07:20.917', '2002', '01', '13', '03', '07', '20',
        'SATDI1', '0001', '0000010.00', -27307,
        [357913940, 357913941, 357913942, 357913943, 357913944, 357913945, 357913946],        5461, 5461, 5461, 21, 1),
    ('2002/01/13 03:07:34.496', '2002', '01', '13', '03', '07', '34',
        'SATDI1', '0001', '0000020.00', -21846,
        [715827880, 715827881, 715827882, 715827883, 715827884, 715827885, 715827886],
        10922, 10922, 10922, 42, 1),
    ('2002/01/13 03:07:48.075', '2002', '01', '13', '03', '07', '48',
        'SATDI1', '0001', '0000030.00', -16385,
        [1073741820, 1073741821, 1073741822, 1073741823, 1073741824, 1073741825, 1073741826],
        16383, 16383, 16383, 63, 1),
    ('2002/01/13 03:08:01.654', '2002', '01', '13', '03', '08', '01',
        'SATDI1', '0001', '0000040.00', -10924,
        [1431655760, 1431655761, 1431655762, 1431655763, 1431655764, 1431655765, 1431655766],
        21844, 21844, 21844, 84, 1),
    ('2002/01/13 03:08:15.233', '2002', '01', '13', '03', '08', '15',
        'SATDI1', '0001', '0000050.00', -5463,
        [1789569700, 1789569701, 1789569702, 1789569703, 1789569704, 1789569705, 1789569706],
        27305, 27305, 27305, 105, 1),
    ('2002/01/13 03:08:28.812', '2002', '01', '13', '03', '08', '28',
        'SATDI1', '0001', '0000060.00', -2,
        [2147483640, 2147483641, 2147483642, 2147483643, 2147483644, 2147483645, 2147483646],
        32766, 32766, 32766, 126, 1),
    ('2002/01/13 03:08:42.391', '2002', '01', '13', '03', '08', '42',
        'SATDI1', '0001', '0000070.00', 5459,
        [2505397580, 2505397581, 2505397582, 2505397583, 2505397584, 2505397585, 2505397586],
        38227, 38227, 38227, 147, 0),
    ('2002/01/13 03:08:55.970', '2002', '01', '13', '03', '08', '55',
        'SATDI1', '0001', '0000080.00', 10920,
        [2863311520, 2863311521, 2863311522, 2863311523, 2863311524, 2863311525, 2863311526],
        43688, 43688, 43688, 168, 1),
    ('2002/01/13 03:09:09.549', '2002', '01', '13', '03', '09', '09',
        'SATDI1', '0001', '0000090.00', 16381,
        [3221225460, 3221225461, 3221225462, 3221225463, 3221225464, 3221225465, 3221225466],
        49149, 49149, 49149, 189, 1),
    ('2002/01/13 03:09:23.128', '2002', '01', '13', '03', '09', '23',
        'SATDI1', '0001', '0000100.00', 21842,
        [3579139400, 3579139401, 3579139402, 3579139403, 3579139404, 3579139405, 3579139406],
        54610, 54610, 54610, 210, 1),
    ('2002/01/13 03:09:36.707', '2002', '01', '13', '03', '09', '36',
        'SATDI1', '0001', '0000110.00', 27303,
        [3937053340, 3937053341, 3937053342, 3937053343, 3937053344, 3937053345, 3937053346],
        60071, 60071, 60071, 231, 1),
    ('2002/01/13 03:09:50.286', '2002', '01', '13', '03', '09', '50',
        'SATDI1', '0001', '0000120.00', 32764,
        [4294967280, 4294967281, 4294967282, 4294967283, 4294967284, 4294967285, 4294967286],
        65532, 65532, 65532, 252, 1),
]

# Expected tuples for data in file 20030208.spkir3.log
EXPECTED_20030208_spkir3 = [
    ('2003/02/08 05:09:09.340', '2003', '02', '08', '05', '09', '09',
        'SATDI2', '0022', '0000000.00', -32768,
        [0, 1, 2, 3, 4, 5, 6],
        0, 0, 0, 0, 1),
    ('2003/02/08 05:09:22.919', '2003', '02', '08', '05', '09', '22',
        'SATDI2', '0022', '0000008.00', -28399,
        [286331152, 286331153, 286331154, 286331155, 286331156, 286331157, 286331158],
        4369, 4369, 4369, 17, 1),
    ('2003/02/08 05:09:36.498', '2003', '02', '08', '05', '09', '36',
        'SATDI2', '0022', '0000016.00', -24030,
        [572662304, 572662305, 572662306, 572662307, 572662308, 572662309, 572662310],
        8738, 8738, 8738, 34, 1),
    ('2003/02/08 05:09:50.077', '2003', '02', '08', '05', '09', '50',
        'SATDI2', '0022', '0000024.00', -19661,
        [858993456, 858993457, 858993458, 858993459, 858993460, 858993461, 858993462],
        13107, 13107, 13107, 51, 1),
    ('2003/02/08 05:10:03.656', '2003', '02', '08', '05', '10', '03',
        'SATDI2', '0022', '0000032.00', -15292,
        [1145324608, 1145324609, 1145324610, 1145324611, 1145324612, 1145324613, 1145324614],
        17476, 17476, 17476, 68, 1),
    ('2003/02/08 05:10:17.235', '2003', '02', '08', '05', '10', '17',
        'SATDI2', '0022', '0000040.00', -10923,
        [1431655760, 1431655761, 1431655762, 1431655763, 1431655764, 1431655765, 1431655766],
        21845, 21845, 21845, 85, 1),
    ('2003/02/08 05:10:30.814', '2003', '02', '08', '05', '10', '30',
        'SATDI2', '0022', '0000048.00', -6554,
        [1717986912, 1717986913, 1717986914, 1717986915, 1717986916, 1717986917, 1717986918],
        26214, 26214, 26214, 102, 1),
    ('2003/02/08 05:10:44.393', '2003', '02', '08', '05', '10', '44',
        'SATDI2', '0022', '0000056.00', -2185,
        [2004318064, 2004318065, 2004318066, 2004318067, 2004318068, 2004318069, 2004318070],
        30583, 30583, 30583, 119, 0),
    ('2003/02/08 05:11:52.288', '2003', '02', '08', '05', '11', '52',
        'SATDI2', '0022', '0000064.00', 2184,
        [2290649216, 2290649217, 2290649218, 2290649219, 2290649220, 2290649221, 2290649222],
        34952, 34952, 34952, 136, 1),
    ('2003/02/08 05:12:05.867', '2003', '02', '08', '05', '12', '05',
        'SATDI2', '0022', '0000072.00', 6553,
        [2576980368, 2576980369, 2576980370, 2576980371, 2576980372, 2576980373, 2576980374],
        39321, 39321, 39321, 153, 1),
    ('2003/02/08 05:12:19.446', '2003', '02', '08', '05', '12', '19',
        'SATDI2', '0022', '0000080.00', 10922,
        [2863311520, 2863311521, 2863311522, 2863311523, 2863311524, 2863311525, 2863311526],
        43690, 43690, 43690, 170, 1),
    ('2003/02/08 05:12:33.025', '2003', '02', '08', '05', '12', '33',
        'SATDI2', '0022', '0000088.00', 15291,
        [3149642672, 3149642673, 3149642674, 3149642675, 3149642676, 3149642677, 3149642678],
        48059, 48059, 48059, 187, 1),
    ('2003/02/08 05:12:46.604', '2003', '02', '08', '05', '12', '46',
        'SATDI2', '0022', '0000096.00', 19660,
        [3435973824, 3435973825, 3435973826, 3435973827, 3435973828, 3435973829, 3435973830],
        52428, 52428, 52428, 204, 1),
    ('2003/02/08 05:13:00.183', '2003', '02', '08', '05', '13', '00',
        'SATDI2', '0022', '0000104.00', 24029,
        [3722304976, 3722304977, 3722304978, 3722304979, 3722304980, 3722304981, 3722304982],
        56797, 56797, 56797, 221, 1),
    ('2003/02/08 05:13:13.762', '2003', '02', '08', '05', '13', '13',
        'SATDI2', '0022', '0000112.00', 28398,
        [4008636128, 4008636129, 4008636130, 4008636131, 4008636132, 4008636133, 4008636134],
        61166, 61166, 61166, 238, 1),
    ('2003/02/08 05:13:27.341', '2003', '02', '08', '05', '13', '27',
        'SATDI2', '0022', '0000120.00', 32767,
        [4294967280, 4294967281, 4294967282, 4294967283, 4294967284, 4294967285, 4294967286],
        65535, 65535, 65535, 255, 0),
]

# Expected tuples for data in file 20040305.spkir4.log
EXPECTED_20040305_spkir4 = [
    ('2004/03/05 07:11:11.342', '2004', '03', '05', '07', '11', '11',
        'SATDI3', '0203', '0000000.00', -32768,
        [0, 1, 2, 3, 4, 5, 6],
        0, 0, 0, 0, 1),
    ('2004/03/05 07:11:24.921', '2004', '03', '05', '07', '11', '24',
        'SATDI3', '0203', '0000008.57', -28087,
        [306783377, 306783378, 306783379, 306783380, 306783381, 306783382, 306783383],
        4681, 4681, 4681, 18, 1),
    ('2004/03/05 07:11:38.500', '2004', '03', '05', '07', '11', '38',
        'SATDI3', '0203', '0000017.14', -23406,
        [613566754, 613566755, 613566756, 613566757, 613566758, 613566759, 613566760],        9362, 9362, 9362, 36, 1),
    ('2004/03/05 07:11:52.079', '2004', '03', '05', '07', '11', '52',
        'SATDI3', '0203', '0000025.71', -18725,
        [920350131, 920350132, 920350133, 920350134, 920350135, 920350136, 920350137],
        14043, 14043, 14043, 54, 1),
    ('2004/03/05 07:12:05.658', '2004', '03', '05', '07', '12', '05',
        'SATDI3', '0203', '0000034.29', -14044,
        [1227133508, 1227133509, 1227133510, 1227133511, 1227133512, 1227133513, 1227133514],
        18724, 18724, 18724, 72, 1),
    ('2004/03/05 07:13:13.553', '2004', '03', '05', '07', '13', '13',
        'SATDI3', '0203', '0000042.86', -9363,
        [1533916885, 1533916886, 1533916887, 1533916888, 1533916889, 1533916890, 1533916891],
        23405, 23405, 23405, 90, 1),
    ('2004/03/05 07:13:27.132', '2004', '03', '05', '07', '13', '27',
        'SATDI3', '0203', '0000051.43', -4682,
        [1840700262, 1840700263, 1840700264, 1840700265, 1840700266, 1840700267, 1840700268],
        28086, 28086, 28086, 108, 1),
    ('2004/03/05 07:13:40.711', '2004', '03', '05', '07', '13', '40',
        'SATDI3', '0203', '0000060.00', -1,
        [2147483639, 2147483640, 2147483641, 2147483642, 2147483643, 2147483644, 2147483645],
        32767, 32767, 32767, 126, 1),
    ('2004/03/05 07:13:54.290', '2004', '03', '05', '07', '13', '54',
        'SATDI3', '0203', '0000068.57', 4680,
        [2454267016, 2454267017, 2454267018, 2454267019, 2454267020, 2454267021, 2454267022],
        37448, 37448, 37448, 144, 1),
    ('2004/03/05 07:14:07.869', '2004', '03', '05', '07', '14', '07',
        'SATDI3', '0203', '0000077.14', 9361,
        [2761050393, 2761050394, 2761050395, 2761050396, 2761050397, 2761050398, 2761050399],
        42129, 42129, 42129, 162, 1),
    ('2004/03/05 07:15:15.764', '2004', '03', '05', '07', '15', '15',
        'SATDI3', '0203', '0000085.71', 14042,
        [3067833770, 3067833771, 3067833772, 3067833773, 3067833774, 3067833775, 3067833776],
        46810, 46810, 46810, 180, 1),
   ('2004/03/05 07:15:29.343', '2004', '03', '05', '07', '15', '29',
        'SATDI3', '0203', '0000094.29', 18723,
        [3374617147, 3374617148, 3374617149, 3374617150, 3374617151, 3374617152, 3374617153],
        51491, 51491, 51491, 198, 1),
    ('2004/03/05 07:15:42.922', '2004', '03', '05', '07', '15', '42',
        'SATDI3', '0203', '0000102.86', 23404,
        [3681400524, 3681400525, 3681400526, 3681400527, 3681400528, 3681400529, 3681400530],
        56172, 56172, 56172, 216, 1),
    ('2004/03/05 07:15:56.501', '2004', '03', '05', '07', '15', '56',
        'SATDI3', '0203', '0000111.43', 28085,
        [3988183901, 3988183902, 3988183903, 3988183904, 3988183905, 3988183906, 3988183907],
        60853, 60853, 60853, 234, 1),
    ('2004/03/05 07:16:10.080', '2004', '03', '05', '07', '16', '10',
        'SATDI3', '0203', '0000120.00', 32766,
        [4294967278, 4294967279, 4294967280, 4294967281, 4294967282, 4294967283, 4294967284],
        65534, 65534, 65534, 252, 1),
]

# Expected tuples for data in file 20050403.spkir5.log
EXPECTED_20050403_spkir5 = [
    ('2005/04/03 09:13:13.344', '2005', '04', '03', '09', '13', '13',
        'SATDI4', '2004', '0000000.00', -32768,
        [0, 1, 2, 3, 4, 5, 6],
        0, 0, 0, 0, 1),
    ('2005/04/03 09:13:26.923', '2005', '04', '03', '09', '13', '26',
        'SATDI4', '2004', '0000010.91', -26811,
        [390451571, 390451572, 390451573, 390451574, 390451575, 390451576, 390451577],
        5957, 5957, 5957, 23, 1),
    ('2005/04/03 09:13:40.502', '2005', '04', '03', '09', '13', '40',
        'SATDI4', '2004', '0000021.82', -20854,
        [780903142, 780903143, 780903144, 780903145, 780903146, 780903147, 780903148],        11914, 11914, 11914, 46, 1),
    ('2005/04/03 09:14:48.397', '2005', '04', '03', '09', '14', '48',
        'SATDI4', '2004', '0000032.73', -14897,
        [1171354713, 1171354714, 1171354715, 1171354716, 1171354717, 1171354718, 1171354719],
        17871, 17871, 17871, 69, 1),
    ('2005/04/03 09:15:01.976', '2005', '04', '03', '09', '15', '01',
        'SATDI4', '2004', '0000043.64', -8940,
        [1561806284, 1561806285, 1561806286, 1561806287, 1561806288, 1561806289, 1561806290],
        23828, 23828, 23828, 92, 1),
    ('2005/04/03 09:15:15.555', '2005', '04', '03', '09', '15', '15',
        'SATDI4', '2004', '0000054.55', -2983,
        [1952257855, 1952257856, 1952257857, 1952257858, 1952257859, 1952257860, 1952257861],
        29785, 29785, 29785, 115, 1),
    ('2005/04/03 09:16:23.450', '2005', '04', '03', '09', '16', '23',
        'SATDI4', '2004', '0000065.45', 2974,
        [2342709426, 2342709427, 2342709428, 2342709429, 2342709430, 2342709431, 2342709432],
        35742, 35742, 35742, 138, 1),
    ('2005/04/03 09:16:37.029', '2005', '04', '03', '09', '16', '37',
        'SATDI4', '2004', '0000076.36', 8931,
        [2733160997, 2733160998, 2733160999, 2733161000, 2733161001, 2733161002, 2733161003],
        41699, 41699, 41699, 161, 1),
    ('2005/04/03 09:16:50.608', '2005', '04', '03', '09', '16', '50',
        'SATDI4', '2004', '0000087.27', 14888,
        [3123612568, 3123612569, 3123612570, 3123612571, 3123612572, 3123612573, 3123612574],
        47656, 47656, 47656, 184, 1),
    ('2005/04/03 09:17:58.503', '2005', '04', '03', '09', '17', '58',
        'SATDI4', '2004', '0000098.18', 20845,
        [3514064139, 3514064140, 3514064141, 3514064142, 3514064143, 3514064144, 3514064145],
        53613, 53613, 53613, 207, 1),
    ('2005/04/03 09:18:12.082', '2005', '04', '03', '09', '18', '12',
        'SATDI4', '2004', '0000109.09', 26802,
        [3904515710, 3904515711, 3904515712, 3904515713, 3904515714, 3904515715, 3904515716],
        59570, 59570, 59570, 230, 1),
    ('2005/04/03 09:18:25.661', '2005', '04', '03', '09', '18', '25',
        'SATDI4', '2004', '0000120.00', 32759,
        [4294967281, 4294967282, 4294967283, 4294967284, 4294967285, 4294967286, 4294967287],
        65527, 65527, 65527, 253, 1),
]

FILE1 = '20010101.spkir1.log'
FILE2 = '20020113.spkir2.log'
FILE3 = '20030208.spkir3.log'
FILE4 = '20040305.spkir4.log'
FILE5 = '20050403.spkir5.log'
FILE6 = '20061220.spkir6.log'
FILE7 = '20071225.spkir7.log'
FILE8 = '20080401.spkir8.log'

EXPECTED_FILE2 = EXPECTED_20020113_spkir2
EXPECTED_FILE3 = EXPECTED_20030208_spkir3
EXPECTED_FILE4 = EXPECTED_20040305_spkir4
EXPECTED_FILE5 = EXPECTED_20050403_spkir5
EXPECTED_FILE6 = 400
EXPECTED_FILE7 = 500

MODULE_NAME = 'mi.dataset.parser.spkir_abj_dcl'


@attr('UNIT', group='mi')
class SpkirAbjDclParserUnitTestCase(ParserUnitTestCase):
    
    def create_rec_parser(self, file_handle, new_state=None):
        """
        This function creates a SpkirAbjDcl parser for recovered data.
        """
        parser = SpkirAbjDclRecoveredParser(self.rec_config,
            file_handle, new_state, self.rec_state_callback,
            self.rec_pub_callback, self.rec_exception_callback)
        return parser

    def create_tel_parser(self, file_handle, new_state=None):
        """
        This function creates a SpkirAbjDcl parser for telemetered data.
        """
        parser = SpkirAbjDclTelemeteredParser(self.tel_config,
            file_handle, new_state, self.rec_state_callback,
            self.tel_pub_callback, self.tel_exception_callback)
        return parser

    def open_file(self, filename):
        file = open(os.path.join(RESOURCE_PATH, filename), mode='r')
        return file

    def rec_state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.rec_state_callback_value = state
        self.rec_file_ingested_value = file_ingested

    def tel_state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.tel_state_callback_value = state
        self.tel_file_ingested_value = file_ingested

    def rec_pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.rec_publish_callback_value = pub

    def tel_pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.tel_publish_callback_value = pub

    def rec_exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.rec_exception_callback_value = exception
        self.rec_exceptions_detected += 1

    def tel_exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.tel_exception_callback_value = exception
        self.tel_exceptions_detected += 1

    def setUp(self):
        ParserUnitTestCase.setUp(self)

        self.rec_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: MODULE_NAME,
            DataSetDriverConfigKeys.PARTICLE_CLASS: None
        }

        self.tel_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: MODULE_NAME,
            DataSetDriverConfigKeys.PARTICLE_CLASS: None
        }

        self.rec_state_callback_value = None
        self.rec_file_ingested_value = False
        self.rec_publish_callback_value = None
        self.rec_exception_callback_value = None
        self.rec_exceptions_detected = 0

        self.tel_state_callback_value = None
        self.tel_file_ingested_value = False
        self.tel_publish_callback_value = None
        self.tel_exception_callback_value = None
        self.tel_exceptions_detected = 0

        self.maxDiff = None

    def test_big_giant_input(self):
        """
        Read a large file and verify that all expected particles can be read.
        Verification is not done at this time, but will be done during
        integration and qualification testing.
        """
        log.debug('===== START TEST BIG GIANT INPUT RECOVERED =====')
        in_file = self.open_file(FILE6)
        parser = self.create_rec_parser(in_file)

        # In a single read, get all particles in this file.
        number_expected_results = EXPECTED_FILE6
        result = parser.get_records(number_expected_results)
        self.assertEqual(len(result), number_expected_results)

        in_file.close()
        self.assertEqual(self.rec_exception_callback_value, None)

        log.debug('===== START TEST BIG GIANT INPUT TELEMETERED =====')
        in_file = self.open_file(FILE7)
        parser = self.create_tel_parser(in_file)

        # In a single read, get all particles in this file.
        number_expected_results = EXPECTED_FILE7
        result = parser.get_records(number_expected_results)
        self.assertEqual(len(result), number_expected_results)

        in_file.close()
        self.assertEqual(self.tel_exception_callback_value, None)

        log.debug('===== END TEST BIG GIANT INPUT =====')
        
    def test_get_many(self):
        """
        Read a file and pull out multiple data particles at one time.
        Verify that the results are those we expected.
        """
        log.debug('===== START TEST GET MANY RECOVERED =====')
        in_file = self.open_file(FILE5)
        parser = self.create_rec_parser(in_file)

        # Generate a list of expected result particles.
        expected_particle = []
        for expected in EXPECTED_FILE5:
            particle = SpkirAbjDclRecoveredInstrumentDataParticle(expected)
            expected_particle.append(particle)

        # In a single read, get all particles for this file.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)

        self.assertEqual(self.rec_exception_callback_value, None)
        in_file.close()

        log.debug('===== START TEST GET MANY TELEMETERED =====')
        in_file = self.open_file(FILE4)
        parser = self.create_tel_parser(in_file)

        # Generate a list of expected result particles.
        expected_particle = []
        for expected in EXPECTED_FILE4:
            particle = SpkirAbjDclTelemeteredInstrumentDataParticle(expected)
            expected_particle.append(particle)

        # In a single read, get all particles for this file.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)

        self.assertEqual(self.tel_exception_callback_value, None)
        in_file.close()

        log.debug('===== END TEST GET MANY =====')

    def test_invalid_sensor_data_records(self):
        """
        Read data from a file containing invalid sensor data records.
        Verify that no instrument particles are produced.
        """
        log.debug('===== START TEST INVALID SENSOR DATA RECOVERED =====')
        in_file = self.open_file(FILE8)
        parser = self.create_rec_parser(in_file)

        # Try to get records and verify that none are returned.
        result = parser.get_records(1)
        self.assertEqual(result, [])

        in_file.close()

        log.debug('===== START TEST INVALID SENSOR DATA TELEMETERED =====')
        in_file = self.open_file(FILE8)
        parser = self.create_tel_parser(in_file)

        # Try to get records and verify that none are returned.
        result = parser.get_records(1)
        self.assertEqual(result, [])

        in_file.close()

        log.debug('===== END TEST INVALID SENSOR DATA =====')
        
    def test_mid_state_start(self):
        """
        Test starting a parser with a state in the middle of processing.
        """
        log.debug('===== START TEST MID-STATE START RECOVERED =====')

        in_file = self.open_file(FILE3)

        # Start at the beginning of the record 10 (of 16 total).
        initial_state = {
            SpkirStateKey.POSITION: 1376
        }

        parser = self.create_rec_parser(in_file, new_state=initial_state)

        # Generate a list of expected result particles.
        expected_particle = []
        for expected in EXPECTED_FILE3[-7: ]:
            particle = SpkirAbjDclRecoveredInstrumentDataParticle(expected)
            expected_particle.append(particle)

        # In a single read, get all particles for this file.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)

        self.assertEqual(self.rec_exception_callback_value, None)
        in_file.close()

        log.debug('===== START TEST MID-STATE START TELEMETERED =====')

        in_file = self.open_file(FILE2)

        # Start at the beginning of the record 6 (of 13 total).
        initial_state = {
            SpkirStateKey.POSITION: 731
        }

        parser = self.create_tel_parser(in_file, new_state=initial_state)

        # Generate a list of expected result particles.
        expected_particle = []
        for expected in EXPECTED_FILE2[-8: ]:
            particle = SpkirAbjDclTelemeteredInstrumentDataParticle(expected)
            expected_particle.append(particle)

        # In a single read, get all particles for this file.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)

        self.assertEqual(self.tel_exception_callback_value, None)
        in_file.close()

        log.debug('===== END TEST MID-STATE START =====')

    def test_no_sensor_data(self):
        """
        Read a file containing no sensor data records
        and verify that no particles are produced.
        """
        log.debug('===== START TEST NO SENSOR DATA RECOVERED =====')
        in_file = self.open_file(FILE1)
        parser = self.create_rec_parser(in_file)

        # Try to get a record and verify that none are produced.
        result = parser.get_records(1)
        self.assertEqual(result, [])

        self.assertEqual(self.rec_exception_callback_value, None)
        in_file.close()

        log.debug('===== START TEST NO SENSOR DATA TELEMETERED =====')
        in_file = self.open_file(FILE1)
        parser = self.create_tel_parser(in_file)

        # Try to get a record and verify that none are produced.
        result = parser.get_records(1)
        self.assertEqual(result, [])

        self.assertEqual(self.tel_exception_callback_value, None)
        in_file.close()

        log.debug('===== END TEST SENSOR DATA =====')
        
    def test_set_state(self):
        """
        This test verifies that the state can be changed after starting.
        Some particles are read and then the parser state is modified to
        skip ahead or back.
        """
        log.debug('===== START TEST SET STATE RECOVERED =====')

        in_file = self.open_file(FILE4)
        parser = self.create_rec_parser(in_file)

        # Read and verify 5 particles (of the 15).
        for expected in EXPECTED_FILE4[ : 5]:

            # Generate expected particle
            expected_particle = SpkirAbjDclRecoveredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        # Skip ahead in the file so that we get the last 4 particles.
        new_state = {
            SpkirStateKey.POSITION: 1854
        }

        # Set the state.
        parser.set_state(new_state)

        # Read and verify the last 4 particles.
        for expected in EXPECTED_FILE4[-4: ]:

            # Generate expected particle
            expected_particle = SpkirAbjDclRecoveredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        log.debug('===== START TEST SET STATE TELEMETERED =====')

        in_file = self.open_file(FILE5)
        parser = self.create_tel_parser(in_file)

        # Read and verify 8 particles (of the 12).
        for expected in EXPECTED_FILE5[ : 8]:

            # Generate expected particle
            expected_particle = SpkirAbjDclTelemeteredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        # Skip back in the file so that we get the last 8 particles.
        new_state = {
            SpkirStateKey.POSITION: 956,
        }

        # Set the state.
        parser.set_state(new_state)

        # Read and verify the last 8 particles.
        for expected in EXPECTED_FILE5[-8: ]:

            # Generate expected particle
            expected_particle = SpkirAbjDclTelemeteredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        log.debug('===== END TEST SET STATE =====')

    def test_simple(self):
        """
        Read data from a file and pull out data particles
        one at a time. Verify that the results are those we expected.
        """
        log.debug('===== START TEST SIMPLE RECOVERED =====')
        in_file = self.open_file(FILE2)
        parser = self.create_rec_parser(in_file)

        for expected in EXPECTED_FILE2:

            # Generate expected particle
            expected_particle = SpkirAbjDclRecoveredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        self.assertEqual(self.rec_exception_callback_value, None)
        in_file.close()

        log.debug('===== START TEST SIMPLE TELEMETERED =====')
        in_file = self.open_file(FILE3)
        parser = self.create_tel_parser(in_file)

        for expected in EXPECTED_FILE3:

            # Generate expected particle
            expected_particle = SpkirAbjDclTelemeteredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        self.assertEqual(self.tel_exception_callback_value, None)
        in_file.close()

        log.debug('===== END TEST SIMPLE =====')
