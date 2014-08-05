#!/usr/bin/env python

"""
@package mi.dataset.parser.dosta_abcdjm_dcl
@file mi/dataset/parser/dosta_abcdjm_dcl.py
@author Steve Myerson
@brief A dosta_abcdjm_dcl-specific data set agent parser

This file contains code for the dosta_abcdjm_dcl parsers and code to produce data particles.
For telemetered data, there is one parser which produces one type of data particle.
For recovered data, there is one parser which produces one type of data particle.
The input files and the content of the data particles are the same for both
recovered and telemetered.
Only the names of the output particle streams are different.

The input file is ASCII and contains 2 types of records.
Records are separated by a newline.
All records start with a timestamp.
Metadata records: timestamp [text] more text newline.
Sensor Data records: timestamp product_number serial_number sensor_data newline.
Only sensor data records produce particles if properly formed.
Mal-formed sensor data records and all metadata records produce no particles.
"""

__author__ = 'Steve Myerson'
__license__ = 'Apache 2.0'

import calendar
import copy
from functools import partial
import re

from mi.core.instrument.chunker import \
    StringChunker

from mi.core.log import get_logger; log = get_logger()

from mi.dataset.dataset_parser import \
    BufferLoadingParser

from mi.core.common import BaseEnum
from mi.core.exceptions import \
    DatasetParserException, \
    UnexpectedDataException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue

# Basic patterns
ANY_CHARS = r'.*'              # any characters excluding a newline
FLOAT = r'(\d+\.\d*)'          # unsigned floating point number
NEW_LINE = r'(?:\r\n|\n)'      # any type of new line
SPACE = ' '
TAB = '\t'

# Timestamp at the start of each record: YYYY/MM/DD HH:MM:SS.mmm
# Metadata fields:  [text] more text
# Sensor data has tab-delimited fields (integers, floats)
# All records end with one of the newlines.
DATE = r'(\d{4})/(\d{2})/(\d{2})'           # Date: YYYY/MM/DD
TIME = r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})'  # Time: HH:MM:SS.mmm
TIMESTAMP = '(' + DATE + SPACE + TIME + ')'
START_METADATA = r'\['
END_METADATA = r'\]'
PRODUCT = '(4831)'                     # the only valid Product Number

# All dosta records are ASCII characters separated by a newline.
DOSTA_RECORD_REGEX = ANY_CHARS       # Any number of characters
DOSTA_RECORD_REGEX += NEW_LINE       # separated by a new line
DOSTA_RECORD_MATCHER = re.compile(DOSTA_RECORD_REGEX)

# Metadata record:
#   Timestamp [Text]MoreText newline
METADATA_REGEX = TIMESTAMP + SPACE   # date and time
METADATA_REGEX += START_METADATA     # Metadata record starts with '['
METADATA_REGEX += ANY_CHARS          #   followed by text
METADATA_REGEX += END_METADATA       #   followed by ']'
METADATA_REGEX += ANY_CHARS          #   followed by more text
METADATA_REGEX += NEW_LINE           # Record ends with a newline
METADATA_MATCHER = re.compile(METADATA_REGEX)

# Sensor data record:
#   Timestamp ProductNumber<tab>SerialNumber<tab>SensorData
#   where SensorData are tab-separated unsigned floating point numbers
SENSOR_DATA_REGEX = TIMESTAMP + SPACE    # date and time
SENSOR_DATA_REGEX += PRODUCT + TAB       # Product number must be valid
SENSOR_DATA_REGEX += r'(\d{3,4})' + TAB  # 3 or 4 digit serial number
SENSOR_DATA_REGEX += FLOAT + TAB         # oxygen content
SENSOR_DATA_REGEX += FLOAT + TAB         # relative air saturation
SENSOR_DATA_REGEX += FLOAT + TAB         # ambient temperature
SENSOR_DATA_REGEX += FLOAT + TAB         # calibrated phase
SENSOR_DATA_REGEX += FLOAT + TAB         # temperature compensated phase
SENSOR_DATA_REGEX += FLOAT + TAB         # phase measurement with blue excitation
SENSOR_DATA_REGEX += FLOAT + TAB         # phase measurement with red excitation
SENSOR_DATA_REGEX += FLOAT + TAB         # amplitude measurement with blue excitation
SENSOR_DATA_REGEX += FLOAT + TAB         # amplitude measurement with red excitation
SENSOR_DATA_REGEX += FLOAT               # raw temperature voltage from thermistor
SENSOR_DATA_REGEX += NEW_LINE            # Record ends with a newline
SENSOR_DATA_MATCHER = re.compile(SENSOR_DATA_REGEX)

# SENSOR_DATA_MATCHER produces the following groups.
# The following are indices into groups() produced by SENSOR_DATA_MATCHER.
# i.e, match.groups()[INDEX]
SENSOR_GROUP_TIMESTAMP = 0
SENSOR_GROUP_YEAR = 1
SENSOR_GROUP_MONTH = 2
SENSOR_GROUP_DAY = 3
SENSOR_GROUP_HOUR = 4
SENSOR_GROUP_MINUTE = 5
SENSOR_GROUP_SECOND = 6
SENSOR_GROUP_MILLI_SECOND = 7
SENSOR_GROUP_PRODUCT = 8
SENSOR_GROUP_SERIAL = 9
SENSOR_GROUP_OXYGEN_CONTENT = 10
SENSOR_GROUP_AIR_SATURATION = 11
SENSOR_GROUP_AMBIENT_TEMPERATURE = 12
SENSOR_GROUP_CALIBRATED_PHASE = 13
SENSOR_GROUP_COMPENSATED_PHASE = 14
SENSOR_GROUP_BLUE_PHASE = 15
SENSOR_GROUP_RED_PHASE = 16
SENSOR_GROUP_BLUE_AMPLITUDE = 17
SENSOR_GROUP_RED_AMPLITUDE = 18
SENSOR_GROUP_RAW_TEMPERATURE = 19

# This table is used in the generation of the instrument data particle.
# Column 1 - particle parameter name
# Column 2 - group number (index into raw_data)
# Column 3 - data encoding function (conversion required - int, float, etc)
INSTRUMENT_PARTICLE_MAP = [
    ('dcl_controller_timestamp',       SENSOR_GROUP_TIMESTAMP,           str),
    ('product_number',                 SENSOR_GROUP_PRODUCT,             int),
    ('serial_number',                  SENSOR_GROUP_SERIAL,              int),
    ('estimated_oxygen_concentration', SENSOR_GROUP_OXYGEN_CONTENT,      float),
    ('estimated_oxygen_saturation',    SENSOR_GROUP_AIR_SATURATION,      float),
    ('optode_temperature',             SENSOR_GROUP_AMBIENT_TEMPERATURE, float),
    ('calibrated_phase',               SENSOR_GROUP_CALIBRATED_PHASE,    float),
    ('temp_compensated_phase',         SENSOR_GROUP_COMPENSATED_PHASE,   float),
    ('blue_phase',                     SENSOR_GROUP_BLUE_PHASE,          float),
    ('red_phase',                      SENSOR_GROUP_RED_PHASE,           float),
    ('blue_amplitude',                 SENSOR_GROUP_BLUE_AMPLITUDE,      float),
    ('red_amplitude',                  SENSOR_GROUP_RED_AMPLITUDE,       float),
    ('raw_temperature',                SENSOR_GROUP_RAW_TEMPERATURE,     float)
]


class DostaStateKey(BaseEnum):
    POSITION = 'position'            # position within the input file


class DataParticleType(BaseEnum):
    REC_INSTRUMENT_PARTICLE = 'dosta_abcdjm_dcl_instrument_recovered'
    TEL_INSTRUMENT_PARTICLE = 'dosta_abcdjm_dcl_instrument'


class DostaAbcdjmDclInstrumentDataParticle(DataParticle):
    """
    Class for generating the Dosta instrument particle.
    """

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        super(DostaAbcdjmDclInstrumentDataParticle, self).__init__(raw_data,
                                                          port_timestamp,
                                                          internal_timestamp,
                                                          preferred_timestamp,
                                                          quality_flag,
                                                          new_sequence)

        # The particle timestamp is the DCL Controller timestamp.
        # The individual fields have already been extracted by the parser.

        timestamp = (
            int(self.raw_data[SENSOR_GROUP_YEAR]),
            int(self.raw_data[SENSOR_GROUP_MONTH]),
            int(self.raw_data[SENSOR_GROUP_DAY]),
            int(self.raw_data[SENSOR_GROUP_HOUR]),
            int(self.raw_data[SENSOR_GROUP_MINUTE]),
            int(self.raw_data[SENSOR_GROUP_SECOND]),
            0, 0, 0)
        elapsed_seconds = calendar.timegm(timestamp)
        self.set_internal_timestamp(unix_time=elapsed_seconds)

    def _build_parsed_values(self):
        """
        Build parsed values for Recovered and Telemetered Instrument Data Particle.
        """

        # Generate a particle by calling encode_value for each entry
        # in the Instrument Particle Mapping table,
        # where each entry is a tuple containing the particle field name,
        # an index into the match groups (which is what has been stored in raw_data),
        # and a function to use for data conversion.

        return [self._encode_value(name, self.raw_data[group], function)
            for name, group, function in INSTRUMENT_PARTICLE_MAP]


class DostaAbcdjmDclRecoveredInstrumentDataParticle(DostaAbcdjmDclInstrumentDataParticle):
    """
    Class for generating Offset Data Particles from Recovered data.
    """
    _data_particle_type = DataParticleType.REC_INSTRUMENT_PARTICLE


class DostaAbcdjmDclTelemeteredInstrumentDataParticle(DostaAbcdjmDclInstrumentDataParticle):
    """
    Class for generating Offset Data Particles from Telemetered data.
    """
    _data_particle_type = DataParticleType.TEL_INSTRUMENT_PARTICLE


class DostaAbcdjmDclParser(BufferLoadingParser):

    """
    Parser for Dosta_abcdjm_dcl data.
    In addition to the standard constructor parameters,
    this constructor takes an additional parameter particle_class.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 particle_class,
                 *args, **kwargs):

        # No fancy sieve function needed for this parser.
        # File is ASCII with records separated by newlines.

        super(DostaAbcdjmDclParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          partial(StringChunker.regex_sieve_function,
                                                  regex_list=[DOSTA_RECORD_MATCHER]),
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)

        # Default the position within the file to the beginning.

        self._read_state = {DostaStateKey.POSITION: 0}
        self.input_file = stream_handle
        self.particle_class = particle_class

        # If there's an existing state, update to it.

        if state is not None:
            self.set_state(state)

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # Handle non-data here.
        # Increment the position within the file.
        # Use the _exception_callback.
        if non_data is not None and non_end <= start:
            self._increment_position(len(non_data))
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" %
                (len(non_data), non_data)))

    def _increment_position(self, bytes_read):
        """
        Increment the position within the file.
        @param bytes_read The number of bytes just read
        """
        self._read_state[DostaStateKey.POSITION] += bytes_read

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker.
        If it is valid data, build a particle.
        Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state.
        """
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        while chunk is not None:
            self._increment_position(len(chunk))

            # If this is a valid sensor data record,
            # use the extracted fields to generate a particle.

            sensor_match = SENSOR_DATA_MATCHER.match(chunk)
            if sensor_match is not None:
                particle = self._extract_sample(self.particle_class,
                                                None,
                                                sensor_match.groups(),
                                                None)
                if particle is not None:
                    result_particles.append((particle, copy.copy(self._read_state)))

            # It's not a sensor data record, see if it's a metadata record.

            else:

                # If it appears to be a metadata record,
                # look for multiple lines which have been garbled,
                # i.e., a metadata record minus the newline
                # plus tab-separated values from a following sensor data record.
                # find returns -1 if not found.
                # Valid Metadata records produce no particles and
                # are silently ignored.

                meta_match = METADATA_MATCHER.match(chunk)
                if meta_match is None or chunk.find(TAB) != -1:
                    error_message = 'Unknown data found in chunk %s' % chunk
                    log.warn(error_message)
                    self._exception_callback(UnexpectedDataException(error_message))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to.
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")

        if not (DostaStateKey.POSITION in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         DostaStateKey.POSITION)

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        self.input_file.seek(state_obj[DostaStateKey.POSITION])


class DostaAbcdjmDclRecoveredParser(DostaAbcdjmDclParser):
    """
    This is the entry point for the Recovered Dosta_abcdjm_dcl parser.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        super(DostaAbcdjmDclRecoveredParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          DostaAbcdjmDclRecoveredInstrumentDataParticle,
                                          *args,
                                          **kwargs)


class DostaAbcdjmDclTelemeteredParser(DostaAbcdjmDclParser):
    """
    This is the entry point for the Telemetered Dosta_abcdjm_dcl parser.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        super(DostaAbcdjmDclTelemeteredParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          DostaAbcdjmDclTelemeteredInstrumentDataParticle,
                                          *args,
                                          **kwargs)
