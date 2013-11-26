#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdmo 
@file mi/dataset/parser/ctdmo.py
@author Emily Hzhn
@brief A CTDMO-specific data set agent parser
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import binascii
import array
import string
import re
import time
import ntplib
from dateutil import parser
from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.parser.mflm import MflmParser, SIO_HEADER_MATCHER
from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.data_particle import DataParticle, DataParticleKey

class DataParticleType(BaseEnum):
    SAMPLE = 'ctdmo_parsed'
    
class CtdmoParserDataParticleKey(BaseEnum):
    INDUCTIVE_ID = "inductive_id"
    TEMPERATURE = "temp"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    CTD_TIME = "ctd_time"

# the [\x16-\x40] is because we need more than just \x0d to correctly
# identify the split between samples, the data might have \x0d in it also,
# so since this value has to do with the year, x16 = august 2011 to
# x40 = july 2034
DATA_REGEX = b'[\x00-\xFF]{8}([\x00-\xFF]{3}[\x16-\x40]{1})\x0d'
DATA_MATCHER = re.compile(DATA_REGEX)

class CtdmoParserDataParticle(DataParticle):
    """
    Class for parsing data from the CTDMO instrument on a MSFM platform node
    """
    
    _data_particle_type = DataParticleType.SAMPLE
    
    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("CtdmoParserDataParticle: No regex match of \
                                  parsed sample data: [%s]", self.raw_data)

        try:
            # convert binary to hex ascii string
            asciihex = binascii.b2a_hex(match.group(0))
            log.debug('Converting data %s', asciihex)
            induct_id = int(asciihex[0:2], 16)
            # just convert directly from hex-ascii to int
            temp_num = int(asciihex[2:7], 16)
            temp = (float(temp_num) / 10000.0) - 10
            log.debug('Hex %s to temp num %d converted to temp %f', asciihex[2:7], temp_num, temp)
            if temp > 50 or temp < -10:
                raise ValueError('Temperature %f outside reasonable range of -10 to 50 C'%temp)
            cond_num = int(asciihex[7:12], 16)
            cond = (float(cond_num) / 100000.0) - .5
            log.debug('Hex %s to cond num %d to conductivity %f', asciihex[7:12], cond_num, cond)
            if cond > 15 or cond < 0:
                raise ValueError('Conductivity %f is outside reasonable range of .005 to 15'%cond)
            # need to swap pressure bytes
            press_byte_swap = asciihex[14:16] + asciihex[12:14]
            press_num = int(press_byte_swap, 16)
            pressure_range = .6894757 * (1000 - 14)
            press = (float(press_num) * pressure_range / (.85 * 65536.0)) - (.05 * pressure_range)
            log.debug('Hex %s convert to press num %d to pressure %f', press_byte_swap, press_num, press)
            if press > 10900 or press < 0:
                raise ValueError('Pressure %f is outside reasonable range of 0 to 10900 dbar'%press)

            asciihextime = binascii.b2a_hex(match.group(1))
            # reverse byte order in time hex string
            timehex_reverse = asciihextime[6:8] + asciihextime[4:6] + \
            asciihextime[2:4] + asciihextime[0:2]
            # time is in seconds since Jan 1 2000, convert to timestamp
            internal_time = int(timehex_reverse, 16)

        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        result = [{DataParticleKey.VALUE_ID: CtdmoParserDataParticleKey.INDUCTIVE_ID,
                   DataParticleKey.VALUE: induct_id},
                  {DataParticleKey.VALUE_ID: CtdmoParserDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temp},
                  {DataParticleKey.VALUE_ID: CtdmoParserDataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: cond},
                  {DataParticleKey.VALUE_ID: CtdmoParserDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: press},
                  {DataParticleKey.VALUE_ID: CtdmoParserDataParticleKey.CTD_TIME,
                   DataParticleKey.VALUE: internal_time}]
        log.trace('CtdmoParserDataParticle: particle=%s', result)
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this particle
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
                log.debug('Timestamp %s and %s do not match',
                          self.contents[DataParticleKey.INTERNAL_TIMESTAMP],
                          arg.contents[DataParticleKey.INTERNAL_TIMESTAMP] )
            return False


class CtdmoParser(MflmParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(CtdmoParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          'CT',
                                          *args,
                                          **kwargs)
        if not 'inductive_id' in config:
            raise DatasetParserException("Parser config is missing inductive ID")

    @staticmethod
    def _convert_time_to_timestamp(sec_since_2000):
        """
        Converts the given string in matched format into an NTP timestamp.
        @param ts_str The timestamp string in the format "mm/dd/yyyy hh:mm:ss"
        @retval The NTP4 timestamp
        """
        log.debug("Convert seconds since 2000: %d", sec_since_2000)

        # get seconds since jan 1 2000 (gmt timezone)
        gmt_dt_2000 = parser.parse("2000-01-01T00:00:00.00Z")
        elapse_2000 = float(gmt_dt_2000.strftime("%s.%f"))
        log.debug("elapse since 2000: %s", elapse_2000)

        # convert from epoch in 2000 to epoch in 1970, GMT
        sec_since_1970 = sec_since_2000 + elapse_2000 - time.timezone
        ntptime = ntplib.system_to_ntp_time(sec_since_1970)
        log.debug("seconds since 1970 %d, ntptime %s", sec_since_1970, ntptime)
        return ntptime

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
        # all non-data packets will be read along with all the data, so we can't just use the fact that
        # there is or is not non-data to determine when a new sequence should occur.  The non-data will
        # keep getting shifted lower as actual data get cleaned out, so as long as the end of non-data
        # is before the start of the data it counts
        non_data_flag = False
        if non_data is not None and non_end <= start:
            non_data_flag = True

        sample_count = 0
        prev_sample = None
        new_seq = 0

        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            prev_sample = None
            new_seq = 0
            if header_match.group(1) == self._instrument_id:
                # Check for missing data between records
                if non_data_flag or self._new_seq_flag:
                    log.trace("Non matching data packet detected")
                    # reset non data flag and new sequence flags now
                    # that we have made a new sequence
                    non_data_flag = False
                    self._new_seq_flag = False
                    # No longer starting new sequences on gaps. for now.
                    #self.start_new_sequence()
                    new_seq = 1

                # need to do special processing on data to handle escape sequences
                # replace 0x182b with 0x2b and 0x1858 into 0x18
                chunk = chunk.replace(b'\x182b', b'\x2b')
                chunk = chunk.replace(b'\x1858', b'\x18')
                log.debug("matched chunk header %s", chunk[1:32])

                for data_match in DATA_MATCHER.finditer(chunk):
                    # check if the end of the last sample connects to the start of the next sample
                    if prev_sample is not None:
                        if data_match.start(0) != prev_sample:
                            log.error('extra data found between samples, leaving out the rest of this chunk')
                            break
                    prev_sample = data_match.end(0)
                    # the timestamp is part of the data, pull out the time stamp
                    # convert from binary to hex string
                    asciihex_id = binascii.b2a_hex(data_match.group(0)[0:1])
                    induct_id = int(asciihex_id, 16)
                    if induct_id == self._config.get('inductive_id'):
                        asciihextime = binascii.b2a_hex(data_match.group(1))
                        # reverse byte order in time hex string
                        timehex_reverse = asciihextime[6:8] + asciihextime[4:6] + \
                        asciihextime[2:4] + asciihextime[0:2]
                        # time is in seconds since Jan 1 2000, convert to timestamp
                        log.trace("time in hex:%s, in seconds:%d", timehex_reverse,
                                  int(timehex_reverse, 16))
                        self._timestamp = self._convert_time_to_timestamp(int(timehex_reverse, 16))
                        # particle-ize the data block received, return the record
                        sample = self._extract_sample(CtdmoParserDataParticle,
                                                      DATA_MATCHER,
                                                      data_match.group(0),
                                                      self._timestamp)
                        if sample:
                            # create particle
                            result_particles.append(sample)
                            sample_count += 1
            # keep track of how many samples were found in this chunk
            self._chunk_sample_count.append(sample_count)
            self._chunk_new_seq.append(new_seq)
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            # need to set a flag in case we read a chunk not matching the instrument ID and overwrite the non_data
            if non_data is not None and non_end <= start:
                non_data_flag = True

        return result_particles

