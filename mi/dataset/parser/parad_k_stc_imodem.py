#!/usr/bin/env python

"""
@package mi.dataset.parser.parad_k_stc_imodem
@file marine-integrations/mi/dataset/parser/parad_k_stc_imodem.py
@author Mike Nicoletti
@brief Parser for the PARAD_K_STC_IMODEM dataset driver
Release notes:

New driver started for PARAD_K_STC_IMODEM
"""

__author__ = 'Mike Nicoletti, Steve Myerson (recovered)'
__license__ = 'Apache 2.0'

import copy
import ntplib
import struct
import math

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException

from mi.dataset.parser.WFP_E_file_common import WfpEFileParser, SAMPLE_BYTES


class DataParticleType(BaseEnum):
    
    PARAD_K_INS = 'parad_k__stc_imodem_instrument'
    PARAD_K_INS_RECOVERED = 'parad_k__stc_imodem_instrument_recovered'


class Parad_k_stc_DataParticleKey(BaseEnum):

    TIMESTAMP = 'wfp_timestamp'  # holds the most recent data sample timestamp
    SENSOR_DATA = 'par_val_v'


class Parad_k_stc_DataParticle(DataParticle):
    """
    Generic class to generate Parad_k_stc data particles for both recovered
    and telemetered data.
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        if len(self.raw_data) < SAMPLE_BYTES:
            raise SampleException("Parad_k_stc_DataParticle: No regex match of parsed sample data: [%s]",
                                  self.raw_data)
        try:
            fields_prof = struct.unpack('>I f f f f h h h', self.raw_data)
            time_stamp = int(fields_prof[0])
            par_value = float(fields_prof[4])
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [0x%s]"
                                  % (ex, self.raw_data))
        # confirm we did not get an NaNs
        if math.isnan(par_value) or math.isnan(time_stamp):
            log.error("Found a NaN value in the data")
            raise SampleException("Got a NaN value")

        result = [self._encode_value(Parad_k_stc_DataParticleKey.TIMESTAMP,
                                     time_stamp, int),
                  self._encode_value(Parad_k_stc_DataParticleKey.SENSOR_DATA,
                                     par_value, float)]

        return result


class Parad_k_stc_imodemDataParticle(Parad_k_stc_DataParticle):
    """
    Class for parsing telemetered data from the PARAD_K_STC_IMODEM data set
    """

    _data_particle_type = DataParticleType.PARAD_K_INS


class Parad_k_stc_imodemRecoveredDataParticle(Parad_k_stc_DataParticle):
    """
    Class for parsing recovered data from the PARAD_K_STC_IMODEM data set
    """

    _data_particle_type = DataParticleType.PARAD_K_INS_RECOVERED


class Parad_k_stc_Parser(WfpEFileParser):

    def parse_parad_k_record(self, record, particle_type):
        """
        This is a PARAD_K particle type, and below we pull the proper value from the
        unpacked data
        """
        result_particle = []
        if len(record) >= SAMPLE_BYTES:
            # pull out the timestamp for this record

            fields = struct.unpack('>I', record[:4])
            timestamp = int(fields[0])
            self._timestamp = float(ntplib.system_to_ntp_time(timestamp))
            # PARAD_K Data
            sample = self._extract_sample(particle_type, None, record, self._timestamp)
            if sample:
                # create particle
                self._increment_state(SAMPLE_BYTES)
                result_particle = (sample, copy.copy(self._read_state))

        return result_particle


class Parad_k_stc_imodemParser(Parad_k_stc_Parser):

    def parse_record(self, record):
        """
        This is a PARAD_K particle type, and below we pull the proper value from the
        unpacked data
        """
        return self.parse_parad_k_record(record, Parad_k_stc_imodemDataParticle)


class Parad_k_stc_imodemRecoveredParser(Parad_k_stc_Parser):

    def parse_record(self, record):
        """
        This is a PARAD_K particle type, and below we pull the proper value from the
        unpacked data
        """
        return self.parse_parad_k_record(record, Parad_k_stc_imodemRecoveredDataParticle)


