#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_cg_stc_eng__stc
@file marine-integrations/mi/dataset/parser/test/test_cg_stc_eng__stc.py
@author Mike Nicoletti
@brief Test code for a Cg_stc_eng__stc data parser
"""

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.cg_stc_eng__stc import Cg_stc_eng__stcParser, Cg_stc_eng__stcParserDataParticle

@attr('UNIT', group='mi')
class CgParserUnitTestCase(ParserUnitTestCase):
    """
    Cg_stc_eng__stc Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def setUp(self): 
	ParserUnitTestCase.setUp(self)
	self.config = {
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.cg_stc_eng__stc',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'Cg_stc_eng__stcParserDataParticle'
	    }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

    def test_simple(self):
        """
	Read test data and pull out data particles one at a time.
	Assert that the results are those we expected.
	"""
        pass

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
    
    def test_param_dict(self ):
	fid = open('/home/mnicoletti/stc_status.txt')
	#str_all = fid.read()
	self.stream_handle = fid #StringIO(fid) #turn into a data stream to look like file ingestion
	#particle = Cg_stc_eng__stcParserDataParticle(str_all)
	#particle = Cg_stc_eng__stcParserDataParticle('Platform.utime=1380902822.253')
	#param_dict = particle.generate_dict()
	
	#all_params = param_dict.get_all()
	#self.assertEqual(1380902822.253,param_dict['cg_eng_platform_utime']) 
	#log.debug('THIS IS FROM THE TEST FILE!!!!!!     %s',param_dict)
	
	
        self.parser =  Cg_stc_eng__stcParser(self, self.config, None, self.stream_handle,
                                                self.state_callback, self.pub_callback)
	
    
    