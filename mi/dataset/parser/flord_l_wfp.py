#!/usr/bin/env python

"""
@package mi.dataset.parser.flord_l_wfp
@file marine-integrations/mi/dataset/parser/flord_l_wfp.py
@author Joe Padula
@brief Particle for the flord_l_wfp dataset driver
Release notes:

Initial Release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

# noinspection PyUnresolvedReferences
import gevent
# noinspection PyUnresolvedReferences
import ntplib
import struct

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle


class DataParticleType(BaseEnum):
    INSTRUMENT = 'flord_l_wfp_instrument_recovered'


class FlordLWfpInstrumentParserDataParticleKey(BaseEnum):
    TIME = 'time'
    RAW_SIGNAL_CHL = 'raw_signal_chl'           # corresponds to 'chl' from E file
    RAW_SIGNAL_BETA = 'raw_signal_beta'         # corresponds to 'ntu' from E file
    RAW_INTERNAL_TEMP = 'raw_internal_temp'     # corresponds to 'temperature' from E file
    WFP_TIMESTAMP = 'wfp_timestamp'


class FlordLWfpInstrumentParserDataParticle(DataParticle):
    """
    Class for parsing data from the flord_l_wfp data set
    """

    _data_particle_type = DataParticleType.INSTRUMENT

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """

        fields_prof = struct.unpack('>I f f f f f h h h', self.raw_data)
        result = [self._encode_value(FlordLWfpInstrumentParserDataParticleKey.RAW_SIGNAL_CHL, fields_prof[6], int),
                  self._encode_value(FlordLWfpInstrumentParserDataParticleKey.RAW_SIGNAL_BETA, fields_prof[7], int),
                  self._encode_value(FlordLWfpInstrumentParserDataParticleKey.RAW_INTERNAL_TEMP, fields_prof[8], int),
                  self._encode_value(FlordLWfpInstrumentParserDataParticleKey.WFP_TIMESTAMP, fields_prof[0], int)]
        return result
