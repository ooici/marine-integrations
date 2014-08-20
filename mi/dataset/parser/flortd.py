#!/usr/bin/env python

"""
@package mi.dataset.parser.flortd
@file mi/dataset/parser/flortd.py
@author Emily Hahn
@brief An flort-d specific dataset agent parser
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re
import ntplib
import time
from time import strftime, strptime
from dateutil import parser

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue

from mi.dataset.dataset_parser import Parser
from mi.dataset.parser.sio_mule_common import SioMuleParser, SioParser, SIO_HEADER_MATCHER
from mi.core.exceptions import SampleException, DatasetParserException


class DataParticleType(BaseEnum):
    SAMPLE = 'flort_dj_sio_instrument'
    SAMPLE_RECOVERED = 'flort_dj_sio_instrument_recovered'

class FlortdParserDataParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = 'sio_controller_timestamp'
    DATE_STRING = 'date_string'
    TIME_STRING = 'time_string'
    MEASUREMENT_WAVELENGTH_BETA = 'measurement_wavelength_beta'
    RAW_SIGNAL_BETA = 'raw_signal_beta'
    MEASUREMENT_WAVELENTH_CHL = 'measurement_wavelength_chl'
    RAW_SIGNAL_CHL = 'raw_signal_chl'
    MEASUREMENT_WAVELENGTH_CDOM = 'measurement_wavelength_cdom'
    RAW_SIGNAL_CDOM = 'raw_signal_cdom'
    RAW_INTERNAL_TEMP = 'raw_internal_temp'

# the first two groups make up the sample timestamp (date, time),
# followed by 7 integer data values, which may be marked as not present by '--'
DATA_REGEX = r'(\d\d/\d\d/\d\d)\t(\d\d:\d\d:\d\d)\t(\d+|--)\t(\d+|--)\t(\d+|--)\t(\d+|--)\t(\d+|--)\t(\d+|--)\t(\d+|--)'
DATA_MATCHER = re.compile(DATA_REGEX)

# match the timestamp from the sio mule header
TIMESTAMP_REGEX = b'[0-9A-Fa-f]{8}'
TIMESTAMP_MATCHER = re.compile(TIMESTAMP_REGEX)

class FlortdCommonParserDataParticle(DataParticle):
    """
    Class for parsing data from the FLORT-D instrument
    """

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(FlortdCommonParserDataParticle, self).__init__(raw_data,
                                                      port_timestamp,
                                                      internal_timestamp,
                                                      preferred_timestamp,
                                                      quality_flag,
                                                      new_sequence)
        # the raw data has the timestamp from the sio header pre-pended to it, match the first 8 bytes
        timestamp_match = TIMESTAMP_MATCHER.match(self.raw_data[:8])
        if not timestamp_match:
            raise RecoverableSampleException("FlortdParserDataParticle: No regex match of " \
                                             "timestamp [%s]" % self.raw_data[:8])
        # now match the flort data, excluding the sio header timestamp in the first 8 bytes
        self._data_match = DATA_MATCHER.match(self.raw_data[8:])
        if not self._data_match:
            raise RecoverableSampleException("FlortdParserDataParticle: No regex match of \
                                              parsed sample data [%s]", self.raw_data[8:])

        # use the timestamp from the sio header as internal timestamp
        sec_since_1970 = int(self.raw_data[:8], 16)
        self.set_internal_timestamp(unix_time=sec_since_1970)

    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        throws SampleException If there is a problem with sample creation
        """
        # match the data inside the wrapper
        result = []
        if self._data_match:
            result = [self._encode_value(FlortdParserDataParticleKey.CONTROLLER_TIMESTAMP, self.raw_data[:8],
                                         FlortdParserDataParticle.encode_int_16),
                      self._encode_value(FlortdParserDataParticleKey.DATE_STRING, self._data_match.group(1), str),
                      self._encode_value(FlortdParserDataParticleKey.TIME_STRING, self._data_match.group(2), str),
                      self._encode_value(FlortdParserDataParticleKey.MEASUREMENT_WAVELENGTH_BETA, self._data_match.group(3),
                                         FlortdParserDataParticle.encode_int_or_dash),
                      self._encode_value(FlortdParserDataParticleKey.RAW_SIGNAL_BETA, self._data_match.group(4),
                                         FlortdParserDataParticle.encode_int_or_dash),
                      self._encode_value(FlortdParserDataParticleKey.MEASUREMENT_WAVELENTH_CHL, self._data_match.group(5),
                                         FlortdParserDataParticle.encode_int_or_dash),
                      self._encode_value(FlortdParserDataParticleKey.RAW_SIGNAL_CHL, self._data_match.group(6),
                                         FlortdParserDataParticle.encode_int_or_dash),
                      self._encode_value(FlortdParserDataParticleKey.MEASUREMENT_WAVELENGTH_CDOM, self._data_match.group(7),
                                         FlortdParserDataParticle.encode_int_or_dash),
                      self._encode_value(FlortdParserDataParticleKey.RAW_SIGNAL_CDOM, self._data_match.group(8),
                                         FlortdParserDataParticle.encode_int_or_dash),
                      self._encode_value(FlortdParserDataParticleKey.RAW_INTERNAL_TEMP, self._data_match.group(9),
                                         FlortdParserDataParticle.encode_int_or_dash)]

        return result

    @staticmethod
    def encode_int_16(hex_str):
        return int(hex_str, 16)

    @staticmethod
    def encode_int_or_dash(val_str):
        """
        Need to handle missing values as "--" instead of an int
        """
        if val_str == "--":
            return None
        return int(val_str)


class FlortdParserDataParticle(FlortdCommonParserDataParticle):
    """
    Class for parsing telemetered FLORT-D data
    """
    _data_particle_type = DataParticleType.SAMPLE


class FlortdRecoveredParserDataParticle(FlortdCommonParserDataParticle):
    """
    Class for parsing recovered FLORT-D data
    """
    _data_particle_type = DataParticleType.SAMPLE_RECOVERED


class FlortdCommonParser(Parser):

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

        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            if header_match.group(1) == 'FL':
                data_match = DATA_MATCHER.search(chunk)
                if data_match:
                    log.debug('Found data match in chunk %s', chunk[1:32])

                    # particle-ize the data block received, return the record
                    # prepend the timestamp from sio mule header to the flort raw data,
                    # which is stored in header_match.group(3)
                    sample = self._extract_sample(self._particle_class, None,
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


class FlortdParser(FlortdCommonParser, SioMuleParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(FlortdParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)


class FlortdRecoveredParser(FlortdCommonParser, SioParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(FlortdRecoveredParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)

