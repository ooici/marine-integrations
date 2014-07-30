#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_cspp_eng_cspp
@file marine-integrations/mi/dataset/parser/test/test_cspp_eng_cspp.py
@author Jeff Roy
@brief Test code for a cspp_eng_cspp data parser
"""

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticleKey

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.cspp_eng_cspp import CsppEngCsppParser, StateKey
from mi.dataset.parser.cspp_eng_cspp import CsppEngCsppParserDataParticle

# The list of generated tests are the suggested tests, but there may
# be other tests needed to fully test your parser

@attr('UNIT', group='mi')
class CsppEngCsppParserUnitTestCase(ParserUnitTestCase):
    """
    cspp_eng_cspp Parser unit test suite
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
	    DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.cspp_eng_cspp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'CsppEngCsppParserDataParticle'
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

    def test_long_stream(self):
        """
        Test a long stream 
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
