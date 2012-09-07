#!/usr/bin/env python

"""
@package mi.core.instrument.test.test_data_particle
@file mi/core/instrument/test/test_data_particle.py
@author Steve Foley
@brief Test cases for the base data_particle module
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'


import json
import base64
from nose.plugins.attrib import attr
from pyon.util.unit_test import IonUnitTestCase

from mi.core.log import get_logger ; log = get_logger()
from mi.core.exceptions import SampleException, ReadOnlyException, NotImplementedException
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue

TEST_INST_ID = "CTD-123"
TEST_PARTICLE_VERSION = 1

@attr('UNIT', group='mi')
class TestUnitDataParticle(IonUnitTestCase):
    """
    Test cases for the DataParticleGenerator class. Functions in this class
    provide unit tests and provide a tutorial on use of
    the data particle generator interface.
    """
    
    class TestDataParticle(DataParticle):
        """
        Simple test DataParticle derivative that returns fixed parsed
        data values
        
        @retval Value list for parased data set [{'value_id': foo,
                                                 'value': bar}, ...]                                   
        """
        def _build_parsed_values(self):
            result = [{DataParticleKey.VALUE_ID: "temp",
                       DataParticleKey.VALUE: "23.45"},
                      {DataParticleKey.VALUE_ID: "cond",
                       DataParticleKey.VALUE: "15.9"},
                      {DataParticleKey.VALUE_ID: "depth",
                       DataParticleKey.VALUE: "305.16"}]
            return result
    
    def setUp(self):
        """
        """
        #self.start_couchdb() # appease the pyon gods        
        self.sample_port_timestamp = 3555423720.711772
        self.sample_driver_timestamp = 3555423721.711772
        self.sample_internal_timestamp = 3555423719.711772
        self.sample_raw_data = "SATPAR0229,10.01,2206748544,234"

        self.parsed_test_particle = self.TestDataParticle(TEST_INST_ID,
                                    self.sample_raw_data,
                                    port_timestamp=self.sample_port_timestamp,
                                    quality_flag=DataParticleValue.INVALID,
                                    preferred_timestamp=DataParticleKey.DRIVER_TIMESTAMP)
        self.sample_parsed_particle = {
                                DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
                                DataParticleKey.PKT_VERSION: TEST_PARTICLE_VERSION,
                                DataParticleKey.STREAM_NAME: DataParticleValue.PARSED,
                                DataParticleKey.INSTRUMENT_ID: TEST_INST_ID,
                                DataParticleKey.PORT_TIMESTAMP: self.sample_port_timestamp,
                                DataParticleKey.DRIVER_TIMESTAMP: self.sample_driver_timestamp,
                                DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.DRIVER_TIMESTAMP,
                                DataParticleKey.QUALITY_FLAG: DataParticleValue.INVALID,
                                DataParticleKey.VALUES: [
                                    {DataParticleKey.VALUE_ID: "temp",
                                     DataParticleKey.VALUE: "23.45"},
                                    {DataParticleKey.VALUE_ID: "cond",
                                     DataParticleKey.VALUE: "15.9"},
                                    {DataParticleKey.VALUE_ID: "depth",
                                     DataParticleKey.VALUE: "305.16"}
                                    ]
                                }

        self.raw_test_particle = self.TestDataParticle(TEST_INST_ID,
                                    self.sample_raw_data,
                                    port_timestamp=self.sample_port_timestamp,
                                    internal_timestamp=self.sample_internal_timestamp)
        self.sample_raw_particle = {
                               DataParticleKey.PKT_FORMAT_ID: DataParticleValue.JSON_DATA,
                               DataParticleKey.PKT_VERSION: TEST_PARTICLE_VERSION,
                               DataParticleKey.STREAM_NAME: DataParticleValue.RAW,
                               DataParticleKey.INSTRUMENT_ID: TEST_INST_ID,
                               DataParticleKey.INTERNAL_TIMESTAMP: self.sample_internal_timestamp,
                               DataParticleKey.PORT_TIMESTAMP: self.sample_port_timestamp,
                               DataParticleKey.DRIVER_TIMESTAMP: self.sample_driver_timestamp,
                               DataParticleKey.PREFERRED_TIMESTAMP: DataParticleKey.PORT_TIMESTAMP,
                               DataParticleKey.QUALITY_FLAG: "ok",
                               DataParticleKey.VALUES: [
                                  {
                                    DataParticleKey.VALUE_ID: "raw",
                                    DataParticleKey.VALUE: base64.b64encode(self.sample_raw_data),
                                    "binary": True
                                  }
                                  ]
                                }

    def test_generate_raw(self):
        """
        Test generation of a raw format data particle
        """
        raw_result = self.raw_test_particle.generate_raw()
        decoded_raw = json.loads(raw_result)
        
        driver_time = decoded_raw["driver_timestamp"]
        self.sample_raw_particle["driver_timestamp"] = driver_time
        
        # run it through json so unicode and everything lines up
        standard = json.dumps(self.sample_raw_particle, sort_keys=True)
        self.assertEqual(raw_result, standard)
        
    
    def test_generate_parsed(self):
        """
        Test generation of a parsed format data particle
        """
        # Create some sample data as a param dict
        # Submit it to a data particle generator with a timestamp
        # compare to JSON-ified output
        #   Be sure to check timestamp format as BASE64 and de-encode it.
        #   Sanity check it as well.
        parsed_result = self.parsed_test_particle.generate_parsed()
        log.debug("parsed_result: %s", parsed_result)
        decoded_parsed = json.loads(parsed_result)
        
        driver_time = decoded_parsed["driver_timestamp"]
        self.sample_parsed_particle["driver_timestamp"] = driver_time
        
        # run it through json so unicode and everything lines up
        standard = json.dumps(self.sample_parsed_particle, sort_keys=True)
        log.debug("standard: %s", standard)        
        self.assertEqual(parsed_result, standard)
        
    def test_timestamps(self):
        """
        Test bad timestamp configurations
        """
        test_particle = self.TestDataParticle(TEST_INST_ID,
            self.sample_raw_data,
            preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
            internal_timestamp=self.sample_internal_timestamp)

        self.assertRaises(SampleException, test_particle.generate_raw)
    
    def test_get_set_value(self):
        """
        Test setting values after creation
        """
        test_particle = self.TestDataParticle(TEST_INST_ID,
            self.sample_raw_data,
            preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
            internal_timestamp=self.sample_internal_timestamp)
        
        new_time = self.sample_internal_timestamp + 200
        
        test_particle.set_value(DataParticleKey.INTERNAL_TIMESTAMP,
                                new_time)
        fetched_time = test_particle.get_value(DataParticleKey.INTERNAL_TIMESTAMP)
        self.assertEquals(new_time, fetched_time)

        self.assertRaises(ReadOnlyException, test_particle.set_value,
                          DataParticleKey.PKT_VERSION, 2)
        
        self.assertRaises(ReadOnlyException, test_particle.set_value,
                          DataParticleKey.INTERNAL_TIMESTAMP,
                          self.sample_internal_timestamp+(86400*600))
        
        self.assertRaises(NotImplementedException, test_particle.get_value,
                          "bad_key")
        
