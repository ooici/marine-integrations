#!/usr/bin/env python

"""
@package mi.dataset.parser.phsen
@file marine-integrations/mi/dataset/parser/phsen.py
@author Emily Hahn
@brief Parser for the mflm_phsen dataset driver
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re
import ntplib
import time
from datetime import datetime
from dateutil import parser

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.parser.mflm import MflmParser, SIO_HEADER_MATCHER

DATA_REGEX = b'\^0A\r\*([0-9A-Fa-f]{4})0A([0-9A-Fa-f]{458})\r'
DATA_MATCHER = re.compile(DATA_REGEX)

class DataParticleType(BaseEnum):
    SAMPLE = 'phsen_parsed'

class PhsenParserDataParticleKey(BaseEnum):
    UNIQUE_ID = 'unique_id'
    RECORD_LENGTH = 'record_length'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time_1904_uint32'
    THERMISTOR_START = 'thermistor_start'
    REFERENCE_LIGHT_MEASUREMENT = 'reference_light_measurement'
    LIGHT_MEASUREMENT = 'light_measurement'
    VOLTAGE_BATTERY = 'voltage_battery'
    THERMISTOR_END = 'thermistor_end'
    CHECKSUM = 'checksum'

class PhsenParserDataParticle(DataParticle):
    """
    Class for parsing data from the mflm_phsen instrument
    """

    _data_particle_type = DataParticleType.SAMPLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("PhsenParserDataParticle: No regex match of \
                                  parsed sample data: [%s]", self.raw_data)

        try:
            log.debug('Converting data %s', match.group(0))
            # just convert directly from hex-ascii to int
            unique_id = int(match.group(0)[5:7], 16)
            rec_length = int(match.group(0)[7:9], 16)
            rec_type = int(match.group(0)[9:11], 16)
            rec_time = int(match.group(0)[11:19], 16)
            therm_start = int(match.group(0)[19:23], 16)
            ref_meas = []
            for i in range(0, 16):
                start_idx = 23 + i*4
                end_idx = 23 + (i+1)*4
                this_ref = int(match.group(0)[start_idx:end_idx], 16)
                ref_meas.append(this_ref)

            light_meas = []
            for i in range(0, 23):
                for s in range(0,4):
                    start_idx = 87 + i*16 + s*4
                    end_idx = 87 + i*16 + (s+1)*4
                    this_meas = int(match.group(0)[start_idx:end_idx], 16)
                    light_meas.append(this_meas)
            # there are 2 non-used characters, skip from 455 to 459
            volt_batt = int(match.group(0)[459:463], 16)
            therm_end = int(match.group(0)[463:467], 16)
            chksum = int(match.group(0)[467:469], 16)

            # calculate the checksum and compare with the received checksum
            sum_bytes = 0
            for i in range(7, 467, 2):
                sum_bytes += int(match.group(0)[i:i+2], 16)
            calc_chksum = sum_bytes & 255
            if calc_chksum != chksum:
                raise ValueError('Calculated internal checksum %d does not match received %d', calc_chksum, chksum)

        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        result = [{DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.UNIQUE_ID,
                   DataParticleKey.VALUE: unique_id},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.RECORD_LENGTH,
                   DataParticleKey.VALUE: rec_length},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.RECORD_TYPE,
                   DataParticleKey.VALUE: rec_type},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.RECORD_TIME,
                   DataParticleKey.VALUE: rec_time},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.THERMISTOR_START,
                   DataParticleKey.VALUE: therm_start},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.REFERENCE_LIGHT_MEASUREMENT,
                   DataParticleKey.VALUE: list(ref_meas)},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.LIGHT_MEASUREMENT,
                   DataParticleKey.VALUE: list(light_meas)},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.VOLTAGE_BATTERY,
                   DataParticleKey.VALUE: volt_batt},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.THERMISTOR_END,
                   DataParticleKey.VALUE: therm_end},
                  {DataParticleKey.VALUE_ID: PhsenParserDataParticleKey.CHECKSUM,
                   DataParticleKey.VALUE: chksum}]
        log.trace('PhsenParserDataParticle: particle=%s', result)
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

class PhsenParser(MflmParser):
    
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(PhsenParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          'PH',
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

                for data_match in DATA_MATCHER.finditer(processed_match):
                    log.debug('Found data match in chunk %s', processed_match[1:32])
                    self._timestamp = self.hex_time_to_ntp(data_match.group(0)[11:19])
                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(PhsenParserDataParticle,
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
    
    def hex_time_to_ntp(self, hex_time):
        """
        Convert between a ascii hex string representing seconds into ntp time
        @param hex_time ascii hex string of seconds since Jan 1 1904
        @retval ntptime time in ntp format 
        """
        sec_since_1904 = int(hex_time, 16)
        local_dt_1904 = parser.parse("1904-01-01T00:00:00.00Z")
        elapse_1904 = float(local_dt_1904.strftime("%s.%f"))
        log.debug('seconds since 1904 %d, elapsed 1904 %d', sec_since_1904, elapse_1904)
        sec_since_1970 = sec_since_1904 + elapse_1904 - time.timezone
        log.debug("Got time %s", datetime.utcfromtimestamp(sec_since_1970))
        ntptime = ntplib.system_to_ntp_time(sec_since_1970)
        log.debug("Converted time \"%s\" (unix: %s) into %s", hex_time,
                              sec_since_1970, ntptime)
        return ntptime



