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
from mi.core.exceptions import SampleException, DatasetParserException, RecoverableSampleException
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER

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
    REFERENCE_LIGHT_MEASUREMENTS = 'reference_light_measurements'
    LIGHT_MEASUREMENTS = 'light_measurements'
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
            raise RecoverableSampleException("PhsenParserDataParticle: No regex match of \
                                              parsed sample data: [%s]", self.raw_data)

        ref_meas = []
        for i in range(0, 16):
            start_idx = 23 + i*4
            end_idx = 23 + (i+1)*4
            try:
                this_ref = int(match.group(0)[start_idx:end_idx], 16)
                ref_meas.append(this_ref)
            except Exception as e:
                ref_meas.append(None)
                self._encoding_errors.append({PhsenParserDataParticleKey.REFERENCE_LIGHT_MEASUREMENTS: "Error encoding %d: %s" % (i, e)})

        light_meas = []
        for i in range(0, 23):
            for s in range(0,4):
                start_idx = 87 + i*16 + s*4
                end_idx = 87 + i*16 + (s+1)*4
                try:
                    this_meas = int(match.group(0)[start_idx:end_idx], 16)
                    light_meas.append(this_meas)
                except Exception as e:
                    light_meas.append(None)
                    self._encoding_errors.append({PhsenParserDataParticleKey.LIGHT_MEASUREMENTS: "Error encoding (%d,%d): %s" % (i, s, e)})

        # calculate the checksum and compare with the received checksum
        try: 
            chksum = PhsenParserDataParticle.encode_int_16(match.group(0)[467:469])
            sum_bytes = 0
            for i in range(7, 467, 2):
                sum_bytes += int(match.group(0)[i:i+2], 16)
            calc_chksum = sum_bytes & 255
            if calc_chksum != chksum:
                raise RecoverableSampleException('Calculated internal checksum %d does not match received %d' % (calc_chksum, chksum))
        except Exception as e:
            raise RecoverableSampleException('Error comparing checksums: %s' % e)

        result = [self._encode_value(PhsenParserDataParticleKey.UNIQUE_ID, match.group(0)[5:7],
                                     PhsenParserDataParticle.encode_int_16),
                  self._encode_value(PhsenParserDataParticleKey.RECORD_LENGTH, match.group(0)[7:9],
                                     PhsenParserDataParticle.encode_int_16),
                  self._encode_value(PhsenParserDataParticleKey.RECORD_TYPE, match.group(0)[9:11],
                                     PhsenParserDataParticle.encode_int_16),
                  self._encode_value(PhsenParserDataParticleKey.RECORD_TIME, match.group(0)[11:19],
                                     PhsenParserDataParticle.encode_int_16),
                  self._encode_value(PhsenParserDataParticleKey.THERMISTOR_START, match.group(0)[19:23],
                                     PhsenParserDataParticle.encode_int_16),
                  self._encode_value(PhsenParserDataParticleKey.REFERENCE_LIGHT_MEASUREMENTS,
                                     ref_meas, list),
                  self._encode_value(PhsenParserDataParticleKey.LIGHT_MEASUREMENTS,
                                     light_meas, list),
                  self._encode_value(PhsenParserDataParticleKey.VOLTAGE_BATTERY, match.group(0)[459:463],
                                     PhsenParserDataParticle.encode_int_16),
                  self._encode_value(PhsenParserDataParticleKey.THERMISTOR_END, match.group(0)[463:467],
                                     PhsenParserDataParticle.encode_int_16),
                  self._encode_value(PhsenParserDataParticleKey.CHECKSUM, match.group(0)[467:469],
                                     PhsenParserDataParticle.encode_int_16)]
        return result

    @staticmethod
    def encode_int_16(int_val):
        """
        Use to convert from hex-ascii to int when encoding data particle values
        """
        return int(int_val, 16)

class PhsenParser(SioMuleParser):
    
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(PhsenParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
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
            #log.debug('parsing header %s', header_match.group(0)[1:32])
            if header_match.group(1) == 'PH':

                for data_match in DATA_MATCHER.finditer(chunk):
                    #log.debug('Found data match in chunk %s', chunk[1:32])
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

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

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
        #log.debug('seconds since 1904 %d, elapsed 1904 %d', sec_since_1904, elapse_1904)
        sec_since_1970 = sec_since_1904 + elapse_1904 - time.timezone
        #log.debug("Got time %s", datetime.utcfromtimestamp(sec_since_1970))
        ntptime = ntplib.system_to_ntp_time(sec_since_1970)
        #log.debug("Converted time \"%s\" (unix: %s) into %s", hex_time,
        #                      sec_since_1970, ntptime)
        return ntptime



