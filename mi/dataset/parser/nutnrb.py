#!/usr/bin/env python

"""
@package mi.dataset.parser.nutnrb
@file marine-integrations/mi/dataset/parser/nutnrb.py
@author Roger Unwin
@brief Parser for the CE_ISSM_RI_NUTNR_B dataset driver
Release notes:

test
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib

from functools import partial
from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.dataset_parser import BufferLoadingParser

DATA_REGEX = '(\d{4}/\d*/\d*\s*\d*:\d*:\d*\.\d*) (SAT)(N[LD]C)(\d+),(\d{7}),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*),([\-\d\.]*)[\r\n]*'  # ^M
DATA_MATCHER = re.compile(DATA_REGEX)


class DataParticleType(BaseEnum):
    SAMPLE = 'nutnrb_parsed'


class NutnrbDataParticleKey(BaseEnum):
    FRAME_HEADER = "frame_header"
    FRAME_TYPE = "frame_type"
    SERIAL_NUMBER = "serial_number"
    DATE_OF_SAMPLE = "date_of_sample"
    TIME_OF_SAMPLE = "time_of_sample"
    NITRATE_CONCENTRAION = "nitrate_concentration"
    AUX_FITTING_1 = "aux_fitting_1"
    AUX_FITTING_2 = "aux_fitting_2"
    AUX_FITTING_3 = "aux_fitting_3"
    RMS_ERROR = "rms_error"


class StateKey(BaseEnum):
    POSITION = "position"


class NutnrbDataParticle(DataParticle):
    """
    Class for parsing data from the CE_ISSM_RI_NUTNR_B instrument
    """

    _data_particle_type = DataParticleType.SAMPLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        log.trace("IN NutnrbDataParticle._build_parsed_values")
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("CtdParserDataParticle: No regex match of \
                                  parsed sample data: [%s]", self.raw_data)
        try:
            frame_header = match.group(2)
            frame_type = match.group(3)
            serial_number = match.group(4)
            date_of_sample = int(match.group(5))
            time_of_sample = float(match.group(6))
            nitrate_concentration = float(match.group(7))
            aux_fitting_1 = float(match.group(8))
            aux_fitting_2 = float(match.group(9))
            aux_fitting_3 = float(match.group(10))
            rms_error = float(match.group(11))
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        result = [{DataParticleKey.VALUE_ID: NutnrbDataParticleKey.FRAME_HEADER,
                   DataParticleKey.VALUE: frame_header},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.FRAME_TYPE,
                   DataParticleKey.VALUE: frame_type},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_number},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.DATE_OF_SAMPLE,
                   DataParticleKey.VALUE: date_of_sample},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.TIME_OF_SAMPLE,
                   DataParticleKey.VALUE: time_of_sample},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.NITRATE_CONCENTRAION,
                   DataParticleKey.VALUE: nitrate_concentration},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.AUX_FITTING_1,
                   DataParticleKey.VALUE: aux_fitting_1},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.AUX_FITTING_2,
                   DataParticleKey.VALUE: aux_fitting_2},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.AUX_FITTING_3,
                   DataParticleKey.VALUE: aux_fitting_3},
                  {DataParticleKey.VALUE_ID: NutnrbDataParticleKey.RMS_ERROR,
                   DataParticleKey.VALUE: rms_error}]

        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """

        if (self.raw_data != arg.raw_data):
            return False
        return True


class NutnrbParser(BufferLoadingParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(NutnrbParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          partial(StringChunker.regex_sieve_function,
                                                  regex_list=[DATA_MATCHER]),
                                          state_callback,
                                          publish_callback,
                                          *args,
                                          **kwargs)

        self._timestamp = 0.0
        self._record_buffer = []
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
        if not (StateKey.POSITION in state_obj):
            raise DatasetParserException("Invalid state keys")
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        # seek to the position
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser state
        @param increment The increment completed up to that position
        """

        self._read_state[StateKey.POSITION] += increment

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
            data_match = DATA_MATCHER.match(chunk)

            if data_match:
                # particle-ize the data block received, return the record
                sample = self._extract_sample(self._particle_class, DATA_MATCHER, chunk, self._timestamp)
                if sample:
                    # create particle
                    self._increment_state(end)
                    result_particles.append((sample, copy.copy(self._read_state)))

            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)

        return result_particles
