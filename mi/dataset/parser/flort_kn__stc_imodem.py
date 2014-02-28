#!/usr/bin/env python

"""
@package mi.dataset.parser.flort_kn__stc_imodem
@file marine-integrations/mi/dataset/parser/flort_kn__stc_imodem.py
@author Emily Hahn
@brief Parser for the FLORT_KN__STC_IMODEM dataset driver
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import struct

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.parser.WFP_E_file_common import WfpEFileParser, StateKey, SAMPLE_BYTES


class DataParticleType(BaseEnum):
    FLORT_KN_INS = 'flort_kn__stc_imodem_instrument'

class Flort_kn__stc_imodemParserDataParticleKey(BaseEnum):
    TIMESTAMP = 'wfp_timestamp'
    RAW_SIGNAL_BETA = 'raw_signal_beta'
    RAW_SIGNAL_CHL = 'raw_signal_chl'
    RAW_SIGNAL_CDOM = 'raw_signal_cdom'

class Flort_kn__stc_imodemParserDataParticle(DataParticle):
    """
    Class for parsing data from the FLORT_KN__STC_IMODEM data set
    """

    _data_particle_type = DataParticleType.FLORT_KN_INS
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data) < SAMPLE_BYTES:
            raise SampleException("Flort_kn__stc_imodemParserDataParticleKey: No regex match of parsed sample data: [%s]",
                                  self.raw_data)
        try:
            fields_prof = struct.unpack('>I f f f f h h h', self.raw_data)
            time_stamp = int(fields_prof[0])
            scatter = int(fields_prof[5])
            chl = int(fields_prof[6])
            CDOM = int(fields_prof[7])
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))
        
        result = [{DataParticleKey.VALUE_ID: Flort_kn__stc_imodemParserDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: time_stamp},
                  {DataParticleKey.VALUE_ID: Flort_kn__stc_imodemParserDataParticleKey.RAW_SIGNAL_BETA,
                   DataParticleKey.VALUE: scatter},
                  {DataParticleKey.VALUE_ID: Flort_kn__stc_imodemParserDataParticleKey.RAW_SIGNAL_CHL,
                   DataParticleKey.VALUE: chl},
                  {DataParticleKey.VALUE_ID: Flort_kn__stc_imodemParserDataParticleKey.RAW_SIGNAL_CDOM,
                   DataParticleKey.VALUE: CDOM}]
        log.debug('Flort_kn__stc_imodemParserDataParticleKey: particle=%s', result)
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

class Flort_kn__stc_imodemParser(WfpEFileParser):

    def parse_record(self, record):
        """
        parse a FLORT_KN data sample into data particle from the input record
        """
        result_particle = []
        if len(record) >= SAMPLE_BYTES:
            # pull out the timestamp for this record
            
            fields = struct.unpack('>I', record[:4])
            timestamp = int(fields[0])
            self._timestamp = float(ntplib.system_to_ntp_time(timestamp))
            log.debug("Converting record timestamp %f to ntp timestamp %f", timestamp, self._timestamp)
            sample = self._extract_sample(Flort_kn__stc_imodemParserDataParticle, None, record, self._timestamp)
            if sample:
                # create particle
                log.trace("Extracting sample %s with read_state: %s", sample, self._read_state)
                self._increment_state(SAMPLE_BYTES)
                result_particle = (sample, copy.copy(self._read_state))

        return result_particle


