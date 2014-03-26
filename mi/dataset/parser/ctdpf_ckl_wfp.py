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
            raise SampleException("CtdpfCklWfpParserDataParticle: Received unexpected number of bytes %d"
                                  % len(self.raw_data))

        fields = struct.unpack('>I', '\x00' + self.raw_data[0:3]) + \
                 struct.unpack('>I', '\x00' + self.raw_data[3:6]) + \
                 struct.unpack('>I', '\x00' + self.raw_data[6:9])

        result = [{DataParticleKey.VALUE_ID: CtdpfCklWfpParserDataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: int(fields[0])},
                  {DataParticleKey.VALUE_ID: CtdpfCklWfpParserDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: int(fields[1])},
                  {DataParticleKey.VALUE_ID: CtdpfCklWfpParserDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: int(fields[2])}]

        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this
        particle
        """
        allowed_diff = .000001
        if ((self.raw_data == arg.raw_data) and
            (abs(self.contents[DataParticleKey.INTERNAL_TIMESTAMP] -
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]) <= allowed_diff)):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif abs(self.contents[DataParticleKey.INTERNAL_TIMESTAMP] -
                     arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]) > allowed_diff:
                log.debug('Timestamp %s does not match %s',
                          self.contents[DataParticleKey.INTERNAL_TIMESTAMP],
                          arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])
            return False


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
            raise SampleException("CtdpfCklWfpMetadataDataParserDataParticle: Received unexpected number of bytes %d" % len(self._raw_data[0]))
        if not isinstance(self.raw_data[1], float):
            raise SampleException("CtdpfCklWfpMetadataDataParserDataParticle: Received invalid format number of samples %s", self._raw_data[1])
        # data is passed in as a tuple, first element is the two timestamps as a binary string
        # the second is the number of samples as an float
        timefields = struct.unpack('>II', self.raw_data[0])
        time_on = int(timefields[0])
        time_off = int(timefields[1])

        number_samples = self.raw_data[1]
        if not number_samples.is_integer():
            raise SampleException("File does not evenly fit into number of records")

        result = [{DataParticleKey.VALUE_ID: WfpMetadataParserDataParticleKey.WFP_TIME_ON,
                   DataParticleKey.VALUE: time_on},
                  {DataParticleKey.VALUE_ID: WfpMetadataParserDataParticleKey.WFP_TIME_OFF,
                   DataParticleKey.VALUE: time_off},
                  {DataParticleKey.VALUE_ID: WfpMetadataParserDataParticleKey.WFP_NUMBER_SAMPLES,
                   DataParticleKey.VALUE: int(number_samples)}]
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this
        particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] == \
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            return False


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
