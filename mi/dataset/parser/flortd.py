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
from mi.dataset.parser.mflm import MflmParser, SIO_HEADER_MATCHER
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
        try:
            date_match = DATE_MATCHER.match(match.group(1))
            if not date_match:
                raise ValueError('Date does not match MM/DD/YY\\tHH:MM:SS format')
            date_str = date_match.group(1)
            time_str = date_match.group(2)
            wav_beta = int(match.group(2))
            if wav_beta not in [470, 532, 650, 700]:
                raise ValueError('Measured wavelength beta %d is not one of the expected values (470,532,650,700)' %
                                 wav_beta)
            beta = int(match.group(3))
            if beta < 0 or beta > 4120:
                raise ValueError('Beta %d counts are outside expected limits (0 to 4120)'% beta )
            wav_chl = int(match.group(4))
            if wav_chl != 695:
                raise ValueError('Measured wavelength clorophyll %d is not the expected value (695 nm)' % wav_chl)
            chl = int(match.group(5))
            if chl < 0 or chl > 4120:
                raise ValueError('Clorophyll %d counts are outside expected limits (0 to 4120)'% chl )
            wav_cdom = int(match.group(6))
            if wav_cdom != 460:
                raise ValueError('Measured wavelength cdom %d is not the expected value (460 nm)' % wav_cdom)
            cdom = int(match.group(7))
            if cdom < 0 or cdom > 4120:
                raise ValueError('CDOM %d counts are outside expected limits (0 to 4120)'% cdom )
            therm = int(match.group(8))
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))

        result = [{DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.DATE_STRING,
                   DataParticleKey.VALUE: date_str},
                  {DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.TIME_STRING,
                   DataParticleKey.VALUE: time_str},
                  {DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.MEASUREMENT_WAVELENGTH_BETA,
                   DataParticleKey.VALUE: wav_beta},
                  {DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.RAW_SIGNAL_BETA,
                   DataParticleKey.VALUE: beta},
                  {DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.MEASUREMENT_WAVELENTH_CHL,
                   DataParticleKey.VALUE: wav_chl},
                  {DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.RAW_SIGNAL_CHL,
                   DataParticleKey.VALUE: chl},
                  {DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.MEASUREMENT_WAVELENGTH_CDOM,
                   DataParticleKey.VALUE: wav_cdom},
                  {DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.RAW_SIGNAL_CDOM,
                   DataParticleKey.VALUE: cdom},
                  {DataParticleKey.VALUE_ID: FlortdParserDataParticleKey.RAW_INTERNAL_TEMP,
                   DataParticleKey.VALUE: therm}]

        log.debug('FlortdParserDataParticle: particle=%s', result)
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

class FlortdParser(MflmParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(FlortdParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
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

                data_match = DATA_MATCHER.search(processed_match)
                if data_match:
                    log.debug('Found data match in chunk %s', processed_match[1:32])
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

            self._chunk_sample_count.append(sample_count)
            self._chunk_new_seq.append(new_seq)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            # need to set a flag in case we read a chunk not matching the instrument ID and overwrite the non_data                    
            if non_data is not None and non_end <= start:
                log.debug('setting non_data_flag')
                non_data_flag = True

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


