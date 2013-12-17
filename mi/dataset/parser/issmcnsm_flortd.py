#!/usr/bin/env python

"""
@package mi.dataset.parser.issmcnsm_flortd
@file marine-integrations/mi/dataset/parser/issmcnsm_flortd.py
@author Emily Hahn
@brief Parser for the issmcnsm_flort dataset driver
Release notes:

Initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import time
from dateutil import parser
from functools import partial

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import StringChunker

# there are two timestamps, the log timestamp and data timestamp
# the internal timestamp uses the regex for the log timestamp
DATA_TIME_REGEX = r'(\d\d/\d\d/\d\d)\t(\d\d:\d\d:\d\d)\t'
DATA_TIME_MATCHER = re.compile(DATA_TIME_REGEX)

LOG_TIME_REGEX = r'(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d.\d{3}) '
LOG_TIME_MATCHER = re.compile(LOG_TIME_REGEX)

DATA_REGEX = r'\d{4}/\d\d/\d\d \d\d:\d\d:\d\d.\d{3} (\d\d/\d\d/\d\d\t\d\d:\d\d:\d\d\t)' \
             '(\d+)\t(\d+)\t(\d+)\t(\d+)\t(\d+)\t(\d+)\t(\d+)\r'
DATA_MATCHER = re.compile(DATA_REGEX)

class DataParticleType(BaseEnum):
    SAMPLE = 'issmcnsm_flortd_parsed'

class Issmcnsm_flortdParserDataParticleKey(BaseEnum):
    DATE_STRING = 'date_string'
    TIME_STRING = 'time_string'
    MEASUREMENT_WAVELENGTH_BETA = 'measurement_wavelength_beta'
    RAW_SIGNAL_BETA = 'raw_signal_beta'
    MEASUREMENT_WAVELENTH_CHL = 'measurement_wavelength_chl'
    RAW_SIGNAL_CHL = 'raw_signal_chl'
    MEASUREMENT_WAVELENGTH_CDOM = 'measurement_wavelength_cdom'
    RAW_SIGNAL_CDOM = 'raw_signal_cdom'
    RAW_INTERNAL_TEMP = 'raw_internal_temp'

class StateKey(BaseEnum):
    TIMESTAMP='timestamp' #holds the most recent data sample timestamp
    POSITION='position' #hold the current file position

class Issmcnsm_flortdParserDataParticle(DataParticle):
    """
    Class for parsing data from the issmcnsm_flort instrument
    """

    _data_particle_type = DataParticleType.SAMPLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        # match the data inside the wrapper
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("Issmcnsm_flortdParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:
            date_match = DATA_TIME_MATCHER.match(match.group(1))
            if not date_match:
                raise ValueError('Date does not match MM/DD/YY\tHH:MM:SS format')
            date_str = date_match.group(1)
            time_str = date_match.group(2)
            wav_beta = int(match.group(2))
            beta = int(match.group(3))
            wav_chl = int(match.group(4))
            chl = int(match.group(5))
            wav_cdom = int(match.group(6))
            cdom = int(match.group(7))
            therm = int(match.group(8))
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))

        result = [{DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.DATE_STRING,
                   DataParticleKey.VALUE: date_str},
                  {DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.TIME_STRING,
                   DataParticleKey.VALUE: time_str},
                  {DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.MEASUREMENT_WAVELENGTH_BETA,
                   DataParticleKey.VALUE: wav_beta},
                  {DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.RAW_SIGNAL_BETA,
                   DataParticleKey.VALUE: beta},
                  {DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.MEASUREMENT_WAVELENTH_CHL,
                   DataParticleKey.VALUE: wav_chl},
                  {DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.RAW_SIGNAL_CHL,
                   DataParticleKey.VALUE: chl},
                  {DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.MEASUREMENT_WAVELENGTH_CDOM,
                   DataParticleKey.VALUE: wav_cdom},
                  {DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.RAW_SIGNAL_CDOM,
                   DataParticleKey.VALUE: cdom},
                  {DataParticleKey.VALUE_ID: Issmcnsm_flortdParserDataParticleKey.RAW_INTERNAL_TEMP,
                   DataParticleKey.VALUE: therm}]

        log.debug('Issmcnsm_flortdParserDataParticle: particle=%s', result)
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP] < .00001)):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP] >= .00001:
                log.debug('Timestamp %f and %f do not match',
                          self.contents[DataParticleKey.INTERNAL_TIMESTAMP],
                          arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])

class Issmcnsm_flortdParser(BufferLoadingParser):
    
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(Issmcnsm_flortdParser, self).__init__(config,
                                                    stream_handle,
                                                    state,
                                                    partial(StringChunker.regex_sieve_function,
                                                            regex_list=[DATA_MATCHER]),
                                                    state_callback,
                                                    publish_callback,
                                                    *args,
                                                    **kwargs)
        self._timestamp = 0.0
        self._record_buffer = [] # holds tuples of (record, state)
        self._read_state = {StateKey.POSITION:0, StateKey.TIMESTAMP:0.0}

        if state:
            self.set_state(self._state)

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. 
        @throws DatasetParserException if there is a bad state structure
        """
        log.debug("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not ((StateKey.POSITION in state_obj) and (StateKey.TIMESTAMP in state_obj)):
            raise DatasetParserException("Invalid state keys")
        self._timestamp = state_obj[StateKey.TIMESTAMP]
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        # make sure the chunker is clean of old data
        self._clean_all_chunker()

        # seek to the position
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, read_increment, timestamp):
        """
        Increment the parser position by a certain amount in bytes. This
        indicates what has been READ from the file, not what has been published.
        The increment takes into account a timestamp of WHEN in the data the
        position corresponds to. This allows a reload of both timestamp and the
        position.
        @param increment Number of bytes to increment the parser position.
        @param timestamp The timestamp completed up to that position
        """
        log.trace("Incrementing current state: %s with inc: %s, timestamp: %s",
                  self._read_state, read_increment, timestamp)

        self._read_state[StateKey.POSITION] += read_increment
        self._read_state[StateKey.TIMESTAMP] = timestamp

    @staticmethod
    def _convert_string_to_timestamp(ts_str):
        """
        Converts the given string from this data stream's format into an NTP
        timestamp. 
        @param ts_str The timestamp string in the format "yyyy/mm/dd hh:mm:ss.sss"
        @retval The NTP4 timestamp
        """
        match = LOG_TIME_MATCHER.match(ts_str)
        if not match:
            raise ValueError("Invalid time format: %s" % ts_str)

        zulu_ts = "%04d-%02d-%02dT%02d:%02d:%fZ" % (
            int(match.group(1)), int(match.group(2)), int(match.group(3)),
            int(match.group(4)), int(match.group(5)), float(match.group(6))
        )
        log.trace("converted ts '%s' to '%s'", ts_str[match.start(0):(match.start(0) + 24)], zulu_ts)

        converted_time = float(parser.parse(zulu_ts).strftime("%s.%f"))
        adjusted_time = converted_time - time.timezone
        ntptime = ntplib.system_to_ntp_time(adjusted_time)

        log.trace("Converted time \"%s\" (unix: %s) into %s", ts_str, adjusted_time, ntptime)
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
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        if end == None:
            data_increment = 0
        else:
            data_increment = end

        while (chunk != None):
            log.debug('checking chunk %s', chunk)
            data_match = DATA_MATCHER.match(chunk)
            if data_match:
                # time is inside the data regex
                self._timestamp = self._convert_string_to_timestamp(chunk)
                # particle-ize the data block received, return the record
                sample = self._extract_sample(self._particle_class, DATA_MATCHER, chunk, self._timestamp)
                if sample:
                    # create particle
                    log.trace("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)
                    self._increment_state(data_increment, self._timestamp)    
                    result_particles.append((sample, copy.copy(self._read_state)))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=True)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            if end == None:
                data_increment = 0
            else:
                data_increment = end - start
            # need to add length of non-data to data to get the final position 
            if non_end != None and non_end != 0:
                data_increment += (non_end - non_start)

        return result_particles

    def _clean_all_chunker(self):
        """
        Clean out the chunker of all possible data types
        """
        # clear out any non matching data.
        (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)
        while non_data is not None:
            (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)
        # clean out raw data
        (nd_timestamp, raw_data) = self._chunker.get_next_raw(clean=True)
        while raw_data is not None:
            (nd_timestamp, raw_data) = self._chunker.get_next_raw(clean=True)
        # clean out data
        (nd_timestamp, data) = self._chunker.get_next_data(clean=True)
        while data is not None:
            (nd_timestamp, data) = self._chunker.get_next_data(clean=True)


