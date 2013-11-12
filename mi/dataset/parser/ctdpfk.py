#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf SBE52 data set agent information
@file mi/dataset/parser/ctdpf.py
@author Roger Unwin
@brief A CTDPF-specific data set agent package
This module should contain classes that handle parsers used with CTDPF dataset
files. It initially holds SBE52-specific logic, ultimately more than that.
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import re
import copy
from functools import partial

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException
from mi.dataset.parser.ctdpf import CtdpfParser, CtdpfParserDataParticle
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.dataset_parser import BufferLoadingParser

TIME_REGEX = r'CTD turned on at (\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{1,2}:\d{1,2})'
TIME_MATCHER = re.compile(TIME_REGEX, re.DOTALL)

DATA_REGEX = r'(\d*\.\d*),\s*(\d*\.\d*),\s*(\d*\.\d*),\s*(\d*)'
DATA_MATCHER = re.compile(DATA_REGEX, re.DOTALL)

DATE_REGEX = r'(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})'
DATE_MATCHER = re.compile(DATE_REGEX)


class DataParticleType(BaseEnum):
    SAMPLE = 'ctdpfk_parsed'


class CtdpfkParserDataParticleKey(BaseEnum):
    TEMPERATURE = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    OXYGEN = "oxygen"


class StateKey(BaseEnum):
    POSITION = "position"
    TIMESTAMP = "timestamp"


class CtdpfkParserDataParticle(CtdpfParserDataParticle):
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
            temp = float(match.group(2))
            cond = float(match.group(1))
            press = float(match.group(3))
            o2 = float(match.group(4))
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        result = [{DataParticleKey.VALUE_ID: CtdpfkParserDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temp},
                  {DataParticleKey.VALUE_ID: CtdpfkParserDataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: cond},
                  {DataParticleKey.VALUE_ID: CtdpfkParserDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: press},
                  {DataParticleKey.VALUE_ID: CtdpfkParserDataParticleKey.OXYGEN,
                   DataParticleKey.VALUE: o2}]
        log.trace('CtdpfkParserDataParticle: particle=%s', result)
        return result



class CtdpfkParser(CtdpfParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(BufferLoadingParser, self).__init__(config,
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
        non_data = None

        # sieve looks for timestamp, update and increment position
        while (chunk != None):
            time_match = TIME_MATCHER.match(chunk)
            data_match = DATA_MATCHER.match(chunk)
            if time_match:
                log.trace("Encountered timestamp in data stream: %s", time_match.group(1))
                self._timestamp = self._convert_string_to_timestamp(time_match.group(1))
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

                # Check for noise between records, but ignore newline.  This is detecting noise following
                # the last successful chunk read which is why it is post sample generation.
                if non_data is not None and non_data != "\n":
                        log.info("Gap in datafile detected.")
                        log.trace("Noise detected: %s", non_data)
                        self.start_new_sequence()

            if non_data is not None:
                self._increment_state(len(non_data), self._timestamp)

            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)

        return result_particles

