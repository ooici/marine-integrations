#!/usr/bin/env python

"""
@package mi.dataset.parser.rte_o_stc
@file marine-integrations/mi/dataset/parser/rte_o_stc.py
@author Jeff Roy
@brief Parser for the rte_o_stc dataset driver
Release notes:

Initial Release
"""

__author__ = 'Jeff Roy'
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
from mi.dataset.dataset_parser import BufferLoadingFilenameParser
from mi.core.instrument.chunker import StringChunker

# This is an example of the input string
#             2013/11/16 20:46:24.989 Coulombs = 1.1110C,
#             AVG Q_RTE Current = 0.002A, AVG RTE Voltage = 12.02V,
#             AVG Supply Voltage = 12.11V, RTE Hits 0, RTE State = 1


DATA_REGEX = r'(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d.\d{3}) (Coulombs) = (\d+.\d+)C, '\
             '(AVG Q_RTE Current) = (\d+.\d+)A, (AVG RTE Voltage) = (\d+.\d+)V, '\
             '(AVG Supply Voltage) = (\d+.\d+)V, (RTE Hits) (\d+), (RTE State) = (\d+)'
DATA_MATCHER = re.compile(DATA_REGEX)

LOG_TIME_REGEX = r'(\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d):(\d\d.\d{3}) '
LOG_TIME_MATCHER = re.compile(LOG_TIME_REGEX)


class DataParticleType(BaseEnum):
    SAMPLE = 'rte_xx__stc_instrument'

class RteOStcParserDataParticleKey(BaseEnum):
    RTE_TIME = 'rte_time'
    RTE_COULOMBS = 'rte_coulombs'
    RTE_AVG_Q_CURRENT = 'rte_avg_q_current'
    RTE_AVG_VOLTAGE = 'rte_avg_voltage'
    RTE_AVG_SUPPLY_VOLTAGE = 'rte_avg_supply_voltage'
    RTE_HITS = 'rte_hits'
    RTE_STATE = 'rte_state'

class StateKey(BaseEnum):
    POSITION='position' #hold the current file position

class RteOStcParserDataParticle(DataParticle):
    """
    Class for parsing data from the rte_o_stc data set
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
            raise SampleException("RteOStcParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)

        result = [self._encode_value(RteOStcParserDataParticleKey.RTE_TIME, match.group(1), str),
                  self._encode_value(RteOStcParserDataParticleKey.RTE_COULOMBS, match.group(3), float),
                  self._encode_value(RteOStcParserDataParticleKey.RTE_AVG_Q_CURRENT, match.group(5), float),
                  self._encode_value(RteOStcParserDataParticleKey.RTE_AVG_VOLTAGE, match.group(7), float),
                  self._encode_value(RteOStcParserDataParticleKey.RTE_SUPPLY_VOLTAGE, match.group(9), float),
                  self._encode_value(RteOStcParserDataParticleKey.RTE_HITS, match.group(11), int),
                  self._encode_value(RteOStcParserDataParticleKey.RTE_STATE, match.group(13), int)]
         
        log.debug('RteOStcParserDataParticle: particle=%s', result)
        return result  

class RteOStcParser(BufferLoadingFilenameParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 file_name,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(RteOStcParser, self).__init__(config,
                                            stream_handle,
                                            file_name,
                                            state,
                                            partial(StringChunker.regex_sieve_function,
                                                    regex_list=[DATA_MATCHER]),
                                            state_callback,
                                            publish_callback,
                                            exception_callback,
                                            *args,
                                            **kwargs)

        self._read_state = {StateKey.POSITION:0}

        if state:
            self.set_state(self._state)

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. 
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not ((StateKey.POSITION in state_obj)):
            raise DatasetParserException("Invalid state keys")
        
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj
        self._chunker.clean_all_chunks()
        
        # seek to the position
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser state
        @param timestamp The timestamp completed up to that position
        """
        self._read_state[StateKey.POSITION] += increment

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
            data_match = DATA_MATCHER.match(chunk)
            if data_match:
                # time is inside the data regex
                self._timestamp = self._convert_string_to_timestamp(chunk)
                
                # particle-ize the data block received, return the record
                sample = self._extract_sample(self._particle_class, DATA_MATCHER, chunk, self._timestamp)
                if sample:
                    # create particle
                    
                    self._increment_state(data_increment)    
                    result_particles.append((sample, copy.copy(self._read_state)))
                    
                    log.debug("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)

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



