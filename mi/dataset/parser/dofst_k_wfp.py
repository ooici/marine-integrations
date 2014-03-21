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

from mi.dataset.parser.wfp_c_file_common import WfpCFileCommonParser

EOP_REGEX = b'\xFF{11}([\x00-\xFF]{8})'
EOP_MATCHER = re.compile(EOP_REGEX)

DATA_RECORD_BYTES = 11
TIME_RECORD_BYTES = 8

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
        
        result = [{DataParticleKey.VALUE_ID: DofstKWfpParserDataParticleKey.DOFST_K_OXYGEN,
                   DataParticleKey.VALUE: int(fields[0])}]
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        allowed_diff = .000001
        if ((self.raw_data == arg.raw_data) and \
            (abs(self.contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]) <= allowed_diff)):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif abs(self.contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
                     arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]) > allowed_diff:
                log.debug('Timestamp %s does not match %s',
                          self.contents[DataParticleKey.INTERNAL_TIMESTAMP],
                          arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])
            return False

class DofstKWfpParser(WfpCFileCommonParser):
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
        super(DofstKWfpParser, self).__init__(config,
                                              stream_handle,
                                              state,
                                              state_callback,
                                              publish_callback,
                                              DofstKWfpParserDataParticle,
                                              DataParticleType.METADATA,
                                              streamsize,
                                              *args, **kwargs)
