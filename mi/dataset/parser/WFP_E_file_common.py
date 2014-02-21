#!/usr/bin/env python

"""
@package mi.dataset.parser.WFP_E_file
@file mi/dataset/parser/WFP_E_file
@author Emily Hahn, Mike Nicoletti, Maria Lutz
@brief A common parser for the E file type of the wire following profiler
"""
__author__ = 'Emily Hahn, Mike Nicoletti, Maria Lutz'
__license__ = 'Apache 2.0'

import re
import time
import ntplib

from mi.core.log import get_logger; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.chunker import BinaryChunker
from mi.dataset.dataset_parser import BufferLoadingParser

# Mike 
FLAGS_REGEX = b''
FLAG_MATCHER = re.compile(FLAGS_REGEX)

# Maria, the rest
START_TIME_REGEX = b''
START_TIME_MATCHER = re.compile(START_TIME_REGEX)

PROFILE_REGEX = b''
PROFILE_MATCHER = re.compile(PROFILE_REGEX)

DATA_SAMPLE_REGEX = b''
DATA_SAMPLE_MATCHER = re.compile(DATA_SAMPLE_REGEX)


class StateKey(BaseEnum):
    POSITION = "position"

class DataParticleType(BaseEnum):
    # Data particle types for the WFP E file
    PARAD_K__STC_IMODEM_PARSED = 'parad_k__stc_imodem_parsed'
    FLORT_KN__STC_IMODEM_PARSED = 'flort_kn__stc_imodem_parsed'


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
	self._profile_start_stop_data = None
        super(WfpEFileParser, self).__init__(config,
                                             stream_handle,
                                             state,
                                             partial(BinaryChunker.regex_sieve_function,
                                                  regex_list=[PROFILE_MATCHER, DATA_SAMPLE_MATCHER]),
                                             state_callback,
                                             publish_callback,
                                             *args, **kwargs)

        if state:
	    if state[StateKey.POSITION] < HEADER_SIZE:
		self._parse_header()
            self.set_state(state)
	else:
	    self._parse_header()

    def set_state(self, state_obj):
	"""
	initialize the state
	"""
	# Mike
        pass

    def increment_state(self, increment):
	"""
        Increment the parser position by the given increment in bytes.
        This indicates what has been read from the file, not what has
        been published.
        @ param increment number of bytes to increment parser position
	"""
	# Mike
        self._read_state[StateKey.Position] += increment

    def _parse_header(self, header):
	"""
	parse the flags (just for error checking) and sensor /profiler time
	"""
	# Maria
	# need to store profile start and stop time to pass to WFP
	match = START_TIME_MATCHER.match(header[])
	if match:
	    self._profile_start_stop_data = match.group(0)

    def parse_record(self, record):
	"""
	determine if this is a engineering or data record and parse
	"""
	# This needs to get implemented by each instrument, not here
	if PROFILE_MATCHER.match(record):
	    # only WFP needs this, Mike and Maria can just match DATA_SAMPLE_MATCHER
	    sample = self._extract_sample()
	else if DATA_SAMPLE_MATCHER.match(record):
	    # send to each individual instrument particle
	    sample = self._extract_sample(YourInstrumentParticle)
	if sample:
	    # update state, return particle

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
            result_particle = parse_record(chunk)
            if result_particle:
                result_particles.append(result_particle)

            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)

        return result_particles

