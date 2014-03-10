#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_vel3d_k__stc_imodem
@file marine-integrations/mi/dataset/parser/test/test_vel3d_k__stc_imodem.py
@author Steve Myerson (Raytheon)
@brief Test code for a Vel3d_k__stc_imodem data parser
"""

from nose.plugins.attrib import attr
from StringIO import StringIO


from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.vel3d_k__stc_imodem import Vel3d_k__stc_imodemParser, Vel3d_k__stc_imodemTimeDataParticle, Vel3d_k__stc_imodemVelocityDataParticle, StateKey

## First record from A000010.DEC sample file
TEST_DATA_GOOD_1_REC = \
  "\x01\x00\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00" \
  "\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8" \
  "\x52\x60\x53\x24\x53\x42\x40\x44" \
  "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x52\x48\x4E\x82\x52\x48\x4F\x9B"

## First byte of flag record is bad
TEST_DATA_BAD_1_REC = \
  "\x09\x00\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00" \
  "\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8" \
  "\x52\x60\x53\x24\x53\x42\x40\x44" \
  "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x52\x48\x4E\x82\x52\x48\x4F\x9B"

## First and last record from A000010.DEC sample file
TEST_DATA_GOOD_2_REC = \
  "\x01\x00\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00" \
  "\x71\x08\x1D\x10\x00\x11\xC3\x08\xC9\x0B\x60\x03\xF9\xFD\xFC\xE8" \
  "\x52\x60\x53\x24\x53\x42\x40\x44" \
  "\x71\x08\x1D\x10\x04\x25\xC4\x08\xBF\x0B\x5E\x03\xF0\xFD" \
  "\xFC\x26\x51\xF6\x51\xFC\x50\x43\x40\x45" \
  "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x00\x00\x00\x00\x00\x00\x00\x00" \
  "\x52\x48\x4E\x82\x52\x48\x4F\x9B"

@attr('UNIT', group='mi')
class Vel3d_k__stc_imodemParserUnitTestCase(ParserUnitTestCase):
    """
    Vel3d_k__stc_imodem Parser unit test suite
    """


    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the 
        position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the 
        publish callback """
        self.publish_callback_value = pub

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: \
              'mi.dataset.parser.vel3d_k__stc_imodem',
            DataSetDriverConfigKeys.PARTICLE_CLASS: \
              ['Vel3d_k__stc_imodemTimeDataParticle',
               'Vel3d_k__stc_imodemVelocityDataParticle']
            }
        # Define test data particles and their associated timestamps 
        # which will be compared with returned results

        self.state_callback_value = None
        self.publish_callback_value = None
        self.state = {StateKey.POSITION:0}

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        log.info("=================== START SIMPLE ======================")
        log.info("Simple length %d", len(TEST_DATA_GOOD_1_REC))
        file = StringIO(TEST_DATA_GOOD_1_REC)
        parser = Vel3d_k__stc_imodemParser(self.config, file, 
          self.state, self.state_callback, self.pub_callback, None)
        result = parser.get_records(1)
        log.info("=================== END SIMPLE ======================")

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        log.info("=================== START MANY ======================")
        log.info("Many length %d", len(TEST_DATA_GOOD_2_REC))
        file = StringIO(TEST_DATA_GOOD_2_REC)
        parser = Vel3d_k__stc_imodemParser(self.config, file, 
          self.state, self.state_callback, self.pub_callback, None)
        result = parser.get_records(1)
        log.info("=================== END MANY ==========================")

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        ##
        ## This parser does not support starting in the middle of a file
        ## because it assumes the flag record is the first one to be
        ## processed.
        ##
        pass

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        ##
        ## This parser does not support starting in the middle of a file
        ## because it assumes the flag record is the first one to be
        ## processed.
        ##
        pass

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        log.info("=================== START BAD ======================")
        log.info("Simple length %d", len(TEST_DATA_BAD_1_REC))
        file = StringIO(TEST_DATA_BAD_1_REC)
        parser = Vel3d_k__stc_imodemParser(self.config, file, 
          self.state, self.state_callback, self.pub_callback, None)
        result = parser.get_records(1)
        log.info("=================== END BAD ======================")

