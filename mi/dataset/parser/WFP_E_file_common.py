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
    WFP_ENG__STC_IMODEM_PARSED = 'wfp_eng__stc_imodem_parsed'


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
	self._parse_header()
        super(WfpEFileParser, self).__init__(config,
                                             stream_handle,
                                             state,
                                             #TODO insert regex <- Maria,
                                             state_callback,
                                             publish_callback,
                                             *args, **kwargs)
        if state:
            self.set_state(self._state)

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

    def _parse_header(self):
	"""
	parse the flags (just for error checking) and sensor /profiler time
	"""
	# Maria
	pass

    def parse_record(self):
	"""
	determine if this is a engineering or data record and parse
	"""
	# Maria
	pass

    def parse_chunks(self):
	"""
	parse wfp e file
	"""
	# Mike
	pass

