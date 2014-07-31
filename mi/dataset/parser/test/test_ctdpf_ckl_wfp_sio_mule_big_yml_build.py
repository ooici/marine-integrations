#!/usr/bin/env python

"""
@package mi.dataset.parser.test.test_ctdpf_ckl_wfp_sio_mule_yml_build
@file marine-integrations/mi/dataset/parser/test/test_ctdpf_ckl_wfp_sio_mule_yml_build.py
@author cgoodrich
@brief Test code for a ctdpf_ckl_wfp_sio_mule data parser
"""
import os
import struct
import ntplib
from StringIO import StringIO

from nose.plugins.attrib import attr

from mi.core.log import get_logger
log = get_logger()
from mi.idk.config import Config

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.parser.ctdpf_ckl_wfp_sio_mule import CtdpfCklWfpSioMuleParser
from mi.dataset.parser.ctdpf_ckl_wfp_sio_mule import CtdpfCklWfpSioMuleDataParticle,\
    CtdpfCklWfpSioMuleMetadataParticle


RESOURCE_PATH = os.path.join(Config().base_dir(), 'mi',
                             'dataset', 'driver', 'ctdpf_ckl',
                             'wfp_sio_mule', 'resource')


@attr('UNIT', group='mi')
class CtdpfCklWfpSioMuleParserUnitTestCase(ParserUnitTestCase):
    """
    ctdpf_ckl_wfp_sio_mule Parser unit test suite
    """
    def state_callback(self, file_ingested):
        """ Call back method to watch what comes in via the position callback """
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
            DataSetDriverConfigKeys.PARTICLE_MODULE: 'mi.dataset.parser.ctdpf_ckl_wfp_sio_mule',
            DataSetDriverConfigKeys.PARTICLE_CLASS: ['CtdpfCklWfpSioMuleDataParticle',
                                                     'CtdpfCklWfpSioMuleMetadataParticle']
            }

        self.file_ingested_value = None
        self.state_callback_value = None
        self.publish_callback_value = None

    def calc_timestamp(self, start, increment, sample_idx):
        new_time = start + (increment * sample_idx)
        return float(ntplib.system_to_ntp_time(new_time))

    def assert_result(self, result, particle, ingested):
        self.assertEqual(result, [particle])
        self.assertEqual(self.file_ingested_value, ingested)
        self.assert_(isinstance(self.publish_callback_value, list))
        self.assertEqual(self.publish_callback_value[0], particle)

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

    def test_build_yml_file(self):
        """
        Read test data. Should detect that there is a decimation factor in the data.
        Check that the data matches the expected results.
        """
        log.debug('CAG TEST: START BUILDING YML FILE')
        stream_handle = open('/home/cgoodrich/Workspace/code/marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp_sio_mule/resource/BIG_DATA_FILE.dat', 'rb')
        self.parser =  CtdpfCklWfpSioMuleParser(self.config, None, stream_handle,
                                                self.state_callback, self.pub_callback, self.exception_callback)
        result = self.parser.get_records(50000)
        self.particle_to_yml(result, 'BIG_DATA_FILE.yml')

        log.debug('CAG TEST: FINISHED BUILDING YML FILE')

    def test_build_esc_free(self):
        """
        Do some stuff
        """
        log.debug('Remove ESC sequences')
        FILENAME = '/home/cgoodrich/Workspace/code/marine-integrations/mi/dataset/driver/ctdpf_ckl/wfp_sio_mule/resource/BIG_DATA_FILE.dat'
        f = open (FILENAME, "rb")

        input_buffer = f.read()
        log.debug('BUFFER BEFORE %d', len(input_buffer))
        input_buffer = input_buffer.replace(b'\x18\x6b', b'\x2b')
        input_buffer = input_buffer.replace(b'\x18\x58', b'\x18')
        log.debug('BUFFER AFTER %d', len(input_buffer))

        fid = open(os.path.join(RESOURCE_PATH, 'escBIG_DATA_FILE.dat'), 'w')
        fid.write(input_buffer)


