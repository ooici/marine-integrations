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
                             'driver', 'moas', 'gl', 'adcpa', 'resource')


@attr('UNIT', group='mi')
class AdcpsMGliderParserUnitTestCase(ParserUnitTestCase):
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
        self.config = {DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.adcpa_m_glider',
                       DataSetDriverConfigKeys.PARTICLE_CLASS: 'AdcpaMGliderInstrumentParticle'}
        # Define test data particles and their associated timestamps which will be
        # compared with returned results

        self.start_state = {StateKey.POSITION: 0}

        self.fid_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

        #test01 data was all manually verified against the IDD
        #and double checked with PD0decoder_v2 MATLAB tool
        self.test01 = {}
        self.test01['ensemble_number'] = 1
        self.test01['real_time_clock'] = [12, 1, 10, 16, 36, 14, 30]
        self.test01['internal_timestamp'] = 3535202174.30000
        self.test01['ensemble_start_time'] = 3535202174.30000
        self.test01['echo_intensity_beam1'] = [114, 96, 84, 74, 73, 71, 68, 68, 68, 68, 67, 67, 67, 66, 66]
        self.test01['correlation_magnitude_beam1'] = [106, 126, 106, 89, 66, 49, 40, 34, 24, 17, 15, 12, 0, 0, 0]
        self.test01['percent_good_3beam'] = [0, 0, 20, 100, 40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.test01['water_velocity_east'] = [23, 23, 45, 110, 68, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768]
        self.test01['water_velocity_north'] = [-62, -62, -53, -27, -17, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768]
        self.test01['water_velocity_up'] = [84, 84, 84, 86, 53, -32768, -32768, -32768, -32768, -32768,
                                            -32768, -32768, -32768, -32768, -32768]
        self.test01['error_velocity'] = [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768, -32768, -32768, -32768, -32768, -32768]

        #test02 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 1 of file LA101636_20.PD0
        self.test02 = {}
        self.test02['ensemble_number'] = 1
        self.test02['real_time_clock'] = [12, 1, 10, 16, 36, 14, 30]
        self.test02['heading'] = 33710
        self.test02['pitch'] = 2739
        self.test02['roll'] = -149
        self.test02['water_velocity_east'] = [23, 23, 45, 110, 68, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768]

        self.test02['water_velocity_north'] = [-62, -62, -53, -27, -17, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768]
        self.test02['water_velocity_up'] = [84, 84, 84, 86, 53, -32768, -32768, -32768, -32768, -32768,
                                            -32768, -32768, -32768, -32768, -32768]
        self.test02['error_velocity'] = [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768, -32768, -32768, -32768, -32768, -32768]


        #test03 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 20 of file LA101636_20.PD0
        self.test03 = {}
        self.test03['ensemble_number'] = 20
        self.test03['real_time_clock'] = [12, 1, 10, 16, 36, 44, 98]
        self.test03['heading'] = 33710
        self.test03['pitch'] = 2739
        self.test03['roll'] = -149
        self.test03['water_velocity_east'] = [-23, -23, -1, -35, -32768, -32768, -32768, -32768, -32768, -32768,
                                              -32768, -32768, -32768, -32768, -32768]

        self.test03['water_velocity_north'] = [62, 62, 71, 8, -32768, -32768, -32768, -32768, -32768,
                                               -32768, -32768, -32768, -32768, -32768, -32768]
        self.test03['water_velocity_up'] = [-84, -84, -83, -27, -32768, -32768, -32768, -32768, -32768, -32768,
                                            -32768, -32768, -32768, -32768, -32768]
        self.test03['error_velocity'] = [0, 0, 0, -32768, -32768, -32768, -32768, -32768, -32768,
                                         -32768, -32768, -32768, -32768, -32768, -32768]

        #test04 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 28 of file LA101636_20.PD0
        self.test04 = {}
        self.test04['ensemble_number'] = 28
        self.test04['real_time_clock'] = [12, 2, 18, 2, 10, 52, 98]
        self.test04['heading'] = 8290
        self.test04['pitch'] = 3080
        self.test04['roll'] = -209

        #test05 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 2 of file LA101636_20.PD00
        self.test05 = {}
        self.test05['ensemble_number'] = 2
        self.test05['real_time_clock'] = [12, 2, 18, 2, 10, 10, 93]
        self.test05['heading'] = 8290
        self.test05['pitch'] = 3080
        self.test05['roll'] = -209

        #test05 data was extracted using the PD0decoder_v2 MATLAB tool
        #ensemble 3 of file LA101636_20.PD00 & of the corrupted version of
        #the data file LB180210_3_corrupted.PD0
        self.test06 = {}
        self.test06['ensemble_number'] = 3
        self.test06['real_time_clock'] = [12, 2, 18, 2, 10, 12, 47]
        self.test06['heading'] = 8290
        self.test06['pitch'] = 3080
        self.test06['roll'] = -209


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
        fid = open(os.path.join(RESOURCE_PATH, 'LB180210_50.PD0'), 'rb')

        self.stream_handle = fid
        self.parser = AdcpPd0Parser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(50)

        self.particle_to_yml(particles, 'LB180210_50.yml')
        fid.close()

    def trim_file(self):
        """
        This utility routine can be used to trim large PD0 files down
        to a more manageable size.  It uses the sieve in the parser to
        create a copy of the file with a specified number of records
        """

        #define these values as needed

        input_file = 'LB180210.PD0'
        output_file = 'LB180210_3.PD0'
        num_rec = 3
        first_rec = 1
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

        #LA101636.PD0 was attached to the IDD and used to verify earlier
        #versions of this parser
        fid = open(os.path.join(RESOURCE_PATH, 'LA101636.PD0'), 'rb')

        self.stream_handle = fid
        self.parser = AdcpPd0Parser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(1)

        log.debug('got back %d particles', len(particles))

        self.assert_result(self.test01, particles[0])

        fid.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """

        #LA101636_20.PD0 has 20 records in it
        fid = open(os.path.join(RESOURCE_PATH, 'LA101636_20.PD0'), 'rb')

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
        #LB180210_50.PD0 has 50 records in it
        fid = open(os.path.join(RESOURCE_PATH, 'LB180210_50.PD0'), 'rb')

        self.stream_handle = fid

        new_state = {StateKey.POSITION: 12042}
        #ensembles in this file are 446 bytes long
        #the first record found should be number 28 at byte 12042

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
         #LB180210_50.PD0 has 50 records in it
        fid = open(os.path.join(RESOURCE_PATH, 'LB180210_50.PD0'), 'rb')

        self.stream_handle = fid

        new_state = {StateKey.POSITION: 446}
        #ensembles in this file are 446 bytes long
        #the first record found should be number 2 at byte 446

        self.parser = AdcpPd0Parser(self.config, new_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        particles = self.parser.get_records(1)
        #just get 1 record
        self.assert_result(self.test05, particles[0])

        new_state = {StateKey.POSITION: 12042}
        #ensembles in this file are 446 bytes long
        #the first record found should be number 28 at byte 12042

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
        #LB180210_3_corrupted.PD0 has three records in it, the 2nd record was corrupted
        fid = open(os.path.join(RESOURCE_PATH, 'LB180210_3_corrupted.PD0'), 'rb')

        self.stream_handle = fid
        self.parser = AdcpPd0Parser(self.config, self.start_state, self.stream_handle,
                                    self.state_callback, self.pub_callback, self.exception_callback)

        #try to get 3 particles, should only get 2 back
        #the second one should correspond to ensemble 3
        particles = self.parser.get_records(3)
        self.assert_result(self.test06, particles[1])

        fid.close()
