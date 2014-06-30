#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_adcp_jln
@fid marine-integrations/mi/dataset/parser/test/test_adcps_jln.py
@author Jeff Roy
@brief Test code for a Adcps_jln data parser
Parts of this test code were taken from test_adcpa.py
Due to the nature of the records in PD0 files, (large binary records with hundreds of parameters)
this code verifies select items in the parsed data particle
"""

from nose.plugins.attrib import attr
import yaml
import numpy
import os

from mi.core.log import get_logger; log = get_logger()
from mi.idk.config import Config
from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.adcp_pd0 import AdcpPd0Parser, StateKey

RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi', 'dataset',
                             'driver', 'adcps_jln', 'stc', 'resource')


@attr('UNIT', group='mi')
class AdcpsJlnParserUnitTestCase(ParserUnitTestCase):
    """
    Adcp_jln Parser unit test suite
    """
    def state_callback(self, state, fid_ingested):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state
        self.fid_ingested_value = fid_ingested

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def exception_callback(self, exception):
        """ Call back method to match what comes in via the exception callback """
        self.exception_callback_value = exception

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        self.config = {DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcps_jln',
                       DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpsJlnParticle'}
        # Define test data particles and their associated timestamps which will be
        # compared with returned results

        self.start_state = {StateKey.POSITION: 0}

        self.fid_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

        #test01 data was all manually verified against the IDD
        #and double checked with PD0decoder_v2 MATLAB tool
        self.test01 = {}
        self.test01['internal_timestamp'] = 3581719370.030000
        self.test01['ensemble_start_time'] = 3581719370.0299997329711914
        self.test01['echo_intensity_beam1'] = [89, 51, 44, 43, 43, 43, 43, 44, 43, 44, 43, 43, 44, 44, 44,
                                               43, 43, 44, 43, 44, 44, 43, 43, 44, 44, 44, 44, 44, 44, 44,
                                               43, 43, 43, 43, 43, 43, 43, 44, 44, 43, 44, 44, 43, 43, 44,
                                               43, 43, 44, 44, 43, 43, 44, 43, 43, 44]
        self.test01['correlation_magnitude_beam1'] = [68, 70, 18, 19, 17, 17, 20, 19, 17, 15, 17, 20, 16,
                                                      17, 16, 17, 17, 18, 18, 17, 17, 19, 18, 17, 17, 19,
                                                      19, 17, 16, 16, 18, 19, 19, 17, 19, 19, 19, 18, 20,
                                                      17, 19, 19, 17, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.test01['percent_good_3beam'] = [53, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                                             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.test01['water_velocity_east'] = [383, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        self.test01['water_velocity_north'] = [314, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768, -32768]
        self.test01['water_velocity_up'] = [459, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                            -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                            -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                            -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                            -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                            -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                            -32768]
        self.test01['error_velocity'] = [80, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768]
        #test02 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 1 of file ADCP_CCE1T_20.000
        self.test02 = {}
        self.test02['ensemble_number'] = 1
        self.test02['real_time_clock'] = [12, 9, 21, 0, 0, 0, 0]
        self.test02['heading'] = 21348
        self.test02['pitch'] = 4216
        self.test02['roll'] = 3980

        #test03 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 20 of file ADCP_CCE1T_20.000
        self.test03 = {}
        self.test03['ensemble_number'] = 20
        self.test03['real_time_clock'] = [12, 9, 21, 19, 0, 0, 0]
        self.test03['heading'] = 538
        self.test03['pitch'] = 147
        self.test03['roll'] = 221

        #test04 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 5 of file ADCP_CCE1T_20.000
        self.test04 = {}
        self.test04['ensemble_number'] = 6
        self.test04['real_time_clock'] = [12, 9, 21, 5, 0, 0, 0]
        self.test04['heading'] = 20127
        self.test04['pitch'] = 4218
        self.test04['roll'] = 3773

        #test05 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 2 of file ADCP_CCE1T_20.000
        self.test05 = {}
        self.test05['ensemble_number'] = 2
        self.test05['real_time_clock'] = [12, 9, 21, 1, 0, 0, 0]
        self.test05['heading'] = 28638
        self.test05['pitch'] = 4192
        self.test05['roll'] = 4004

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

            fid.write('  - _index: %d\n' % (i+1))

            fid.write('    particle_object: %s\n' % particles[i].__class__.__name__)
            fid.write('    particle_type: %s\n' % particle_dict.get('stream_name'))
            fid.write('    internal_timestamp: %f\n' % particle_dict.get('internal_timestamp'))

            for val in particle_dict.get('values'):
                if isinstance(val.get('value'), float):
                    fid.write('    %s: %16.16f\n' % (val.get('value_id'), val.get('value')))
                else:
                    fid.write('    %s: %s\n' % (val.get('value_id'), val.get('value')))
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

        #ADCP_data_20130702.PD0 has one record in it
        fid = open(os.path.join(RESOURCE_PATH, 'ADCP_CCE1T_21_40.000'), 'rb')

        self.stream_handle = fid
        self.parser = AdcpPd0Parser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(20)

        self.particle_to_yml(particles, 'ADCP_CCE1T_21_40.yml')
        fid.close()

    def trim_file(self):
        """
        This utility routine can be used to trim large PD0 files down
        to a more manageable size.  It uses the sieve in the parser to
        create a copy of the file with a specified number of records
        """

        #define these values as needed

        input_file = 'ADCP_CCE1T.000'
        output_file = 'ADCP_CCE1T_21_40.000'
        num_rec = 20
        first_rec = 21
        log.info("opening file")
        infid = open(os.path.join(RESOURCE_PATH, input_file), 'rb')
        in_buffer = infid.read()
        log.info("file read")
        stream_handle = infid
        #parser needs a stream handle even though it won't use it
        parser = AdcpPd0Parser(self.config, self.start_state, stream_handle,
                               self.state_callback, self.pub_callback, self.exception_callback)
        log.info("parser created, calling sieve")
        indices = parser.sieve_function(in_buffer)
        #get the start and ends of all the records
        log.info("sieve returned %d indeces", len(indices))
        if len(indices) < first_rec + num_rec:
            log.info('trim_file: not enough records in file no output created')
            return

        first_byte = indices[first_rec-1][0]
        last_byte = indices[first_rec-1 + num_rec-1][1]
        log.info('first byte is %d last_byte is %d', first_byte, last_byte)

        outfid = open(os.path.join(RESOURCE_PATH, output_file), 'wb')
        outfid.write(in_buffer[first_byte:last_byte])
        outfid.close()
        infid.close()

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
            elif key == 'position':
                particle_data = self.state_callback_value['position']
                #position corresponds to the position in the file
            else:
                particle_data = particle_values.get(key)
                #others are all part of the parsed values part of the particle

            if particle_data is None:
                #generally OK to ignore index keys in the test data, verify others

                log.warning("\nWarning: assert_result ignoring test key %s, does not exist in particle", key)
            else:
                if isinstance(test_data, float):
                    # slightly different test for these values as they are floats.
                    compare = numpy.abs(test_data - particle_data) <= 1e-5
                    self.assertTrue(compare)
                else:
                    # otherwise they are all ints and should be exactly equal
                    self.assertEqual(test_data, particle_data)

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        The contents of ADCP_data_20130702.000 are the expected results
        from the IDD.  These results for the that record were manually verified
        and are the entire parsed particle is represented in ADCP_data_20130702.yml
        """

        #ADCP_data_20130702.PD0 has one record in it
        fid = open(os.path.join(RESOURCE_PATH, 'ADCP_data_20130702.000'), 'rb')

        self.stream_handle = fid
        self.parser = AdcpPd0Parser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(1)

        #this simple test shows the 2 ways to verify results
        self.assert_result(self.test01, particles[0])

        test_data = self.get_dict_from_yml('ADCP_data_20130702.yml')
        self.assert_result(test_data['data'][0], particles[0])

        #close the file
        fid.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """

        #ADCP_CCE1T_20.000 has 20 records in it
        fid = open(os.path.join(RESOURCE_PATH, 'ADCP_CCE1T_20.000'), 'rb')

        self.stream_handle = fid
        self.parser = AdcpPd0Parser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(20)
        log.info('got back %d records', len(particles))

        self.assert_result(self.test02, particles[0])
        self.assert_result(self.test03, particles[19])

        fid.close()

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        #ADCP_CCE1T_20.000 has 20 records in it
        fid = open(os.path.join(RESOURCE_PATH, 'ADCP_CCE1T_20.000'), 'rb')

        self.stream_handle = fid

        new_state = {StateKey.POSITION: 6000}
        #ensembles in this file are 1254 bytes long
        #the first record found should be number 6 at byte 6270

        self.parser = AdcpPd0Parser(self.config, new_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(5)

        self.assert_result(self.test04, particles[0])

        fid.close()

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and
        reading data, as if new data has been found and the state has
        changed
        """
        #ADCP_CCE1T_20.000 has 20 records in it
        fid = open(os.path.join(RESOURCE_PATH, 'ADCP_CCE1T_20.000'), 'rb')

        self.stream_handle = fid

        new_state = {StateKey.POSITION: 100}
        #ensembles in this file are 1254 bytes long
        #the first record found should be number 2 at byte 1254

        self.parser = AdcpPd0Parser(self.config, new_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(1)
        #just get 1 record
        self.assert_result(self.test05, particles[0])

        new_state = {StateKey.POSITION: 6000}
        #ensembles in this file are 1254 bytes long
        #the first record found should be number 6 at byte 6270

        self.parser = AdcpPd0Parser(self.config, new_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(1)
        #just get 1 record
        self.assert_result(self.test04, particles[0])

        fid.close()

    def test_bad_data(self):
        """
        Ensure that bad data is skipped when it exists.
        """
        #ADCP_data_Corrupted.PD0 has one bad record followed by one good in it
        fid = open(os.path.join(RESOURCE_PATH, 'ADCP_data_Corrupted.000'), 'rb')

        self.stream_handle = fid
        self.parser = AdcpPd0Parser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(1)
        self.assert_result(self.test01, particles[0])

        fid.close()
