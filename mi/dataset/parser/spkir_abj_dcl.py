#!/usr/bin/env python

"""
@package mi.dataset.parser.spkir_abj_dcl
@file marine-integrations/mi/dataset/parser/spkir_abj_dcl.py
@author Steve Myerson
@brief Parser for the spkir_abj_dcl dataset driver

This file contains code for the spkir_abj_dcl parsers and code to produce data particles.
For telemetered data, there is one parser which produces one type of data particle.
For recovered data, there is one parser which produces one type of data particle.
The input files and the content of the data particles are the same for both
recovered and telemetered.
Only the names of the output particle streams are different.

The input file is ASCII and binary and contains 2 types of records.
All records start with a timestamp.
Records are separated by one of the newlines.
Binary data is big endian.

Metadata records: timestamp [text] more text line-feed.
Sensor Data records: timestamp ASCII-data Binary-data carriage-return line-feed.
Only sensor data records produce particles if properly formed.
Metadata records produce no particles.

Release notes:

Initial Release
"""

__author__ = 'Steve Myerson'
__license__ = 'Apache 2.0'

import calendar
import copy
from functools import partial
import re
import struct

from mi.core.instrument.chunker import \
    StringChunker

from mi.core.log import get_logger; log = get_logger()

from mi.dataset.dataset_parser import \
    BufferLoadingParser

from mi.core.common import BaseEnum
from mi.core.exceptions import \
    DatasetParserException, \
    UnexpectedDataException

from mi.core.instrument.data_particle import \
    DataParticle, \
    DataParticleKey, \
    DataParticleValue

# Basic patterns
ANY_CHARS = r'.*'                   # Any characters excluding a newline
BINARY_BYTE = b'([\x00-\xFF])'      # Binary 8-bit field (1 bytes)
BINARY_SHORT = b'([\x00-\xFF]{2})'  # Binary 16-bit field (2 bytes)
BINARY_LONG = b'([\x00-\xFF]{4})'   # Binary 32-bit field (4 bytes)
SPACE = ' '
START_GROUP = '('
END_GROUP = ')'

# Timestamp at the start of each record: YYYY/MM/DD HH:MM:SS.mmm
DATE = r'(\d{4})/(\d{2})/(\d{2})'           # Date: YYYY/MM/DD
TIME = r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})'  # Time: HH:MM:SS.mmm
TIMESTAMP = START_GROUP + DATE + SPACE + TIME + END_GROUP
START_METADATA = r'\['
END_METADATA = r'\]'

# Metadata record:
#   Timestamp [Text]MoreText newline
METADATA_REGEX = TIMESTAMP + SPACE  # date and time
METADATA_REGEX += START_METADATA    # Metadata record starts with '['
METADATA_REGEX += ANY_CHARS         # followed by text
METADATA_REGEX += END_METADATA      # followed by ']'
METADATA_REGEX += ANY_CHARS         # followed by more text
METADATA_REGEX += r'\n'             # Metadata record ends with a line-feed
METADATA_MATCHER = re.compile(METADATA_REGEX)

# Sensor data record:
#   Timestamp SATDI<id><ascii data><binary data> newline
SENSOR_DATA_REGEX = TIMESTAMP + SPACE   # date and time
SENSOR_DATA_REGEX += START_GROUP        # Group data fields (for checksum calc)
SENSOR_DATA_REGEX += r'(SATDI\d)'       #   ASCII SATDI id
SENSOR_DATA_REGEX += r'(\d{4})'         #   ASCII serial number
SENSOR_DATA_REGEX += r'(\d{7}\.\d{2})'  #   ASCII timer
SENSOR_DATA_REGEX += BINARY_SHORT       #   2-byte signed sample delay
SENSOR_DATA_REGEX += START_GROUP        #   Group all the channel ADC counts
SENSOR_DATA_REGEX += BINARY_LONG        #     4-byte unsigned Channel 1 ADC count
SENSOR_DATA_REGEX += BINARY_LONG        #     4-byte unsigned Channel 2 ADC count
SENSOR_DATA_REGEX += BINARY_LONG        #     4-byte unsigned Channel 3 ADC count
SENSOR_DATA_REGEX += BINARY_LONG        #     4-byte unsigned Channel 4 ADC count
SENSOR_DATA_REGEX += BINARY_LONG        #     4-byte unsigned Channel 5 ADC count
SENSOR_DATA_REGEX += BINARY_LONG        #     4-byte unsigned Channel 6 ADC count
SENSOR_DATA_REGEX += BINARY_LONG        #     4-byte unsigned Channel 7 ADC count
SENSOR_DATA_REGEX += END_GROUP          #   End of channel ADC counts group
SENSOR_DATA_REGEX += BINARY_SHORT       #   2-byte unsigned Supply Voltage
SENSOR_DATA_REGEX += BINARY_SHORT       #   2-byte unsigned Analog Voltage
SENSOR_DATA_REGEX += BINARY_SHORT       #   2-byte unsigned Internal Temperature
SENSOR_DATA_REGEX += BINARY_BYTE        #   1-byte unsigned Frame Count
SENSOR_DATA_REGEX += BINARY_BYTE        #   1-byte unsigned Checksum
SENSOR_DATA_REGEX += END_GROUP          # End of all the data group
SENSOR_DATA_REGEX += r'\r\n'            # Sensor data record ends with CR-LF
SENSOR_DATA_MATCHER = re.compile(SENSOR_DATA_REGEX)

# The following are indices into SENSOR_DATA_MATCHER.groups()
SENSOR_GROUP_TIMESTAMP = 0
SENSOR_GROUP_YEAR = 1
SENSOR_GROUP_MONTH = 2
SENSOR_GROUP_DAY = 3
SENSOR_GROUP_HOUR = 4
SENSOR_GROUP_MINUTE = 5
SENSOR_GROUP_SECOND = 6
SENSOR_GROUP_MILLI_SECOND = 7
SENSOR_GROUP_CHECKSUM_SECTION = 8
SENSOR_GROUP_ID = 9
SENSOR_GROUP_SERIAL = 10
SENSOR_GROUP_TIMER = 11
SENSOR_GROUP_DELAY = 12
SENSOR_GROUP_ADC_COUNTS = 13
SENSOR_GROUP_SUPPLY_VOLTAGE = 21
SENSOR_GROUP_ANALOG_VOLTAGE = 22
SENSOR_GROUP_TEMPERATURE = 23
SENSOR_GROUP_FRAME_COUNT = 24
SENSOR_GROUP_CHECKSUM = 25

# The following are indices into raw_data
PARTICLE_GROUP_TIMESTAMP = 0
PARTICLE_GROUP_YEAR = 1
PARTICLE_GROUP_MONTH = 2
PARTICLE_GROUP_DAY = 3
PARTICLE_GROUP_HOUR = 4
PARTICLE_GROUP_MINUTE = 5
PARTICLE_GROUP_SECOND = 6
PARTICLE_GROUP_ID = 7
PARTICLE_GROUP_SERIAL = 8
PARTICLE_GROUP_TIMER = 9
PARTICLE_GROUP_DELAY = 10
PARTICLE_GROUP_CHANNEL = 11
PARTICLE_GROUP_SUPPLY_VOLTAGE = 12
PARTICLE_GROUP_ANALOG_VOLTAGE = 13
PARTICLE_GROUP_TEMPERATURE = 14
PARTICLE_GROUP_FRAME_COUNT = 15
PARTICLE_GROUP_CHECKSUM = 16

CHECKSUM_FAILED = 0                # particle value if the checksum does not match
CHECKSUM_PASSED = 1                # particle value if the checksum matches

# This table is used in the generation of the instrument data particle.
# Column 1 - particle parameter name
# Column 2 - index into raw_data
# Column 3 - data encoding function (conversion required - int, float, etc)
INSTRUMENT_PARTICLE_MAP = [
    ('dcl_controller_timestamp',  PARTICLE_GROUP_TIMESTAMP,       str),
    ('instrument_id',             PARTICLE_GROUP_ID,              str),
    ('serial_number',             PARTICLE_GROUP_SERIAL,          str),
    ('timer',                     PARTICLE_GROUP_TIMER,           float),
    ('sample_delay',              PARTICLE_GROUP_DELAY,           int),
    ('channel_array',             PARTICLE_GROUP_CHANNEL,         list),
    ('vin_sense',                 PARTICLE_GROUP_SUPPLY_VOLTAGE,  int),
    ('va_sense',                  PARTICLE_GROUP_ANALOG_VOLTAGE,  int),
    ('internal_temperature',      PARTICLE_GROUP_TEMPERATURE,     int),
    ('frame_counter',             PARTICLE_GROUP_FRAME_COUNT,     int),
    ('passed_checksum',           PARTICLE_GROUP_CHECKSUM,        int)
]


class SpkirDataParticleType(BaseEnum):
    REC_INSTRUMENT_PARTICLE = 'spkir_abj_dcl_instrument_recovered'
    TEL_INSTRUMENT_PARTICLE = 'spkir_abj_dcl_instrument'


class SpkirStateKey(BaseEnum):
    POSITION = 'position'            # position within the input file
    
    
class SpkirAbjDclInstrumentDataParticle(DataParticle):
    """
    Class for generating the Spkir instrument particle.
    """

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        super(SpkirAbjDclInstrumentDataParticle, self).__init__(raw_data,
                                                          port_timestamp,
                                                          internal_timestamp,
                                                          preferred_timestamp,
                                                          quality_flag,
                                                          new_sequence)

        # The particle timestamp is the DCL Controller timestamp.
        # The individual fields have already been extracted by the parser.

        timestamp = (
            int(self.raw_data[PARTICLE_GROUP_YEAR]),
            int(self.raw_data[PARTICLE_GROUP_MONTH]),
            int(self.raw_data[PARTICLE_GROUP_DAY]),
            int(self.raw_data[PARTICLE_GROUP_HOUR]),
            int(self.raw_data[PARTICLE_GROUP_MINUTE]),
            int(self.raw_data[PARTICLE_GROUP_SECOND]),
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
        # an index into raw_data, and a function to use for data conversion.

        return [self._encode_value(name, self.raw_data[group], function)
            for name, group, function in INSTRUMENT_PARTICLE_MAP]


class SpkirAbjDclRecoveredInstrumentDataParticle(SpkirAbjDclInstrumentDataParticle):
    """
    Class for generating Offset Data Particles from Recovered data.
    """
    _data_particle_type = SpkirDataParticleType.REC_INSTRUMENT_PARTICLE


class SpkirAbjDclTelemeteredInstrumentDataParticle(SpkirAbjDclInstrumentDataParticle):
    """
    Class for generating Offset Data Particles from Telemetered data.
    """
    _data_particle_type = SpkirDataParticleType.TEL_INSTRUMENT_PARTICLE


class SpkirAbjDclParser(BufferLoadingParser):

    """
    Parser for Spkir_abj_dcl data.
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

        super(SpkirAbjDclParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          partial(StringChunker.regex_sieve_function,
                                                  regex_list=[METADATA_MATCHER,
                                                              SENSOR_DATA_MATCHER]),
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)

        # Default the position within the file to the beginning.

        self._read_state = {SpkirStateKey.POSITION: 0}
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
        self._read_state[SpkirStateKey.POSITION] += bytes_read

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

                # Got a sensor data match.
                # The separated fields will go into the particle data.

                groups = sensor_match.groups()

                # See if the checksum is correct.
                # Checksum is the modulo 256 sum of all data bytes.
                # If calculated checksum is zero, the record checksum is valid.

                buffer_to_be_checksummed = groups[SENSOR_GROUP_CHECKSUM_SECTION]
                checksum = reduce(lambda x, y: x + y,
                                  map(ord, buffer_to_be_checksummed)) % 256

                if checksum == 0:
                    checksum_status = CHECKSUM_PASSED
                else:
                    checksum_status = CHECKSUM_FAILED

                # Create a tuple containing all the data to be used when
                # creating the particle.
                # The order of the particle data matches the PARTICLE_GROUPS.

                particle_data = (
                    groups[SENSOR_GROUP_TIMESTAMP],
                    groups[SENSOR_GROUP_YEAR],
                    groups[SENSOR_GROUP_MONTH],
                    groups[SENSOR_GROUP_DAY],
                    groups[SENSOR_GROUP_HOUR],
                    groups[SENSOR_GROUP_MINUTE],
                    groups[SENSOR_GROUP_SECOND],
                    groups[SENSOR_GROUP_ID],
                    groups[SENSOR_GROUP_SERIAL],
                    groups[SENSOR_GROUP_TIMER],
                    struct.unpack('>h', groups[SENSOR_GROUP_DELAY])[0],
                    list(struct.unpack('>7I', groups[SENSOR_GROUP_ADC_COUNTS])),
                    struct.unpack('>H', groups[SENSOR_GROUP_SUPPLY_VOLTAGE])[0],
                    struct.unpack('>H', groups[SENSOR_GROUP_ANALOG_VOLTAGE])[0],
                    struct.unpack('>H', groups[SENSOR_GROUP_TEMPERATURE])[0],
                    struct.unpack('>B', groups[SENSOR_GROUP_FRAME_COUNT])[0],
                    checksum_status
                )

                particle = self._extract_sample(self.particle_class,
                                                None,
                                                particle_data,
                                                None)
                if particle is not None:
                    result_particles.append((particle, copy.copy(self._read_state)))

            # It's not a sensor data record, see if it's a metadata record.
            # If not a valid metadata record, generate warning.
            # Valid Metadata records produce no particles and are silently ignored.

            else:
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

        if not (SpkirStateKey.POSITION in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         SpkirStateKey.POSITION)

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        self.input_file.seek(state_obj[SpkirStateKey.POSITION])


class SpkirAbjDclRecoveredParser(SpkirAbjDclParser):
    """
    This is the entry point for the Recovered Spkir_abj_dcl parser.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        super(SpkirAbjDclRecoveredParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          SpkirAbjDclRecoveredInstrumentDataParticle,
                                          *args,
                                          **kwargs)


class SpkirAbjDclTelemeteredParser(SpkirAbjDclParser):
    """
    This is the entry point for the Telemetered Spkir_abj_dcl parser.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        super(SpkirAbjDclTelemeteredParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          SpkirAbjDclTelemeteredInstrumentDataParticle,
                                          *args,
                                          **kwargs)
