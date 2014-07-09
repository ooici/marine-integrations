#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_dosta_abcdjm_cspp
@file marine-integrations/mi/dataset/parser/test/test_dosta_abcdjm_cspp.py
@author Mark Worden
@brief Test code for a dosta_abcdjm_cspp data parser
"""

import os
import numpy
import yaml
import copy

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.driver.dosta_abcdjm.cspp.driver import DataTypeKey
from mi.dataset.parser.cspp_base import StateKey, METADATA_PARTICLE_CLASS_KEY, DATA_PARTICLE_CLASS_KEY
from mi.dataset.parser.dosta_abcdjm_cspp import DostaAbcdjmCsppParser
from mi.dataset.parser.dosta_abcdjm_cspp import DostaAbcdjmCsppMetadataRecoveredDataParticle, \
    DostaAbcdjmCsppInstrumentRecoveredDataParticle, DostaAbcdjmCsppMetadataTelemeteredDataParticle, \
    DostaAbcdjmCsppInstrumentTelemeteredDataParticle

from mi.idk.config import Config

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'dosta_abcdjm', 'cspp', 'resource')


@attr('UNIT', group='mi')
class DostaAbcdjmCsppParserUnitTestCase(ParserUnitTestCase):
    """
    dosta_abcdjm_cspp Parser unit test suite
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
            DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_abcdjm_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: DostaAbcdjmCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: DostaAbcdjmCsppInstrumentRecoveredDataParticle,
                }
            },
            DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.dosta_abcdjm_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: DostaAbcdjmCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: DostaAbcdjmCsppInstrumentTelemeteredDataParticle,
                }
            },
        }
        # Define test data particles and their associated timestamps which will be
        # compared with returned results

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = None

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        file_path = os.path.join(RESOURCE_PATH, '11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1000)

        log.info("Num particles %s", len(particles))

        for particle in particles:
            print particle.generate_dict()

        # test_data = self.get_dict_from_yml('good.yml')
        # self.assert_result(test_data['data'][0], particles[5])

        stream_handle.close()


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
