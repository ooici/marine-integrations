#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_flord_l_wfp
@file marine-integrations/mi/dataset/parser/test/test_flord_l_wfp.py
@author Joe Padula
@brief Test code for a flord_l_wfp data parser
"""

from nose.plugins.attrib import attr

import yaml
import numpy
import os

from mi.core.log import get_logger ; log = get_logger()
from mi.idk.config import Config
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticleKey

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.WFP_E_file_common import HEADER_BYTES, StateKey
from mi.dataset.parser.flord_l_wfp import FlordLWfpParser
from mi.dataset.parser.flord_l_wfp import FlordLWfpParserDataParticle

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'flord_l', 'wfp', 'resource')


@attr('UNIT', group='mi')
class FlordLWfpParserUnitTestCase(ParserUnitTestCase):
    """
    flord_l_wfp Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to match what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.flord_l_wfp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'FlordLWfpParserDataParticle'
        }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results

        self.start_state = {StateKey.POSITION: 0}

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """

        file_path = os.path.join(RESOURCE_PATH, 'small.DAT')
        self.stream_handle = open(file_path, 'rb')

        self.parser = FlordLWfpParser(self.config, self.start_state, self.stream_handle,
                                      self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(6)

        log.debug("particles: %s", particles)
        for particle in particles:
            log.info(particle.generate_dict())
        #
        # # Make sure the fifth particle has the correct values
        # self.assert_result(self.test_particle1, particles[5])
        #
        # test_data = self.get_dict_from_yml('good.yml')
        # self.assert_result(test_data['data'][0], particles[5])

        self.stream_handle.close()


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
