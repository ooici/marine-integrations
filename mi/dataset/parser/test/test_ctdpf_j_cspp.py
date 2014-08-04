#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_ctdpf_j_cspp
@file marine-integrations/mi/dataset/parser/test/test_ctdpf_j_cspp.py
@author Joe Padula
@brief Test code for a ctdpf_j_cspp data parser
"""

import os
import yaml
import numpy

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import RecoverableSampleException

from mi.idk.config import Config

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

from mi.dataset.parser.cspp_base import \
    StateKey, \
    METADATA_PARTICLE_CLASS_KEY, \
    DATA_PARTICLE_CLASS_KEY

from mi.dataset.parser.ctdpf_j_cspp import \
    CtdpfJCsppParser, \
    CtdpfJCsppInstrumentTelemeteredDataParticle, \
    CtdpfJCsppMetadataTelemeteredDataParticle, \
    CtdpfJCsppInstrumentRecoveredDataParticle, \
    CtdpfJCsppMetadataRecoveredDataParticle

from mi.dataset.driver.ctdpf_j.cspp.driver import DataTypeKey

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'ctdpf_j', 'cspp', 'resource')

RECOVERED_SAMPLE_DATA = '11079364_PPB_CTD.txt'
TELEMETERED_SAMPLE_DATA = '11079364_PPD_CTD.txt'


@attr('UNIT', group='mi')
class CtdpfJCsppParserUnitTestCase(ParserUnitTestCase):
    """
    ctdpf_j_cspp Parser unit test suite
    """
    def state_callback(self, state, file_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.file_ingested_value = file_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value.append(exception)
        self.count += 1

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataTypeKey.CTDPF_J_CSPP_TELEMETERED: {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpf_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: CtdpfJCsppMetadataTelemeteredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: CtdpfJCsppInstrumentTelemeteredDataParticle,
                }
            },
            DataTypeKey.CTDPF_J_CSPP_RECOVERED: {
                DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpf_j_cspp',
                DataSetDriverConfigKeys.PARTICLE_CLASS: None,
                DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT: {
                    METADATA_PARTICLE_CLASS_KEY: CtdpfJCsppMetadataRecoveredDataParticle,
                    DATA_PARTICLE_CLASS_KEY: CtdpfJCsppInstrumentRecoveredDataParticle,
                }
            },
        }
        # Define test data particles and their associated timestamps which will be 
        # compared with returned results

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None
        self.exception_callback_value = []
        self.count = 0

    def particle_to_yml(self, particles, filename, mode='w'):
        """
        This is added as a testing helper, not actually as part of the parser tests. Since the same particles
        will be used for the driver test it is helpful to write them to .yml in the same form they need in the
        results.yml fids here.
        """
        # open write append, if you want to start from scratch manually delete this fid
        fid = open(os.path.join(RESOURCE_PATH, filename), mode)

        fid.write('header:\n')
        fid.write(" particle_object: 'MULTIPLE'\n")
        fid.write(" particle_type: 'MULTIPLE'\n")
        fid.write('data:\n')

        for i in range(0, len(particles)):
            particle_dict = particles[i].generate_dict()

            fid.write(' - _index: %d\n' % (i+1))

            fid.write('   particle_object: %s\n' % particles[i].__class__.__name__)
            fid.write('   particle_type: %s\n' % particle_dict.get('stream_name'))
            fid.write('   internal_timestamp: %f\n' % particle_dict.get('internal_timestamp'))

            for val in particle_dict.get('values'):
                if isinstance(val.get('value'), float):
                    fid.write('   %s: %16.16f\n' % (val.get('value_id'), val.get('value')))
                elif isinstance(val.get('value'), str):
                    fid.write("   %s: '%s'\n" % (val.get('value_id'), val.get('value')))
                else:
                    fid.write('   %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()

    def get_dict_from_yml(self, filename):
        """
        This utility routine loads the contents of a yml file
        into a dictionary
        """

        fid = open(os.path.join(RESOURCE_PATH, filename), 'r')
        result = yaml.load(fid)
        fid.close()

        return result

    def create_yml(self):
        """
        This utility creates a yml file
        """

        fid = open(os.path.join(RESOURCE_PATH, TELEMETERED_SAMPLE_DATA), 'r')

        stream_handle = fid
        parser = CtdpfJCsppParser(self.config.get(DataTypeKey.CTDPF_J_CSPP_TELEMETERED),
                                  None, stream_handle,
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)

        particles = parser.get_records(20)

        self.particle_to_yml(particles, '11079364_PPD_CTD_telem.yml')
        fid.close()

    def assert_result(self, test, particle):
        """
        Suite of tests to run against each returned particle and expected
        results of the same. The test parameter should be a dictionary
        that contains the keys to be tested in the particle
        the 'internal_timestamp' and 'position' keys are
        treated differently than others but can be verified if supplied
        """

        particle_dict = particle.generate_dict()

        # for efficiency turn the particle values list of dictionaries into a dictionary
        particle_values = {}
        for param in particle_dict.get('values'):
            particle_values[param['value_id']] = param['value']
            # log.debug('### building building particle values ###')
            # log.debug('value_id = %s', param['value_id'])
            # log.debug('value = %s', param['value'])

        # compare each key in the test to the data in the particle
        for key in test:
            test_data = test[key]

            # get the correct data to compare to the test
            if key == 'internal_timestamp':
                particle_data = particle.get_value('internal_timestamp')
                #the timestamp is in the header part of the particle
            elif key == 'position':
                particle_data = self.state_callback_value['position']
                #position corresponds to the position in the file
            else:
                particle_data = particle_values.get(key)
                #others are all part of the parsed values part of the particle

            # log.debug('*** assert result: test data key = %s', key)
            # log.debug('*** assert result: test data val = %s', test_data)
            # log.debug('*** assert result: part data val = %s', particle_data)

            if particle_data is None:
                #generally OK to ignore index keys in the test data, verify others

                log.warning("\nWarning: assert_result ignoring test key %s, does not exist in particle", key)
            else:
                if isinstance(test_data, float):

                    # slightly different test for these values as they are floats.
                    compare = numpy.abs(test_data - particle_data) <= 1e-5
                    # log.debug('*** assert result: compare = %s', compare)
                    self.assertTrue(compare)
                else:
                    # otherwise they are all ints and should be exactly equal
                    self.assertEqual(test_data, particle_data)

    def test_simple(self):
        """
        Read test data and pull out 20 data particles.
        Assert that the results are those we expected.
        """
        file_path = os.path.join(RESOURCE_PATH, RECOVERED_SAMPLE_DATA)
        stream_handle = open(file_path, 'r')

        # Note: since the recovered and telemetered parser and particles are common
        # to each other, testing one is sufficient, will be completely tested
        # in driver tests

        parser = CtdpfJCsppParser(self.config.get(DataTypeKey.CTDPF_J_CSPP_RECOVERED),
                                  None, stream_handle,
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)

        particles = parser.get_records(20)

        log.debug("*** test_simple Num particles %s", len(particles))

        # load a dictionary from the yml file
        test_data = self.get_dict_from_yml('11079364_PPB_CTD_recov.yml')

        # check all the values against expected results.

        for i in range(len(particles)):

            self.assert_result(test_data['data'][i], particles[i])

        stream_handle.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles
        Assert that we have the correct number of particles
        """
        file_path = os.path.join(RESOURCE_PATH, RECOVERED_SAMPLE_DATA)
        stream_handle = open(file_path, 'r')

        # Note: since the recovered and telemetered parser and particles are common
        # to each other, testing one is sufficient, will be completely tested
        # in driver tests

        parser = CtdpfJCsppParser(self.config.get(DataTypeKey.CTDPF_J_CSPP_RECOVERED),
                                  None, stream_handle,
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)

        # try to get 2000 particles, 1999 data records plus one meta data
        particles = parser.get_records(2000)

        log.debug("*** test_get_many Num particles %s", len(particles))
        self.assertEqual(len(particles), 2000)

        stream_handle.close()

    def test_mid_state_start(self):
        """
        This test makes sure that we retrieve the correct particles upon starting with an offset state.
        """

        file_path = os.path.join(RESOURCE_PATH, RECOVERED_SAMPLE_DATA)
        stream_handle = open(file_path, 'rb')

        # position 309 is the beginning of the second data record, which would have produced the
        # metadata particle and the first instrument particle
        initial_state = {StateKey.POSITION: 309, StateKey.METADATA_EXTRACTED: True}

        parser = CtdpfJCsppParser(self.config.get(DataTypeKey.CTDPF_J_CSPP_RECOVERED),
                                  initial_state, stream_handle,
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)

        # expect to get the 2nd and 3rd instrument particles next
        particles = parser.get_records(2)

        log.debug("Num particles: %s", len(particles))

        self.assertTrue(len(particles) == 2)

        expected_results = self.get_dict_from_yml('mid_state_start.yml')

        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i], particles[i])

        # now expect the state to be the beginning of 5th data record and metadata sent
        the_new_state = {StateKey.POSITION: 403, StateKey.METADATA_EXTRACTED: True}
        log.debug("********** expected state: %s", the_new_state)
        log.debug("******** new parser state: %s", parser._state)
        self.assertTrue(parser._state == the_new_state)

        stream_handle.close()

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        file_path = os.path.join(RESOURCE_PATH, RECOVERED_SAMPLE_DATA)
        stream_handle = open(file_path, 'r')

        # The yml file has the metadata and the first 19
        # instrument particles in it
        expected_results = self.get_dict_from_yml('11079364_PPB_CTD_recov.yml')

        parser = CtdpfJCsppParser(self.config.get(DataTypeKey.CTDPF_J_CSPP_RECOVERED),
                                  None, stream_handle,
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)

        particles = parser.get_records(2)

        log.debug("Num particles: %s", len(particles))

        self.assertTrue(len(particles) == 2)

        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i], particles[i])

        # position 1061 is the byte at the start of the 18th data record
        new_state = {StateKey.POSITION: 1061, StateKey.METADATA_EXTRACTED: True}

        parser.set_state(new_state)

        particles = parser.get_records(2)

        self.assertTrue(len(particles) == 2)

        # offset in the expected results, into the 18th result
        offset = 18
        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i + offset], particles[i])

        stream_handle.close()

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists and a RecoverableSampleException is thrown.
        Note: every other data record has bad data (float instead of int, extra column etc.)
        """

        file_path = os.path.join(RESOURCE_PATH, '11079364_BAD_PPB_CTD.txt')
        stream_handle = open(file_path, 'rb')

        log.info(self.exception_callback_value)

        parser = CtdpfJCsppParser(self.config.get(DataTypeKey.CTDPF_J_CSPP_RECOVERED),
                                  None, stream_handle,
                                  self.state_callback, self.pub_callback,
                                  self.exception_callback)

        parser.get_records(1)

        log.info("Exception callback value: %s", self.exception_callback_value)

        self.assertTrue(self.exception_callback_value is not None)

        for i in range(len(self.exception_callback_value)):
            self.assert_(isinstance(self.exception_callback_value[i], RecoverableSampleException))

        # 14 bad records
        self.assertEqual(self.count, 12)
        stream_handle.close()
