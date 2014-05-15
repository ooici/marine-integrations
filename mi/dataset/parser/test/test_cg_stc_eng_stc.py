#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_cg_stc_eng_stc
@file marine-integrations/mi/dataset/parser/test/test_cg_stc_eng_stc.py
@author Mike Nicoletti
@brief Test code for a Cg_stc_eng_stc data parser
"""
import os
import re
import ntplib

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException, SampleEncodingException
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
        utime_grp = re.search(r'Platform.utime=(.+?)(\r\n?|\n)', data)
        self.timestamp_a = ntplib.system_to_ntp_time(float(utime_grp.group(1)))
        self.particle_a = CgStcEngStcParserDataParticle(data, internal_timestamp=self.timestamp_a)

	self.comparison_list = [{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_PLATFORM_TIME,
				 DataParticleKey.VALUE: '2013/10/04 16:07:02.253'},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_PLATFORM_UTIME,
				 DataParticleKey.VALUE: 1380902822.253},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_GPS,
				 DataParticleKey.VALUE: 83},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_NTP,
				 DataParticleKey.VALUE: 0},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_PPS,
				 DataParticleKey.VALUE: 4},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_POWER_SYS,
				 DataParticleKey.VALUE: 0},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_SUPERV,
				 DataParticleKey.VALUE: 7},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MSG_CNTS_C_TELEM,
				 DataParticleKey.VALUE: 0},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_GPS,
				 DataParticleKey.VALUE: 1},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_PPS,
				 DataParticleKey.VALUE: 1},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_ERR_C_TELEM_SYS,
				 DataParticleKey.VALUE: 3},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_GPS,
				 DataParticleKey.VALUE: '***Warning, BAD GPS CHECKSUM'},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_PPS,
				 DataParticleKey.VALUE: 'C_PPS: Warning: Pulse delta [790] above warning level [500], still within window [900]'},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_ERRMSG_C_TELEM_SYS,
				 DataParticleKey.VALUE: ' "***Error turning on fb1 [ret=No Device]'},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_CPU_UPTIME,
				 DataParticleKey.VALUE: '0 days 00:01:22'},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_CPU_LOAD1,
				 DataParticleKey.VALUE: 1.03},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_CPU_LOAD5,
				 DataParticleKey.VALUE: 0.36},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_CPU_LOAD15,
				 DataParticleKey.VALUE: 0.12},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MEMORY_RAM,
				 DataParticleKey.VALUE: 127460},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MEMORY_FREE,
				 DataParticleKey.VALUE: 93396},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_NPROC,
				 DataParticleKey.VALUE: 76},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_EFLAG,
				 DataParticleKey.VALUE: 0},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_MAIN_V,
				 DataParticleKey.VALUE: 17.90},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_MAIN_C,
				 DataParticleKey.VALUE: 379.20},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_BAT_V,
				 DataParticleKey.VALUE: 0.0},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_BAT_C,
				 DataParticleKey.VALUE: 0.0},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_TEMP1,
				 DataParticleKey.VALUE: 25.0},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_TEMP2,
				 DataParticleKey.VALUE: 23.3},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_HUMID,
				 DataParticleKey.VALUE: 31.6},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_PRESS,
				 DataParticleKey.VALUE: 14.7},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GF_ENA,
				 DataParticleKey.VALUE: 15},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GFLT1,
				 DataParticleKey.VALUE: 7.7},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GFLT2,
				 DataParticleKey.VALUE: 5.2},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GFLT3,
				 DataParticleKey.VALUE: 2.8},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_GFLT4,
				 DataParticleKey.VALUE: 4.0},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_MPIC_LD_ENA,
				 DataParticleKey.VALUE: 3},
				{DataParticleKey.VALUE_ID: CgStcEngStcParserDataParticleKey.CG_ENG_GPS_DATE,
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
	# uncomment the following to write the above comparison list in yml format to a file
	#self.write_comparison_to_yml()

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def write_comparison_to_yml(self):
        """
        Helper class to create a yml file for driver tests
        """
        fid = open('particle.yml', 'a')
        fid.write('header:\n')
        fid.write('    particle_object: CgStcEngStcParserDataParticle\n')
        fid.write('    particle_type: cg_stc_eng_stc\n')
        fid.write('data:\n')
        fid.write('  - _index: 1\n')
        fid.write('    internal_timestamp: 0.0\n')

        for item in self.comparison_list:
            if isinstance(item.get('value'), float):
                fid.write('    %s: %16.20f\n' % (item.get('value_id'), item.get('value')))
            else:
                fid.write('    %s: %s\n' % (item.get('value_id'), item.get('value')))
        fid.close()

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
        # assert two lists of generated dictionaries are the same
        for cdict in self.comparison_list:
            for rdict in res_dict['values']:
                if cdict.get('value_id') == rdict.get('value_id'):
                    if cdict.get('value') != rdict.get('value'):
                        log.error("mismatch for key %s, values '%s' '%s'", cdict.get('value_id'),
                                                                           cdict.get('value'),
                                                                           rdict.get('value'))
                        self.fail("mismatch for key %s, values '%s', '%s'" % (cdict.get('value_id'),
                                                                              cdict.get('value'),
                                                                              rdict.get('value')))

    def test_bad_data(self):
        """
        Ensure that the missing timestamp field causes a sample exception
        """
        with self.assertRaises(SampleException):
            stream_handle = open(os.path.join(RESOURCE_PATH, 'stc_status_missing_time.txt'))
            self.parser = CgStcEngStcParser(self.config, None, stream_handle,
                                            self.state_callback, self.pub_callback,
                                            self.exception_callback)
            result = self.parser.get_records(1)

    def test_encoding(self):
        """
        Create an encoding error in the data and make sure an encoding error shows up
        """
	stream_handle = open(os.path.join(RESOURCE_PATH, 'stc_status_bad_encode.txt'))
	self.parser = CgStcEngStcParser(self.config, None, stream_handle,
					self.state_callback, self.pub_callback,
					self.exception_callback)
	result = self.parser.get_records(1)
	res_dict = result[0].generate_dict()
	errors = result[0].get_encoding_errors()
	log.debug("encoding errors: %s", errors)
	self.assertNotEqual(errors, [])