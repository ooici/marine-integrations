#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_wfp_eng_wfp_sio_mule
@file marine-integrations/mi/dataset/parser/test/test_wfp_eng_wfp_sio_mule.py
@author Mark Worden
@brief Test code for a wfp_eng_wfp_sio_mule data parser
"""

from nose.plugins.attrib import attr

import os
import numpy
import yaml

from mi.core.log import get_logger
log = get_logger()
from mi.idk.config import Config

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.wfp_eng_wfp_sio_mule import WfpEngWfpSioMuleParser
from mi.dataset.parser.wfp_eng_wfp_sio_mule import WfpEngWfpSioMuleParserDataEngineeringParticleKey, \
    WfpEngWfpSioMuleParserDataStartTimeParticleKey, WfpEngWfpSioMuleParserDataStatusParticleKey

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset', 'driver', 'WFP_ENG', 'wfp', 'resource')


# The list of generated tests are the suggested tests, but there may
# be other tests needed to fully test your parser


@attr('UNIT', group='mi')
class WfpEngWfpSioMuleParserUnitTestCase(ParserUnitTestCase):
    """
    wfp_eng_wfp_sio_mule Parser unit test suite
    """

    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to match what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.wfp_eng_wfp_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: None
        }
        # Define test data particles and their associated timestamps which will be
        # compared with returned results

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

        self.test_eng_particle1 = {'internal_timestamp': 3583889968.0, 
                                   WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_TIMESTAMP: 1374901168,
                                   WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_CURRENT: 295.3860778808594,
                                   WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_VOLTAGE: 10.81559944152832,
                                   WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_PRESSURE: 2335.27001953125}

        self.test_eng_particle2 = {'internal_timestamp': 3583825326.0,
                                   WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_TIMESTAMP: 1374836526,
                                   WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_CURRENT: 0.0,
                                   WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_VOLTAGE:
                                       11.584400177001953,
                                   WfpEngWfpSioMuleParserDataEngineeringParticleKey.WFP_PROF_PRESSURE: 0.0}

        self.test_start_particle1 = {'internal_timestamp': 3583954925.0,
                                     WfpEngWfpSioMuleParserDataStartTimeParticleKey.CONTROLLER_TIMESTAMP: 1374973536,
                                     WfpEngWfpSioMuleParserDataStartTimeParticleKey.WFP_PROFILE_START: 1374966125,
                                     WfpEngWfpSioMuleParserDataStartTimeParticleKey.WFP_SENSOR_START: 1374966002}

        self.test_status_particle1 = {'internal_timestamp': 3583826263.0,
                                      WfpEngWfpSioMuleParserDataStatusParticleKey.CONTROLLER_TIMESTAMP: 1374837724,
                                      WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_INDICATOR: -1,
                                      WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_RAMP_STATUS: 0,
                                      WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_PROFILE_STATUS: 14,
                                      WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_PROFILE_STOP: 1374837463,
                                      WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_SENSOR_STOP: 1374837591,
                                      WfpEngWfpSioMuleParserDataStatusParticleKey.WFP_DECIMATION_FACTOR: None}

    def test_simple(self):
        """
        Read test data and pull out 5 data particles. Then examine each particle against its expected result.
        Assert that the results are those we expected.
        """
        file_path = os.path.join(RESOURCE_PATH, 'wfp_eng_wfp_sio_mule_small.DAT')

        # Obtain statistics on the test sample file
        stat_info = os.stat(file_path)

        # Init the state to declare the UNPROCESSED_DATA as the full length of the file
        state = {
            StateKey.UNPROCESSED_DATA: [[0, stat_info.st_size]],
            StateKey.IN_PROCESS_DATA: [],
            StateKey.FILE_SIZE: stat_info.st_size
        }

        # Open the file holding the test sample data
        stream_handle = open(file_path, 'rb')

        self.parser = WfpEngWfpSioMuleParser(self.config, state, stream_handle,
                                             self.state_callback, self.pub_callback, self.exception_callback)

        # Attempt to retrieve 5 particles
        particles = self.parser.get_records(5)

        # Close the file stream as we don't need it anymore
        stream_handle.close()

        # Make sure we obtained 5 particles
        self.assertTrue(len(particles) == 5)

        # Obtain the expected 5 samples from a yml file
        test_data = self.get_dict_from_yml('first_five.yml')

        index = 0
        for particle in particles:
            log.info(particle.generate_dict())

            # Make sure each retrieved sample matches its expected result
            self.assert_result(test_data['data'][index], particles[index])

            index += 1

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """
        file_path = os.path.join(RESOURCE_PATH, 'node58p1.dat')

        # Obtain statistics on the test sample file
        stat_info = os.stat(file_path)

        # Init the state to declare the UNPROCESSED_DATA as the full length of the file
        state = {
            StateKey.UNPROCESSED_DATA: [[0, stat_info.st_size]],
            StateKey.IN_PROCESS_DATA: [],
            StateKey.FILE_SIZE: stat_info.st_size
        }

        # Open the file holding the test sample data
        stream_handle = open(file_path, 'rb')

        self.parser = WfpEngWfpSioMuleParser(self.config, state, stream_handle,
                                             self.state_callback, self.pub_callback, self.exception_callback)

        # Attempt to retrieve 30 particles
        particles = self.parser.get_records(30)

        log.info(len(particles))

        # Make sure we obtained 30 particles
        self.assertTrue(len(particles) == 30)

        for particle in particles:
            log.info(particle.generate_dict())

        # Compare one of the particles to its expected result
        self.assert_result(self.test_eng_particle1, particles[28])

        # Attempt to retrieve 50 particles
        particles = self.parser.get_records(50)

        # Make sure we obtained 50 particles
        self.assertTrue(len(particles) == 50)

        for particle in particles:
            log.info(particle.generate_dict())

        # Compare one of the particles to its expected result
        self.assert_result(self.test_start_particle1, particles[48])

        stream_handle.close()

    def test_long_stream(self):
        """
        Test a long stream
        """
        file_path = os.path.join(RESOURCE_PATH, 'node58p1.dat')

        # Obtain statistics on the test sample file
        stat_info = os.stat(file_path)

        # Init the state to declare the UNPROCESSED_DATA as the full length of the file
        state = {
            StateKey.UNPROCESSED_DATA: [[0, stat_info.st_size]],
            StateKey.IN_PROCESS_DATA: [],
            StateKey.FILE_SIZE: stat_info.st_size
        }

        # Open the file holding the test sample data
        stream_handle = open(file_path, 'rb')

        self.parser = WfpEngWfpSioMuleParser(self.config, state, stream_handle,
                                             self.state_callback, self.pub_callback, self.exception_callback)

        # Attempt to retrieve 200000 particles
        particles = self.parser.get_records(20000)

        # There is NOT 20000 in the file.  Make sure we obtained 11456 particles.
        self.assertTrue(len(particles) == 11456)

        # Close the file stream as we don't need it anymore
        stream_handle.close()

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        file_path = os.path.join(RESOURCE_PATH, 'wfp_eng_wfp_sio_mule_small.DAT')
        
        # Obtain statistics on the test sample file
        stat_info = os.stat(file_path)

        # Init the state to declare the UNPROCESSED_DATA as one WE chunk.  Declare the IN_PROCESS_DATA as the one WE
        # chunk that has 5 samples with 1 of the samples as returned.
        initial_state = {
            StateKey.UNPROCESSED_DATA: [[2818, 2992]],
            StateKey.IN_PROCESS_DATA: [[2818, 2982, 5, 1]],
            StateKey.FILE_SIZE: stat_info.st_size
        }

        # Open the file holding the test sample data
        stream_handle = open(file_path, 'rb')

        self.parser = WfpEngWfpSioMuleParser(self.config, initial_state, stream_handle,
                                             self.state_callback, self.pub_callback, self.exception_callback)

        # Attempt to retrieve 1 particle
        particles = self.parser.get_records(1)

        # Make sure we obtained 1 particle
        self.assertTrue(len(particles) == 1)

        # Compare the particle to its expected result
        self.assert_result(self.test_status_particle1, particles[0])

        stream_handle.close()

    def test_start_stop_set_state_and_resume(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        file_path = os.path.join(RESOURCE_PATH, 'wfp_eng_wfp_sio_mule_small.DAT')

        # Obtain statistics on the test sample file
        stat_info = os.stat(file_path)

        # Init the state to declare the UNPROCESSED_DATA as the full length of the file
        initial_state = {
            StateKey.UNPROCESSED_DATA: [[0, stat_info.st_size]],
            StateKey.IN_PROCESS_DATA: [],
            StateKey.FILE_SIZE: stat_info.st_size
        }

        # Open the file holding the test sample data
        stream_handle = open(file_path, 'rb')

        self.parser = WfpEngWfpSioMuleParser(self.config, initial_state, stream_handle,
                                             self.state_callback, self.pub_callback, self.exception_callback)

        # Attempt to retrieve 2 particles
        particles = self.parser.get_records(2)

        # Make sure we obtained 2 particles
        self.assertTrue(len(particles) == 2)

        # Create a new state to declare the UNPROCESSED_DATA as one chunk.  Declare the IN_PROCESS_DATA as one chunk
        # that has 5 samples with 4 of the samples as returned.
        new_state = {
            StateKey.UNPROCESSED_DATA: [[2818, 2992]],
            StateKey.IN_PROCESS_DATA: [[2818, 2982, 5, 4]],
            StateKey.FILE_SIZE: stat_info.st_size
        }

        # Re-set the parser's state
        self.parser.set_state(new_state)

        # Attempt to retrieve 2 particles
        particles = self.parser.get_records(2)

        # Make sure we only obtained 1 particle since the sample test file only holds one WE chunk with 5 total
        # samples with 4 already returned.
        self.assertTrue(len(particles) == 1)

        # Compare the retrieved particle to its expected result.
        self.assert_result(self.test_eng_particle2, particles[0])

        # Attempt to retrieve 1 particle
        particles = self.parser.get_records(1)

        # Make sure we obtained 0 particles
        self.assertTrue(len(particles) == 0)

        # Close the file stream as we don't need it anymore
        stream_handle.close()

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and 
        reading data, as if new data has been found and the state has
        changed
        """
        file_path = os.path.join(RESOURCE_PATH, 'node58p3.dat')

        # Obtain statistics on the test sample file
        stat_info = os.stat(file_path)

        # Init the state to declare the UNPROCESSED_DATA as the full length of the file
        initial_state = {
            StateKey.UNPROCESSED_DATA: [[0, stat_info.st_size]],
            StateKey.IN_PROCESS_DATA: [],
            StateKey.FILE_SIZE: stat_info.st_size
        }

        # Open the file holding the test sample data
        stream_handle = open(file_path, 'rb')

        self.parser = WfpEngWfpSioMuleParser(self.config, initial_state, stream_handle,
                                             self.state_callback, self.pub_callback, self.exception_callback)

        # Attempt to retrieve 3 particles
        particles = self.parser.get_records(3)

        # Make sure we obtained 3 particles
        self.assertTrue(len(particles) == 3)

        # Make sure the state indicates:
        # 1) The IN_PROCESSED_DATA includes two chunks with one chunk having 5 samples with 3 returned and the other
        # chunk with 20 samples and 0 returned.
        # 2) The UNPROCESSED_DATA includes 4 chunks.
        self.assert_state([[2818, 2982, 5, 3], [4059, 4673, 20, 0]], [[2818, 2982], [4058, 4673], [7423, 7424],
                                                                      [7594, 7623]])

        # Attempt to retrieve 30 particles
        particles = self.parser.get_records(30)

        # Make sure we obtained 22 particles
        self.assertTrue(len(particles) == 22)

        # Make sure the parser's new state indicates that there 3 remaining chunks in the UNPROCESSED_DATA, none of
        # which have WE samples.
        self.assert_state([], [[4058, 4059], [7423, 7424], [7594, 7623]])

        # Create a new state to declare the UNPROCESSED_DATA including 4 chunks.  Declare the IN_PROCESS_DATA as
        # the two chunks with WE samples one having 5 samples with 3 returned and the other having 20 samples with
        # 0 returned.
        new_state = {StateKey.UNPROCESSED_DATA: [[2818, 2982], [4058, 4673], [7423, 7424], [7594, 7623]],
                     StateKey.IN_PROCESS_DATA: [[2818, 2982, 5, 3], [4059, 4673, 20, 0]],
                     StateKey.FILE_SIZE: stat_info.st_size}

        # Re-set the parser's state
        self.parser.set_state(new_state)

        # Attempt to retrieve 2 particles
        particles = self.parser.get_records(2)

        # Make sure we obtained 2 particles
        self.assertTrue(len(particles) == 2)

        # Make sure the state indicates:
        # 1) The IN_PROCESSED_DATA includes one chunk with 20 samples and 0 returned.
        # 2) The UNPROCESSED_DATA includes 3 chunks within one corresponding to the chunk with WE samples.  The
        # other two chunks contain invalid data.
        self.assert_state([[4059, 4673, 20, 0]], [[4058, 4673], [7423, 7424], [7594, 7623]])

        # Close the file stream as we don't need it anymore
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

        log.info(particle_dict)

        #for efficiency turn the particle values list of dictionaries into a dictionary
        particle_values = {}
        for param in particle_dict.get('values'):
            particle_values[param['value_id']] = param['value']

        # compare each key in the test to the data in the particle
        for key in test:

            log.info("key: %s", key)

            test_data = test[key]

            #get the correct data to compare to the test
            if key == 'internal_timestamp':
                particle_data = particle.get_value('internal_timestamp')
                #the timestamp is in the header part of the particle

                log.info("internal_timestamp %d", particle_data)

            else:
                particle_data = particle_values.get(key)
                #others are all part of the parsed values part of the particle

            if particle_data is None:
                #generally OK to ignore index keys in the test data, verify others

                log.warning("\nWarning: assert_result ignoring test key %s, does not exist in particle", key)
            else:
                log.info("test_data %s - particle_data %s", test_data, particle_data)
                if isinstance(test_data, float):
                    # slightly different test for these values as they are floats.
                    compare = numpy.abs(test_data - particle_data) <= 1e-5
                    self.assertTrue(compare)
                else:
                    # otherwise they are all ints and should be exactly equal
                    self.assertEqual(test_data, particle_data)

    def get_dict_from_yml(self, filename):
        """
        This utility routine loads the contents of a yml file
        into a dictionary
        """

        fid = open(os.path.join(RESOURCE_PATH, filename), 'r')
        result = yaml.load(fid)
        fid.close()

        return result

    def assert_state(self, in_process_data, unprocessed_data):
        self.assertEqual(self.parser._state[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        self.assertEqual(self.state_callback_value[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)
