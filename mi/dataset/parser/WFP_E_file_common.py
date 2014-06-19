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

from mi.core.log import get_logger
log = get_logger()
from mi.core.exceptions import SampleException, NotImplementedException, DatasetParserException
from mi.core.common import BaseEnum
from mi.dataset.dataset_parser import BufferLoadingParser

# This regex will be used to match the flags for one of the two bit patterns:
#  0001 0000 0000 0000 0001 0001 0000 0000  (regex: \x00\x01\x00{7}\x01\x00\x01\x00{4})
#  0001 0000 0000 0001 0000 0000 0000 0001 (regex: \x00\x01\x00{5}\x01\x00{7}\x01)
#  followed by 8 bytes of variable timestamp data (regex: [\x00-\xff]{8})
HEADER_REGEX = b'(\x00\x01\x00{5}[\x00-\x01]\x00[\x00-\x01]\x00[\x00-\x01]\x00{3}[\x00-\x01])([\x00-\xff]{8})'
HEADER_MATCHER = re.compile(HEADER_REGEX)

STATUS_START_REGEX = b'\xff\xff\xff[\xfa-\xff]'
STATUS_START_MATCHER = re.compile(STATUS_START_REGEX)

PROFILE_REGEX = b'\xff\xff\xff[\xfa-\xff][\x00-\xff]{12}'
PROFILE_MATCHER = re.compile(PROFILE_REGEX)

PROFILE_WITH_DECIM_FACTOR_REGEX = b'\xff\xff\xff[\xfa-\xff][\x00-\xff]{14}'
PROFILE_WITH_DECIM_FACTOR_MATCHER = re.compile(PROFILE_WITH_DECIM_FACTOR_REGEX)

# This regex will be used to match the flags for the coastal wfp e engineering record:
# 0001 0000 0000 0000 0001 0001 0000 0000  (regex: \x00\x01\x00{7}\x01\x00\x01\x00{4})
# followed by 8 bytes of variable timestamp data (regex: [\x00-\xff]{8})
WFP_E_COASTAL_FLAGS_HEADER_REGEX = b'(\x00\x01\x00{7}\x01\x00\x01\x00{4})([\x00-\xff]{8})'
WFP_E_COASTAL_FLAGS_HEADER_MATCHER = re.compile(WFP_E_COASTAL_FLAGS_HEADER_REGEX)

# This regex will be used to match the flags for the global wfp e engineering record:
# 0001 0000 0000 0001 0000 0000 0000 0001 (regex: \x00\x01\x00{5}\x01\x00{7}\x01)
# followed by 8 bytes of variable timestamp data (regex: [\x00-\xff]{8})
WFP_E_GLOBAL_FLAGS_HEADER_REGEX = b'(\x00\x01\x00{5}\x01\x00{7}\x01)([\x00-\xff]{8})'
WFP_E_GLOBAL_FLAGS_HEADER_MATCHER = re.compile(WFP_E_GLOBAL_FLAGS_HEADER_REGEX)

# Includes indicator/timestamp and the data consists of variable 26 bytes
WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_REGEX = b'([\x00-\xff]{4})([\x00-\xff]{26})'
WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_MATCHER = re.compile(WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_REGEX)

# 4 bytes for the Engineering Data Record time stamp, 26 bytes for the global Engineering Data Record
WFP_E_GLOBAL_RECOVERED_ENG_DATA_SAMPLE_BYTES = 30

HEADER_BYTES = 24

SAMPLE_BYTES = 26

STATUS_BYTES = 16
STATUS_BYTES_AUGMENTED = 18


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
        self._record_buffer = []  # holds tuples of (record, state)
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
        remain_bytes = raw_data_len

        while data_index < raw_data_len:

            # check if this is a status or data sample message
            if remain_bytes >= STATUS_BYTES and STATUS_START_MATCHER.match(raw_data[data_index:data_index+4]):
                return_list.append((data_index, data_index + STATUS_BYTES))
                data_index += STATUS_BYTES
            elif remain_bytes >= SAMPLE_BYTES:
                return_list.append((data_index, data_index + SAMPLE_BYTES))
                data_index += SAMPLE_BYTES
            else:
                log.debug("not enough bytes to deal with")
                break

            remain_bytes = raw_data_len - data_index

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
        raise NotImplementedException("parse_record must be implemented")

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

        while chunk is not None:
            result_particle = self.parse_record(chunk)
            if result_particle:
                result_particles.append(result_particle)

            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            self._chunker.get_next_non_data(clean=True)

        return result_particles

