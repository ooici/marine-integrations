#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf SBE52 data set agent information
@file mi/dataset/parser/ctdpf.py
@author Steve Foley
@brief A CTDPF-specific data set agent package
This module should contain classes that handle parsers used with CTDPF dataset
files. It initially holds SBE52-specific logic, ultimately more than that.
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import copy
import re
import time
import ntplib
from functools import partial

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.dataset_parser import BufferLoadingParser

TIME_REGEX = r'\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{1,2}:\d{1,2}'
TIME_MATCHER = re.compile(TIME_REGEX, re.DOTALL)

DATA_REGEX = r' (\d*\.\d*),\s*(\d*\.\d*),\s*(\d*\.\d*),\s*(\d*\.\d)*'
DATA_MATCHER = re.compile(DATA_REGEX, re.DOTALL)

# TODO: This should be passed in as a parameter so the driver can define the particle name.
class DataParticleType(BaseEnum):
    SAMPLE = 'nose_ctd_external'
    
class CtdpfParserDataParticleKey(BaseEnum):
    TEMPERATURE = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    OXYGEN = "oxygen"
    
class StateKey(BaseEnum):
    POSITION = "position"
    TIMESTAMP = "timestamp"
    
class CtdpfParserDataParticle(DataParticle):
    """
    Class for parsing data from the CTDPF instrument on a HYPM SP platform node
    """
    
    _data_particle_type = DataParticleType.SAMPLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format CSV delimited values and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("CtdParserDataParticle: No regex match of \
                                  parsed sample data: [%s]", self.raw_data)
        try:
            temp = float(match.group(1))
            cond = float(match.group(2))
            press = float(match.group(3))
            o2 = float(match.group(4))
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))
        
        result = [{DataParticleKey.VALUE_ID: CtdpfParserDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temp},
                  {DataParticleKey.VALUE_ID: CtdpfParserDataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: cond},
                  {DataParticleKey.VALUE_ID: CtdpfParserDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: press},
                  {DataParticleKey.VALUE_ID: CtdpfParserDataParticleKey.OXYGEN,
                   DataParticleKey.VALUE: o2}]
        log.debug('CtdpfParserDataParticle: particle=%s', result)
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data and timestamp, they are the same enough for this particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] == arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])):
            return True
        else:
            return False
    
class CtdpfParser(BufferLoadingParser):
    
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(CtdpfParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          partial(StringChunker.regex_sieve_function,
                                                  regex_list=[DATA_MATCHER,
                                                              TIME_MATCHER]),
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
        @param state_obj The object to set the state to. Should be a list with
        a StateKey.POSITION value and StateKey.TIMESTAMP value. The position is
        number of bytes into the file, the timestamp is an NTP4 format timestamp.
        @throws DatasetParserException if there is a bad state structure
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not ((StateKey.POSITION in state_obj) and (StateKey.TIMESTAMP in state_obj)):
            raise DatasetParserException("Invalid state keys")
        
        self._timestamp = state_obj[StateKey.TIMESTAMP]
        self._timestamp += 1
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj
        
        # seek to it
        self._stream_handle.seek(state_obj[StateKey.POSITION])
        
    @staticmethod
    def _convert_string_to_timestamp(ts_str):
        """
        Converts the given string from this data stream's format into an NTP
        timestamp. This is very likely instrument specific.
        @param ts_str The timestamp string in the format "mm/dd/yyyy hh:mm:ss"
        @retval The NTP4 timestamp
        """
        systime = time.strptime(ts_str, "%m/%d/%Y %H:%M:%S")
        ntptime = ntplib.system_to_ntp_time(time.mktime(systime))
        log.trace("Converted time \"%s\" into %s", ts_str, ntptime) 
        return ntptime
        
    def _increment_timestamp(self, increment=1):
        """
        Increment timestamp by a certain amount in seconds. By default this
        dataset definition takes one sample per minute between lines. This method
        is designed to be called with each sample line collected. Override this
        as needed in subclasses
        @param increment Number of seconds in increment the timestamp.
        """
        self._timestamp += increment

    def _increment_state(self, increment, timestamp):
        """
        Increment the parser position by a certain amount in bytes. This
        indicates what has been READ from the file, not what has been published.
        The increment takes into account a timestamp of WHEN in the data the
        position corresponds to. This allows a reload of both timestamp and the
        position.
        
        This is a base implementation, override as needed.
        
        @param increment Number of bytes to increment the parser position.
        @param timestamp The timestamp completed up to that position
        """
        log.trace("Incrementing current state: %s with inc: %s, timestamp: %s",
                  self._read_state, increment, timestamp)
        
        self._read_state[StateKey.POSITION] += increment
        self._read_state[StateKey.TIMESTAMP] = timestamp
        
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
        # sieve looks for timestamp, update and increment position
        while (chunk != None):
            time_match = TIME_MATCHER.match(chunk)
            data_match = DATA_MATCHER.match(chunk)
            if time_match:
                log.trace("Encountered timestamp in data stream: %s", time_match.group(0))
                self._timestamp = self._convert_string_to_timestamp(time_match.group(0))
                self._increment_state(end, self._timestamp)
            
            elif data_match:
                if self._timestamp <= 1.0:
                    raise SampleException("No reasonable timestamp encountered at beginning of file!")
                # particle-ize the data block received, return the record
                sample = self._extract_sample(self._particle_class, DATA_MATCHER, chunk, self._timestamp)
                if sample:
                    # create particle
                    log.trace("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)
                    self._increment_state(end, self._timestamp)    
                    self._increment_timestamp() # increment one samples worth of time
                    result_particles.append((sample, copy.copy(self._read_state)))
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
                       
        return result_particles
   

