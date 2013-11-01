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
from dateutil import parser

from mi.core.log import get_logger; log = get_logger()
from mi.dataset.parser.mflm import MflmParser, SIO_HEADER_MATCHER
from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.dataset_parser import BufferLoadingParser

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
            packet_id = fields[0]
            num_bytes = fields[1]
            if len(match.group(0)) - 2 != num_bytes:
                raise ValueError('num bytes %d does not match data length %d'
                          % (num_bytes, len(match.group(0))))
            log.debug('unpacked fields %s', fields)
            nbins = fields[14]
            if len(match.group(0)) < (36+(nbins*8)):
                raise ValueError('Number of bins %d does not fit in data length %d'%(nbins,
                                                                                     len(match.group(0))))
            date_fields = struct.unpack('HBBBBBB', match.group(0)[11:19])
            date_str = self.unpack_date(match.group(0)[11:19])
            log.debug('unpacked date string %s', date_str)
            # get seconds from 1990 to 1970
            elapse_1900 = float(parser.parse("1900-01-01T00:00:00.00Z").strftime("%s.%f"))
            # get seconds 
            elapse_date = float(parser.parse(date_str).strftime("%s.%f"))
            # subtract seconds from 1900 to 1970 to convert to seconds since 1900
            sec_since_1900 = round((elapse_date - elapse_1900)*100)/100
            log.debug('calculated seconds since 1900 %f', sec_since_1900)
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

            # heading/pitch/roll/temp units of cdegrees (= .01 deg)
            heading = fields[7]
            pitch = fields[8]
            roll = fields[9]
            temp = fields[10]
            # pressure in units of daPa (= .01 kPa)
            pressure = fields[11]

            if heading < 0 or heading > 35999:
                raise ValueError('Heading outside of expected range 0 to 359.99 deg')
            if pitch < -6000 or pitch > 6000:
                raise ValueError('Pitch outside of expected range +/- 60.0 deg')
            if roll < -6000 or roll > 6000:
                raise ValueError('Roll outside of expected range +/- 60.0 deg')
            if temp < -500 or temp > 4000:
                raise ValueError('Temperature outside expected range -5.0 to 40.0 deg C')

        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))

        result = [{DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.PD12_PACKET_ID,
                   DataParticleKey.VALUE: packet_id},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.NUM_BYTES,
                   DataParticleKey.VALUE: num_bytes},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.ENSEMBLE_NUMBER,
                   DataParticleKey.VALUE: fields[2]},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.UNIT_ID,
                   DataParticleKey.VALUE: fields[3]},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.FIRMWARE_VERSION,
                   DataParticleKey.VALUE: fields[4]},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.FIRMWARE_REVISION,
                   DataParticleKey.VALUE: fields[5]},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.REAL_TIME_CLOCK,
                   DataParticleKey.VALUE: list(date_fields)},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.ENSEMBLE_START_TIME,
                   DataParticleKey.VALUE: sec_since_1900},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.HEADING,
                   DataParticleKey.VALUE: heading},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.PITCH,
                   DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.ROLL,
                   DataParticleKey.VALUE: roll},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temp},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.VELOCITY_PO_ERROR_FLAG,
                   DataParticleKey.VALUE: fields[12]&1},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.VELOCITY_PO_UP_FLAG,
                   DataParticleKey.VALUE: (fields[12]&2) >> 1},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.VELOCITY_PO_NORTH_FLAG,
                   DataParticleKey.VALUE: (fields[12]&4) >> 2},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.VELOCITY_PO_EAST_FLAG,
                   DataParticleKey.VALUE: (fields[12]&8) >> 3},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.SUBSAMPLING_PARAMETER,
                   DataParticleKey.VALUE: (fields[12]&240) >> 4},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.START_BIN,
                   DataParticleKey.VALUE: fields[13]},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.NUM_BINS,
                   DataParticleKey.VALUE: nbins},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.WATER_VELOCITY_EAST,
                   DataParticleKey.VALUE: list(vel_east)},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.WATER_VELOCITY_NORTH,
                   DataParticleKey.VALUE: list(vel_north)},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.WATER_VELOCITY_UP,
                   DataParticleKey.VALUE: list(vel_up)},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.ERROR_VELOCITY,
                   DataParticleKey.VALUE: list(vel_err)},
                  {DataParticleKey.VALUE_ID: AdcpsParserDataParticleKey.CHECKSUM,
                   DataParticleKey.VALUE: checksum[0]},]

        log.debug('AdcpsParserDataParticle: particle=%s', result)
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] == arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]) and \
            (self.contents[DataParticleKey.NEW_SEQUENCE] == arg.contents[DataParticleKey.NEW_SEQUENCE])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            elif self.contents[DataParticleKey.NEW_SEQUENCE] != arg.contents[DataParticleKey.NEW_SEQUENCE]:
                log.debug('Sequence does not match')
            return False

    @staticmethod
    def unpack_date(data):
        fields = struct.unpack('HBBBBBB', data)
        log.debug('Unpacked data into date fields %s', fields)
        zulu_ts = "%04d-%02d-%02dT%02d:%02d:%02d.%02dZ" % (
            fields[0], fields[1], fields[2], fields[3],
            fields[4], fields[5], fields[6])
        return zulu_ts


class AdcpsParser(MflmParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(AdcpsParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
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
        # all non-data packets will be read along with all the data, so we can't just use the fact that
        # there is or is not non-data to determine when a new sequence should occur.  The non-data will
        # keep getting shifted lower as things get cleaned out, and when it reaches the 0 index the non-data
        # is actually next
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        non_data_flag = False
        if non_data is not None and non_end <= start:
            log.debug('start setting non_data_flag')
            non_data_flag = True
            
        sample_count = 0
        new_seq = 0

        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            new_seq = 0
            log.debug('parsing header %s', header_match.group(0)[1:32])
            if header_match.group(1) == self._instrument_id:
                # Check for missing data between records
                if non_data_flag or self._new_seq_flag:
                    log.debug("Non matching data packet detected")
                    # reset non data flag and new sequence flags now
                    # that we have made a new sequence
                    non_data = None
                    non_data_flag = False
                    self._new_seq_flag = False
                    self.start_new_sequence()
                    # need to figure out if there is a new sequence the first time through,
                    # since if we are using in process data we don't read unprocessed again
                    new_seq = 1

                # need to do special processing on data to handle escape sequences
                # replace 0x182b with 0x2b and 0x1858 into 0x18
                processed_match = chunk.replace(b'\x182b', b'\x2b')
                processed_match = processed_match.replace(b'\x1858', b'\x18')
                log.debug("matched chunk header %s", processed_match[1:32])

                data_wrapper_match = DATA_WRAPPER_MATCHER.search(processed_match)
                if data_wrapper_match:
                    data_match = DATA_MATCHER.search(data_wrapper_match.group(1))
                    if data_match:
                        log.debug('Found data match in chunk %s', processed_match[1:32])
                        # pull out the date string from the data
                        date_str = AdcpsParserDataParticle.unpack_date(data_match.group(0)[11:19])
                        # convert to ntp
                        localtime_offset = float(parser.parse("1970-01-01T00:00:00.00Z").strftime("%s.%f"))
                        converted_time = float(parser.parse(date_str).strftime("%s.%f"))
                        # round to nearest .01
                        adjusted_time = round((converted_time - localtime_offset)*100)/100
                        self._timestamp = ntplib.system_to_ntp_time(adjusted_time)
                        log.debug("Converted time \"%s\" (unix: %s) into %s", date_str, adjusted_time, self._timestamp)

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
            self._chunk_new_seq.append(new_seq)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            # need to set a flag in case we read a chunk not matching the instrument ID and overwrite the non_data                    
            if non_data is not None and non_end <= start:
                log.debug('setting non_data_flag')
                non_data_flag = True

        return result_particles
