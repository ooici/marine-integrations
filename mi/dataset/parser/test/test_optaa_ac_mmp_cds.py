#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_optaa_ac_mmp_cds
@file marine-integrations/mi/dataset/parser/test/test_optaa_ac_mmp_cds.py
@author Mark Worden
@brief Test code for a optaa_ac_mmp_cds data parser
"""

import os
import numpy
import yaml
import copy

from nose.plugins.attrib import attr

from mi.core.log import get_logger
from mi.idk.config import Config

log = get_logger()
from mi.core.exceptions import SampleException, DatasetParserException

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.optaa_ac_mmp_cds import OptaaAcMmpCdsParser
from mi.dataset.parser.mmp_cds_base import StateKey

# Resource path for ctdpf ckl mmp cds
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'optaa_ac', 'mmp_cds', 'resource')


@attr('UNIT', group='mi')
class OptaaAcMmpCdsParserUnitTestCase(ParserUnitTestCase):
    """
    optaa_ac_mmp_cds Parser unit test suite
    """

    state_callback_value = None
    file_ingested_value = None
    publish_callback_value = None
    config = None

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
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.optaa_ac_mmp_cds',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'OptaaAcMmpCdsParserDataParticle'
        }

        # Define test data particles and their associated timestamps which will be
        # compared with returned results
        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

    def test_simple(self):
        """
        This test reads in a small number of particles and verifies the result of one of the particles.
        """

        file_path = os.path.join(RESOURCE_PATH, 'simple.mpk')
        stream_handle = open(file_path, 'rb')

        parser = OptaaAcMmpCdsParser(self.config, None, stream_handle,
                                     self.state_callback, self.pub_callback)

        particles = parser.get_records(1)

        test_data = self.get_dict_from_yml('simple.yml')
        self.assert_result(test_data['data'][0], particles[0])

        stream_handle.close()

    def test_get_many(self):
        """
        This test exercises retrieving 20 particles, verifying the 20th particle, then retrieves 30 particles
         and verifies the 30th particle.
        """

        file_path = os.path.join(RESOURCE_PATH, 'get_many.mpk')
        stream_handle = open(file_path, 'rb')

        parser = OptaaAcMmpCdsParser(self.config, None, stream_handle,
                                     self.state_callback, self.pub_callback)

        particles = parser.get_records(20)

        # Should end up with 20 particles
        self.assertTrue(len(particles) == 20)

        test_data = self.get_dict_from_yml('get_many.yml')

        for i in range(len(particles)):
            self.assert_result(test_data['data'][i], particles[i])

        particles = parser.get_records(30)

        # Should end up with 30 particles
        self.assertTrue(len(particles) == 30)

        for i in range(len(particles)):
            self.assert_result(test_data['data'][i+20], particles[i])

        stream_handle.close()

    def test_long_stream(self):
        """
        This test exercises retrieve approximately 200 particles.
        """

        file_path = os.path.join(RESOURCE_PATH, 'large_import.mpk')
        stream_handle = open(file_path, 'rb')

        parser = OptaaAcMmpCdsParser(self.config, None, stream_handle,
                                     self.state_callback, self.pub_callback)

        # Attempt to retrieve 500 particles
        particles = parser.get_records(500)

        # Should end up with 500 particles
        self.assertTrue(len(particles) == 500)

        test_data = self.get_dict_from_yml('large_import.yml')

        for i in range(len(particles)):
            self.assert_result(test_data['data'][i], particles[i])

        stream_handle.close()

    def test_mid_state_start(self):
        """
        This test exercises setting the state past one chunk, retrieving particles and verify the result of one
        of the particles.
        """

        # Using two concatenated msgpack files to simulate two chunks.
        file_path = os.path.join(RESOURCE_PATH, 'set_state.mpk')
        stream_handle = open(file_path, 'rb')

        # Moving the file position to the end of the first chunk
        state = {StateKey.PARTICLES_RETURNED: 20}

        parser = OptaaAcMmpCdsParser(self.config, state, stream_handle,
                                     self.state_callback, self.pub_callback)

        particles = parser.get_records(4)

        log.info(len(particles))

        # Should end up with 4 particles
        self.assertTrue(len(particles) == 4)

        test_data = self.get_dict_from_yml('set_state.yml')

        for i in range(len(particles)):
            self.assert_result(test_data['data'][20+i], particles[i])

        stream_handle.close()

    def test_set_state(self):
        """
        This test exercises setting the state past one chunk, retrieving particles, verifying one
        of the particles, and then setting the state back to the beginning, retrieving a few particles, and
        verifying one of the particles.
        """

        # Using the default mspack test file.
        file_path = os.path.join(RESOURCE_PATH, 'set_state.mpk')
        stream_handle = open(file_path, 'rb')

        parser = OptaaAcMmpCdsParser(self.config, None, stream_handle,
                                     self.state_callback, self.pub_callback)

        particles = parser.get_records(4)

        # Should end up with 4 particles
        self.assertTrue(len(particles) == 4)

        log.info(parser._state)

        test_data = self.get_dict_from_yml('set_state.yml')

        for i in range(len(particles)):
            self.assert_result(test_data['data'][i], particles[i])

        state = copy.copy(parser._state)

        log.info(state)

        # Re-create the parser with a state of None
        parser = OptaaAcMmpCdsParser(self.config, None, stream_handle,
                                     self.state_callback, self.pub_callback)

        # Retrieve the first 4 particles again
        particles = parser.get_records(4)

        # Check the particles again
        for i in range(len(particles)):
            self.assert_result(test_data['data'][i], particles[i])

        # Set the parser's state
        parser.set_state(state)

        particles = parser.get_records(4)

        # Should end up with 4 particles
        self.assertTrue(len(particles) == 4)

        for i in range(len(particles)):
            self.assert_result(test_data['data'][4+i], particles[i])

        # Reset the state to 0 particles returned
        parser.set_state({StateKey.PARTICLES_RETURNED: 0})

        particles = parser.get_records(1)

        self.assertTrue(len(particles) == 1)

        # Check the particle
        self.assert_result(test_data['data'][0], particles[0])

        # Set the state to a bad state (i.e. None)
        with self.assertRaises(DatasetParserException):
            parser.set_state(None)

        # Set the state to a bad state (i.e. a list)
        with self.assertRaises(DatasetParserException):
            parser.set_state(['particles_returned'])

        # Set the state to 0 particles returned
        parser.set_state({StateKey.PARTICLES_RETURNED: 0})

        # Attempt to retrieve 1000 particles
        particles = parser.get_records(1000)

        # Ensure we got all expected 30
        self.assertTrue(len(particles) == 30)

        for i in range(len(particles)):
            self.assert_result(test_data['data'][i], particles[i])

        # Provide a bad particles returned
        state = {StateKey.PARTICLES_RETURNED: 80}

        parser = OptaaAcMmpCdsParser(self.config, state, stream_handle,
                                     self.state_callback, self.pub_callback)

        particles = parser.get_records(1)

        self.assertTrue(len(particles) == 0)

        stream_handle.close()

    def test_bad_data_one(self):
        """
        This test verifies that a SampleException is raised when msgpack data is malformed.
        """

        file_path = os.path.join(RESOURCE_PATH, 'acs_archive.mpk')
        stream_handle = open(file_path, 'rb')

        parser = OptaaAcMmpCdsParser(self.config, None, stream_handle,
                                     self.state_callback, self.pub_callback)

        particles = parser.get_records(100)

        self.assertTrue(len(particles) == 40)

        stream_handle.close()

        file_path = os.path.join(RESOURCE_PATH, 'acs_archive_BAD.mpk')
        stream_handle = open(file_path, 'rb')

        parser = OptaaAcMmpCdsParser(self.config, None, stream_handle,
                                     self.state_callback, self.pub_callback)

        with self.assertRaises(SampleException):
            parser.get_records(1)

        stream_handle.close()

    def test_bad_data_two(self):
        """
        This test verifies that a SampleException is raised when an entire msgpack buffer is not msgpack.
        """

        file_path = os.path.join(RESOURCE_PATH, 'not-msg-pack.mpk')
        stream_handle = open(file_path, 'rb')

        parser = OptaaAcMmpCdsParser(self.config, None, stream_handle,
                                     self.state_callback, self.pub_callback)

        with self.assertRaises(SampleException):
            parser.get_records(1)

        stream_handle.close()

    def assert_result(self, test, particle):
        """
        Suite of tests to run against each returned particle and expected
        results of the same.  The test parameter should be a dictionary
        that contains the keys to be tested in the particle
        the 'internal_timestamp' and 'position' keys are
        treated differently than others but can be verified if supplied
        """

        particle_dict = particle.generate_dict()

        #for efficiency turn the particle values list of dictionaries into a dictionary
        particle_values = {}
        for param in particle_dict.get('values'):
            particle_values[param['value_id']] = param['value']

        # compare each key in the test to the data in the particle
        for key in test:
            test_data = test[key]

            #get the correct data to compare to the test
            if key == 'internal_timestamp':
                particle_data = particle.get_value('internal_timestamp')
                #the timestamp is in the header part of the particle

                log.info("internal_timestamp %.10f", particle_data)

            elif key == StateKey.PARTICLES_RETURNED:
                particle_data = self.state_callback_value[StateKey.PARTICLES_RETURNED]

                log.info("particles returned %d", particle_data)

            else:
                particle_data = particle_values.get(key)
                #others are all part of the parsed values part of the particle

            if particle_data is None:
                #generally OK to ignore index keys in the test data, verify others

                log.warning("\nWarning: assert_result ignoring test key %s, does not exist in particle", key)
            else:
                # log.info(key)
                # log.info(type(test_data))
                # log.info(test_data)
                # log.info(type(particle_data))
                # log.info(particle_data)
                if isinstance(test_data, float):
                    # slightly different test for these values as they are floats.
                    compare = numpy.abs(test_data - particle_data) <= 1e-5
                    self.assertTrue(compare)
                else:
                    # otherwise they are all ints and should be exactly equal
                    self.assertEqual(test_data, particle_data)

    @staticmethod
    def get_dict_from_yml(filename):
        """
        This utility routine loads the contents of a yml file
        into a dictionary
        """

        fid = open(os.path.join(RESOURCE_PATH, filename), 'r')
        result = yaml.load(fid)
        fid.close()

        return result