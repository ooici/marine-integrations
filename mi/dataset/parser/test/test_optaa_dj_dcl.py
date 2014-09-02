#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_optaa_dj_dcl
@file marine-integrations/mi/dataset/parser/test/test_optaa_dj_dcl.py
@author Steve Myerson (Raytheon)
@brief Test code for a optaa_dj_dcl data parser

Files used for testing:

20010314_010314.optaa1.log
  Records - 3, Measurements - 1, 3, 14

20020704_020704.optaa2.log
  Records - 5, Measurements - 0, 2, 7, 4, 27

20031031_031031.optaa3.log
  Records - 3, Measurements - 50, 255, 125

20041220_041220.optaa4.log
  Records - 4, Measurements - 255, 175, 150, 255

20050401_050401.optaa5.log
  Records - 3, Measurements - 1, 2, 3
  All records have a checksum error - No particles will be produced

20061225_061225.optaa6.log
  Records - 10, Measurements - 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
"""

import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger; log = get_logger()

from mi.core.exceptions import DatasetParserException
from mi.core.instrument.data_particle import DataParticleKey

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

from mi.dataset.parser.optaa_dj_dcl import \
    OptaaDjDclRecoveredParser, \
    OptaaDjDclTelemeteredParser, \
    OptaaDjDclRecoveredInstrumentDataParticle, \
    OptaaDjDclRecoveredMetadataDataParticle, \
    OptaaDjDclTelemeteredInstrumentDataParticle, \
    OptaaDjDclTelemeteredMetadataDataParticle, \
    OptaaStateKey

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver',
                             'optaa_dj', 'dcl', 'resource')

MODULE_NAME = 'mi.dataset.parser.optaa_dj_dcl'

# Expected tuples for data in file 20010314_010314.optaa1.log
EXPECTED_20010314_010314_optaa1 = [
    ((3193520594.000), ('2001-03-14 01:03:14', 4, 83, 1193047)),
    ((3193520594.000), (1, 2, 3, 4, 5, 6, 7, 111, 1,
      [0],
      [32767],
      [32767],
      [65535])),
    ((3193520594.111), (2, 4, 6, 8, 10, 12, 14, 222, 3,
      [0, 16383, 32766],
      [32767, 49150, 65533],
      [32767, 16384, 1],
      [65535, 49152, 32769])),
    ((3193520594.222), (3, 6, 9, 12, 15, 18, 21, 333, 14,
      [0, 2520, 5040, 7560, 10080, 12600, 15120, 17640, 20160, 22680, 25200,
        27720, 30240, 32760],
      [32767, 35287, 37807, 40327, 42847, 45367, 47887, 50407, 52927, 55447,
        57967, 60487, 63007, 65527],
      [32767, 30247, 27727, 25207, 22687, 20167, 17647, 15127, 12607, 10087,
        7567, 5047, 2527, 7],
      [65535, 63015, 60495, 57975, 55455, 52935, 50415, 47895, 45375, 42855,
        40335, 37815, 35295, 32775]))
]

# Expected tuples for data in file 20020704_020704.optaa2.log
EXPECTED_20020704_020704_optaa2 = [
    ((3234737224.000), ('2002-07-04 02:07:04', 5, 83, 1193048)),
    ((3234737224.000), (1, 2, 3, 4, 5, 6, 7, 222, 0,
      [],
      [],
      [],
      [])),
    ((3234737224.222), (2, 4, 6, 8, 10, 12, 14, 444, 2,
      [0, 32767],
      [32767, 65534],
      [32767, 0],
      [65535, 32768])),
    ((3234737224.444), (3, 6, 9, 12, 15, 18, 21, 666, 7,
      [0, 5461, 10922, 16383, 21844, 27305, 32766],
      [32767, 38228, 43689, 49150, 54611, 60072, 65533],
      [32767, 27306, 21845, 16384, 10923, 5462, 1],
      [65535, 60074, 54613, 49152, 43691, 38230, 32769])),
    ((3234737224.666), (4, 8, 12, 16, 20, 24, 28, 888, 4,
      [0, 10922, 21844, 32766],
      [32767, 43689, 54611, 65533],
      [32767, 21845, 10923, 1],
      [65535, 54613, 43691, 32769])),
    ((3234737224.888), (5, 10, 15, 20, 25, 30, 35, 1110, 27,
      [0, 1260, 2520, 3780, 5040, 6300, 7560, 8820, 10080, 11340, 12600, 13860,
        15120, 16380, 17640, 18900, 20160, 21420, 22680, 23940, 25200, 26460, 27720,
        28980, 30240, 31500, 32760],
      [32767, 34027, 35287, 36547, 37807, 39067, 40327, 41587, 42847, 44107,
        45367, 46627, 47887, 49147, 50407, 51667, 52927, 54187, 55447, 56707, 57967,
        59227, 60487, 61747, 63007, 64267, 65527],
      [32767, 31507, 30247, 28987, 27727, 26467, 25207, 23947, 22687, 21427,
        20167, 18907, 17647, 16387, 15127, 13867, 12607, 11347, 10087, 8827, 7567,
        6307, 5047, 3787, 2527, 1267, 7],
      [65535, 64275, 63015, 61755, 60495, 59235, 57975, 56715, 55455, 54195,
        52935, 51675, 50415, 49155, 47895, 46635, 45375, 44115, 42855, 41595, 40335,
        39075, 37815, 36555, 35295, 34035, 32775]))
]

# Expected tuples for data in file 20031031_031031.optaa3.log
EXPECTED_20031031_031031_optaa3 = [
    ((3276558631.000), ('2003-10-31 03:10:31', 6, 83, 1193049)),
    ((3276558631.000), (1, 2, 3, 4, 5, 6, 7, 333, 50,
      [0, 668, 1336, 2004, 2672, 3340, 4008, 4676, 5344, 6012, 6680, 7348,
        8016, 8684, 9352, 10020, 10688, 11356, 12024, 12692, 13360, 14028, 14696,
        15364, 16032, 16700, 17368, 18036, 18704, 19372, 20040, 20708, 21376, 22044,
        22712, 23380, 24048, 24716, 25384, 26052, 26720, 27388, 28056, 28724, 29392,
        30060, 30728, 31396, 32064, 32732],
      [32767, 33435, 34103, 34771, 35439, 36107, 36775, 37443, 38111, 38779,
        39447, 40115, 40783, 41451, 42119, 42787, 43455, 44123, 44791, 45459, 46127,
        46795, 47463, 48131, 48799, 49467, 50135, 50803, 51471, 52139, 52807, 53475,
        54143, 54811, 55479, 56147, 56815, 57483, 58151, 58819, 59487, 60155, 60823,
        61491, 62159, 62827, 63495, 64163, 64831, 65499],
      [32767, 32099, 31431, 30763, 30095, 29427, 28759, 28091, 27423, 26755,
        26087, 25419, 24751, 24083, 23415, 22747, 22079, 21411, 20743, 20075, 19407,
        18739, 18071, 17403, 16735, 16067, 15399, 14731, 14063, 13395, 12727, 12059,
        11391, 10723, 10055, 9387, 8719, 8051, 7383, 6715, 6047, 5379, 4711, 4043,
        3375, 2707, 2039, 1371, 703, 35],
      [65535, 64867, 64199, 63531, 62863, 62195, 61527, 60859, 60191, 59523,
        58855, 58187, 57519, 56851, 56183, 55515, 54847, 54179, 53511, 52843, 52175,
        51507, 50839, 50171, 49503, 48835, 48167, 47499, 46831, 46163, 45495, 44827,
        44159, 43491, 42823, 42155, 41487, 40819, 40151, 39483, 38815, 38147, 37479,
        36811, 36143, 35475, 34807, 34139, 33471, 32803])),
    ((3276558631.333), (2, 4, 6, 8, 10, 12, 14, 666, 255,
      [0, 129, 258, 387, 516, 645, 774, 903, 1032, 1161, 1290, 1419, 1548,
        1677, 1806, 1935, 2064, 2193, 2322, 2451, 2580, 2709, 2838, 2967, 3096, 3225,
        3354, 3483, 3612, 3741, 3870, 3999, 4128, 4257, 4386, 4515, 4644, 4773, 4902,
        5031, 5160, 5289, 5418, 5547, 5676, 5805, 5934, 6063, 6192, 6321, 6450, 6579,
        6708, 6837, 6966, 7095, 7224, 7353, 7482, 7611, 7740, 7869, 7998, 8127, 8256,
        8385, 8514, 8643, 8772, 8901, 9030, 9159, 9288, 9417, 9546, 9675, 9804, 9933,
        10062, 10191, 10320, 10449, 10578, 10707, 10836, 10965, 11094, 11223, 11352,
        11481, 11610, 11739, 11868, 11997, 12126, 12255, 12384, 12513, 12642, 12771,
        12900, 13029, 13158, 13287, 13416, 13545, 13674, 13803, 13932, 14061, 14190,
        14319, 14448, 14577, 14706, 14835, 14964, 15093, 15222, 15351, 15480, 15609,
        15738, 15867, 15996, 16125, 16254, 16383, 16512, 16641, 16770, 16899, 17028,
        17157, 17286, 17415, 17544, 17673, 17802, 17931, 18060, 18189, 18318, 18447,
        18576, 18705, 18834, 18963, 19092, 19221, 19350, 19479, 19608, 19737, 19866,
        19995, 20124, 20253, 20382, 20511, 20640, 20769, 20898, 21027, 21156, 21285,
        21414, 21543, 21672, 21801, 21930, 22059, 22188, 22317, 22446, 22575, 22704,
        22833, 22962, 23091, 23220, 23349, 23478, 23607, 23736, 23865, 23994, 24123,
        24252, 24381, 24510, 24639, 24768, 24897, 25026, 25155, 25284, 25413, 25542,
        25671, 25800, 25929, 26058, 26187, 26316, 26445, 26574, 26703, 26832, 26961,
        27090, 27219, 27348, 27477, 27606, 27735, 27864, 27993, 28122, 28251, 28380,
        28509, 28638, 28767, 28896, 29025, 29154, 29283, 29412, 29541, 29670, 29799,
        29928, 30057, 30186, 30315, 30444, 30573, 30702, 30831, 30960, 31089, 31218,
        31347, 31476, 31605, 31734, 31863, 31992, 32121, 32250, 32379, 32508, 32637,
        32766],
      [32767, 32896, 33025, 33154, 33283, 33412, 33541, 33670, 33799, 33928,
        34057, 34186, 34315, 34444, 34573, 34702, 34831, 34960, 35089, 35218, 35347,
        35476, 35605, 35734, 35863, 35992, 36121, 36250, 36379, 36508, 36637, 36766,
        36895, 37024, 37153, 37282, 37411, 37540, 37669, 37798, 37927, 38056, 38185,
        38314, 38443, 38572, 38701, 38830, 38959, 39088, 39217, 39346, 39475, 39604,
        39733, 39862, 39991, 40120, 40249, 40378, 40507, 40636, 40765, 40894, 41023,
        41152, 41281, 41410, 41539, 41668, 41797, 41926, 42055, 42184, 42313, 42442,
        42571, 42700, 42829, 42958, 43087, 43216, 43345, 43474, 43603, 43732, 43861,
        43990, 44119, 44248, 44377, 44506, 44635, 44764, 44893, 45022, 45151, 45280,
        45409, 45538, 45667, 45796, 45925, 46054, 46183, 46312, 46441, 46570, 46699,
        46828, 46957, 47086, 47215, 47344, 47473, 47602, 47731, 47860, 47989, 48118,
        48247, 48376, 48505, 48634, 48763, 48892, 49021, 49150, 49279, 49408, 49537,
        49666, 49795, 49924, 50053, 50182, 50311, 50440, 50569, 50698, 50827, 50956,
        51085, 51214, 51343, 51472, 51601, 51730, 51859, 51988, 52117, 52246, 52375,
        52504, 52633, 52762, 52891, 53020, 53149, 53278, 53407, 53536, 53665, 53794,
        53923, 54052, 54181, 54310, 54439, 54568, 54697, 54826, 54955, 55084, 55213,
        55342, 55471, 55600, 55729, 55858, 55987, 56116, 56245, 56374, 56503, 56632,
        56761, 56890, 57019, 57148, 57277, 57406, 57535, 57664, 57793, 57922, 58051,
        58180, 58309, 58438, 58567, 58696, 58825, 58954, 59083, 59212, 59341, 59470,
        59599, 59728, 59857, 59986, 60115, 60244, 60373, 60502, 60631, 60760, 60889,
        61018, 61147, 61276, 61405, 61534, 61663, 61792, 61921, 62050, 62179, 62308,
        62437, 62566, 62695, 62824, 62953, 63082, 63211, 63340, 63469, 63598, 63727,
        63856, 63985, 64114, 64243, 64372, 64501, 64630, 64759, 64888, 65017, 65146,
        65275, 65404, 65533],
      [32767, 32638, 32509, 32380, 32251, 32122, 31993, 31864, 31735, 31606,
        31477, 31348, 31219, 31090, 30961, 30832, 30703, 30574, 30445, 30316, 30187,
        30058, 29929, 29800, 29671, 29542, 29413, 29284, 29155, 29026, 28897, 28768,
        28639, 28510, 28381, 28252, 28123, 27994, 27865, 27736, 27607, 27478, 27349,
        27220, 27091, 26962, 26833, 26704, 26575, 26446, 26317, 26188, 26059, 25930,
        25801, 25672, 25543, 25414, 25285, 25156, 25027, 24898, 24769, 24640, 24511,
        24382, 24253, 24124, 23995, 23866, 23737, 23608, 23479, 23350, 23221, 23092,
        22963, 22834, 22705, 22576, 22447, 22318, 22189, 22060, 21931, 21802, 21673,
        21544, 21415, 21286, 21157, 21028, 20899, 20770, 20641, 20512, 20383, 20254,
        20125, 19996, 19867, 19738, 19609, 19480, 19351, 19222, 19093, 18964, 18835,
        18706, 18577, 18448, 18319, 18190, 18061, 17932, 17803, 17674, 17545, 17416,
        17287, 17158, 17029, 16900, 16771, 16642, 16513, 16384, 16255, 16126, 15997,
        15868, 15739, 15610, 15481, 15352, 15223, 15094, 14965, 14836, 14707, 14578,
        14449, 14320, 14191, 14062, 13933, 13804, 13675, 13546, 13417, 13288, 13159,
        13030, 12901, 12772, 12643, 12514, 12385, 12256, 12127, 11998, 11869, 11740,
        11611, 11482, 11353, 11224, 11095, 10966, 10837, 10708, 10579, 10450, 10321,
        10192, 10063, 9934, 9805, 9676, 9547, 9418, 9289, 9160, 9031, 8902, 8773,
        8644, 8515, 8386, 8257, 8128, 7999, 7870, 7741, 7612, 7483, 7354, 7225, 7096,
        6967, 6838, 6709, 6580, 6451, 6322, 6193, 6064, 5935, 5806, 5677, 5548, 5419,
        5290, 5161, 5032, 4903, 4774, 4645, 4516, 4387, 4258, 4129, 4000, 3871, 3742,
        3613, 3484, 3355, 3226, 3097, 2968, 2839, 2710, 2581, 2452, 2323, 2194, 2065,
        1936, 1807, 1678, 1549, 1420, 1291, 1162, 1033, 904, 775, 646, 517, 388, 259,
        130, 1],
      [65535, 65406, 65277, 65148, 65019, 64890, 64761, 64632, 64503, 64374,
        64245, 64116, 63987, 63858, 63729, 63600, 63471, 63342, 63213, 63084, 62955,
        62826, 62697, 62568, 62439, 62310, 62181, 62052, 61923, 61794, 61665, 61536,
        61407, 61278, 61149, 61020, 60891, 60762, 60633, 60504, 60375, 60246, 60117,
        59988, 59859, 59730, 59601, 59472, 59343, 59214, 59085, 58956, 58827, 58698,
        58569, 58440, 58311, 58182, 58053, 57924, 57795, 57666, 57537, 57408, 57279,
        57150, 57021, 56892, 56763, 56634, 56505, 56376, 56247, 56118, 55989, 55860,
        55731, 55602, 55473, 55344, 55215, 55086, 54957, 54828, 54699, 54570, 54441,
        54312, 54183, 54054, 53925, 53796, 53667, 53538, 53409, 53280, 53151, 53022,
        52893, 52764, 52635, 52506, 52377, 52248, 52119, 51990, 51861, 51732, 51603,
        51474, 51345, 51216, 51087, 50958, 50829, 50700, 50571, 50442, 50313, 50184,
        50055, 49926, 49797, 49668, 49539, 49410, 49281, 49152, 49023, 48894, 48765,
        48636, 48507, 48378, 48249, 48120, 47991, 47862, 47733, 47604, 47475, 47346,
        47217, 47088, 46959, 46830, 46701, 46572, 46443, 46314, 46185, 46056, 45927,
        45798, 45669, 45540, 45411, 45282, 45153, 45024, 44895, 44766, 44637, 44508,
        44379, 44250, 44121, 43992, 43863, 43734, 43605, 43476, 43347, 43218, 43089,
        42960, 42831, 42702, 42573, 42444, 42315, 42186, 42057, 41928, 41799, 41670,
        41541, 41412, 41283, 41154, 41025, 40896, 40767, 40638, 40509, 40380, 40251,
        40122, 39993, 39864, 39735, 39606, 39477, 39348, 39219, 39090, 38961, 38832,
        38703, 38574, 38445, 38316, 38187, 38058, 37929, 37800, 37671, 37542, 37413,
        37284, 37155, 37026, 36897, 36768, 36639, 36510, 36381, 36252, 36123, 35994,
        35865, 35736, 35607, 35478, 35349, 35220, 35091, 34962, 34833, 34704, 34575,
        34446, 34317, 34188, 34059, 33930, 33801, 33672, 33543, 33414, 33285, 33156,
        33027, 32898, 32769])),
    ((3276558631.666), (3, 6, 9, 12, 15, 18, 21, 999, 125,
      [0, 264, 528, 792, 1056, 1320, 1584, 1848, 2112, 2376, 2640, 2904, 3168,
        3432, 3696, 3960, 4224, 4488, 4752, 5016, 5280, 5544, 5808, 6072, 6336, 6600,
        6864, 7128, 7392, 7656, 7920, 8184, 8448, 8712, 8976, 9240, 9504, 9768,
        10032, 10296, 10560, 10824, 11088, 11352, 11616, 11880, 12144, 12408, 12672,
        12936, 13200, 13464, 13728, 13992, 14256, 14520, 14784, 15048, 15312, 15576,
        15840, 16104, 16368, 16632, 16896, 17160, 17424, 17688, 17952, 18216, 18480,
        18744, 19008, 19272, 19536, 19800, 20064, 20328, 20592, 20856, 21120, 21384,
        21648, 21912, 22176, 22440, 22704, 22968, 23232, 23496, 23760, 24024, 24288,
        24552, 24816, 25080, 25344, 25608, 25872, 26136, 26400, 26664, 26928, 27192,
        27456, 27720, 27984, 28248, 28512, 28776, 29040, 29304, 29568, 29832, 30096,
        30360, 30624, 30888, 31152, 31416, 31680, 31944, 32208, 32472, 32736],
      [32767, 33031, 33295, 33559, 33823, 34087, 34351, 34615, 34879, 35143,
        35407, 35671, 35935, 36199, 36463, 36727, 36991, 37255, 37519, 37783, 38047,
        38311, 38575, 38839, 39103, 39367, 39631, 39895, 40159, 40423, 40687, 40951,
        41215, 41479, 41743, 42007, 42271, 42535, 42799, 43063, 43327, 43591, 43855,
        44119, 44383, 44647, 44911, 45175, 45439, 45703, 45967, 46231, 46495, 46759,
        47023, 47287, 47551, 47815, 48079, 48343, 48607, 48871, 49135, 49399, 49663,
        49927, 50191, 50455, 50719, 50983, 51247, 51511, 51775, 52039, 52303, 52567,
        52831, 53095, 53359, 53623, 53887, 54151, 54415, 54679, 54943, 55207, 55471,
        55735, 55999, 56263, 56527, 56791, 57055, 57319, 57583, 57847, 58111, 58375,
        58639, 58903, 59167, 59431, 59695, 59959, 60223, 60487, 60751, 61015, 61279,
        61543, 61807, 62071, 62335, 62599, 62863, 63127, 63391, 63655, 63919, 64183,
        64447, 64711, 64975, 65239, 65503],
      [32767, 32503, 32239, 31975, 31711, 31447, 31183, 30919, 30655, 30391,
        30127, 29863, 29599, 29335, 29071, 28807, 28543, 28279, 28015, 27751, 27487,
        27223, 26959, 26695, 26431, 26167, 25903, 25639, 25375, 25111, 24847, 24583,
        24319, 24055, 23791, 23527, 23263, 22999, 22735, 22471, 22207, 21943, 21679,
        21415, 21151, 20887, 20623, 20359, 20095, 19831, 19567, 19303, 19039, 18775,
        18511, 18247, 17983, 17719, 17455, 17191, 16927, 16663, 16399, 16135, 15871,
        15607, 15343, 15079, 14815, 14551, 14287, 14023, 13759, 13495, 13231, 12967,
        12703, 12439, 12175, 11911, 11647, 11383, 11119, 10855, 10591, 10327, 10063,
        9799, 9535, 9271, 9007, 8743, 8479, 8215, 7951, 7687, 7423, 7159, 6895, 6631,
        6367, 6103, 5839, 5575, 5311, 5047, 4783, 4519, 4255, 3991, 3727, 3463, 3199,
        2935, 2671, 2407, 2143, 1879, 1615, 1351, 1087, 823, 559, 295, 31],
      [65535, 65271, 65007, 64743, 64479, 64215, 63951, 63687, 63423, 63159,
        62895, 62631, 62367, 62103, 61839, 61575, 61311, 61047, 60783, 60519, 60255,
        59991, 59727, 59463, 59199, 58935, 58671, 58407, 58143, 57879, 57615, 57351,
        57087, 56823, 56559, 56295, 56031, 55767, 55503, 55239, 54975, 54711, 54447,
        54183, 53919, 53655, 53391, 53127, 52863, 52599, 52335, 52071, 51807, 51543,
        51279, 51015, 50751, 50487, 50223, 49959, 49695, 49431, 49167, 48903, 48639,
        48375, 48111, 47847, 47583, 47319, 47055, 46791, 46527, 46263, 45999, 45735,
        45471, 45207, 44943, 44679, 44415, 44151, 43887, 43623, 43359, 43095, 42831,
        42567, 42303, 42039, 41775, 41511, 41247, 40983, 40719, 40455, 40191, 39927,
        39663, 39399, 39135, 38871, 38607, 38343, 38079, 37815, 37551, 37287, 37023,
        36759, 36495, 36231, 35967, 35703, 35439, 35175, 34911, 34647, 34383, 34119,
        33855, 33591, 33327, 33063, 32799]))
]

# Expected tuples for data in file 20061225_061225.optaa6.log
EXPECTED_20061225_061225_optaa6 = [
    ((3376015945.000), ('2006-12-25 06:12:25', 9, 83, 1193052)),
    ((3376015945.000), (1, 2, 3, 4, 5, 6, 7, 666, 1,
      [0],
      [32767],
      [32767],
      [65535])),
    ((3376015945.666), (2, 4, 6, 8, 10, 12, 14, 1332, 2,
      [0, 32767],
      [32767, 65534],
      [32767, 0],
      [65535, 32768])),
    ((3376015946.332), (3, 6, 9, 12, 15, 18, 21, 1998, 3,
      [0, 16383, 32766],
      [32767, 49150, 65533],
      [32767, 16384, 1],
      [65535, 49152, 32769])),
    ((3376015946.998), (4, 8, 12, 16, 20, 24, 28, 2664, 4,
      [0, 10922, 21844, 32766],
      [32767, 43689, 54611, 65533],
      [32767, 21845, 10923, 1],
      [65535, 54613, 43691, 32769])),
    ((3376015947.664), (5, 10, 15, 20, 25, 30, 35, 3330, 5,
      [0, 8191, 16382, 24573, 32764],
      [32767, 40958, 49149, 57340, 65531],
      [32767, 24576, 16385, 8194, 3],
      [65535, 57344, 49153, 40962, 32771])),
    ((3376015948.330), (6, 12, 18, 24, 30, 36, 42, 3996, 6,
      [0, 6553, 13106, 19659, 26212, 32765],
      [32767, 39320, 45873, 52426, 58979, 65532],
      [32767, 26214, 19661, 13108, 6555, 2],
      [65535, 58982, 52429, 45876, 39323, 32770])),
    ((3376015948.996), (7, 14, 21, 28, 35, 42, 49, 4662, 7,
      [0, 5461, 10922, 16383, 21844, 27305, 32766],
      [32767, 38228, 43689, 49150, 54611, 60072, 65533],
      [32767, 27306, 21845, 16384, 10923, 5462, 1],
      [65535, 60074, 54613, 49152, 43691, 38230, 32769])),
    ((3376015949.662), (8, 16, 24, 32, 40, 48, 56, 5328, 8,
      [0, 4681, 9362, 14043, 18724, 23405, 28086, 32767],
      [32767, 37448, 42129, 46810, 51491, 56172, 60853, 65534],
      [32767, 28086, 23405, 18724, 14043, 9362, 4681, 0],
      [65535, 60854, 56173, 51492, 46811, 42130, 37449, 32768])),
    ((3376015950.328), (9, 18, 27, 36, 45, 54, 63, 5994, 9,
      [0, 4095, 8190, 12285, 16380, 20475, 24570, 28665, 32760],
      [32767, 36862, 40957, 45052, 49147, 53242, 57337, 61432, 65527],
      [32767, 28672, 24577, 20482, 16387, 12292, 8197, 4102, 7],
      [65535, 61440, 57345, 53250, 49155, 45060, 40965, 36870, 32775])),
    ((3376015950.994), (10, 20, 30, 40, 50, 60, 70, 6660, 10,
      [0, 3640, 7280, 10920, 14560, 18200, 21840, 25480, 29120, 32760],
      [32767, 36407, 40047, 43687, 47327, 50967, 54607, 58247, 61887, 65527],
      [32767, 29127, 25487, 21847, 18207, 14567, 10927, 7287, 3647, 7],
      [65535, 61895, 58255, 54615, 50975, 47335, 43695, 40055, 36415, 32775]))
]

FILE1 = '20010314_010314.optaa1.log'
FILE2 = '20020704_020704.optaa2.log'
FILE3 = '20031031_031031.optaa3.log'
FILE4 = '20041220_041220.optaa4.log'
FILE5 = '20050401_050401.optaa5.log'
FILE6 = '20061225_061225.optaa6.log'
FILE_BAD_FILENAME = '20190401.optaa19.log'

EXPECTED_FILE1 = EXPECTED_20010314_010314_optaa1
EXPECTED_FILE2 = EXPECTED_20020704_020704_optaa2
EXPECTED_FILE3 = EXPECTED_20031031_031031_optaa3
EXPECTED_FILE6 = EXPECTED_20061225_061225_optaa6
RECORDS_FILE4 = 5       # 1 metadata, 4 instrument records
RECORDS_FILE6 = 11      # 1 metadata, 10 instrument records
EXCEPTIONS_FILE5 = 3    # number of exceptions expected


@attr('UNIT', group='mi')
class OptaaDjDclParserUnitTestCase(ParserUnitTestCase):
    """
    optaa_dj_dcl Parser unit test suite
    """
    def create_rec_parser(self, file_handle, filename, new_state=None):
        """
        This function creates a OptaaDjDcl parser for recovered data.
        """
        return OptaaDjDclRecoveredParser(self.rec_config,
            file_handle, new_state, self.rec_state_callback,
            self.rec_pub_callback, self.rec_exception_callback, filename)

    def create_tel_parser(self, file_handle, filename, new_state=None):
        """
        This function creates a OptaaDjDcl parser for telemetered data.
        """
        return OptaaDjDclTelemeteredParser(self.tel_config,
            file_handle, new_state, self.rec_state_callback,
            self.tel_pub_callback, self.tel_exception_callback, filename)

    def open_file(self, filename):
        return open(os.path.join(RESOURCE_PATH, filename), mode='r')

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

    def test_bad_filename(self):
        """
        This test verifies that a DatasetParserException occurs if the filename
        is bad.
        """
        log.debug('===== START TEST BAD FILENAME =====')
        in_file = self.open_file(FILE_BAD_FILENAME)

        with self.assertRaises(DatasetParserException):
            parser = self.create_rec_parser(in_file, FILE_BAD_FILENAME)

        with self.assertRaises(DatasetParserException):
            parser = self.create_tel_parser(in_file, FILE_BAD_FILENAME)

        log.debug('===== END TEST BAD FILENAME =====')

    def test_big_giant_input(self):
        """
        Read a large file and verify that all expected particles can be read.
        Verification is not done at this time, but will be done during
        integration and qualification testing.
        """
        log.debug('===== START TEST BIG GIANT INPUT RECOVERED =====')
        in_file = self.open_file(FILE6)
        parser = self.create_rec_parser(in_file, FILE6)

        # In a single read, get all particles in this file.
        number_expected_results = RECORDS_FILE6
        result = parser.get_records(number_expected_results)
        self.assertEqual(len(result), number_expected_results)

        in_file.close()
        self.assertEqual(self.rec_exception_callback_value, None)

        log.debug('===== START TEST BIG GIANT INPUT TELEMETERED =====')
        in_file = self.open_file(FILE4)
        parser = self.create_tel_parser(in_file, FILE4)

        # In a single read, get all particles in this file.
        number_expected_results = RECORDS_FILE4
        result = parser.get_records(number_expected_results)
        self.assertEqual(len(result), number_expected_results)

        in_file.close()
        self.assertEqual(self.tel_exception_callback_value, None)

        log.debug('===== END TEST BIG GIANT INPUT =====')

    def test_checksum_errors(self):
        """
        This test verifies that records containing checksum errors
        are detected and that particles are not generated.
        """
        log.debug('===== START TEST CHECKSUM ERRORS =====')
        in_file = self.open_file(FILE5)
        parser = self.create_rec_parser(in_file, FILE5)

        # Try to get a record and verify that none are produced.
        # Verify that the correct number of checksum errors are detected.
        result = parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.rec_exceptions_detected, EXCEPTIONS_FILE5)
        in_file.close()

        in_file = self.open_file(FILE5)
        parser = self.create_tel_parser(in_file, FILE5)

        # Try to get a record and verify that none are produced.
        # Verify that the correct number of checksum errors are detected.
        result = parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.rec_exceptions_detected, EXCEPTIONS_FILE5)
        in_file.close()

        log.debug('===== END TEST CHECKSUM ERRORS =====')
        
    def test_get_many(self):
        """
        Read a file and pull out multiple data particles at one time.
        Verify that the results are those we expected.
        """
        log.debug('===== START TEST GET MANY RECOVERED =====')
        in_file = self.open_file(FILE2)
        parser = self.create_rec_parser(in_file, FILE2)

        # Generate a list of expected result particles.
        expected_particle = []
        for count, expected in enumerate(EXPECTED_FILE2):
            ntp_time, fields = expected

            # Generate expected particle
            if count == 0:
                particle = OptaaDjDclRecoveredMetadataDataParticle(fields,
                    internal_timestamp=ntp_time)
            else:
                particle = OptaaDjDclRecoveredInstrumentDataParticle(fields,
                    internal_timestamp=ntp_time)
            expected_particle.append(particle)

        # In a single read, get all particles for this file.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)

        self.assertEqual(self.rec_exception_callback_value, None)
        in_file.close()

        log.debug('===== START TEST GET MANY TELEMETERED =====')
        in_file = self.open_file(FILE3)
        parser = self.create_tel_parser(in_file, FILE3)

        # Generate a list of expected result particles.
        expected_particle = []
        for count, expected in enumerate(EXPECTED_FILE3):
            ntp_time, fields = expected

            # Generate expected particle
            if count == 0:
                particle = OptaaDjDclTelemeteredMetadataDataParticle(fields,
                    internal_timestamp=ntp_time)
            else:
                particle = OptaaDjDclTelemeteredInstrumentDataParticle(fields,
                    internal_timestamp=ntp_time)
            expected_particle.append(particle)

        # In a single read, get all particles for this file.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)

        self.assertEqual(self.tel_exception_callback_value, None)
        in_file.close()

        log.debug('===== END TEST GET MANY =====')

    def test_invalid_state(self):
        """
        This test verifies an exception is raised when an invalid state
        is used to initialize the parser.
        """
        log.debug('===== START TEST INVALID STATE =====')
        in_file = self.open_file(FILE1)

        # TIME_SINCE_POWER_UP is missing
        initial_state = {
            OptaaStateKey.POSITION: 12,
            OptaaStateKey.METADATA_GENERATED: True
        }

        with self.assertRaises(DatasetParserException):
            parser = self.create_rec_parser(in_file, FILE1, new_state=initial_state)

        # POSITION is missing
        initial_state = {
            OptaaStateKey.TIME_SINCE_POWER_UP: 1.345,
            OptaaStateKey.METADATA_GENERATED: True
        }

        with self.assertRaises(DatasetParserException):
            parser = self.create_tel_parser(in_file, FILE1, new_state=initial_state)

        # METADATA_GENERATED is missing
        initial_state = {
            OptaaStateKey.TIME_SINCE_POWER_UP: 1.345,
            OptaaStateKey.POSITION: 12,
        }

        with self.assertRaises(DatasetParserException):
            parser = self.create_rec_parser(in_file, FILE1, new_state=initial_state)

        # Instead of a dictionary, pass a list of dictionaries.
        initial_state = [
            {OptaaStateKey.POSITION: 12},
            {OptaaStateKey.METADATA_GENERATED: True},
            {OptaaStateKey.TIME_SINCE_POWER_UP: 1.345}
        ]

        with self.assertRaises(DatasetParserException):
            parser = self.create_tel_parser(in_file, FILE1, new_state=initial_state)

        log.debug('===== END TEST INVALID STATE =====')
        
    def test_mid_state_start(self):
        """
        Test starting a parser with a state in the middle of processing.
        """
        log.debug('===== START TEST MID-STATE START RECOVERED =====')

        in_file = self.open_file(FILE2)
        
        # Start at the beginning of record 4 (of 5 total)
        initial_state = {
            OptaaStateKey.POSITION: 177,
            OptaaStateKey.METADATA_GENERATED: True,
            OptaaStateKey.TIME_SINCE_POWER_UP: 0.222
        }

        parser = self.create_rec_parser(in_file, FILE2, new_state=initial_state)
        
        # Generate a list of expected result particles.
        expected_particle = []
        for count, expected in enumerate(EXPECTED_FILE2):
            if count >= 4:
                ntp_time, fields = expected

                particle = OptaaDjDclRecoveredInstrumentDataParticle(fields,
                           internal_timestamp=ntp_time)

                expected_particle.append(particle)

        # Get record and verify.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)
        in_file.close()

        log.debug('===== START TEST MID-STATE START TELEMETERED =====')

        in_file = self.open_file(FILE1)

        # Start at the beginning of record 3 (of 3 total)
        initial_state = {
            OptaaStateKey.POSITION: 102,
            OptaaStateKey.METADATA_GENERATED: True,
            OptaaStateKey.TIME_SINCE_POWER_UP: 0.111
        }

        parser = self.create_rec_parser(in_file, FILE1, new_state=initial_state)

        # Generate a list of expected result particles.
        expected_particle = []
        for count, expected in enumerate(EXPECTED_FILE1):
            if count >= 3:
                ntp_time, fields = expected

                particle = OptaaDjDclTelemeteredInstrumentDataParticle(fields,
                           internal_timestamp=ntp_time)

                expected_particle.append(particle)

        # Get record and verify.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)
        in_file.close()
        
        log.debug('===== END TEST MID-STATE START  =====')
        
    def test_set_state(self):
        """
        This test verifies that the state can be changed after starting.
        Some particles are read and then the parser state is modified to
        skip ahead or back.
        """
        log.debug('===== START TEST SET STATE RECOVERED =====')

        in_file = self.open_file(FILE6)
        parser = self.create_rec_parser(in_file, FILE6)

        # Read and verify 4 particles (of the 11).
        # 1 metadata particle, 3 instrument particles.
        for count, expected in enumerate(EXPECTED_FILE6[ : 4]):
            ntp_time, fields = expected

            # Generate expected particle
            if count == 0:
                expected_particle = \
                    OptaaDjDclRecoveredMetadataDataParticle(fields,
                    internal_timestamp=ntp_time)

            else:
                expected_particle = \
                    OptaaDjDclRecoveredInstrumentDataParticle(fields,
                    internal_timestamp=ntp_time)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        # Skip ahead in the file so that we get the last 3 particles.
        new_state = {
            OptaaStateKey.POSITION: 469,
            OptaaStateKey.METADATA_GENERATED: True,
            OptaaStateKey.TIME_SINCE_POWER_UP: 0.666
        }

        # Set the state.
        parser.set_state(new_state)

        # Read and verify the last 3 particles.
        for count, expected in enumerate(EXPECTED_FILE6[-3: ]):
            ntp_time, fields = expected

            expected_particle = \
                OptaaDjDclRecoveredInstrumentDataParticle(fields,
                internal_timestamp=ntp_time)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        in_file.close()

        log.debug('===== START TEST SET STATE TELEMETERED =====')

        in_file = self.open_file(FILE6)
        parser = self.create_rec_parser(in_file, FILE6)

        # Read and verify 8 particles (of the 11).
        # 1 metadata particle, 7 instrument particles.
        for count, expected in enumerate(EXPECTED_FILE6[ : 8]):
            ntp_time, fields = expected

            # Generate expected particle
            if count == 0:
                expected_particle = \
                    OptaaDjDclTelemeteredMetadataDataParticle(fields,
                    internal_timestamp=ntp_time)

            else:
                expected_particle = \
                    OptaaDjDclTelemeteredInstrumentDataParticle(fields,
                    internal_timestamp=ntp_time)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        # Go back in the file so that we get the last 8 particles.
        new_state = {
            OptaaStateKey.POSITION: 94,
            OptaaStateKey.METADATA_GENERATED: True,
            OptaaStateKey.TIME_SINCE_POWER_UP: 0.666
        }

        # Set the state.
        parser.set_state(new_state)

        # Read and verify the last 8 particles.
        for count, expected in enumerate(EXPECTED_FILE6[-8: ]):
            ntp_time, fields = expected

            expected_particle = \
                OptaaDjDclTelemeteredInstrumentDataParticle(fields,
                internal_timestamp=ntp_time)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        in_file.close()
        log.debug('===== END TEST SET STATE =====')
        
    def test_simple(self):
        """
        Read data from a file and pull out data particles
        one at a time. Verify that the results are those we expected.
        """
        log.debug('===== START TEST SIMPLE RECOVERED =====')
        in_file = self.open_file(FILE1)
        parser = self.create_rec_parser(in_file, FILE1)

        for count, expected in enumerate(EXPECTED_FILE1):
            ntp_time, fields = expected

            # Generate expected particle
            if count == 0:
                expected_particle = \
                    OptaaDjDclRecoveredMetadataDataParticle(fields,
                    internal_timestamp=ntp_time)

            else:
                expected_particle = \
                    OptaaDjDclRecoveredInstrumentDataParticle(fields,
                    internal_timestamp=ntp_time)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        self.assertEqual(self.rec_exception_callback_value, None)
        in_file.close()

        log.debug('===== START TEST SIMPLE TELEMETERED =====')
        in_file = self.open_file(FILE2)
        parser = self.create_tel_parser(in_file, FILE2)

        for count, expected in enumerate(EXPECTED_FILE2):
            ntp_time, fields = expected

            # Generate expected particle
            if count == 0:
                expected_particle = \
                    OptaaDjDclTelemeteredMetadataDataParticle(fields,
                    internal_timestamp=ntp_time)
            else:
                expected_particle = \
                    OptaaDjDclTelemeteredInstrumentDataParticle(fields,
                    internal_timestamp=ntp_time)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        self.assertEqual(self.tel_exception_callback_value, None)
        in_file.close()

        log.debug('===== END TEST SIMPLE =====')
