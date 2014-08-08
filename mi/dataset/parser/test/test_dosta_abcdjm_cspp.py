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
from StringIO import StringIO

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()

from mi.core.exceptions import SampleException
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

    def particle_to_yml(self, particles, filename, mode='w'):
        """
        This is added as a testing helper, not actually as part of the parser tests. Since the same particles
        will be used for the driver test it is helpful to write them to .yml in the same form they need in the
        results.yml fids here.
        """
        # open write append, if you want to start from scratch manually delete this fid
        fid = open(os.path.join(RESOURCE_PATH, filename), mode)

        fid.write('header:\n')
        fid.write("    particle_object: 'MULTIPLE'\n")
        fid.write("    particle_type: 'MULTIPLE'\n")
        fid.write('data:\n')

        for i in range(0, len(particles)):
            particle_dict = particles[i].generate_dict()

            fid.write('  - _index: %d\n' %(i+1))

            fid.write('    particle_object: %s\n' % particles[i].__class__.__name__)
            fid.write('    particle_type: %s\n' % particle_dict.get('stream_name'))
            fid.write('    internal_timestamp: %f\n' % particle_dict.get('internal_timestamp'))

            for val in particle_dict.get('values'):
                if isinstance(val.get('value'), float):
                    fid.write('    %s: %16.6f\n' % (val.get('value_id'), val.get('value')))
                elif isinstance(val.get('value'), str):
                    fid.write("    %s: '%s'\n" % (val.get('value_id'), val.get('value')))
                else:
                    fid.write('    %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()

    def create_yml(self):
        """
        This utility creates a yml file
        """

        fid = open(os.path.join(RESOURCE_PATH, '11194982_PPD_OPT.txt'))
        test_buffer = fid.read()
        fid.close()

        self.stream_handle = StringIO(test_buffer)
        self.parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_TELEMETERED),
                                            None, self.stream_handle,
                                            self.state_callback, self.pub_callback,
                                            self.exception_callback)

        particles = self.parser.get_records(20)

        log.info("Exception callback value: %s", self.exception_callback_value)

        self.particle_to_yml(particles, '11194982_PPD_OPT.yml')

    def test_simple(self):
        """
        Read test data and pull out data particles.
        Assert that the results are those we expected.
        """
        file_path = os.path.join(RESOURCE_PATH, '11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(5)

        log.info("Exception callback value: %s", self.exception_callback_value)

        self.assertTrue(self.exception_callback_value is None)

        self.assertTrue(len(particles) == 5)

        expected_results = self.get_dict_from_yml('11079894_PPB_OPT.yml')

        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i], particles[i])

        stream_handle.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """

        file_path = os.path.join(RESOURCE_PATH, '11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        # Let's attempt to retrieve 20 particles
        particles = parser.get_records(20)

        log.info("Exception callback value: %s", self.exception_callback_value)

        # Should end up with 20 particles
        self.assertTrue(len(particles) == 20)

        expected_results = self.get_dict_from_yml('11079894_PPB_OPT.yml')
        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i], particles[i])

    def test_long_stream(self):
        """
        Test a long stream 
        """

        file_path = os.path.join(RESOURCE_PATH, '11079364_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        # Let's attempt to retrieve 2000 particles
        particles = parser.get_records(300)

        log.info("Num particles: %s", len(particles))

        log.info("Exception callback value: %s", self.exception_callback_value)

        # Should end up with 272 particles
        self.assertTrue(len(particles) == 272)

        stream_handle.close()

    def test_state_after_one_record_retrieval(self):
        """
        This test makes sure that we get the correct particles upon requesting one record at
        a time.
        """

        expected_results = self.get_dict_from_yml('11079894_PPB_OPT.yml')

        file_path = os.path.join(RESOURCE_PATH, '11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')
    
        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)
    
        log.info("Num particles: %s", len(particles))
    
        self.assertTrue(len(particles) == 1)
    
        log.info("11111111 Read State: %s", parser._read_state)
        log.info("11111111 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][0], particles[0])
        
        new_state = copy.copy(parser._state)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        log.info("22222222 Read State: %s", parser._read_state)
        log.info("22222222 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 332, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][1], particles[0])

        new_state = copy.copy(parser._state)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        log.info("33333333 Read State: %s", parser._read_state)
        log.info("33333333 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 425, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][2], particles[0])

        new_state = copy.copy(parser._state)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        log.info("44444444 Read State: %s", parser._read_state)
        log.info("44444444 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 518, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][3], particles[0])

        new_state = copy.copy(parser._state)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        log.info("55555555 Read State: %s", parser._read_state)
        log.info("55555555 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 611, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][4], particles[0])

    def test_state_after_two_record_retrievals(self):
        """
        This test makes sure that we get the correct particles upon requesting two records at
        a time.
        """

        expected_results = self.get_dict_from_yml('11079894_PPB_OPT.yml')

        file_path = os.path.join(RESOURCE_PATH, '11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(2)

        log.info("Num particles: %s", len(particles))

        self.assertTrue(len(particles) == 2)

        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i], particles[i])

        log.info("11111111 Read State: %s", parser._read_state)
        log.info("11111111 State: %s", parser._state)

        the_new_state = {StateKey.POSITION: 332, StateKey.METADATA_EXTRACTED: True}
        log.info("11111111 new parser state: %s", the_new_state)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       the_new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(2)

        log.info("Num particles: %s", len(particles))

        self.assertTrue(len(particles) == 2)

        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i+2], particles[i])

        log.info("22222222 Read State: %s", parser._read_state)
        log.info("22222222 State: %s", parser._state)

        the_new_state = {StateKey.POSITION: 480, StateKey.METADATA_EXTRACTED: True}
        log.info("22222222 new parser state: %s", the_new_state)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       the_new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(2)

        log.info("Num particles: %s", len(particles))

        self.assertTrue(len(particles) == 2)

        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i+4], particles[i])

        log.info("33333333 Read State: %s", parser._read_state)
        log.info("33333333 State: %s", parser._state)

    def test_position_and_metadata_extracted_state(self):
        """
        This test makes sure that we retrieve the metadata record upon resetting the state position to 0
        and setting the METADATA_EXTRACTED to False.
        """

        expected_results = self.get_dict_from_yml('11079894_PPB_OPT.yml')

        file_path = os.path.join(RESOURCE_PATH, '11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        log.info("Num particles: %s", len(particles))

        self.assertTrue(len(particles) == 1)

        log.info("11111111 Read State: %s", parser._read_state)
        log.info("11111111 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][0], particles[0])

        new_state = {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: False}

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        self.assertTrue(len(particles) == 1)

        log.info("22222222 Read State: %s", parser._read_state)
        log.info("22222222 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][0], particles[0])

        new_state = {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: True}

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        self.assertTrue(len(particles) == 1)

        log.info("22222222 Read State: %s", parser._read_state)
        log.info("22222222 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 332, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][1], particles[0])

    def test_midstate_start(self):
        """
        This test makes sure that we retrieve the correct particles upon starting with an offsetted state.
        """
        expected_results = self.get_dict_from_yml('11079894_PPB_OPT.yml')

        file_path = os.path.join(RESOURCE_PATH, '11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        initial_state = {StateKey.POSITION: 332, StateKey.METADATA_EXTRACTED: True}

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       initial_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(2)

        log.info("Num particles: %s", len(particles))

        self.assertTrue(len(particles) == 2)

        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i+2], particles[i])

        log.info("******** Read State: %s", parser._read_state)
        log.info("******** State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 518, StateKey.METADATA_EXTRACTED: True})

    def test_state_reset(self):
        """
        This test makes sure that we retrieve the correct particles upon resetting the state to a prior position.
        """
        expected_results = self.get_dict_from_yml('11079894_PPB_OPT.yml')

        file_path = os.path.join(RESOURCE_PATH, '11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        log.info("Num particles: %s", len(particles))

        self.assertTrue(len(particles) == 1)

        log.info("11111111 Read State: %s", parser._read_state)
        log.info("11111111 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][0], particles[0])

        new_state = copy.copy(parser._state)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        log.info("22222222 Read State: %s", parser._read_state)
        log.info("22222222 State: %s", parser._state)

        self.assertTrue(len(particles) == 1)

        self.assertTrue(parser._state == {StateKey.POSITION: 332, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][1], particles[0])

        new_state = copy.copy(parser._state)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(1)

        log.info("33333333 Read State: %s", parser._read_state)
        log.info("33333333 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 425, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][2], particles[0])

        new_state = {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: True}

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       new_state, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        # Now retrieve two particles.  We should end up with the metadata and first data record
        particles = parser.get_records(1)

        log.info("44444444 Read State: %s", parser._read_state)
        log.info("44444444 State: %s", parser._state)

        self.assertTrue(parser._state == {StateKey.POSITION: 332, StateKey.METADATA_EXTRACTED: True})

        self.assert_result(expected_results['data'][1], particles[0])

    def test_bad_data_record(self):
        """
        Ensure that bad data is skipped when it exists.
        """

        file_path = os.path.join(RESOURCE_PATH, 'BadDataRecord_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        log.info(self.exception_callback_value)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        parser.get_records(1)

        log.info("Exception callback value: %s", self.exception_callback_value)

        self.assertTrue(self.exception_callback_value is not None)

        stream_handle.close()

    def test_bad_header_source_file_name(self):
        """
        Ensure that bad data is skipped when it exists.
        """

        file_path = os.path.join(RESOURCE_PATH, 'BadHeaderSourceFileName_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        log.info(self.exception_callback_value)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        parser.get_records(1)

        log.info("Exception callback value: %s", self.exception_callback_value)

        self.assertTrue(self.exception_callback_value != None)

        stream_handle.close()

    def test_bad_header_start_date(self):
        """
        Ensure that bad data is skipped when it exists.
        """

        file_path = os.path.join(RESOURCE_PATH, 'BadHeaderProcessedData_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        log.info(self.exception_callback_value)

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        with self.assertRaises(SampleException):
            parser.get_records(1)

        stream_handle.close()

    def test_linux_source_path_handling(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """
        file_path = os.path.join(RESOURCE_PATH, 'linux_11079894_PPB_OPT.txt')
        stream_handle = open(file_path, 'rb')

        parser = DostaAbcdjmCsppParser(self.config.get(DataTypeKey.DOSTA_ABCDJM_CSPP_RECOVERED),
                                       None, stream_handle,
                                       self.state_callback, self.pub_callback,
                                       self.exception_callback)

        particles = parser.get_records(5)

        self.assertTrue(len(particles) == 5)

        expected_results = self.get_dict_from_yml('linux.yml')

        for i in range(len(particles)):
            self.assert_result(expected_results['data'][i], particles[i])

        stream_handle.close()

    def assert_result(self, test, particle):
        """
        Suite of tests to run against each returned particle and expected
        results of the same.  The test parameter should be a dictionary
        that contains the keys to be tested in the particle
        the 'internal_timestamp' and StateKey.POSITION keys are
        treated differently than others but can be verified if supplied
        """

        particle_dict = particle.generate_dict()

        #for efficiency turn the particle values list of dictionaries into a dictionary
        particle_values = {}
        for param in particle_dict.get('values'):
            particle_values[param['value_id']] = param['value']

        # compare each key in the test to the data in the particle
        for key in test:
            expected_results = test[key]

            #get the correct data to compare to the test
            if key == 'internal_timestamp':
                particle_data = particle.get_value('internal_timestamp')
                #the timestamp is in the header part of the particle

                # log.info("internal_timestamp %.10f", particle_data)

            else:
                particle_data = particle_values.get(key)
                #others are all part of the parsed values part of the particle

            if particle_data is None:
                #generally OK to ignore index keys in the test data, verify others

                log.warning("\nWarning: assert_result ignoring test key %s, does not exist in particle", key)
            else:
                log.info("Key: %s", key)
                log.info("Expected Results Type: %s: ", type(expected_results))
                if isinstance(expected_results, float):
                    # log.info("Expected data: %.10f", expected_results)
                    # log.info("Actual data: %.10f", particle_data)
                    # slightly different test for these values as they are floats.
                    compare = numpy.abs(expected_results - particle_data) <= 1e-5
                    self.assertTrue(compare)
                else:
                    # log.info("Expected data: %s", expected_results)
                    # log.info("Actual data: %s", particle_data)
                    # otherwise they are all ints and should be exactly equal
                    self.assertEqual(expected_results, particle_data)

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