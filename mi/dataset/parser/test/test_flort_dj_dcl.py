#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_flort_dj_dcl
@file marine-integrations/mi/dataset/parser/test/test_flort_dj_dcl.py
@author Steve Myerson
@brief Test code for a flort_dj_dcl data parser

In the following files, Metadata consists of 4 records.
There is 1 group of Sensor Data records for each set of metadata.

Files used for testing:

20010101.flort1.log
  Metadata - 1 set,  Sensor Data - 0 records

20020215.flort2.log
  Metadata - 2 sets,  Sensor Data - 15 records

20030413.flort3.log
  Metadata - 4 sets,  Sensor Data - 13 records

20040505.flort4.log
  Metadata - 5 sets,  Sensor Data - 5 records

20050406.flort5.log
  Metadata - 4 sets,  Sensor Data - 6 records

20061220.flort6.log
  Metadata - 1 set,  Sensor Data - 300 records

20071225.flort7.log
  Metadata - 2 sets,  Sensor Data - 200 records

20080401.flort8.log
  This file contains a boatload of invalid sensor data records.
  See metadata in file for a list of the errors.
  20 metadata records, 47 sensor data records
"""

import unittest
import os
from nose.plugins.attrib import attr

from mi.core.log import get_logger; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

from mi.dataset.parser.flort_dj_dcl import \
    FlortDjDclRecoveredParser, \
    FlortDjDclTelemeteredParser, \
    FlortDjDclRecoveredInstrumentDataParticle, \
    FlortDjDclTelemeteredInstrumentDataParticle, \
    FlortStateKey

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver',
                             'flort_dj', 'dcl', 'resource')

MODULE_NAME = 'mi.dataset.parser.flort_dj_dcl'


# Expected tuples for data in file 20020215.flort2.log
EXPECTED_20020215_flort2 = [
    ('2002/02/15 05:07:17.089', '2002', '02', '15', '05', '07', '17',
    '02/15/01', '17:07:17', '0', '1', '2', '3', '4', '5', '6'),
    ('2002/02/15 05:07:19.447', '2002', '02', '15', '05', '07', '19',
    '02/15/01', '17:07:19', '2259', '2260', '2261', '2262', '2263', '2264', '2265'),
    ('2002/02/15 05:07:21.805', '2002', '02', '15', '05', '07', '21',
    '02/15/01', '17:07:21', '4518', '4519', '4520', '4521', '4522', '4523', '4524'),
    ('2002/02/15 05:07:24.163', '2002', '02', '15', '05', '07', '24',
    '02/15/01', '17:07:24', '6777', '6778', '6779', '6780', '6781', '6782', '6783'),
    ('2002/02/15 05:07:26.521', '2002', '02', '15', '05', '07', '26',
    '02/15/01', '17:07:26', '9036', '9037', '9038', '9039', '9040', '9041', '9042'),
    ('2002/02/15 05:07:28.879', '2002', '02', '15', '05', '07', '28',
    '02/15/01', '17:07:28', '11295', '11296', '11297', '11298', '11299', '11300', '11301'),
    ('2002/02/15 05:07:31.237', '2002', '02', '15', '05', '07', '31',
    '02/15/01', '17:07:31', '13554', '13555', '13556', '13557', '13558', '13559', '13560'),
    ('2002/02/15 05:07:33.595', '2002', '02', '15', '05', '07', '33',
    '02/15/01', '17:07:33', '15813', '15814', '15815', '15816', '15817', '15818', '15819'),
    ('2002/02/15 05:07:35.953', '2002', '02', '15', '05', '07', '35',
    '02/15/01', '17:07:35', '18072', '18073', '18074', '18075', '18076', '18077', '18078'),
    ('2002/02/15 05:07:38.311', '2002', '02', '15', '05', '07', '38',
    '02/15/01', '17:07:38', '20331', '20332', '20333', '20334', '20335', '20336', '20337'),
    ('2002/02/15 05:07:40.669', '2002', '02', '15', '05', '07', '40',
    '02/15/01', '17:07:40', '22590', '22591', '22592', '22593', '22594', '22595', '22596'),
    ('2002/02/15 05:07:43.027', '2002', '02', '15', '05', '07', '43',
    '02/15/01', '17:07:43', '24849', '24850', '24851', '24852', '24853', '24854', '24855'),
    ('2002/02/15 05:07:45.385', '2002', '02', '15', '05', '07', '45',
    '02/15/01', '17:07:45', '27108', '27109', '27110', '27111', '27112', '27113', '27114'),
    ('2002/02/15 05:07:47.743', '2002', '02', '15', '05', '07', '47',
    '02/15/01', '17:07:47', '29367', '29368', '29369', '29370', '29371', '29372', '29373'),
    ('2002/02/15 05:07:50.101', '2002', '02', '15', '05', '07', '50',
    '02/15/01', '17:07:50', '31626', '31627', '31628', '31629', '31630', '31631', '31632'),
    ('2002/02/15 05:07:59.533', '2002', '02', '15', '05', '07', '59',
    '02/15/01', '17:07:59', '33885', '33886', '33887', '33888', '33889', '33890', '33891'),
    ('2002/02/15 05:08:01.891', '2002', '02', '15', '05', '08', '01',
    '02/15/01', '17:08:01', '36144', '36145', '36146', '36147', '36148', '36149', '36150'),
    ('2002/02/15 05:08:04.249', '2002', '02', '15', '05', '08', '04',
    '02/15/01', '17:08:04', '38403', '38404', '38405', '38406', '38407', '38408', '38409'),
    ('2002/02/15 05:08:06.607', '2002', '02', '15', '05', '08', '06',
    '02/15/01', '17:08:06', '40662', '40663', '40664', '40665', '40666', '40667', '40668'),
    ('2002/02/15 05:08:08.965', '2002', '02', '15', '05', '08', '08',
    '02/15/01', '17:08:08', '42921', '42922', '42923', '42924', '42925', '42926', '42927'),
    ('2002/02/15 05:08:11.323', '2002', '02', '15', '05', '08', '11',
    '02/15/01', '17:08:11', '45180', '45181', '45182', '45183', '45184', '45185', '45186'),
    ('2002/02/15 05:08:13.681', '2002', '02', '15', '05', '08', '13',
    '02/15/01', '17:08:13', '47439', '47440', '47441', '47442', '47443', '47444', '47445'),
    ('2002/02/15 05:08:16.039', '2002', '02', '15', '05', '08', '16',
    '02/15/01', '17:08:16', '49698', '49699', '49700', '49701', '49702', '49703', '49704'),
    ('2002/02/15 05:08:18.397', '2002', '02', '15', '05', '08', '18',
    '02/15/01', '17:08:18', '51957', '51958', '51959', '51960', '51961', '51962', '51963'),
    ('2002/02/15 05:08:20.755', '2002', '02', '15', '05', '08', '20',
    '02/15/01', '17:08:20', '54216', '54217', '54218', '54219', '54220', '54221', '54222'),
    ('2002/02/15 05:08:23.113', '2002', '02', '15', '05', '08', '23',
    '02/15/01', '17:08:23', '56475', '56476', '56477', '56478', '56479', '56480', '56481'),
    ('2002/02/15 05:08:25.471', '2002', '02', '15', '05', '08', '25',
    '02/15/01', '17:08:25', '58734', '58735', '58736', '58737', '58738', '58739', '58740'),
    ('2002/02/15 05:08:27.829', '2002', '02', '15', '05', '08', '27',
    '02/15/01', '17:08:27', '60993', '60994', '60995', '60996', '60997', '60998', '60999'),
    ('2002/02/15 05:08:30.187', '2002', '02', '15', '05', '08', '30',
    '02/15/01', '17:08:30', '63252', '63253', '63254', '63255', '63256', '63257', '63258'),
    ('2002/02/15 05:08:32.545', '2002', '02', '15', '05', '08', '32',
    '02/15/01', '17:08:32', '65511', '65512', '65513', '65514', '65515', '65516', '65517')
]

# Expected tuples for data in file 20030413.flort3.log
EXPECTED_20030413_flort3 = [
    ('2003/04/13 07:09:19.091', '2003', '04', '13', '07', '09', '19',
    '04/13/02', '19:09:19', '0', '1', '2', '3', '4', '5', '6'),
    ('2003/04/13 07:09:21.449', '2003', '04', '13', '07', '09', '21',
    '04/13/02', '19:09:21', '1284', '1285', '1286', '1287', '1288', '1289', '1290'),
    ('2003/04/13 07:09:23.807', '2003', '04', '13', '07', '09', '23',
    '04/13/02', '19:09:23', '2568', '2569', '2570', '2571', '2572', '2573', '2574'),
    ('2003/04/13 07:09:26.165', '2003', '04', '13', '07', '09', '26',
    '04/13/02', '19:09:26', '3852', '3853', '3854', '3855', '3856', '3857', '3858'),
    ('2003/04/13 07:09:28.523', '2003', '04', '13', '07', '09', '28',
    '04/13/02', '19:09:28', '5136', '5137', '5138', '5139', '5140', '5141', '5142'),
    ('2003/04/13 07:09:30.881', '2003', '04', '13', '07', '09', '30',
    '04/13/02', '19:09:30', '6420', '6421', '6422', '6423', '6424', '6425', '6426'),
    ('2003/04/13 07:09:33.239', '2003', '04', '13', '07', '09', '33',
    '04/13/02', '19:09:33', '7704', '7705', '7706', '7707', '7708', '7709', '7710'),
    ('2003/04/13 07:09:35.597', '2003', '04', '13', '07', '09', '35',
    '04/13/02', '19:09:35', '8988', '8989', '8990', '8991', '8992', '8993', '8994'),
    ('2003/04/13 07:09:37.955', '2003', '04', '13', '07', '09', '37',
    '04/13/02', '19:09:37', '10272', '10273', '10274', '10275', '10276', '10277', '10278'),
    ('2003/04/13 07:09:40.313', '2003', '04', '13', '07', '09', '40',
    '04/13/02', '19:09:40', '11556', '11557', '11558', '11559', '11560', '11561', '11562'),
    ('2003/04/13 07:09:42.671', '2003', '04', '13', '07', '09', '42',
    '04/13/02', '19:09:42', '12840', '12841', '12842', '12843', '12844', '12845', '12846'),
    ('2003/04/13 07:09:45.029', '2003', '04', '13', '07', '09', '45',
    '04/13/02', '19:09:45', '14124', '14125', '14126', '14127', '14128', '14129', '14130'),
    ('2003/04/13 07:09:47.387', '2003', '04', '13', '07', '09', '47',
    '04/13/02', '19:09:47', '15408', '15409', '15410', '15411', '15412', '15413', '15414'),
    ('2003/04/13 07:09:56.819', '2003', '04', '13', '07', '09', '56',
    '04/13/02', '19:09:56', '16692', '16693', '16694', '16695', '16696', '16697', '16698'),
    ('2003/04/13 07:09:59.177', '2003', '04', '13', '07', '09', '59',
    '04/13/02', '19:09:59', '17976', '17977', '17978', '17979', '17980', '17981', '17982'),
    ('2003/04/13 07:10:01.535', '2003', '04', '13', '07', '10', '01',
    '04/13/02', '19:10:01', '19260', '19261', '19262', '19263', '19264', '19265', '19266'),
    ('2003/04/13 07:10:03.893', '2003', '04', '13', '07', '10', '03',
    '04/13/02', '19:10:03', '20544', '20545', '20546', '20547', '20548', '20549', '20550'),
    ('2003/04/13 07:10:06.251', '2003', '04', '13', '07', '10', '06',
    '04/13/02', '19:10:06', '21828', '21829', '21830', '21831', '21832', '21833', '21834'),
    ('2003/04/13 07:10:08.609', '2003', '04', '13', '07', '10', '08',
    '04/13/02', '19:10:08', '23112', '23113', '23114', '23115', '23116', '23117', '23118'),
    ('2003/04/13 07:10:10.967', '2003', '04', '13', '07', '10', '10',
    '04/13/02', '19:10:10', '24396', '24397', '24398', '24399', '24400', '24401', '24402'),
    ('2003/04/13 07:10:13.325', '2003', '04', '13', '07', '10', '13',
    '04/13/02', '19:10:13', '25680', '25681', '25682', '25683', '25684', '25685', '25686'),
    ('2003/04/13 07:10:15.683', '2003', '04', '13', '07', '10', '15',
    '04/13/02', '19:10:15', '26964', '26965', '26966', '26967', '26968', '26969', '26970'),
    ('2003/04/13 07:10:18.041', '2003', '04', '13', '07', '10', '18',
    '04/13/02', '19:10:18', '28248', '28249', '28250', '28251', '28252', '28253', '28254'),
    ('2003/04/13 07:10:20.399', '2003', '04', '13', '07', '10', '20',
    '04/13/02', '19:10:20', '29532', '29533', '29534', '29535', '29536', '29537', '29538'),
    ('2003/04/13 07:10:22.757', '2003', '04', '13', '07', '10', '22',
    '04/13/02', '19:10:22', '30816', '30817', '30818', '30819', '30820', '30821', '30822'),
    ('2003/04/13 07:10:25.115', '2003', '04', '13', '07', '10', '25',
    '04/13/02', '19:10:25', '32100', '32101', '32102', '32103', '32104', '32105', '32106'),
    ('2003/04/13 07:10:34.547', '2003', '04', '13', '07', '10', '34',
    '04/13/02', '19:10:34', '33384', '33385', '33386', '33387', '33388', '33389', '33390'),
    ('2003/04/13 07:10:36.905', '2003', '04', '13', '07', '10', '36',
    '04/13/02', '19:10:36', '34668', '34669', '34670', '34671', '34672', '34673', '34674'),
    ('2003/04/13 07:10:39.263', '2003', '04', '13', '07', '10', '39',
    '04/13/02', '19:10:39', '35952', '35953', '35954', '35955', '35956', '35957', '35958'),
    ('2003/04/13 07:10:41.621', '2003', '04', '13', '07', '10', '41',
    '04/13/02', '19:10:41', '37236', '37237', '37238', '37239', '37240', '37241', '37242'),
    ('2003/04/13 07:10:43.979', '2003', '04', '13', '07', '10', '43',
    '04/13/02', '19:10:43', '38520', '38521', '38522', '38523', '38524', '38525', '38526'),
    ('2003/04/13 07:10:46.337', '2003', '04', '13', '07', '10', '46',
    '04/13/02', '19:10:46', '39804', '39805', '39806', '39807', '39808', '39809', '39810'),
    ('2003/04/13 07:10:48.695', '2003', '04', '13', '07', '10', '48',
    '04/13/02', '19:10:48', '41088', '41089', '41090', '41091', '41092', '41093', '41094'),
    ('2003/04/13 07:10:51.053', '2003', '04', '13', '07', '10', '51',
    '04/13/02', '19:10:51', '42372', '42373', '42374', '42375', '42376', '42377', '42378'),
    ('2003/04/13 07:10:53.411', '2003', '04', '13', '07', '10', '53',
    '04/13/02', '19:10:53', '43656', '43657', '43658', '43659', '43660', '43661', '43662'),
    ('2003/04/13 07:10:55.769', '2003', '04', '13', '07', '10', '55',
    '04/13/02', '19:10:55', '44940', '44941', '44942', '44943', '44944', '44945', '44946'),
    ('2003/04/13 07:10:58.127', '2003', '04', '13', '07', '10', '58',
    '04/13/02', '19:10:58', '46224', '46225', '46226', '46227', '46228', '46229', '46230'),
    ('2003/04/13 07:11:00.485', '2003', '04', '13', '07', '11', '00',
    '04/13/02', '19:11:00', '47508', '47509', '47510', '47511', '47512', '47513', '47514'),
    ('2003/04/13 07:11:02.843', '2003', '04', '13', '07', '11', '02',
    '04/13/02', '19:11:02', '48792', '48793', '48794', '48795', '48796', '48797', '48798'),
    ('2003/04/13 07:11:12.275', '2003', '04', '13', '07', '11', '12',
    '04/13/02', '19:11:12', '50076', '50077', '50078', '50079', '50080', '50081', '50082'),
    ('2003/04/13 07:11:14.633', '2003', '04', '13', '07', '11', '14',
    '04/13/02', '19:11:14', '51360', '51361', '51362', '51363', '51364', '51365', '51366'),
    ('2003/04/13 07:11:16.991', '2003', '04', '13', '07', '11', '16',
    '04/13/02', '19:11:16', '52644', '52645', '52646', '52647', '52648', '52649', '52650'),
    ('2003/04/13 07:11:19.349', '2003', '04', '13', '07', '11', '19',
    '04/13/02', '19:11:19', '53928', '53929', '53930', '53931', '53932', '53933', '53934'),
    ('2003/04/13 07:11:21.707', '2003', '04', '13', '07', '11', '21',
    '04/13/02', '19:11:21', '55212', '55213', '55214', '55215', '55216', '55217', '55218'),
    ('2003/04/13 07:11:24.065', '2003', '04', '13', '07', '11', '24',
    '04/13/02', '19:11:24', '56496', '56497', '56498', '56499', '56500', '56501', '56502'),
    ('2003/04/13 07:11:26.423', '2003', '04', '13', '07', '11', '26',
    '04/13/02', '19:11:26', '57780', '57781', '57782', '57783', '57784', '57785', '57786'),
    ('2003/04/13 07:11:28.781', '2003', '04', '13', '07', '11', '28',
    '04/13/02', '19:11:28', '59064', '59065', '59066', '59067', '59068', '59069', '59070'),
    ('2003/04/13 07:11:31.139', '2003', '04', '13', '07', '11', '31',
    '04/13/02', '19:11:31', '60348', '60349', '60350', '60351', '60352', '60353', '60354'),
    ('2003/04/13 07:11:33.497', '2003', '04', '13', '07', '11', '33',
    '04/13/02', '19:11:33', '61632', '61633', '61634', '61635', '61636', '61637', '61638'),
    ('2003/04/13 07:11:35.855', '2003', '04', '13', '07', '11', '35',
    '04/13/02', '19:11:35', '62916', '62917', '62918', '62919', '62920', '62921', '62922'),
    ('2003/04/13 07:11:38.213', '2003', '04', '13', '07', '11', '38',
    '04/13/02', '19:11:38', '64200', '64201', '64202', '64203', '64204', '64205', '64206'),
    ('2003/04/13 07:11:40.571', '2003', '04', '13', '07', '11', '40',
    '04/13/02', '19:11:40', '65484', '65485', '65486', '65487', '65488', '65489', '65490')
]

# Expected tuples for data in file 20040505.flort4.log
EXPECTED_20040505_flort4 = [
    ('2004/05/05 09:11:21.093', '2004', '05', '05', '09', '11', '21',
    '05/05/03', '21:11:21', '0', '1', '2', '3', '4', '5', '6'),
    ('2004/05/05 09:11:23.451', '2004', '05', '05', '09', '11', '23',
    '05/05/03', '21:11:23', '2730', '2731', '2732', '2733', '2734', '2735', '2736'),
    ('2004/05/05 09:11:25.809', '2004', '05', '05', '09', '11', '25',
    '05/05/03', '21:11:25', '5460', '5461', '5462', '5463', '5464', '5465', '5466'),
    ('2004/05/05 09:11:28.167', '2004', '05', '05', '09', '11', '28',
    '05/05/03', '21:11:28', '8190', '8191', '8192', '8193', '8194', '8195', '8196'),
    ('2004/05/05 09:11:30.525', '2004', '05', '05', '09', '11', '30',
    '05/05/03', '21:11:30', '10920', '10921', '10922', '10923', '10924', '10925', '10926'),
    ('2004/05/05 09:11:39.957', '2004', '05', '05', '09', '11', '39',
    '05/05/03', '21:11:39', '13650', '13651', '13652', '13653', '13654', '13655', '13656'),
    ('2004/05/05 09:11:42.315', '2004', '05', '05', '09', '11', '42',
    '05/05/03', '21:11:42', '16380', '16381', '16382', '16383', '16384', '16385', '16386'),
    ('2004/05/05 09:11:44.673', '2004', '05', '05', '09', '11', '44',
    '05/05/03', '21:11:44', '19110', '19111', '19112', '19113', '19114', '19115', '19116'),
    ('2004/05/05 09:11:47.031', '2004', '05', '05', '09', '11', '47',
    '05/05/03', '21:11:47', '21840', '21841', '21842', '21843', '21844', '21845', '21846'),
    ('2004/05/05 09:11:49.389', '2004', '05', '05', '09', '11', '49',
    '05/05/03', '21:11:49', '24570', '24571', '24572', '24573', '24574', '24575', '24576'),
    ('2004/05/05 09:11:58.821', '2004', '05', '05', '09', '11', '58',
    '05/05/03', '21:11:58', '27300', '27301', '27302', '27303', '27304', '27305', '27306'),
    ('2004/05/05 09:12:01.179', '2004', '05', '05', '09', '12', '01',
    '05/05/03', '21:12:01', '30030', '30031', '30032', '30033', '30034', '30035', '30036'),
    ('2004/05/05 09:12:03.537', '2004', '05', '05', '09', '12', '03',
    '05/05/03', '21:12:03', '32760', '32761', '32762', '32763', '32764', '32765', '32766'),
    ('2004/05/05 09:12:05.895', '2004', '05', '05', '09', '12', '05',
    '05/05/03', '21:12:05', '35490', '35491', '35492', '35493', '35494', '35495', '35496'),
    ('2004/05/05 09:12:08.253', '2004', '05', '05', '09', '12', '08',
    '05/05/03', '21:12:08', '38220', '38221', '38222', '38223', '38224', '38225', '38226'),
    ('2004/05/05 09:12:17.685', '2004', '05', '05', '09', '12', '17',
    '05/05/03', '21:12:17', '40950', '40951', '40952', '40953', '40954', '40955', '40956'),
    ('2004/05/05 09:12:20.043', '2004', '05', '05', '09', '12', '20',
    '05/05/03', '21:12:20', '43680', '43681', '43682', '43683', '43684', '43685', '43686'),
    ('2004/05/05 09:12:22.401', '2004', '05', '05', '09', '12', '22',
    '05/05/03', '21:12:22', '46410', '46411', '46412', '46413', '46414', '46415', '46416'),
    ('2004/05/05 09:12:24.759', '2004', '05', '05', '09', '12', '24',
    '05/05/03', '21:12:24', '49140', '49141', '49142', '49143', '49144', '49145', '49146'),
    ('2004/05/05 09:12:27.117', '2004', '05', '05', '09', '12', '27',
    '05/05/03', '21:12:27', '51870', '51871', '51872', '51873', '51874', '51875', '51876'),
    ('2004/05/05 09:12:36.549', '2004', '05', '05', '09', '12', '36',
    '05/05/03', '21:12:36', '54600', '54601', '54602', '54603', '54604', '54605', '54606'),
    ('2004/05/05 09:12:38.907', '2004', '05', '05', '09', '12', '38',
    '05/05/03', '21:12:38', '57330', '57331', '57332', '57333', '57334', '57335', '57336'),
    ('2004/05/05 09:12:41.265', '2004', '05', '05', '09', '12', '41',
    '05/05/03', '21:12:41', '60060', '60061', '60062', '60063', '60064', '60065', '60066'),
    ('2004/05/05 09:12:43.623', '2004', '05', '05', '09', '12', '43',
    '05/05/03', '21:12:43', '62790', '62791', '62792', '62793', '62794', '62795', '62796'),
    ('2004/05/05 09:12:45.981', '2004', '05', '05', '09', '12', '45',
    '05/05/03', '21:12:45', '65520', '65521', '65522', '65523', '65524', '65525', '65526')
]

# Expected tuples for data in file 20050406.flort5.log
EXPECTED_20050406_flort5 = [
    ('2005/04/06 11:13:23.095', '2005', '04', '06', '11', '13', '23',
    '04/06/04', '23:13:23', '0', '1', '2', '3', '4', '5', '6'),
    ('2005/04/06 11:13:25.453', '2005', '04', '06', '11', '13', '25',
    '04/06/04', '23:13:25', '2849', '2850', '2851', '2852', '2853', '2854', '2855'),
    ('2005/04/06 11:13:27.811', '2005', '04', '06', '11', '13', '27',
    '04/06/04', '23:13:27', '5698', '5699', '5700', '5701', '5702', '5703', '5704'),
    ('2005/04/06 11:13:30.169', '2005', '04', '06', '11', '13', '30',
    '04/06/04', '23:13:30', '8547', '8548', '8549', '8550', '8551', '8552', '8553'),
    ('2005/04/06 11:13:32.527', '2005', '04', '06', '11', '13', '32',
    '04/06/04', '23:13:32', '11396', '11397', '11398', '11399', '11400', '11401', '11402'),
    ('2005/04/06 11:13:34.885', '2005', '04', '06', '11', '13', '34',
    '04/06/04', '23:13:34', '14245', '14246', '14247', '14248', '14249', '14250', '14251'),
    ('2005/04/06 11:13:44.317', '2005', '04', '06', '11', '13', '44',
    '04/06/04', '23:13:44', '17094', '17095', '17096', '17097', '17098', '17099', '17100'),
    ('2005/04/06 11:13:46.675', '2005', '04', '06', '11', '13', '46',
    '04/06/04', '23:13:46', '19943', '19944', '19945', '19946', '19947', '19948', '19949'),
    ('2005/04/06 11:13:49.033', '2005', '04', '06', '11', '13', '49',
    '04/06/04', '23:13:49', '22792', '22793', '22794', '22795', '22796', '22797', '22798'),
    ('2005/04/06 11:13:51.391', '2005', '04', '06', '11', '13', '51',
    '04/06/04', '23:13:51', '25641', '25642', '25643', '25644', '25645', '25646', '25647'),
    ('2005/04/06 11:13:53.749', '2005', '04', '06', '11', '13', '53',
    '04/06/04', '23:13:53', '28490', '28491', '28492', '28493', '28494', '28495', '28496'),
    ('2005/04/06 11:13:56.107', '2005', '04', '06', '11', '13', '56',
    '04/06/04', '23:13:56', '31339', '31340', '31341', '31342', '31343', '31344', '31345'),
    ('2005/04/06 11:14:05.539', '2005', '04', '06', '11', '14', '05',
    '04/06/04', '23:14:05', '34188', '34189', '34190', '34191', '34192', '34193', '34194'),
    ('2005/04/06 11:14:07.897', '2005', '04', '06', '11', '14', '07',
    '04/06/04', '23:14:07', '37037', '37038', '37039', '37040', '37041', '37042', '37043'),
    ('2005/04/06 11:14:10.255', '2005', '04', '06', '11', '14', '10',
    '04/06/04', '23:14:10', '39886', '39887', '39888', '39889', '39890', '39891', '39892'),
    ('2005/04/06 11:14:12.613', '2005', '04', '06', '11', '14', '12',
    '04/06/04', '23:14:12', '42735', '42736', '42737', '42738', '42739', '42740', '42741'),
    ('2005/04/06 11:14:14.971', '2005', '04', '06', '11', '14', '14',
    '04/06/04', '23:14:14', '45584', '45585', '45586', '45587', '45588', '45589', '45590'),
    ('2005/04/06 11:14:17.329', '2005', '04', '06', '11', '14', '17',
    '04/06/04', '23:14:17', '48433', '48434', '48435', '48436', '48437', '48438', '48439'),
    ('2005/04/06 11:14:26.761', '2005', '04', '06', '11', '14', '26',
    '04/06/04', '23:14:26', '51282', '51283', '51284', '51285', '51286', '51287', '51288'),
    ('2005/04/06 11:14:29.119', '2005', '04', '06', '11', '14', '29',
    '04/06/04', '23:14:29', '54131', '54132', '54133', '54134', '54135', '54136', '54137'),
    ('2005/04/06 11:14:31.477', '2005', '04', '06', '11', '14', '31',
    '04/06/04', '23:14:31', '56980', '56981', '56982', '56983', '56984', '56985', '56986'),
    ('2005/04/06 11:14:33.835', '2005', '04', '06', '11', '14', '33',
    '04/06/04', '23:14:33', '59829', '59830', '59831', '59832', '59833', '59834', '59835'),
    ('2005/04/06 11:14:36.193', '2005', '04', '06', '11', '14', '36',
    '04/06/04', '23:14:36', '62678', '62679', '62680', '62681', '62682', '62683', '62684'),
    ('2005/04/06 11:14:38.551', '2005', '04', '06', '11', '14', '38',
    '04/06/04', '23:14:38', '65527', '65528', '65529', '65530', '65531', '65532', '65533'),
]

FILE1 = '20010101.flort1.log'
FILE2 = '20020215.flort2.log'
FILE3 = '20030413.flort3.log'
FILE4 = '20040505.flort4.log'
FILE5 = '20050406.flort5.log'
FILE6 = '20061220.flort6.log'
FILE7 = '20071225.flort7.log'
FILE8 = '20080401.flort8.log'

EXPECTED_FILE2 = EXPECTED_20020215_flort2
EXPECTED_FILE3 = EXPECTED_20030413_flort3
EXPECTED_FILE4 = EXPECTED_20040505_flort4
EXPECTED_FILE5 = EXPECTED_20050406_flort5
RECORDS_FILE6 = 300      # number of records expected
RECORDS_FILE7 = 400      # number of records expected
EXCEPTIONS_FILE8 = 47    # number of exceptions expected


@attr('UNIT', group='mi')
class FlortDjDclParserUnitTestCase(ParserUnitTestCase):
    """
    flort_dj_dcl Parser unit test suite
    """
    def create_rec_parser(self, file_handle, new_state=None):
        """
        This function creates a FlortDjDcl parser for recovered data.
        """
        parser = FlortDjDclRecoveredParser(self.rec_config,
            file_handle, new_state, self.rec_state_callback,
            self.rec_pub_callback, self.rec_exception_callback)
        return parser

    def create_tel_parser(self, file_handle, new_state=None):
        """
        This function creates a FlortDjDcl parser for telemetered data.
        """
        parser = FlortDjDclTelemeteredParser(self.tel_config,
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
        number_expected_results = RECORDS_FILE6
        result = parser.get_records(number_expected_results)
        self.assertEqual(len(result), number_expected_results)

        in_file.close()
        self.assertEqual(self.rec_exception_callback_value, None)

        log.debug('===== START TEST BIG GIANT INPUT TELEMETERED =====')
        in_file = self.open_file(FILE7)
        parser = self.create_tel_parser(in_file)

        # In a single read, get all particles in this file.
        number_expected_results = RECORDS_FILE7
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
            particle = FlortDjDclRecoveredInstrumentDataParticle(expected)
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
            particle = FlortDjDclTelemeteredInstrumentDataParticle(expected)
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
        Verify that no instrument particles are produced
        and the correct number of exceptions are detected.
        """
        log.debug('===== START TEST INVALID SENSOR DATA RECOVERED =====')
        in_file = self.open_file(FILE8)
        parser = self.create_rec_parser(in_file)

        # Try to get records and verify that none are returned.
        result = parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.rec_exceptions_detected, EXCEPTIONS_FILE8)

        in_file.close()

        log.debug('===== START TEST INVALID SENSOR DATA TELEMETERED =====')
        in_file = self.open_file(FILE8)
        parser = self.create_tel_parser(in_file)

        # Try to get records and verify that none are returned.
        result = parser.get_records(1)
        self.assertEqual(result, [])
        self.assertEqual(self.tel_exceptions_detected, EXCEPTIONS_FILE8)

        in_file.close()

        log.debug('===== END TEST INVALID SENSOR DATA =====')
        
    def test_mid_state_start(self):
        """
        Test starting a parser with a state in the middle of processing.
        """
        log.debug('===== START TEST MID-STATE START RECOVERED =====')

        in_file = self.open_file(FILE3)

        # Start at the beginning of record 27 (of 52 total)
        initial_state = {
            FlortStateKey.POSITION: 2579
        }

        parser = self.create_rec_parser(in_file, new_state=initial_state)

        # Generate a list of expected result particles.
        expected_particle = []
        for expected in EXPECTED_FILE3[-26: ]:
            particle = FlortDjDclRecoveredInstrumentDataParticle(expected)
            expected_particle.append(particle)

        # In a single read, get all particles for this file.
        result = parser.get_records(len(expected_particle))
        self.assertEqual(result, expected_particle)

        self.assertEqual(self.rec_exception_callback_value, None)
        in_file.close()
        
        log.debug('===== START TEST MID-STATE START TELEMETERED =====')

        in_file = self.open_file(FILE2)

        # Start at the beginning of record 11 (of 30 total).
        initial_state = {
            FlortStateKey.POSITION: 1017
        }

        parser = self.create_tel_parser(in_file, new_state=initial_state)

        # Generate a list of expected result particles.
        expected_particle = []
        for expected in EXPECTED_FILE2[-20: ]:
            particle = FlortDjDclTelemeteredInstrumentDataParticle(expected)
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

        log.debug('===== END TEST NO SENSOR DATA =====')
        
    def test_set_state(self):
        """
        This test verifies that the state can be changed after starting.
        Some particles are read and then the parser state is modified to
        skip ahead or back.
        """
        log.debug('===== START TEST SET STATE RECOVERED =====')

        in_file = self.open_file(FILE4)
        parser = self.create_rec_parser(in_file)

        # Read and verify 5 particles (of the 25).
        for expected in EXPECTED_FILE4[ : 5]:

            # Generate expected particle
            expected_particle = FlortDjDclRecoveredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        # Skip ahead in the file so that we get the last 10 particles.
        new_state = {
            FlortStateKey.POSITION: 2118
        }

        # Set the state.
        parser.set_state(new_state)

        # Read and verify the last 10 particles.
        for expected in EXPECTED_FILE4[-10: ]:

            # Generate expected particle
            expected_particle = FlortDjDclRecoveredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        log.debug('===== START TEST SET STATE TELEMETERED =====')

        in_file = self.open_file(FILE5)
        parser = self.create_tel_parser(in_file)

        # Read and verify 20 particles (of the 24).
        for expected in EXPECTED_FILE5[ : 20]:

            # Generate expected particle
            expected_particle = FlortDjDclTelemeteredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        # Skip back in the file so that we get the last 17 particles.
        new_state = {
            FlortStateKey.POSITION: 992,
        }

        # Set the state.
        parser.set_state(new_state)

        # Read and verify the last 17 particles.
        for expected in EXPECTED_FILE5[-17: ]:

            # Generate expected particle
            expected_particle = FlortDjDclTelemeteredInstrumentDataParticle(expected)

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
            expected_particle = FlortDjDclRecoveredInstrumentDataParticle(expected)

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
            expected_particle = FlortDjDclTelemeteredInstrumentDataParticle(expected)

            # Get record and verify.
            result = parser.get_records(1)
            self.assertEqual(result, [expected_particle])

        self.assertEqual(self.tel_exception_callback_value, None)
        in_file.close()

        log.debug('===== END TEST SIMPLE =====')
