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
from time import strftime, strptime

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey

from dateutil import parser
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER
from mi.core.exceptions import SampleException, DatasetParserException


class DataParticleType(BaseEnum):
    SAMPLE = 'flortd_parsed'

class FlortdParserDataParticleKey(BaseEnum):
    DATE_STRING = 'date_string'
    TIME_STRING = 'time_string'
    MEASUREMENT_WAVELENGTH_BETA = 'measurement_wavelength_beta'
    RAW_SIGNAL_BETA = 'raw_signal_beta'
    MEASUREMENT_WAVELENTH_CHL = 'measurement_wavelength_chl'
    RAW_SIGNAL_CHL = 'raw_signal_chl'
    MEASUREMENT_WAVELENGTH_CDOM = 'measurement_wavelength_cdom'
    RAW_SIGNAL_CDOM = 'raw_signal_cdom'
    RAW_INTERNAL_TEMP = 'raw_internal_temp'

DATE_REGEX = r'(\d\d/\d\d/\d\d)\t(\d\d:\d\d:\d\d)'
DATE_MATCHER = re.compile(DATE_REGEX)
DATA_REGEX = r'(\d\d/\d\d/\d\d\t\d\d:\d\d:\d\d)\t(\d+)\t(\d+)\t(\d+)\t(\d+)\t(\d+)\t(\d+)\t(\d+)'
DATA_MATCHER = re.compile(DATA_REGEX)

class FlortdParserDataParticle(DataParticle):
    """
    Class for parsing data from the FLORT-D instrument on a MSFM platform node
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
            raise SampleException("FlortdParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)

        date_match = DATE_MATCHER.match(match.group(1))
        if not date_match:
            log.warn('Date does not match MM/DD/YY\\tHH:MM:SS format')
            raise RecoverableSampleException('Date does not match MM/DD/YY\\tHH:MM:SS format')

        result = [self._encode_value(FlortdParserDataParticleKey.DATE_STRING, date_match.group(1), str),
                  self._encode_value(FlortdParserDataParticleKey.TIME_STRING, date_match.group(2), str),
                  self._encode_value(FlortdParserDataParticleKey.MEASUREMENT_WAVELENGTH_BETA, match.group(2), int),
                  self._encode_value(FlortdParserDataParticleKey.RAW_SIGNAL_BETA, match.group(3), int),
                  self._encode_value(FlortdParserDataParticleKey.MEASUREMENT_WAVELENTH_CHL, match.group(4), int),
                  self._encode_value(FlortdParserDataParticleKey.RAW_SIGNAL_CHL, match.group(5), int),
                  self._encode_value(FlortdParserDataParticleKey.MEASUREMENT_WAVELENGTH_CDOM, match.group(6), int),
                  self._encode_value(FlortdParserDataParticleKey.RAW_SIGNAL_CDOM, match.group(7), int),
                  self._encode_value(FlortdParserDataParticleKey.RAW_INTERNAL_TEMP, match.group(8), int)]

        return result

class FlortdParser(SioMuleParser):

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
                                          'FL',
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
                    # pull out the date string from the data
                    date_zulu = self.date_str_to_zulu(data_match.group(1))
                    if date_zulu is not None:
                        # convert to ntp
                        localtime_offset = float(parser.parse("1970-01-01T00:00:00.00Z").strftime("%s.%f"))
                        converted_time = float(parser.parse(date_zulu).strftime("%s.%f"))
                        # round to nearest .01
                        adjusted_time = round((converted_time - localtime_offset)*100)/100
                        self._timestamp = ntplib.system_to_ntp_time(adjusted_time)
                        log.debug("Converted time \"%s\" (unix: %s) into %s", date_zulu,
                                  adjusted_time, self._timestamp)

                        # particle-ize the data block received, return the record
                        sample = self._extract_sample(FlortdParserDataParticle,
                                                      DATA_MATCHER,
                                                      data_match.group(0),
                                                      self._timestamp)
                        if sample:
                            # create particle
                            result_particles.append(sample)
                            sample_count += 1
                    else:
                        log.warn("Unable to unpack timestamp from data %s", data_match.group(1))
                        self._exception_callback(RecoverableSampleException("Unable to unpack timestamp from data %s" % data_match.group(1)))

            self._chunk_sample_count.append(sample_count)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        return result_particles

    def date_str_to_zulu(self, date_str):
        """
        Convert the date string from the instrument into the zulu date
        string format
        @ retval zulu formatted date string or None if it did not match
        """
        zulu_str = None
        match = DATE_MATCHER.match(date_str)
        if match:
            date_struct = strptime(date_str, '%m/%d/%y\t%H:%M:%S')
            zulu_str = strftime('%Y-%m-%dT%H:%M:%SZ', date_struct)
        return zulu_str


