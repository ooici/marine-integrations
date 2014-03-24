#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf_ckl__stc_imodem
@file marine-integrations/mi/dataset/parser/ctdpf_ckl__stc_imodem.py
@author cgoodrich
@brief Parser for the CTDPF_CKL__STC_IMODEM dataset driver
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

from mi.dataset.parser.wfp_c_file_common import WfpCFileCommonParser

EOP_REGEX = b'\xFF{11}([\x00-\xFF]{8})'
EOP_MATCHER = re.compile(EOP_REGEX)

DATA_RECORD_BYTES = 11
TIME_RECORD_BYTES = 8


class DataParticleType(BaseEnum):
    DATA = 'ctdpf_ckl_wfp_instrument'
    METADATA = 'ctdpf_ckl_wfp_metadata'


class CtdpfCklWfpParserDataParticleKey(BaseEnum):
    CONDUCTIVITY = 'conductivity'
    TEMPERATURE = 'temperature'
    PRESSURE = 'pressure'


class CtdpfCklWfpParserDataParticle(DataParticle):
    """
    Class for parsing CTDPF_CKL metadata from the WFP C file data
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


class CtdpfCklWfpParser(WfpCFileCommonParser):
    """
    Make use of the common wfp C file type parser, just passing in the
    data particle type and metadata stream type.
    @param config The parser configuration dictionary
    @param state The state dictionary
    @param stream_handle The data stream to obtain data from
    @param state_callback The callback to use when the state changes
    @param publish_callback The callback to use to publish a particle
    @param streamsize The total length of the data stream
    """
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 streamsize,
                 *args, **kwargs):
        super(CtdpfCklWfpParser, self).__init__(config,
                                                stream_handle,
                                                state,
                                                state_callback,
                                                publish_callback,
                                                CtdpfCklWfpParserDataParticle,
                                                DataParticleType.METADATA,
                                                streamsize,
                                                *args, **kwargs)
