#!/usr/bin/env python

"""
@package mi.dataset.parser.issmcnsm_dostad
@file marine-integrations/mi/dataset/parser/issmcnsm_dostad.py
@author Emily Hahn
@brief Parser for the issmcnsm_dosta dataset driver
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

TIME_REGEX = r'(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d.\d{3}) '
TIME_MATCHER = re.compile(TIME_REGEX)

DATA_REGEX = r'\d{4}/\d\d/\d\d \d\d:\d\d:\d\d.\d{3} (\d+)\t(\d+)\t(\d+.\d+)\t(\d+.\d+)\t' \
             '(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d)\t(\d+.\d)\t(\d+.\d)\r'
DATA_MATCHER = re.compile(DATA_REGEX)

class DataParticleType(BaseEnum):
    SAMPLE = 'issmcnsm_dostad_parsed'

class Issmcnsm_dostadParserDataParticleKey(BaseEnum):
    PRODUCT_NUMBER = 'product_number'
    SERIAL_NUMBER = 'serial_number'
    ESTIMATED_OXYGEN = 'estimated_oxygen'
    AIR_SATURATION = 'air_saturation'
    OPTODE_TEMPERATURE = 'optode_temperature'
    CALIBRATED_PHASE = 'calibrated_phase'
    TEMP_COMPENSATED_PHASE = 'temp_compensated_phase'
    BLUE_PHASE = 'blue_phase'
    RED_PHASE = 'red_phase'
    BLUE_AMPLITUDE = 'blue_amplitude'
    RED_AMPLITUDE = 'red_amplitude'
    RAW_TEMP = 'raw_temp'

class StateKey(BaseEnum):
    TIMESTAMP='timestamp' #holds the most recent data sample timestamp
    POSITION='position' #hold the current file position

class Issmcnsm_dostadParserDataParticle(DataParticle):
    """
    Class for parsing data from the issmcnsm_dosta instrument
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
            raise SampleException("Issmcnsm_dostadParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:
            prod_num = int(match.group(1))
            if prod_num != 4831:
                raise ValueError('Product number %d was not expected 4831' % prod_num)
            serial_num = int(match.group(2))
            est_oxygen = float(match.group(3))
            air_sat = float(match.group(4))
            optode_temp = float(match.group(5))
            calibrated_phase = float(match.group(6))
            if calibrated_phase < -360.0 or calibrated_phase > 360.0:
                raise ValueError('Calibrated phase %f it outside expected limits -360 to 360' % calibrated_phase)
            temp_compens_phase = float(match.group(7))
            if temp_compens_phase < -360.0 or temp_compens_phase > 360.0:
                raise ValueError('Temp compensated phase %f it outside expected limits -360 to 360' % temp_compens_phase)
            blue_phase = float(match.group(8))
            if blue_phase < -360.0 or blue_phase > 360.0:
                raise ValueError('Blue Phase %f it outside expected limits -360 to 360' % blue_phase)
            red_phase = float(match.group(9))
            if red_phase < -360.0 or red_phase > 360.0:
                raise ValueError('Red Phase %f it outside expected limits -360 to 360' % red_phase)
            blue_amp = float(match.group(10))
            red_amp = float(match.group(11))
            raw_temp = float(match.group(12))

        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))

        result = [{DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.PRODUCT_NUMBER,
                   DataParticleKey.VALUE: prod_num},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_num},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.ESTIMATED_OXYGEN,
                   DataParticleKey.VALUE: est_oxygen},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.AIR_SATURATION,
                   DataParticleKey.VALUE: air_sat},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.OPTODE_TEMPERATURE,
                   DataParticleKey.VALUE: optode_temp},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.CALIBRATED_PHASE,
                   DataParticleKey.VALUE: calibrated_phase},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.TEMP_COMPENSATED_PHASE,
                   DataParticleKey.VALUE: temp_compens_phase},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.BLUE_PHASE,
                   DataParticleKey.VALUE: blue_phase},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.RED_PHASE,
                   DataParticleKey.VALUE: red_phase},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.BLUE_AMPLITUDE,
                   DataParticleKey.VALUE: blue_amp},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.RED_AMPLITUDE,
                   DataParticleKey.VALUE: red_amp},
                  {DataParticleKey.VALUE_ID: Issmcnsm_dostadParserDataParticleKey.RAW_TEMP,
                   DataParticleKey.VALUE: raw_temp}]

        log.debug('Issmcnsm_dostadParserDataParticle: particle=%s', result)
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP] < .0000001)):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP] >= .0000001:
                log.debug('Timestamp %f and %f do not match',
                          self.contents[DataParticleKey.INTERNAL_TIMESTAMP],
                          arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])
            return False

class Issmcnsm_dostadParser(BufferLoadingParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(Issmcnsm_dostadParser, self).__init__(config,
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
        match = TIME_MATCHER.match(ts_str)
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


