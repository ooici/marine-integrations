#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_sio_eng_sio_mule
@file marine-integrations/mi/dataset/parser/test/test_sio_eng_sio_mule.py
@author Mike Nicoletti
@brief Test code for a sio_eng_sio_mule data parser
"""

from nose.plugins.attrib import attr
import os
import ntplib

from mi.core.log import get_logger
log = get_logger()

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.parser.sio_mule_common import StateKey
from mi.dataset.parser.sio_eng_sio_mule import \
    SioEngSioMuleDataParticle, \
    SioEngSioRecoveredDataParticle, \
    SioEngSioMuleParser, \
    SioEngSioRecoveredParser, \
    ENG_MATCHER

from mi.idk.config import Config
RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
                             'dataset', 'driver', 'sio_eng',
                             'sio_mule', 'resource')
# The list of generated tests are the suggested tests, but there may
# be other tests needed to fully test your parser


@attr('UNIT', group='mi')
class SioEngSioMuleParserUnitTestCase(ParserUnitTestCase):
    """
    sio_eng_sio_mule Parser unit test suite
    """
    def state_callback(self, state):
        """ Call back method to watch what comes in via the position callback """
        self.state_callback_value = state

    def state_callback_recovered(self, state, ingested):
        """ Call back method to watch what comes in via the position callback for the recovered parser"""
        self.state_callback_recov_value = state

    def exception_callback(self, exception):
        """ Call back method to watch what comes in via the exception callback """
        self.exception_callback_value = exception

    def pub_callback(self, pub):
        """ Call back method to watch what comes in via the publish callback """
        self.publish_callback_value = pub

    def assert_particle(self, result_particle, particle):

        # raw data is the match result of comparing the chunk against the
        # Engineering data Regex.  Checking group 0 verifies it is the correct chunk
        self.assertEqual(result_particle.raw_data.group(0), particle.raw_data.group(0))

        # verify the timestamp is within the acceptable tolerance
        allowed_diff = .000001
        self.assertTrue(abs(result_particle.contents[DataParticleKey.INTERNAL_TIMESTAMP] -
                            particle.contents[DataParticleKey.INTERNAL_TIMESTAMP]) <= allowed_diff)

    def assert_result(self, result, in_process_data, unprocessed_data, particle, recov_flag=False):
        """
        print(result.raw_data)
        print(particle.raw_data)
        """

        # verify the raw data and timestamp of the result against expected particle data
        self.assert_particle(result[0], particle)

        # verify the state is correct
        self.assert_state(in_process_data, unprocessed_data, recov_flag)

    def assert_state(self, in_process_data, unprocessed_data, recov_flag=False):
        self.assertEqual(self._parser._state[StateKey.IN_PROCESS_DATA], in_process_data)
        self.assertEqual(self._parser._state[StateKey.UNPROCESSED_DATA], unprocessed_data)
        if recov_flag:
            self.assertEqual(self.state_callback_recov_value[StateKey.IN_PROCESS_DATA], in_process_data)
            self.assertEqual(self.state_callback_recov_value[StateKey.UNPROCESSED_DATA], unprocessed_data)
        else:
            self.assertEqual(self.state_callback_value[StateKey.IN_PROCESS_DATA], in_process_data)
            self.assertEqual(self.state_callback_value[StateKey.UNPROCESSED_DATA], unprocessed_data)

    def setUp(self):
        ParserUnitTestCase.setUp(self)
        
        self.telem_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.sio_eng_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'SioEngSioMuleDataParticle'
        }

        self.recov_config = {
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.sio_eng_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: 'SioEngSioRecoveredDataParticle'
        }

        # Define test data particles and their associated timestamps which will be 
        # compared with returned results

        # using the particle class constuctor and the Engineering data matcher to retain as
        # as much of the old test structure as possible JAR
        posix_time = int('51EC763C', 16)
        self._timestamp1 = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_a = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0018u51EC763C_04_8D91\x02\n18.95 15.9 1456 308 -2\n\x03'),
            internal_timestamp=self._timestamp1)

        posix_time = int('51EC844C', 16)
        self._timestamp2 = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_b = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0018u51EC844C_0D_9AE3\x02\n18.96 15.7 1499 318 -2\n\x03'),
            internal_timestamp=self._timestamp2)

        posix_time = int('51EC925D', 16)
        self._timestamp3 = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_c = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0018u51EC925D_16_BD7E\x02\n18.95 15.8 1542 328 -2\n\x03'),
            internal_timestamp=self._timestamp3)

        posix_time = int('51ECA06D', 16)
        self._timestamp4 = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_d = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0018u51ECA06D_1F_B90E\x02\n18.94 16.0 1586 338 -2\n\x03'),
            internal_timestamp=self._timestamp4)

        posix_time = int('51ECAE7E', 16)
        self._timestamp5 = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_e = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0018u51ECAE7E_28_46EC\x02\n18.96 15.6 1629 348 -2\n\x03'),
            internal_timestamp=self._timestamp5)

        posix_time = int('51ECBC8D', 16)
        self._timestamp6 = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_f = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0018u51ECBC8D_31_8DAA\x02\n18.94 15.1 1674 358 -2\n\x03'),
            internal_timestamp=self._timestamp6)

        posix_time = int('51ED02DD', 16)
        self._timestamp11 = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_11 = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0018u51ED02DD_5E_2B7D\x02\n18.93 14.0 1902 408 -3\n\x03'),
            internal_timestamp=self._timestamp11)

        posix_time = int('51ED10ED', 16)
        self._timestamp12 = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_12 = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0018u51ED10ED_67_EDD2\x02\n18.93 14.0 1947 418 -3\n\x03'),
            internal_timestamp=self._timestamp12)

        posix_time = int('51EF04CE', 16)
        self._timestampAA = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_AA = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1237101_0012u51EF04CE_04_C3AF\x02\n18.72 17.4 2 1 1\n\x03'),
            internal_timestamp=self._timestampAA)

        posix_time = int('51EF1B95', 16)
        self._timestampBB = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_BB = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1237101_0014u51EF1B95_14_C795\x02\n18.88 18.5 206 6 0\n\x03'),
            internal_timestamp=self._timestampBB)

        posix_time = int('51EF0DA6', 16)
        self._timestampCC = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_CC = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0012u51EF0DA6_04_C5D1\x02\n18.58 15.3 2 1 0\n\x03'),
            internal_timestamp=self._timestampCC)

        posix_time = int('51EF1B95', 16)
        self._timestampDD = ntplib.system_to_ntp_time(float(posix_time))
        self.particle_DD = SioEngSioMuleDataParticle(
            ENG_MATCHER.match('\x01CS1236501_0014u51EF1B95_0D_B13D\x02\n18.93 14.2 71 11 0\n\x03'),
            internal_timestamp=self._timestampDD)

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

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
                    fid.write('    %s: %4.2f\n' % (val.get('value_id'), val.get('value')))
                elif isinstance(val.get('value'), str):
                    fid.write("    %s: '%s'\n" % (val.get('value_id'), val.get('value')))
                else:
                    fid.write('    %s: %s\n' % (val.get('value_id'), val.get('value')))
        fid.close()

    def create_recov_yml(self):
        """
        This utility creates a yml file
        Be sure to verify the results by eye before trusting!
        """

        fid = open(os.path.join(RESOURCE_PATH, 'STA15908.DAT'), 'r')

        stream_handle = fid
        parser = SioEngSioRecoveredParser(self.recov_config, None, stream_handle,
                                                self.state_callback_recovered,
                                                self.pub_callback,
                                                self.exception_callback)

        particles = parser.get_records(30)

        self.particle_to_yml(particles, 'STA15908.yml')
        fid.close()

    def test_simple(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))
        # NOTE: using the unprocessed data state of 0,200 limits the file to reading
        # just 200 bytes, so even though the file is longer it only reads the first
        # 200. FILE_SIZE is also ignored but must be present, so a dummy value is set
        state = {StateKey.UNPROCESSED_DATA: [[0, 200]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}
        self._parser = SioEngSioMuleParser(self.telem_config, state, stream_handle,
                                     self.state_callback, self.pub_callback, self.exception_callback)

        result = self._parser.get_records(1)
        self.assert_result(result,
                           [[58, 116, 1, 0], [116, 174, 1, 0]],
                           [[58, 200]],
                           self.particle_a)

        result = self._parser.get_records(1)
        self.assert_result(result,
                           [[116, 174, 1, 0]],
                           [[116, 200]],
                           self.particle_b)

        result = self._parser.get_records(1)
        self.assert_result(result,
                           [],
                           [[174, 200]],
                           self.particle_c)

        stream_handle.close()

    def test_simple_recov(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))
        # NOTE: using the unprocessed data state of 0,200 limits the file to reading
        # just 200 bytes, so even though the file is longer it only reads the first
        # 200. FILE_SIZE is also ignored but must be present, so a dummy value is set
        state = {StateKey.UNPROCESSED_DATA: [[0, 200]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}

        self._parser = SioEngSioRecoveredParser(self.recov_config, state, stream_handle,
                                                self.state_callback_recovered,
                                                self.pub_callback,
                                                self.exception_callback)

        result = self._parser.get_records(1)
        self.assert_result(result,
                           [[58, 116, 1, 0], [116, 174, 1, 0]],
                           [[58, 200]],
                           self.particle_a,
                           recov_flag=True)

        result = self._parser.get_records(1)
        self.assert_result(result,
                           [[116, 174, 1, 0]],
                           [[116, 200]],
                           self.particle_b,
                           recov_flag=True)

        result = self._parser.get_records(1)
        self.assert_result(result,
                           [],
                           [[174, 200]],
                           self.particle_c,
                           recov_flag=True)

        stream_handle.close()

    def test_simple2(self):
        """
        Read test data and pull out data particles one at a time.
        Assert that the results are those we expected.
        """

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'node59p1.dat'))

        # A second test simple was written to use the node59p1.dat file instead
        # of the smaller STA15908.DAT. Unprocessed data was set to two sections
        # of the file so a reasonable number of particles would be created while
        # assuring the parser could read a larger file. FILE_SIZE is also ignored
        # but must be present, so a dummy value is set

        state = {StateKey.UNPROCESSED_DATA: [[0, 5000], [7800, 8800]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}

        self._parser = SioEngSioMuleParser(self.telem_config, state, stream_handle,
                                     self.state_callback, self.pub_callback, self.exception_callback)

        result = self._parser.get_records(1)

        self.assert_result(result,
                           [[4190, 4244, 1, 0]],
                           [[4190, 4244], [4336, 4394], [4853, 5000], [7800, 8800]],
                           self.particle_AA)

        result = self._parser.get_records(1)
        self.assert_result(result,
                           [],
                           [[4336, 4394], [4853, 5000], [7800, 8800]],
                           self.particle_BB)

        result = self._parser.get_records(1)
        self.assert_result(result,
                           [],
                           [[4336, 4394], [4853, 5000], [7800, 8664], [8792, 8800]],
                           self.particle_CC)

        stream_handle.close()

    def test_get_many(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))

        # NOTE: using the unprocessed data state of 0,600 limits the file to reading
        # just 600 bytes, so even though the file is longer it only reads the first
        # 600

        log.debug('--------------------------------------------------------Starting test_get_many')

        state = {StateKey.UNPROCESSED_DATA: [[0, 600]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}

        self._parser = SioEngSioMuleParser(self.telem_config, state, stream_handle,
                                     self.state_callback, self.pub_callback, self.exception_callback)

        result = self._parser.get_records(6)

        self.assert_state([[348, 406, 1, 0], [406, 464, 1, 0], [464, 522, 1, 0], [522, 580, 1, 0]],
                          [[348, 600]])

        self.assert_particle(result[0], self.particle_a)
        self.assert_particle(result[1], self.particle_b)
        self.assert_particle(result[2], self.particle_c)
        self.assert_particle(result[3], self.particle_d)
        self.assert_particle(result[4], self.particle_e)
        self.assert_particle(result[5], self.particle_f)

        stream_handle.close()

    def test_get_many_recov(self):
        """
        Read test data and pull out multiple data particles at one time.
        Assert that the results are those we expected.
        """

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))

        # NOTE: using the unprocessed data state of 0,600 limits the file to reading
        # just 600 bytes, so even though the file is longer it only reads the first
        # 600

        log.debug('--------------------------------------------------------Starting test_get_many')

        state = {StateKey.UNPROCESSED_DATA: [[0, 600]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}

        self._parser = SioEngSioRecoveredParser(self.recov_config, state, stream_handle,
                                                self.state_callback_recovered,
                                                self.pub_callback,
                                                self.exception_callback)

        result = self._parser.get_records(6)

        # no more in process or unprocessed data
        self.assert_state([[348, 406, 1, 0], [406, 464, 1, 0], [464, 522, 1, 0], [522, 580, 1, 0]],
                          [[348, 600]], recov_flag=True)

        self.assert_particle(result[0], self.particle_a)
        self.assert_particle(result[1], self.particle_b)
        self.assert_particle(result[2], self.particle_c)
        self.assert_particle(result[3], self.particle_d)
        self.assert_particle(result[4], self.particle_e)
        self.assert_particle(result[5], self.particle_f)

        stream_handle.close()

    def test_long_stream(self):
        """
        Test a long stream 
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))
        # NOTE: using the unprocessed data state of 0,1000 limits the file to reading
        # just 1000 bytes, so even though the file is longer it only reads the first
        # 1000

        state = {StateKey.UNPROCESSED_DATA: [[0, 700]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}

        self._parser = SioEngSioMuleParser(self.telem_config, state, stream_handle,
                                      self.state_callback, self.pub_callback, self.exception_callback)

        result = self._parser.get_records(12)

        self.assert_particle(result[0], self.particle_a)
        self.assert_particle(result[1], self.particle_b)
        self.assert_particle(result[2], self.particle_c)
        self.assert_particle(result[3], self.particle_d)
        self.assert_particle(result[4], self.particle_e)
        self.assert_particle(result[5], self.particle_f)

        self.assert_particle(result[-2], self.particle_11)
        self.assert_particle(result[-1], self.particle_12)

        self.assert_state([], [[696, 700]])

        stream_handle.close()

    def test_long_stream_recov(self):
        """
        Test a long stream
        """
        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))
        # NOTE: using the unprocessed data state of 0,1000 limits the file to reading
        # just 1000 bytes, so even though the file is longer it only reads the first
        # 1000

        state = {StateKey.UNPROCESSED_DATA: [[0, 700]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}

        self._parser = SioEngSioRecoveredParser(self.recov_config, state, stream_handle,
                                                self.state_callback_recovered,
                                                self.pub_callback,
                                                self.exception_callback)

        result = self._parser.get_records(12)

        self.assert_particle(result[0], self.particle_a)
        self.assert_particle(result[1], self.particle_b)
        self.assert_particle(result[2], self.particle_c)
        self.assert_particle(result[3], self.particle_d)
        self.assert_particle(result[4], self.particle_e)
        self.assert_particle(result[5], self.particle_f)

        self.assert_particle(result[-2], self.particle_11)
        self.assert_particle(result[-1], self.particle_12)

        self.assert_state([], [[696, 700]], recov_flag=True)

        stream_handle.close()

    def test_mid_state_start(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        log.debug('-----------------------------------------------------------Starting test_mid_state_start')

        new_state = {StateKey.IN_PROCESS_DATA: [],
                     StateKey.UNPROCESSED_DATA: [[174, 290]],
                     StateKey.FILE_SIZE: 7}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))

        self._parser = SioEngSioMuleParser(self.telem_config, new_state, stream_handle,
                                     self.state_callback, self.pub_callback, self.exception_callback)

        result = self._parser.get_records(1)

        self.assert_result(result, [[232, 290, 1, 0]],
                           [[232, 290]], self.particle_d)

        result = self._parser.get_records(1)

        self.assert_result(result, [], [], self.particle_e)

        stream_handle.close()

    def test_mid_state_start_recov(self):
        """
        Test starting the parser in a state in the middle of processing
        """
        log.debug('-----------------------------------------------------------Starting test_mid_state_start')

        new_state = {StateKey.IN_PROCESS_DATA: [],
                     StateKey.UNPROCESSED_DATA: [[174, 290]],
                     StateKey.FILE_SIZE: 7}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))

        self._parser = SioEngSioRecoveredParser(self.recov_config, new_state, stream_handle,
                                                self.state_callback_recovered,
                                                self.pub_callback,
                                                self.exception_callback)

        result = self._parser.get_records(1)

        self.assert_result(result, [[232, 290, 1, 0]],
                           [[232, 290]], self.particle_d, recov_flag=True)

        result = self._parser.get_records(1)

        self.assert_result(result, [], [], self.particle_e, recov_flag=True)

        stream_handle.close()

    def test_in_process_start(self):
        """
        test starting a parser with a state in the middle of processing
        """

        log.debug('-------------------------------------------------------------Starting test_in_process_start')

        new_state = {StateKey.IN_PROCESS_DATA: [[174, 232, 1, 0], [232, 290, 1, 0], [290, 348, 1, 0]],
                     StateKey.UNPROCESSED_DATA: [[174, 600]],
                     StateKey.FILE_SIZE: 7}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))

        self._parser = SioEngSioMuleParser(self.telem_config, new_state, stream_handle,
                                     self.state_callback, self.pub_callback, self.exception_callback)

        result = self._parser.get_records(1)

        self.assert_result(result, [[232, 290, 1, 0], [290, 348, 1, 0]],
                           [[232, 600]], self.particle_d)

        result = self._parser.get_records(2)

        self.assert_particle(result[0], self.particle_e)
        self.assert_particle(result[1], self.particle_f)

        self.assert_state([], [[348, 600]])

        stream_handle.close()

    def test_in_process_start_recov(self):
        """
        test starting a parser with a state in the middle of processing
        """

        log.debug('-------------------------------------------------------------Starting test_in_process_start')

        new_state = {StateKey.IN_PROCESS_DATA: [[174, 232, 1, 0], [232, 290, 1, 0], [290, 348, 1, 0]],
                     StateKey.UNPROCESSED_DATA: [[174, 600]],
                     StateKey.FILE_SIZE: 7}

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))

        self._parser = SioEngSioRecoveredParser(self.recov_config, new_state, stream_handle,
                                                self.state_callback_recovered,
                                                self.pub_callback,
                                                self.exception_callback)

        result = self._parser.get_records(1)

        self.assert_result(result, [[232, 290, 1, 0], [290, 348, 1, 0]],
                           [[232, 600]], self.particle_d, recov_flag=True)

        result = self._parser.get_records(2)

        self.assert_particle(result[0], self.particle_e)
        self.assert_particle(result[1], self.particle_f)

        self.assert_state([], [[348, 600]], recov_flag=True)

        stream_handle.close()

    def test_set_state(self):
        """
        Test changing to a new state after initializing the parser and
        reading data, as if new data has been found and the state has
        changed
        """
        log.debug('-------------------------------------------------------------Starting test_set_state	')

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))

        # NOTE: using the unprocessed data state of 0,700 limits the file to reading
        # just 700 bytes, so even though the file is longer it only reads the first
        # 700. Also, FILE_SIZE must exist but is unused so a dummy value is inserted

        state = {StateKey.UNPROCESSED_DATA: [[0, 700]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}

        self._parser = SioEngSioMuleParser(self.telem_config, state, stream_handle,
                                     self.state_callback, self.pub_callback, self.exception_callback)

        result = self._parser.get_records(1)

        self.assert_particle(result[0], self.particle_a)

        new_state2 = {StateKey.IN_PROCESS_DATA: [[174, 232, 1, 0], [232, 290, 1, 0], [290, 348, 1, 0]],
                      StateKey.UNPROCESSED_DATA: [[174, 600]],
                      StateKey.FILE_SIZE: 7}

        log.debug("----------------- Setting State!------------")
        log.debug("New_state: %s", new_state2)
        self._parser.set_state(new_state2)

        result = self._parser.get_records(2)
        self.assert_particle(result[0], self.particle_d)
        self.assert_particle(result[1], self.particle_e)
        self.assert_state([[290, 348, 1, 0]], [[290, 600]])

        stream_handle.close()

    def test_set_state_recov(self):
        """
        Test changing to a new state after initializing the parser and
        reading data, as if new data has been found and the state has
        changed
        """
        log.debug('-------------------------------------------------------------Starting test_set_state	')

        stream_handle = open(os.path.join(RESOURCE_PATH,
                                          'STA15908.DAT'))

        # NOTE: using the unprocessed data state of 0,700 limits the file to reading
        # just 700 bytes, so even though the file is longer it only reads the first
        # 700. Also, FILE_SIZE must exist but is unused so a dummy value is inserted

        state = {StateKey.UNPROCESSED_DATA: [[0, 700]],
                 StateKey.IN_PROCESS_DATA: [],
                 StateKey.FILE_SIZE: 7}

        self._parser = SioEngSioRecoveredParser(self.recov_config, state, stream_handle,
                                                self.state_callback_recovered,
                                                self.pub_callback,
                                                self.exception_callback)

        result = self._parser.get_records(1)

        self.assert_particle(result[0], self.particle_a)

        new_state2 = {StateKey.IN_PROCESS_DATA: [[174, 232, 1, 0], [232, 290, 1, 0], [290, 348, 1, 0]],
                      StateKey.UNPROCESSED_DATA: [[174, 600]],
                      StateKey.FILE_SIZE: 7}

        log.debug("----------------- Setting State!------------")
        log.debug("New_state: %s", new_state2)
        self._parser.set_state(new_state2)

        result = self._parser.get_records(2)
        self.assert_particle(result[0], self.particle_d)
        self.assert_particle(result[1], self.particle_e)
        self.assert_state([[290, 348, 1, 0]], [[290, 600]], recov_flag=True)

        stream_handle.close()