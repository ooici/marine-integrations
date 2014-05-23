#! /usr/bin/env python

"""
@file ion/core/unit_test.py
@author Bill French
@brief Base test class for all MI tests.  Provides two base classes, 
One for pyon tests and one for stand alone MI tests. 

We have the stand alone test case for tests that don't require or can't
integrate with the common ION test case.
"""


from mi.core.log import get_logger
log = get_logger()

import unittest
import json 

from pyon.util.unit_test import IonUnitTestCase
from pyon.util.unit_test import PyonTestCase
from pyon.util.int_test  import IonIntegrationTestCase
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.data_particle import DataParticleValue
from mi.idk.exceptions import IDKException


class MiUnitTest(unittest.TestCase):
    """
    Base class for non-ion tests.  Use only if needed to avoid ion 
    test common code.
    """
    def shortDescription(self):
        return None


class MiUnitTestCase(IonUnitTestCase):
    """
    Base class for most tests in MI.
    """
    def shortDescription(self):
        return None

    def test_verify_service(self):
        pass

class MiTestCase(PyonTestCase):
    """
    Base class for most tests in MI.
    """
    def shortDescription(self):
        return None

    def test_verify_service(self):
        pass

class MiIntTestCase(IonIntegrationTestCase):
    """
    Base class for most tests in MI.
    """

    def shortDescription(self):
        return None

class ParticleTestMixin(object):
    """
    A class with some methods to test data particles. Intended to be mixed
    into test classes so that particles can be tested in different areas of
    the MI code base.
    """

    def convert_data_particle_to_dict(self, data_particle):
        """
        Convert a data particle object to a dict.  This will work for data
        particles as DataParticle object, dictionaries or a string
        @param data_particle data particle
        @return dictionary representation of a data particle
        """
        if (isinstance(data_particle, DataParticle)):
            sample_dict = data_particle.generate_dict()
        elif (isinstance(data_particle, str)):
            sample_dict = json.loads(data_particle)
        elif (isinstance(data_particle, dict)):
            sample_dict = data_particle
        else:
            raise IDKException("invalid data particle type: %s", type(data_particle))

        return sample_dict

    def get_data_particle_values_as_dict(self, data_particle):
        """
        Return all of the data particle values as a dictionary with the value
        id as the key and the value as the value.  This method will decimate
        the data, in the any characteristics other than value id and value.
        i.e. binary.
        @param data_particle data particle to inspect
        @return return a dictionary with keys and values { value-id: value }
        @throws IDKException when missing values dictionary
        """
        sample_dict = self.convert_data_particle_to_dict(data_particle)

        values = sample_dict.get('values')
        if(not values):
            raise IDKException("Data particle missing values")

        if(not isinstance(values, list)):
            raise IDKException("Data particle values not a list")

        result = {}
        for param in values:
            if(not isinstance(param, dict)):
                raise IDKException("must be a dict")

            key = param.get('value_id')
            if(key == None):
                raise IDKException("value_id not defined")

            if(key in result.keys()):
                raise IDKException("duplicate value detected for %s" % key)

            result[key] = param.get('value')

        return result

    def assert_data_particle_keys(self, data_particle_key, test_config):
        """
        Ensure that the keys defined in the data particle key enum match
        the keys defined in the test configuration.
        @param data_particle_key object that defines all data particle keys.
        @param test_config dictionary containing parameter verification values
        """
        driver_keys = sorted(data_particle_key.list())
        test_config_keys = sorted(test_config.keys())

        self.assertEqual(driver_keys, test_config_keys)

    def assert_data_particle_header(self, data_particle, stream_name, require_instrument_timestamp=False):
        """
        Verify a data particle header is formatted properly
        @param data_particle version 1 data particle
        @param stream_name version 1 data particle
        @param require_instrument_timestamp should we verify the instrument timestamp exists
        """
        sample_dict = self.convert_data_particle_to_dict(data_particle)
        log.debug("SAMPLEDICT: %s", sample_dict)

        self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME], stream_name)
        self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID], DataParticleValue.JSON_DATA)
        self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
        self.assertIsInstance(sample_dict[DataParticleKey.VALUES], list)

        self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

        self.assertIsNotNone(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP))
        self.assertIsInstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float)

        # It is highly unlikely that we should have a particle without a port agent timestamp,
        # at least that's the current assumption.
        self.assertIsNotNone(sample_dict.get(DataParticleKey.PORT_TIMESTAMP))
        self.assertIsInstance(sample_dict.get(DataParticleKey.PORT_TIMESTAMP), float)

        if(require_instrument_timestamp):
            self.assertIsNotNone(sample_dict.get(DataParticleKey.INTERNAL_TIMESTAMP))
            self.assertIsInstance(sample_dict.get(DataParticleKey.INTERNAL_TIMESTAMP), float)



