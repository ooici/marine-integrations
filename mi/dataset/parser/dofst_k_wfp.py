#!/usr/bin/env python

"""
@package mi.dataset.parser.dofst_k_wfp
@file marine-integrations/mi/dataset/parser/dofst_k_wfp.py
@author Emily Hahn
@brief Parser for the dofst_k_wfp dataset driver
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re
import struct

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException

from mi.dataset.parser.wfp_c_file_common import WfpCFileCommonParser, WfpMetadataParserDataParticleKey
from mi.dataset.parser.wfp_c_file_common import DATA_RECORD_BYTES, TIME_RECORD_BYTES

class DataParticleType(BaseEnum):
    DATA = 'dofst_k_wfp_instrument'
    METADATA = 'dofst_k_wfp_metadata'

class DofstKWfpParserDataParticleKey(BaseEnum):
    DOFST_K_OXYGEN = 'dofst_k_oxygen'

class DofstKWfpParserDataParticle(DataParticle):
    """
    Class for parsing data from the dofst_k_wfp data set
    """

    _data_particle_type = DataParticleType.DATA

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data) != DATA_RECORD_BYTES:
            raise SampleException("DofstKWfpParserDataParticle: Received unexpected number of bytes %d" % len(self.raw_data))
        fields = struct.unpack('>H', self.raw_data[9:11])

        result = [self._encode_value(DofstKWfpParserDataParticleKey.DOFST_K_OXYGEN, fields[0], int)]
        return result

class DofstKWfpMetadataParserDataParticle(DataParticle):
    """
    Class for creating the data particle for the common wfp metadata
    """
    _data_particle_type = DataParticleType.METADATA

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data[0]) != TIME_RECORD_BYTES:
            raise SampleException("DofstKWfpMetadataDataParserDataParticle: Received unexpected number of bytes %d" % len(self.raw_data[0]))
        # data is passed in as a tuple, first element is the two timestamps as a binary string
        # the second is the number of samples as an float
        timefields = struct.unpack('>II', self.raw_data[0])

        number_samples = self.raw_data[1]

        result = [self._encode_value(WfpMetadataParserDataParticleKey.WFP_TIME_ON, timefields[0], int),
                  self._encode_value(WfpMetadataParserDataParticleKey.WFP_TIME_OFF, timefields[1], int),
                  self._encode_value(WfpMetadataParserDataParticleKey.WFP_NUMBER_SAMPLES, number_samples, int)
                  ]
        return result


class DofstKWfpParser(WfpCFileCommonParser):
    """
    Make use of the common wfp C file type parser
    """

    def extract_metadata_particle(self, raw_data, timestamp):
        """
        Class for extracting the metadata data particle
        @param raw_data raw data to parse, in this case a tuple of the time string to parse and the number of records
        @param timestamp timestamp in NTP64
        """
        sample = self._extract_sample(DofstKWfpMetadataParserDataParticle, None,
                                     raw_data, timestamp)
        return sample

    def extract_data_particle(self, raw_data, timestamp):
        """
        Class for extracting the data sample data particle
        @param raw_data the raw data to parse
        @param timestamp the timestamp in NTP64
        """
        sample = self._extract_sample(DofstKWfpParserDataParticle, None, raw_data, timestamp)
        return sample