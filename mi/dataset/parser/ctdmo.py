#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdmo 
@file mi/dataset/parser/ctdmo.py
@author Emily Hahn
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

from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER
from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, RecoverableSampleException, DatasetParserException
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue

class DataParticleType(BaseEnum):
    CT = 'ctdmo_ghqr_sio_mule_instrument'
    CO = 'ctdmo_ghqr_sio_offset'
    
class CtdmoParserDataParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = "sio_controller_timestamp"
    INDUCTIVE_ID = "inductive_id"
    TEMPERATURE = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    CTD_TIME = "ctd_time"

DATA_REGEX = b'[\x00-\xFF]{8}([\x00-\xFF]{4})\x0d'
DATA_MATCHER = re.compile(DATA_REGEX)

CO_REGEX = b'[\x00-\xFF]{5}\x13'
CO_MATCHER = re.compile(CO_REGEX)

DATA_SAMPLE_BYTES = 13
SIO_HEADER_BYTES = 32
CO_SAMPLE_BYTES = 6

class CtdmoParserDataParticle(DataParticle):
    """
    Class for parsing data from the CTDMO instrument on a MSFM platform node
    """
    
    _data_particle_type = DataParticleType.CT
    
    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(CtdmoParserDataParticle, self).__init__(raw_data,
                                                      port_timestamp=None,
                                                      internal_timestamp=None,
                                                      preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                                                      quality_flag=DataParticleValue.OK,
                                                      new_sequence=None)
        self._data_match = DATA_MATCHER.match(self.raw_data[8:])
        if not self._data_match:
            raise RecoverableSampleException("CtdmoParserDataParticle: No regex match of "\
                                              "parsed sample data: [%s]" % self.raw_data[8:])
        asciihextime = binascii.b2a_hex(self._data_match.group(1))
        # reverse byte order in time hex string
        timehex_reverse = asciihextime[6:8] + asciihextime[4:6] + \
        asciihextime[2:4] + asciihextime[0:2]
        gmt_dt_2000 = parser.parse("2000-01-01T00:00:00.00Z")
        elapse_2000 = float(gmt_dt_2000.strftime("%s.%f"))
        # convert from epoch in 2000 to epoch in 1970, GMT
        sec_since_1970 = int(timehex_reverse, 16) + elapse_2000 - time.timezone

        self.set_internal_timestamp(unix_time=sec_since_1970)

    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        result = []
        if self._data_match:
            try:
                # convert binary to hex ascii string
                asciihex = binascii.b2a_hex(self._data_match.group(0))
                # need to swap pressure bytes
                press_byte_swap = asciihex[14:16] + asciihex[12:14]

                asciihextime = binascii.b2a_hex(self._data_match.group(1))
                # reverse byte order in time hex string
                timehex_reverse = asciihextime[6:8] + asciihextime[4:6] + \
                asciihextime[2:4] + asciihextime[0:2]

            except (ValueError, TypeError, IndexError) as ex:
                log.warn("Error (%s) while decoding parameters in data: [%s]", ex, self.raw_data)
                raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                      % (ex, self.raw_data))

            result = [self._encode_value(CtdmoParserDataParticleKey.CONTROLLER_TIMESTAMP, self.raw_data[0:8],
                                         CtdmoParserDataParticle.encode_int_16),
                      self._encode_value(CtdmoParserDataParticleKey.INDUCTIVE_ID, asciihex[0:2],
                                         CtdmoParserDataParticle.encode_int_16),
                      self._encode_value(CtdmoParserDataParticleKey.TEMPERATURE, asciihex[2:7],
                                         CtdmoParserDataParticle.encode_int_16),
                      self._encode_value(CtdmoParserDataParticleKey.CONDUCTIVITY, asciihex[7:12],
                                         CtdmoParserDataParticle.encode_int_16),
                      self._encode_value(CtdmoParserDataParticleKey.PRESSURE, press_byte_swap,
                                         CtdmoParserDataParticle.encode_int_16),
                      self._encode_value(CtdmoParserDataParticleKey.CTD_TIME, timehex_reverse,
                                         CtdmoParserDataParticle.encode_int_16)]
        log.trace('CtdmoParserDataParticle: particle=%s', result)
        return result

    @staticmethod
    def encode_int_16(int_val):
        """
        Use to convert from hex-ascii to int when encoding data particle values
        """
        return int(int_val, 16)

class CtdmoOffsetDataParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = "sio_controller_timestamp"
    INDUCTIVE_ID = "inductive_id"
    CTD_OFFSET = "ctd_time_offset"

class CtdmoOffsetDataParticle(DataParticle):
    """
    Class for parsing data from the CTDMO instrument on a MSFM platform node
    """

    _data_particle_type = DataParticleType.CO

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(CtdmoOffsetDataParticle, self).__init__(raw_data,
                                                      port_timestamp=None,
                                                      internal_timestamp=None,
                                                      preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                                                      quality_flag=DataParticleValue.OK,
                                                      new_sequence=None)
        timestamp = int(self.raw_data[:8], 16)
        self.set_internal_timestamp(unix_time=timestamp)

    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = CO_MATCHER.match(self.raw_data[8:])
        if not match:
            raise RecoverableSampleException("CtdmoOffsetParserDataParticle: No regex match of \
                                              parsed sample data: [%s]", self.raw_data[8:])
        # convert binary to hex ascii string
        asciihex = binascii.b2a_hex(match.group(0))
        result = [self._encode_value(CtdmoOffsetDataParticleKey.CONTROLLER_TIMESTAMP, self.raw_data[0:8],
                                     CtdmoParserDataParticle.encode_int_16),
                  self._encode_value(CtdmoOffsetDataParticleKey.INDUCTIVE_ID, asciihex[0:2],
                                     CtdmoParserDataParticle.encode_int_16),
                  self._encode_value(CtdmoOffsetDataParticleKey.CTD_OFFSET, asciihex[2:10],
                                     CtdmoParserDataParticle.encode_int_16)]
        log.trace('CtdmoOffsetParserDataParticle: particle=%s', result)
        return result

class CtdmoParser(SioMuleParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(CtdmoParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)
        if not 'inductive_id' in config:
            raise DatasetParserException("Parser config is missing inductive ID")

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
        prev_sample = None

        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            prev_sample = None
            # start looping at the end of the header, after \x02
            chunk_idx = SIO_HEADER_BYTES + 1
            # last possible chunk index, excluding \x03
            last_chunk_idx = len(chunk) - 1

            if header_match.group(1) == 'CT':
                log.debug("matched CT chunk header %s", chunk[1:SIO_HEADER_BYTES])
                while chunk_idx < last_chunk_idx:
                    data_match = DATA_MATCHER.match(chunk[chunk_idx:chunk_idx+DATA_SAMPLE_BYTES])
                    if data_match:
                        if self.compare_inductive_id(data_match):
                            # particle-ize the data block received, return the record
                            sample = self._extract_sample(CtdmoParserDataParticle, None,
                                                          header_match.group(3) + data_match.group(0),
                                                          None)
                            if sample:
                                # create particle
                                result_particles.append(sample)
                                sample_count += 1
                        chunk_idx += DATA_SAMPLE_BYTES
                    else:
                        log.error('unknown data found in CT chunk %s at %d, leaving out the rest',
                                  binascii.b2a_hex(chunk), chunk_idx)
                        self._exception_callback(SampleException(
                            'unknown data found in CT chunk at %d, leaving out the rest' % chunk_idx))
                        break

            elif header_match.group(1) == 'CO':
                log.debug("matched CO chunk header %s", chunk[1:SIO_HEADER_BYTES])
                while chunk_idx < last_chunk_idx:
                    data_match = CO_MATCHER.match(chunk[chunk_idx:chunk_idx+CO_SAMPLE_BYTES])
                    if data_match:
                        if self.compare_inductive_id(data_match):
                            # particle-ize the data block received, return the record
                            sample = self._extract_sample(CtdmoOffsetDataParticle, None,
                                                          header_match.group(3) + data_match.group(0),
                                                          None)
                            if sample:
                                # create particle
                                result_particles.append(sample)
                                sample_count += 1
                        chunk_idx += CO_SAMPLE_BYTES
                    else:
                        log.error('unknown data found in CO chunk %s at %d, leaving out the rest',
                                  binascii.b2a_hex(chunk), chunk_idx)
                        self._exception_callback(SampleException(
                            'unknown data found in CO chunk at %d, leaving out the rest' % chunk_idx))
                        break

            # keep track of how many samples were found in this chunk
            self._chunk_sample_count.append(sample_count)
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        return result_particles

    def compare_inductive_id(self, data_match):
        """
        Compare the inductive id from the data with the configured inductive ID
        @param data_match block of binary data starting with inductive ID
        @returns True if IDs match, False if they don't
        """
        asciihex_id = binascii.b2a_hex(data_match.group(0)[0:1])
        induct_id = int(asciihex_id, 16)
        if induct_id == self._config.get('inductive_id'):
            return True
        return False
