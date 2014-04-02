#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_cg_stc_eng__stc
@file marine-integrations/mi/dataset/parser/test/test_cg_stc_eng__stc.py
@author Mike Nicoletti
@brief Test code for a Cg_stc_eng__stc data parser
"""
import os
import re
import ntplib

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticleKey

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.cg_stc_eng_stc import CgStcEngStcParser, CgStcEngStcParserDataParticle
from mi.dataset.parser.cg_stc_eng_stc import CgStcEngStcParserDataParticleKey

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
			     'dataset', 'driver', 'cg_stc_eng',
			     'stc', 'resource')

@attr('UNIT', group='mi')
class CgParserUnitTestCase(ParserUnitTestCase):
    """
    Cg_stc_eng_stc Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub
        
    def exception_callback(self, exception):
        """ Callback method to watch what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self): 
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.cg_stc_eng_stc',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'CgStcEngStcParserDataParticle'
            }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
        fid = open(os.path.join(RESOURCE_PATH, 'stc_status.txt'))
        data = fid.read()
        fid.close()
        utime_grp = re.search(r'Platform.utime=(.+)\r\n', data)
        self.timestamp_a = ntplib.system_to_ntp_time(float(utime_grp.group(1)))
        self.particle_a = CgStcEngStcParserDataParticle(data, internal_timestamp=self.timestamp_a)

	self.comparison_list = [{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_GPS_DATE,
				 DataParticleKey.VALUE: 41013},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_GPS_TIME,
				 DataParticleKey.VALUE: 160701},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LATSTR,
				 DataParticleKey.VALUE: '4132.1353 N'},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LONSTR,
				 DataParticleKey.VALUE: '07038.8306 W'},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LAT,
				 DataParticleKey.VALUE: 41.535588},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_GPS_LON,
				 DataParticleKey.VALUE: -70.647177},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_GPS_SPD,
				 DataParticleKey.VALUE: 0.0}]

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def assert_result(self, result, particle, ingested):
        if result[0].raw_data == particle.raw_data:
            log.debug("raw data match")
        log.debug("comparing result %s, particle %s", result[0].contents, particle.contents)
        self.assertEqual(result, [particle])
        self.assertEqual(self.file_ingested_value, ingested)

        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        stream_handle = open(os.path.join(RESOURCE_PATH, 'stc_status.txt'))
        self.parser = CgStcEngStcParser(self.config, None, stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.exception_callback)

        result = self.parser.get_records(1)
        self.assert_result(result, self.particle_a, True)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.exception_callback_value, None)

    def test_get_many(self):
        """
        Read test data and try to pull out multiple data particles at one time,
        but we should only get 1 .
        Assert that the results are those we expected.
        """
        stream_handle = open(os.path.join(RESOURCE_PATH, 'stc_status.txt'))
        self.parser = CgStcEngStcParser(self.config, None, stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.exception_callback)

        result = self.parser.get_records(4)
        self.assert_result(result, self.particle_a, True)
        self.assertEqual(len(self.publish_callback_value), 1)

        # no data left, dont move the position
        result = self.parser.get_records(1)
        self.assertEqual(result, [])
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], self.particle_a)
        self.assertEqual(self.exception_callback_value, None)

    def test_generate(self):
        """
        Ensure we can generate the particle dictionary and compare it to expected ones
        """
        a_dict = self.particle_a.generate_dict()
        
        stream_handle = open(os.path.join(RESOURCE_PATH, 'stc_status.txt'))
        self.parser = CgStcEngStcParser(self.config, None, stream_handle,
                                        self.state_callback, self.pub_callback,
                                        self.exception_callback)

        result = self.parser.get_records(1)
        res_dict = result[0].generate_dict()
        # assert two generated dictionaries are the same
        for cdict in self.comparison_list:
            for rdict in res_dict['values']:
                if cdict.get('value_id') == rdict.get('value_id'):
                    if cdict.get('value') != rdict.get('value'):
                        self.fail("mismatch for %s, values %s, %s" % (cdict.get('value_id'),
                                                                      cdict.get('value'),
                                                                      rdict.get('value')))

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        with self.assertRaises(SampleException):
            stream_handle = open(os.path.join(RESOURCE_PATH, 'stc_status_missing_time.txt'))
            self.parser = CgStcEngStcParser(self.config, None, stream_handle,
                                            self.state_callback, self.pub_callback,
                                            self.exception_callback)
            result = self.parser.get_records(1)
