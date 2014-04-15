#!/usr/bin/env python

"""
@package mi.dataset.parser.dostad
@file mi/dataset/parser/dostad.py
@author Emily Hahn
@brief An dosta-d specific dataset agent parser
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re
from datetime import datetime
import ntplib

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER
from mi.core.exceptions import SampleException, DatasetParserException

class DataParticleType(BaseEnum):
    SAMPLE = 'dostad_parsed'

class DostadParserDataParticleKey(BaseEnum):
    PRODUCT_NUMBER = 'product_number'
    SERIAL_NUMBER = 'serial_number'
    ESTIMATED_OXYGEN = 'estimated_oxygen_concentration'
    AIR_SATURATION = 'estimated_oxygen_saturation'
    OPTODE_TEMPERATURE = 'optode_temperature'
    CALIBRATED_PHASE = 'calibrated_phase'
    TEMP_COMPENSATED_PHASE = 'temp_compensated_phase'
    BLUE_PHASE = 'blue_phase'
    RED_PHASE = 'red_phase'
    BLUE_AMPLITUDE = 'blue_amplitude'
    RED_AMPLITUDE = 'red_amplitude'
    RAW_TEMP = 'raw_temperature'
    
DATA_REGEX = b'\xff\x11\x25\x11(\d+)\t(\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t' \
             '(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\x0d\x0a'
DATA_MATCHER = re.compile(DATA_REGEX)

class DostadParserDataParticle(DataParticle):
    """
    Class for parsing data from the DOSTA-D instrument on a MSFM platform node
    """

    _data_particle_type = DataParticleType.SAMPLE

    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        throws SampleException If there is a problem with sample creation
        """
        # match the data inside the wrapper
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("DostadParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)

        result = [self._encode_value(DostadParserDataParticleKey.PRODUCT_NUMBER, match.group(1), int),
                  self._encode_value(DostadParserDataParticleKey.SERIAL_NUMBER, match.group(2), int),
                  self._encode_value(DostadParserDataParticleKey.ESTIMATED_OXYGEN, match.group(3), float),
                  self._encode_value(DostadParserDataParticleKey.AIR_SATURATION, match.group(4), float),
                  self._encode_value(DostadParserDataParticleKey.OPTODE_TEMPERATURE, match.group(5), float),
                  self._encode_value(DostadParserDataParticleKey.CALIBRATED_PHASE, match.group(6), float),
                  self._encode_value(DostadParserDataParticleKey.TEMP_COMPENSATED_PHASE, match.group(7), float),
                  self._encode_value(DostadParserDataParticleKey.BLUE_PHASE, match.group(8), float),
                  self._encode_value(DostadParserDataParticleKey.RED_PHASE, match.group(9), float),
                  self._encode_value(DostadParserDataParticleKey.BLUE_AMPLITUDE, match.group(10), float),
                  self._encode_value(DostadParserDataParticleKey.RED_AMPLITUDE, match.group(11), float),
                  self._encode_value(DostadParserDataParticleKey.RAW_TEMP, match.group(12), float)]

        return result

class DostadParser(SioMuleParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(DostadParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          'DO',
                                          *args,
                                          **kwargs)

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        sample_count = 0

        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            log.debug('parsing header %s', header_match.group(0)[1:32])
            if header_match.group(1) == self._instrument_id:

                data_match = DATA_MATCHER.search(chunk)
                if data_match:
                    log.debug('Found data match in chunk %s', chunk[1:32])
                    # get the time from the header
                    posix_time = int(header_match.group(3), 16)
                    # convert from posix to local time
                    log.debug('utc timestamp %s', datetime.utcfromtimestamp(posix_time))
                    self._timestamp = ntplib.system_to_ntp_time(float(posix_time))
                    log.debug("Converted time \"%s\" (unix: %s) into %s", header_match.group(3),
                              posix_time, self._timestamp)

                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(DostadParserDataParticle,
                                                  DATA_MATCHER,
                                                  data_match.group(0),
                                                  self._timestamp)
                    if sample:
                        # create particle
                        result_particles.append(sample)
                        sample_count += 1

            self._chunk_sample_count.append(sample_count)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        return result_particles
