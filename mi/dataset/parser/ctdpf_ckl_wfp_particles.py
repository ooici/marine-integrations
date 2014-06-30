#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf_ckl_wfp_particles
@file marine-integrations/mi/dataset/parser/ctdpf_ckl_wfp_particles.py
@author cgoodrich
@brief Particles for the ctdpf_ckl_wfp dataset driver
Release notes:

initial release
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

import struct

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import SampleException

from mi.dataset.parser.wfp_c_file_common import WfpMetadataParserDataParticleKey
from mi.dataset.parser.wfp_c_file_common import DATA_RECORD_BYTES, TIME_RECORD_BYTES

class DataParticleType(BaseEnum):
    TELEMETERED_DATA = 'ctdpf_ckl_wfp_instrument'
    TELEMETERED_METADATA = 'ctdpf_ckl_wfp_metadata'
    RECOVERED_DATA = 'ctdpf_ckl_wfp_instrument_recovered'
    RECOVERED_METADATA = 'ctdpf_ckl_wfp_metadata_recovered'

class CtdpfCklWfpDataParticleKey(BaseEnum):
    CONDUCTIVITY = 'conductivity'
    TEMPERATURE = 'temperature'
    PRESSURE = 'pressure'

class CtdpfCklWfpDataParticle(DataParticle):
    """
    Class for creating the instrument particle for ctdpf_ckl_wfp
    """
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data) != DATA_RECORD_BYTES:
            raise SampleException("CtdpfCklWfpDataParticle: Received unexpected number of bytes %d"
                                  % len(self.raw_data))

        fields = struct.unpack('>I', '\x00' + self.raw_data[0:3]) + \
                 struct.unpack('>I', '\x00' + self.raw_data[3:6]) + \
                 struct.unpack('>I', '\x00' + self.raw_data[6:9])

        result = [self._encode_value(CtdpfCklWfpDataParticleKey.CONDUCTIVITY, fields[0], int),
                  self._encode_value(CtdpfCklWfpDataParticleKey.TEMPERATURE, fields[1], int),
                  self._encode_value(CtdpfCklWfpDataParticleKey.PRESSURE, fields[2], int)]

        return result

class CtdpfCklWfpRecoveredDataParticle(CtdpfCklWfpDataParticle):
    """
    Class for the recovered ctdpf_ckl_wfp instrument particle
    """
    _data_particle_type = DataParticleType.RECOVERED_DATA

class CtdpfCklWfpTelemeteredDataParticle(CtdpfCklWfpDataParticle):
    """
    Class for the telemetered ctdpf_ckl_wfp instrument particle
    """
    _data_particle_type = DataParticleType.TELEMETERED_DATA

class CtdpfCklWfpMetadataParticle(DataParticle):
    """
    Class for creating the metadata particle for ctdpf_ckl
    """
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data[0]) != TIME_RECORD_BYTES:
            raise SampleException("CtdpfCklWfpMetadataDataParticle: Received unexpected number of bytes %d"
                                  % len(self.raw_data[0]))
        # data is passed in as a tuple, first element is the two timestamps as a binary string
        # the second is the number of samples as an float
        timefields = struct.unpack('>II', self.raw_data[0])

        number_samples = self.raw_data[1]

        result = [self._encode_value(WfpMetadataParserDataParticleKey.WFP_TIME_ON, timefields[0], int),
                  self._encode_value(WfpMetadataParserDataParticleKey.WFP_TIME_OFF, timefields[1], int),
                  self._encode_value(WfpMetadataParserDataParticleKey.WFP_NUMBER_SAMPLES, number_samples, int)
                  ]
        return result

class CtdpfCklWfpRecoveredMetadataParticle(CtdpfCklWfpMetadataParticle):
    """
    Class for the recovered ctdpf_ckl_wfp metadata particle
    """
    _data_particle_type = DataParticleType.RECOVERED_METADATA

class CtdpfCklWfpTelemeteredMetadataParticle(CtdpfCklWfpMetadataParticle):
    """
    Class for the telemetered ctdpf_ckl_wfp metadata particle
    """
    _data_particle_type = DataParticleType.TELEMETERED_METADATA
