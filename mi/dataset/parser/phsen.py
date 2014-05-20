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
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.exceptions import SampleException, DatasetParserException, RecoverableSampleException
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER

DATA_REGEX = b'(\^0A\r\*|\*)([0-9A-Fa-f]{4}0A)([\x00-\xFF]{8})([0-9A-Fa-f]{450})\r'
DATA_MATCHER = re.compile(DATA_REGEX)

TIMESTAMP_REGEX = b'[0-9A-Fa-f]{8}'
TIMESTAMP_MATCHER = re.compile(TIMESTAMP_REGEX)

class DataParticleType(BaseEnum):
    SAMPLE = 'phsen_abcdef_sio_mule_instrument'

class PhsenParserDataParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = 'controller_timestamp'
    UNIQUE_ID = 'unique_id'
    RECORD_TYPE = 'record_type'
    RECORD_TIME = 'record_time_1904_uint32'
    THERMISTOR_START = 'thermistor_start'
    REFERENCE_LIGHT_MEASUREMENTS = 'reference_light_measurements'
    LIGHT_MEASUREMENTS = 'light_measurements'
    VOLTAGE_BATTERY = 'voltage_battery'
    THERMISTOR_END = 'thermistor_end'
    PASSED_CHECKSUM = 'passed_checksum'

class PhsenParserDataParticle(DataParticle):
    """
    Class for parsing data from the mflm_phsen instrument
    """

    _data_particle_type = DataParticleType.SAMPLE

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(PhsenParserDataParticle, self).__init__(raw_data,
                                                      port_timestamp=None,
                                                      internal_timestamp=None,
                                                      preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                                                      quality_flag=DataParticleValue.OK,
                                                      new_sequence=None)
        timestamp_match = TIMESTAMP_MATCHER.match(self.raw_data[:8])
        if not timestamp_match:
            raise RecoverableSampleException("PhsenParserDataParticle: No regex match of " \
                                             "timestamp [%s]" % self.raw_data[:8])
        self._data_match = DATA_MATCHER.match(self.raw_data[8:])
        if not self._data_match:
            raise RecoverableSampleException("PhsenParserDataParticle: No regex match of " \
                                             "parsed sample data [%s]" % self.raw_data[8:])

        # use the timestamp from the sio header as internal timestamp
        sec_since_1970 = int(self.raw_data[:8], 16)
        self.set_internal_timestamp(unix_time=sec_since_1970)

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        result = []
        if self._data_match:

            ref_meas = []
            for i in range(0, 16):
                start_idx = 4 + i*4
                end_idx = 4 + (i+1)*4
                try:
                    this_ref = int(self._data_match.group(4)[start_idx:end_idx], 16)
                    ref_meas.append(this_ref)
                except Exception as e:
                    ref_meas.append(None)
                    self._encoding_errors.append({PhsenParserDataParticleKey.REFERENCE_LIGHT_MEASUREMENTS: "Error encoding %d: %s" % (i, e)})
    
            light_meas = []
            for i in range(0, 23):
                for s in range(0,4):
                    start_idx = 68 + i*16 + s*4
                    end_idx = 68 + i*16 + (s+1)*4
                    try:
                        this_meas = int(self._data_match.group(4)[start_idx:end_idx], 16)
                        light_meas.append(this_meas)
                    except Exception as e:
                        light_meas.append(None)
                        self._encoding_errors.append({PhsenParserDataParticleKey.LIGHT_MEASUREMENTS: "Error encoding (%d,%d): %s" % (i, s, e)})
    
            # calculate the checksum and compare with the received checksum
            passed_checksum = True
            try: 
                chksum = PhsenParserDataParticle.encode_int_16(self._data_match.group(0)[-3:-1])
                sum_bytes = 0
                for i in range(7, 467, 2):
                    sum_bytes += int(self._data_match.group(0)[i:i+2], 16)
                calc_chksum = sum_bytes & 255
                if calc_chksum != chksum:
                    passed_checksum = False
                    log.debug('Calculated internal checksum %d does not match received %d', calc_chksum, chksum)
            except Exception as e:
                log.debug('Error calculating checksums: %s, setting passed checksum to False', e)
                passed_checksum = False

            result = [self._encode_value(PhsenParserDataParticleKey.CONTROLLER_TIMESTAMP, self.raw_data[:8],
                                         PhsenParserDataParticle.encode_int_16),
                      self._encode_value(PhsenParserDataParticleKey.UNIQUE_ID, self._data_match.group(2)[0:2],
                                         PhsenParserDataParticle.encode_int_16),
                      self._encode_value(PhsenParserDataParticleKey.RECORD_TYPE, self._data_match.group(2)[4:6],
                                         PhsenParserDataParticle.encode_int_16),
                      self._encode_value(PhsenParserDataParticleKey.RECORD_TIME, self._data_match.group(3),
                                         PhsenParserDataParticle.encode_timestamp),
                      self._encode_value(PhsenParserDataParticleKey.THERMISTOR_START, self._data_match.group(4)[0:4],
                                         PhsenParserDataParticle.encode_int_16),
                      self._encode_value(PhsenParserDataParticleKey.REFERENCE_LIGHT_MEASUREMENTS,
                                         ref_meas, list),
                      self._encode_value(PhsenParserDataParticleKey.LIGHT_MEASUREMENTS,
                                         light_meas, list),
                      self._encode_value(PhsenParserDataParticleKey.VOLTAGE_BATTERY, self._data_match.group(0)[-11:-7],
                                         PhsenParserDataParticle.encode_int_16),
                      self._encode_value(PhsenParserDataParticleKey.THERMISTOR_END, self._data_match.group(0)[-7:-3],
                                         PhsenParserDataParticle.encode_int_16),
                      self._encode_value(PhsenParserDataParticleKey.PASSED_CHECKSUM, passed_checksum,
                                         bool)]
        return result

    @staticmethod
    def encode_int_16(int_val):
        """
        Use to convert from hex-ascii to int when encoding data particle values
        """
        return int(int_val, 16)

    @staticmethod
    def encode_timestamp(timestamp_str):
        timestamp_match = TIMESTAMP_MATCHER.match(timestamp_str)
        if not timestamp_match:
            return None
        else:
            return PhsenParserDataParticle.encode_int_16(timestamp_str)

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
            if header_match.group(1) == 'PH':

                for data_match in DATA_MATCHER.finditer(chunk):
                    log.debug('Found data match in chunk %s', chunk[1:32])
                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(PhsenParserDataParticle, None,
                                                  header_match.group(3) + data_match.group(0),
                                                  None)
                    if sample:
                        # create particle
                        result_particles.append(sample)
                        sample_count += 1

            self._chunk_sample_count.append(sample_count)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        return result_particles
