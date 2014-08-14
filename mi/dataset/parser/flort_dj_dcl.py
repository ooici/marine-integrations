#!/usr/bin/env python

"""
@package mi.dataset.parser.flort_dj_dcl
@file marine-integrations/mi/dataset/parser/flort_dj_dcl.py
@author Steve Myerson
@brief Parser for the flort_dj_dcl dataset driver

This file contains code for the flort_dj_dcl parsers and code to produce data particles.
For telemetered data, there is one parser which produces one type of data particle.
For recovered data, there is one parser which produces one type of data particle.
The input files and the content of the data particles are the same for both
recovered and telemetered.
Only the names of the output particle streams are different.

The input file is ASCII and contains 2 types of records.
Records are separated by a newline.
All records start with a timestamp.
Metadata records: timestamp [text] more text newline.
Sensor Data records: timestamp sensor_data newline.
Only sensor data records produce particles if properly formed.
Mal-formed sensor data records and all metadata records produce no particles.

Release notes:

Initial Release
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
from mi.core.common import BaseEnum
from mi.core.exceptions import \
    DatasetParserException, \
    UnexpectedDataException

from mi.core.instrument.data_particle import \
    DataParticle, \
    DataParticleKey, \
    DataParticleValue

from mi.dataset.dataset_parser import BufferLoadingParser

# Basic patterns
ANY_CHARS = r'.*'          # Any characters excluding a newline
NEW_LINE = r'(?:\r\n|\n)'  # any type of new line
UINT = r'(\d*)'            # unsigned integer as a group
SPACE = ' '
TAB = '\t'
START_GROUP = '('
END_GROUP = ')'

# Timestamp at the start of each record: YYYY/MM/DD HH:MM:SS.mmm
# Metadata fields:  [text] more text
# Sensor data has tab-delimited fields (date, time, integers)
# All records end with one of the newlines.
DATE = r'(\d{4})/(\d{2})/(\d{2})'         # Date: YYYY/MM/DD
TIME = r'(\d{2}):(\d{2}):(\d{2})\.\d{3}'  # Time: HH:MM:SS.mmm
SENSOR_DATE = r'(\d{2}/\d{2}/\d{2})'      # Sensor Date: MM/DD/YY
SENSOR_TIME = r'(\d{2}:\d{2}:\d{2})'      # Sensor Time: HH:MM:SS
TIMESTAMP = START_GROUP + DATE + SPACE + TIME + END_GROUP
START_METADATA = r'\['
END_METADATA = r'\]'

# All flort records are ASCII characters separated by a newline.
FLORT_RECORD_PATTERN = ANY_CHARS       # Any number of ASCII characters
FLORT_RECORD_PATTERN += NEW_LINE       # separated by a new line
FLORT_RECORD_MATCHER = re.compile(FLORT_RECORD_PATTERN)

# Metadata record:
#   Timestamp [Text]MoreText newline
METADATA_PATTERN = TIMESTAMP + SPACE  # dcl controller timestamp
METADATA_PATTERN += START_METADATA    # Metadata record starts with '['
METADATA_PATTERN += ANY_CHARS         # followed by text
METADATA_PATTERN += END_METADATA      # followed by ']'
METADATA_PATTERN += ANY_CHARS         # followed by more text
METADATA_PATTERN += r'\n'             # metadata record ends with LF
METADATA_MATCHER = re.compile(METADATA_PATTERN)

# Sensor data record:
#   Timestamp Date<tab>Time<tab>SensorData
#   where SensorData are tab-separated unsigned integer numbers
SENSOR_DATA_PATTERN = TIMESTAMP + SPACE    # dcl controller timestamp
SENSOR_DATA_PATTERN += SENSOR_DATE + TAB   # sensor date
SENSOR_DATA_PATTERN += SENSOR_TIME + TAB   # sensor time
SENSOR_DATA_PATTERN += UINT + TAB          # measurement wavelength beta
SENSOR_DATA_PATTERN += UINT + TAB          # raw signal beta
SENSOR_DATA_PATTERN += UINT + TAB          # measurement wavelength chl
SENSOR_DATA_PATTERN += UINT + TAB          # raw signal chl
SENSOR_DATA_PATTERN += UINT + TAB          # measurement wavelength cdom
SENSOR_DATA_PATTERN += UINT + TAB          # raw signal cdom
SENSOR_DATA_PATTERN += UINT                # raw internal temperature
SENSOR_DATA_PATTERN += r'\r\n'             # sensor data ends with CR-LF
SENSOR_DATA_MATCHER = re.compile(SENSOR_DATA_PATTERN)

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
SENSOR_GROUP_SENSOR_DATE = 7
SENSOR_GROUP_SENSOR_TIME = 8
SENSOR_GROUP_WAVELENGTH_BETA = 9
SENSOR_GROUP_RAW_SIGNAL_BETA = 10
SENSOR_GROUP_WAVELENGTH_CHL = 11
SENSOR_GROUP_RAW_SIGNAL_CHL = 12
SENSOR_GROUP_WAVELENGTH_CDOM = 13
SENSOR_GROUP_RAW_SIGNAL_CDOM = 14
SENSOR_GROUP_INTERNAL_TEMPERATURE = 15

# This table is used in the generation of the instrument data particle.
# Column 1 - particle parameter name
# Column 2 - group number (index into raw_data)
# Column 3 - data encoding function (conversion required - int, float, etc)
INSTRUMENT_PARTICLE_MAP = [
    ('dcl_controller_timestamp',    SENSOR_GROUP_TIMESTAMP,             str),
    ('date_string',                 SENSOR_GROUP_SENSOR_DATE,           str),
    ('time_string',                 SENSOR_GROUP_SENSOR_TIME,           str),
    ('measurement_wavelength_beta', SENSOR_GROUP_WAVELENGTH_BETA,       int),
    ('raw_signal_beta',             SENSOR_GROUP_RAW_SIGNAL_BETA,       int),
    ('measurement_wavelength_chl',  SENSOR_GROUP_WAVELENGTH_CHL,        int),
    ('raw_signal_chl',              SENSOR_GROUP_RAW_SIGNAL_CHL,        int),
    ('measurement_wavelength_cdom', SENSOR_GROUP_WAVELENGTH_CDOM,       int),
    ('raw_signal_cdom',             SENSOR_GROUP_RAW_SIGNAL_CDOM,       int),
    ('raw_internal_temp',           SENSOR_GROUP_INTERNAL_TEMPERATURE,  int)
]


class FlortStateKey(BaseEnum):
    POSITION = 'position'            # position within the input file


class DataParticleType(BaseEnum):
    REC_INSTRUMENT_PARTICLE = 'flort_dj_dcl_instrument_recovered'
    TEL_INSTRUMENT_PARTICLE = 'flort_dj_dcl_instrument'
    
    
class FlortDjDclInstrumentDataParticle(DataParticle):
    """
    Class for generating the Flort_dj instrument particle.
    """

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        super(FlortDjDclInstrumentDataParticle, self).__init__(raw_data,
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


class FlortDjDclRecoveredInstrumentDataParticle(FlortDjDclInstrumentDataParticle):
    """
    Class for generating Offset Data Particles from Recovered data.
    """
    _data_particle_type = DataParticleType.REC_INSTRUMENT_PARTICLE


class FlortDjDclTelemeteredInstrumentDataParticle(FlortDjDclInstrumentDataParticle):
    """
    Class for generating Offset Data Particles from Telemetered data.
    """
    _data_particle_type = DataParticleType.TEL_INSTRUMENT_PARTICLE


class FlortDjDclParser(BufferLoadingParser):

    """
    Parser for Flort_dj_dcl data.
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

        super(FlortDjDclParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          partial(StringChunker.regex_sieve_function,
                                                  regex_list=[FLORT_RECORD_MATCHER]),
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)

        # Default the position within the file to the beginning.

        self._read_state = {FlortStateKey.POSITION: 0}
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
        self._read_state[FlortStateKey.POSITION] += bytes_read

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

                # If it's a valid metadata record, ignore it.
                # Otherwise generate warning for unknown data.

                meta_match = METADATA_MATCHER.match(chunk)
                if meta_match is None:
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

        if not (FlortStateKey.POSITION in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         FlortStateKey.POSITION)

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        self.input_file.seek(state_obj[FlortStateKey.POSITION])


class FlortDjDclRecoveredParser(FlortDjDclParser):
    """
    This is the entry point for the Recovered Flort_dj_dcl parser.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        super(FlortDjDclRecoveredParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          FlortDjDclRecoveredInstrumentDataParticle,
                                          *args,
                                          **kwargs)


class FlortDjDclTelemeteredParser(FlortDjDclParser):
    """
    This is the entry point for the Telemetered Flort_dj_dcl parser.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        super(FlortDjDclTelemeteredParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          FlortDjDclTelemeteredInstrumentDataParticle,
                                          *args,
                                          **kwargs)
