#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf_ckl_wfp
@file marine-integrations/mi/dataset/parser/ctdpf_ckl_wfp.py
@author cgoodrich
@brief Parser for the ctdpf_ckl_wfp dataset driver
Release notes:

Initial Release
"""

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

import re
import struct

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException

from mi.dataset.parser.wfp_c_file_common import WfpCFileCommonParser, WfpMetadataParserDataParticleKey
from mi.dataset.parser.wfp_c_file_common import DATA_RECORD_BYTES, TIME_RECORD_BYTES


class DataParticleType(BaseEnum):
    DATA = 'ctdpf_ckl_wfp_instrument'
    METADATA = 'ctdpf_ckl_wfp_metadata'


class CtdpfCklWfpParserDataParticleKey(BaseEnum):
    CONDUCTIVITY = 'conductivity'
    TEMPERATURE = 'temperature'
    PRESSURE = 'pressure'


class CtdpfCklWfpParserDataParticle(DataParticle):
    """
    Class for parsing data from the ctdpf_ckl_wfp data set
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
            raise SampleException("CtdpfCklWfpParserDataParticle: Received unexpected number of bytes %d"
                                  % len(self.raw_data))

        fields = struct.unpack('>I', '\x00' + self.raw_data[0:3]) + \
                 struct.unpack('>I', '\x00' + self.raw_data[3:6]) + \
                 struct.unpack('>I', '\x00' + self.raw_data[6:9])

        result = [self._encode_value(CtdpfCklWfpParserDataParticleKey.CONDUCTIVITY, fields[0], int),
                  self._encode_value(CtdpfCklWfpParserDataParticleKey.TEMPERATURE, fields[1], int),
                  self._encode_value(CtdpfCklWfpParserDataParticleKey.PRESSURE, fields[2], int)]

        return result


class CtdpfCklWfpMetadataParserDataParticle(DataParticle):
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
            raise SampleException("CtdpfCklWfpMetadataDataParserDataParticle: Received unexpected number of bytes %d" % len(self.raw_data[0]))
        # data is passed in as a tuple, first element is the two timestamps as a binary string
        # the second is the number of samples as an float
        timefields = struct.unpack('>II', self.raw_data[0])

        number_samples = self.raw_data[1]

        result = [self._encode_value(WfpMetadataParserDataParticleKey.WFP_TIME_ON, timefields[0], int),
                  self._encode_value(WfpMetadataParserDataParticleKey.WFP_TIME_OFF, timefields[1], int),
                  self._encode_value(WfpMetadataParserDataParticleKey.WFP_NUMBER_SAMPLES, number_samples, int)
                  ]
        return result


class CtdpfCklWfpParser(WfpCFileCommonParser):
    """
    Make use of the common wfp C file type parser
    """

    def extract_metadata_particle(self, raw_data, timestamp):
        """
        Class for extracting the metadata data particle
        @param raw_data raw data to parse, in this case a tuple of the time string to parse and the number of records
        @param timestamp timestamp in NTP64
        """
        sample = self._extract_sample(CtdpfCklWfpMetadataParserDataParticle, None,
                                     raw_data, timestamp)
        return sample

    def extract_data_particle(self, raw_data, timestamp):
        """
        Class for extracting the data sample data particle
        @param raw_data the raw data to parse
        @param timestamp the timestamp in NTP64
        """
        sample = self._extract_sample(CtdpfCklWfpParserDataParticle, None, raw_data, timestamp)
        return sample
