#!/usr/bin/env python

"""
@package mi.dataset.parser.WFP_E_file_common
@file mi/dataset/parser/WFP_E_file_common
@author Emily Hahn, Mike Nicoletti, Maria Lutz
@brief A common parser for the E file type of the wire following profiler
"""
__author__ = 'Emily Hahn, Mike Nicoletti, Maria Lutz'
__license__ = 'Apache 2.0'

import re
import time
import ntplib
import struct

from functools import partial

from mi.core.log import get_logger; log = get_logger()
from mi.core.exceptions import SampleException
from mi.core.common import BaseEnum
from mi.core.instrument.chunker import BinaryChunker
from mi.dataset.dataset_parser import BufferLoadingParser

HEADER_REGEX = b'(\x00\x01\x00{7,7}\x01\x00\x01\x00{4,4})([\x00-\xff]{8,8})'
HEADER_MATCHER = re.compile(HEADER_REGEX)

STATUS_START_REGEX = b'\xff\xff\xff[\xfa-\xff]'
STATUS_START_MATCHER = re.compile(STATUS_START_REGEX)

PROFILE_REGEX = b'\xff\xff\xff[\xfa-\xff][\x00-\xff]{12}'
PROFILE_MATCHER = re.compile(PROFILE_REGEX)

HEADER_BYTES = 24
SAMPLE_BYTES = 26
STATUS_BYTES = 16


class StateKey(BaseEnum):
    POSITION = "position"


class WfpEFileParser(BufferLoadingParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):

        self._timestamp = 0.0
        self._record_buffer = [] # holds tuples of (record, state)
        self._read_state = {StateKey.POSITION: 0}
        super(WfpEFileParser, self).__init__(config,
                                             stream_handle,
                                             state,
                                             self.sieve_function,
                                             state_callback,
                                             publish_callback,
                                             *args, **kwargs)

        if state:
            self.set_state(state)
            if state[StateKey.POSITION] == 0:
                self._parse_header()
        else:
            self._parse_header()

    def sieve_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        This is needed instead of a regex because blocks are identified by position
        in this binary file.
        """
        data_index = 0
        return_list = []
        raw_data_len = len(raw_data)

        while data_index < raw_data_len:
            # check if this is a status or data sample message
            if STATUS_START_MATCHER.match(raw_data[data_index:data_index+4]):
                return_list.append((data_index, data_index + STATUS_BYTES))
                data_index += STATUS_BYTES
            else:
                return_list.append((data_index, data_index + SAMPLE_BYTES))
                data_index += SAMPLE_BYTES

            remain_bytes = raw_data_len - data_index
            # if the remaining bytes are less than the data sample bytes, all we might have left is a status sample, if we don't we're done
            if remain_bytes < STATUS_BYTES or (remain_bytes < SAMPLE_BYTES and remain_bytes > STATUS_BYTES and \
            not STATUS_START_MATCHER.match(raw_data[data_index:data_index+4])):
                break
        log.debug("returning sieve list %s", return_list)
        return return_list

    def set_state(self, state_obj):
        """
        initialize the state
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not (StateKey.POSITION in state_obj):
            raise DatasetParserException("Invalid state keys")
        self._chunker.clean_all_chunks()
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser position by the given increment in bytes.
        This indicates what has been read from the file, not what has
        been published.
        @ param increment number of bytes to increment parser position
        """
        self._read_state[StateKey.POSITION] += increment

    def _parse_header(self):
        """
        parse the flags and sensor / profiler start time from the header
        """
        # read the first bytes from the file
        header = self._stream_handle.read(HEADER_BYTES)
        match = HEADER_MATCHER.match(header)
        if not match:
            raise SampleException("File header does not match the header regex")

        # update the state to show we have read the header
        self._increment_state(HEADER_BYTES)

    def parse_record(self, record):
        """
        determine if this is a engineering or data record and parse
        FLORT and PARAD can copy paste this and insert their own data particle class
        needs extending for WFP_ENG
        """
        result_particle = []
        if DATA_SAMPLE_MATCHER.match(record):
            # pull out the timestamp for this record
            match = DATA_SAMPLE_MATCHER.match(record)
            fields = struct.unpack('<I', match.group(0)[:4])
            timestamp = int(fields[0])
            self._timestamp = ntplib.system_to_ntp_time(timestamp)
            log.debug("Converting record timestamp %f to ntp timestamp %f", timestamp, self._timestamp)
            # INSERT YOUR DATA PARTICLE CLASS HERE
            sample = self._extract_sample(data_particle_class, DATA_SAMPLE_MATCHER, record, self._timestamp)
            if sample:
                # create particle
                log.trace("Extracting sample %s with read_state: %s", sample, self._read_state)
                self._increment_state(SAMPLE_BYTES)
                result_particle = (sample, copy.copy(self._read_state))

        return result_particle

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

        while (chunk != None):
            result_particle = self.parse_record(chunk)
            if result_particle:
                result_particles.append(result_particle)

            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)

        return result_particles

