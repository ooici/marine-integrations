#!/usr/bin/env python

"""
@package mi.dataset.parser.dofst_k_wfp_particles
@file marine-integrations/mi/dataset/parser/dofst_k_wfp_particles.py
@author cgoodrich
@brief Particles for the dofst_k_wfp dataset driver
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
    TELEMETERED_DATA = 'dofst_k_wfp_instrument'
    TELEMETERED_METADATA = 'dofst_k_wfp_metadata'
    RECOVERED_DATA = 'dofst_k_wfp_instrument_recovered'
    RECOVERED_METADATA = 'dofst_k_wfp_metadata_recovered'


class DofstKWfpDataParticleKey(BaseEnum):
    DOFST_K_OXYGEN = 'dofst_k_oxygen'


class DofstKWfpDataParticle(DataParticle):
    """
    Class for creating the instrument particle for dofst_k
    """
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data) != DATA_RECORD_BYTES:
            raise SampleException("DofstKWfpDataParticle: Received unexpected number of bytes %d" % len(self.raw_data))
        fields = struct.unpack('>H', self.raw_data[9:11])

        result = [self._encode_value(DofstKWfpDataParticleKey.DOFST_K_OXYGEN, fields[0], int)]
        return result


class DofstKWfpRecoveredDataParticle(DofstKWfpDataParticle):
    """
    Class for the recovered dofst_k_wfp instrument particle
    """
    _data_particle_type = DataParticleType.RECOVERED_DATA


class DofstKWfpTelemeteredDataParticle(DofstKWfpDataParticle):
    """
    Class for the telemetered dofst_k_wfp instrument particle
    """
    _data_particle_type = DataParticleType.TELEMETERED_DATA


class DofstKWfpMetadataParticle(DataParticle):
    """
    Class for creating the metadata particle for dofst_k
    """
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data[0]) != TIME_RECORD_BYTES:
            raise SampleException("DofstKWfpMetadataParticle: Received unexpected number of bytes %d" % len(self.raw_data[0]))
        # data is passed in as a tuple, first element is the two timestamps as a binary string
        # the second is the number of samples as an float
        timefields = struct.unpack('>II', self.raw_data[0])

        number_samples = self.raw_data[1]

        result = [self._encode_value(WfpMetadataParserDataParticleKey.WFP_TIME_ON, timefields[0], int),
                  self._encode_value(WfpMetadataParserDataParticleKey.WFP_TIME_OFF, timefields[1], int),
                  self._encode_value(WfpMetadataParserDataParticleKey.WFP_NUMBER_SAMPLES, number_samples, int)
                  ]
        return result


class DofstKWfpRecoveredMetadataParticle(DofstKWfpMetadataParticle):
    """
    Class for the recovered dofst_k_wfp metadata particle
    """
    _data_particle_type = DataParticleType.RECOVERED_METADATA


class DofstKWfpTelemeteredMetadataParticle(DofstKWfpMetadataParticle):
    """
    Class for the telemetered dofst_k_wfp metadata particle
    """
    _data_particle_type = DataParticleType.TELEMETERED_METADATA
