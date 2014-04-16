#!/usr/bin/env python

"""
@package mi.dataset.parser.adcps
@file mi/dataset/parser/adcps.py
@author Emily Hahn
@brief An adcps-specific dataset agent parser
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re
import struct
import ntplib
import time
import datetime
from dateutil import parser

from mi.core.log import get_logger; log = get_logger()
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER
from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, RecoverableSampleException, DatasetParserException
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.time import string_to_ntp_date_time

class DataParticleType(BaseEnum):
    SAMPLE = 'adcps_parsed'

class AdcpsParserDataParticleKey(BaseEnum):
    PD12_PACKET_ID = 'pd12_packet_id'
    NUM_BYTES = 'num_bytes'
    ENSEMBLE_NUMBER = 'ensemble_number'
    UNIT_ID = 'unit_id'
    FIRMWARE_VERSION = 'firmware_version'
    FIRMWARE_REVISION = 'firmware_revision'
    REAL_TIME_CLOCK = 'real_time_clock'
    ENSEMBLE_START_TIME = 'ensemble_start_time'
    HEADING = 'heading'
    PITCH = 'pitch'
    ROLL = 'roll'
    TEMPERATURE = 'temperature'
    PRESSURE = 'pressure'
    VELOCITY_PO_ERROR_FLAG = 'velocity_po_error_flag'
    VELOCITY_PO_UP_FLAG = 'velocity_po_up_flag'
    VELOCITY_PO_NORTH_FLAG = 'velocity_po_north_flag'
    VELOCITY_PO_EAST_FLAG = 'velocity_po_east_flag'
    SUBSAMPLING_PARAMETER = 'subsampling_parameter'
    START_BIN = 'start_bin'
    NUM_BINS = 'num_bins'
    WATER_VELOCITY_EAST = 'water_velocity_east'
    WATER_VELOCITY_NORTH = 'water_velocity_north'
    WATER_VELOCITY_UP = 'water_velocity_up'
    ERROR_VELOCITY = 'error_velocity'
    CHECKSUM = 'checksum'

DATA_WRAPPER_REGEX = b'<Executing/>\x0d\x0a<SampleData ID=\'0x[0-9a-f]+\' LEN=\'[0-9]+\' CRC=\'0x[0-9a-f]+\'>([\x00-\xFF]+)</SampleData>\x0d\x0a<Executed/>\x0d\x0a'
DATA_WRAPPER_MATCHER = re.compile(DATA_WRAPPER_REGEX)
DATA_REGEX = b'\x6e\x7f[\x00-\xFF]{32}([\x00-\xFF]+)([\x00-\xFF]{2})'
DATA_MATCHER = re.compile(DATA_REGEX)

class AdcpsParserDataParticle(DataParticle):
    """
    Class for parsing data from the ADCPS instrument on a MSFM platform node
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
            raise SampleException("AdcpsParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:
            fields = struct.unpack('<HHIBBBdHhhhIbBB', match.group(0)[0:34])
            num_bytes = fields[1]
            if len(match.group(0)) - 2 != num_bytes:
                raise ValueError('num bytes %d does not match data length %d'
                          % (num_bytes, len(match.group(0))))
            nbins = fields[14]
            if len(match.group(0)) < (36+(nbins*8)):
                raise ValueError('Number of bins %d does not fit in data length %d'%(nbins,
                                                                                     len(match.group(0))))
            date_fields = struct.unpack('HBBBBBB', match.group(0)[11:19])
            date_str = self.unpack_date(match.group(0)[11:19])
            log.debug('unpacked date string %s', date_str)
            sec_since_1900 = string_to_ntp_date_time(date_str)

            # create a string with the right number of shorts to unpack
            struct_format = '>'
            for i in range(0,nbins):
                struct_format = struct_format + 'h'

            bin_len = nbins*2
            vel_east = struct.unpack(struct_format, match.group(0)[34:(34+bin_len)])
            vel_north = struct.unpack(struct_format, match.group(0)[(34+bin_len):(34+(bin_len*2))])
            vel_up = struct.unpack(struct_format, match.group(0)[(34+(bin_len*2)):(34+(bin_len*3))])
            vel_err = struct.unpack(struct_format, match.group(0)[(34+(bin_len*3)):(34+(bin_len*4))])

            checksum = struct.unpack('<h', match.group(0)[(34+(bin_len*4)):(36+(bin_len*4))])
        except (ValueError, TypeError, IndexError) as ex:
            # we can recover and read additional samples after this, just this one is missed
            log.warn("Error %s while decoding parameters in data [%s]", ex, match.group(0))
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))

        result = [self._encode_value(AdcpsParserDataParticleKey.PD12_PACKET_ID, fields[0], int),
                  self._encode_value(AdcpsParserDataParticleKey.NUM_BYTES, fields[1], int),
                  self._encode_value(AdcpsParserDataParticleKey.ENSEMBLE_NUMBER, fields[2], int),
                  self._encode_value(AdcpsParserDataParticleKey.UNIT_ID, fields[3], int),
                  self._encode_value(AdcpsParserDataParticleKey.FIRMWARE_VERSION, fields[4], int),
                  self._encode_value(AdcpsParserDataParticleKey.FIRMWARE_REVISION, fields[5], int),
                  self._encode_value(AdcpsParserDataParticleKey.REAL_TIME_CLOCK, date_fields, list),
                  self._encode_value(AdcpsParserDataParticleKey.ENSEMBLE_START_TIME, sec_since_1900, float),
                  self._encode_value(AdcpsParserDataParticleKey.HEADING, fields[7], int),
                  self._encode_value(AdcpsParserDataParticleKey.PITCH, fields[8], int),
                  self._encode_value(AdcpsParserDataParticleKey.ROLL, fields[9], int),
                  self._encode_value(AdcpsParserDataParticleKey.TEMPERATURE, fields[10], int),
                  self._encode_value(AdcpsParserDataParticleKey.PRESSURE, fields[11], int),
                  self._encode_value(AdcpsParserDataParticleKey.VELOCITY_PO_ERROR_FLAG, fields[12]&1, int),
                  self._encode_value(AdcpsParserDataParticleKey.VELOCITY_PO_UP_FLAG, (fields[12]&2) >> 1, int),
                  self._encode_value(AdcpsParserDataParticleKey.VELOCITY_PO_NORTH_FLAG, (fields[12]&4) >> 2, int),
                  self._encode_value(AdcpsParserDataParticleKey.VELOCITY_PO_EAST_FLAG, (fields[12]&8) >> 3, int),
                  self._encode_value(AdcpsParserDataParticleKey.SUBSAMPLING_PARAMETER, (fields[12]&240) >> 4, int),
                  self._encode_value(AdcpsParserDataParticleKey.START_BIN, fields[13], int),
                  self._encode_value(AdcpsParserDataParticleKey.NUM_BINS, fields[14], int),
                  self._encode_value(AdcpsParserDataParticleKey.WATER_VELOCITY_EAST, vel_east, list),
                  self._encode_value(AdcpsParserDataParticleKey.WATER_VELOCITY_NORTH, vel_north, list),
                  self._encode_value(AdcpsParserDataParticleKey.WATER_VELOCITY_UP, vel_up, list),
                  self._encode_value(AdcpsParserDataParticleKey.ERROR_VELOCITY, vel_err, list),
                  self._encode_value(AdcpsParserDataParticleKey.CHECKSUM, checksum[0], int)]

        log.trace('AdcpsParserDataParticle: particle=%s', result)
        return result

    @staticmethod
    def unpack_date(data):
        fields = struct.unpack('HBBBBBB', data)
        log.debug('Unpacked data into date fields %s', fields)
        zulu_ts = "%04d-%02d-%02dT%02d:%02d:%02d.%02dZ" % (
            fields[0], fields[1], fields[2], fields[3],
            fields[4], fields[5], fields[6])
        return zulu_ts


class AdcpsParser(SioMuleParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(AdcpsParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          'AD',
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
                log.debug("matched chunk header %s", chunk[1:32])

                data_wrapper_match = DATA_WRAPPER_MATCHER.search(chunk)
                if data_wrapper_match:
                    data_match = DATA_MATCHER.search(data_wrapper_match.group(1))
                    if data_match:
                        log.debug('Found data match in chunk %s', chunk[1:32])
                        # pull out the date string from the data
                        date_str = AdcpsParserDataParticle.unpack_date(data_match.group(0)[11:19])
                        # convert to ntp
                        converted_time = float(parser.parse(date_str).strftime("%s.%f"))
                        adjusted_time = converted_time - time.timezone
                        self._timestamp = ntplib.system_to_ntp_time(adjusted_time)
                        # round to ensure the timestamps match
                        self._timestamp = round(self._timestamp*100)/100
                        log.debug("Converted time \"%s\" (unix: %10.9f) into %10.9f", date_str, adjusted_time, self._timestamp)
                        # particle-ize the data block received, return the record
                        sample = self._extract_sample(AdcpsParserDataParticle,
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
