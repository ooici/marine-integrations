#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_nutnr_j_cspp
@file marine-integrations/mi/dataset/parser/test/test_nutnr_j_cspp.py
@author Emily Hahn
@brief Test code for a nutnr_j_cspp data parser
"""

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException
from mi.core.instrument.data_particle import DataParticleKey

from mi.idk.config import Config

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.cspp_base import StateKey
from mi.dataset.parser.nutnr_j_cspp import NutnrJCsppParser, \
                                           NutnrJCsppMetadataTelemeteredDataParticle, \
                                           NutnrJCsppTelemeteredDataParticle, \
                                           NutnrJCsppMetadataRecoveredDataParticle, \
                                           NutnrJCsppRecoveredDataParticle


RESOURCE_PATH = os.path.join(Config().base_dir(),
			     'mi', 'dataset', 'driver', 'nutnr_j', 'cspp', 'resource')

@attr('UNIT', group='mi')
class NutnrJCsppParserUnitTestCase(ParserUnitTestCase):
    """
    nutnr_j_cspp Parser unit test suite
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
        self.telem_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnr_j_cspp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: None
            DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                METADATA_PARTICLE_CLASS_KEY: NutnrJCsppMetadataTelemeteredDataParticle,
                DATA_PARTICLE_CLASS_KEY: NutnrJCsppTelemeteredDataParticle
            }
        }
        
        self.recov_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.nutnr_j_cspp',
            DataSetDriverConfigKeys.PARTICLE_CLASS: None
            DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                METADATA_PARTICLE_CLASS_KEY: NutnrJCsppMetadataRecoveredDataParticle,
                DATA_PARTICLE_CLASS_KEY: NutnrJCsppRecoveredDataParticle
            }
        }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results
        
        self.meta_telem_particle = NutnrJCsppMetadataTelemeteredDataParticle()
        self.telem_particle_a = NutnrJCsppTelemeteredDataParticle()
        
        self.meta_recov_particle = NutnrJCsppMetadataRecoveredDataParticle()
        self.recov_particle_a = NutnrJCsppRecoveredDataParticle()

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          '11079894_PPB_OPT.txt'), 'rb')
        
        parser = NutnrJCsppParser(self.telem_config, None, stream_handle, 
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)
        
        parser.get_records(1)

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
