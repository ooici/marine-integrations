#!/usr/bin/env python

"""
@package mi.dataset.parser.parad_k_stc_imodem
@file marine-integrations/mi/dataset/parser/parad_k_stc_imodem.py
@author Mike Nicoletti
@brief Parser for the PARAD_K_STC_IMODEM dataset driver
Release notes:

New driver started for PARAD_K_STC_IMODEM
"""

__author__ = 'Mike Nicoletti'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import struct
import binhex

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.parser.WFP_E_file_common import WfpEFileParser, StateKey, SAMPLE_BYTES

# *** Need to define data regex for this parser ***
#DATA_REGEX = ''
#DATA_MATCHER = re.compile(DATA_REGEX)

class DataParticleType(BaseEnum):
    
    PARAD_K_INS = "parad_k__stc_imodem_instrument"
    
class Parad_k_stc_imodemParserDataParticleKey(BaseEnum):

    TIMESTAMP = 'wfp_timestamp' #holds the most recent data sample timestamp
    SENSOR_DATA = 'par_val'
    
class Parad_k_stc_imodemParserDataParticle(DataParticle):
    """
    Class for parsing data from the PARAD_K_STC_IMODEM data set
    """

    _data_particle_type = DataParticleType.PARAD_K_INS
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data) < SAMPLE_BYTES:
            raise SampleException("Parad_k_stc_imodem_statusParserDataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)
        try:
            fields_prof = struct.unpack('>I f f f f h h h', self.raw_data)
            time_stamp = int(fields_prof[0])
            #current = int(fields_prof[1])
            #voltage = int(fields_prof[2])
            #ressr = int(fields_prof[3])
            par_value = float(fields_prof[4])
            #scatter = int(fields_prof[5])
            #ch1 = int(fields_prof[6])
            #CDOM = int(fields_prof[7])
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))
        
        result = [{DataParticleKey.VALUE_ID: Parad_k_stc_imodemParserDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: time_stamp},
                  {DataParticleKey.VALUE_ID: Parad_k_stc_imodemParserDataParticleKey.SENSOR_DATA,
                   DataParticleKey.VALUE: par_value}]
        log.debug('Parad_k_stc_imodem_statusParserDataParticle: particle=%s', result)
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

class Parad_k_stc_imodemParser(WfpEFileParser):

    def parse_record(self, record):
        """
        determine if this is a engineering or data record and parse
        FLORT and PARAD can copy paste this and insert their own data particle class
        needs extending for WFP_ENG
        """
        result_particle = []
        if len(record) >= SAMPLE_BYTES:
            # pull out the timestamp for this record
            
            fields = struct.unpack('>I', record[:4])
            timestamp = int(fields[0])
            self._timestamp = ntplib.system_to_ntp_time(timestamp)
            log.debug("Converting record timestamp %f to ntp timestamp %f", timestamp, self._timestamp)
            # INSERT YOUR DATA PARTICLE CLASS HERE
            sample = self._extract_sample(Parad_k_stc_imodemParserDataParticle, None, record, self._timestamp)
            if sample:
                # create particle
                log.trace("Extracting sample %s with read_state: %s", sample, self._read_state)
                self._increment_state(SAMPLE_BYTES)
                result_particle = (sample, copy.copy(self._read_state))

        return result_particle


