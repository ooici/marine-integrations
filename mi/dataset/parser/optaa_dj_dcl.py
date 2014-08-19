#!/usr/bin/env python

"""
@package mi.dataset.parser.optaa_dj_dcl
@file marine-integrations/mi/dataset/parser/optaa_dj_dcl.py
@author Steve Myerson (Raytheon)
@brief Parser for the optaa_dj_dcl dataset driver

This file contains code for the optaa_dj_dcl parsers and code to produce data particles.
For telemetered data, there is one parser which produces two types of data particles.
For recovered data, there is one parser which produces two types of data particles.
Both parsers produce instrument and metadata data particles.
There is 1 metadata data particle produced for each file.
There is 1 instrument data particle produced for each record in a file.
The input files and the content of the data particles are the same for both
recovered and telemetered.
Only the names of the output particle streams are different.

Input files are binary with variable length records.

Release notes:

Initial release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import calendar
import copy
import re
import ntplib
import struct

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.exceptions import \
    DatasetParserException, \
    RecoverableSampleException, \
    UnexpectedDataException

from mi.core.instrument.data_particle import \
    DataParticle, \
    DataParticleKey, \
    DataParticleValue

from mi.dataset.dataset_parser import BufferLoadingParser

SIZE_CHECKSUM = 2
SIZE_PAD = 1

# Basic patterns
START_GROUP = '('
END_GROUP = ')'
ANY_BYTE = r'[\x00-\xFF]'            # Any value from 0x00 to 0xFF
BINARY_BYTE = r'([\x00-\xFF])'       # Binary 8-bit field (1 byte)
BINARY_SHORT = r'([\x00-\xFF]{2})'   # Binary 16-bit field (2 bytes)
BINARY_LONG = r'([\x00-\xFF]{4})'    # Binary 32-bit field (4 bytes)
UNUSED_BINARY_BYTE = r'[\x00-\xFF]'  # Non-grouped Binary 8-bit field (1 byte)
DATE = r'(\d{4})(\d{2})(\d{2})'      # Date: YYYYMMDD
TIME = r'(\d{2})(\d{2})(\d{2})'      # Time: HHMMSS

# Define a regex to parse the filename.
FILENAME_REGEX = DATE + '_' + TIME
FILENAME_MATCHER = re.compile(FILENAME_REGEX)

# FILENAME_MATCHER produces the following match.group() indices.
GROUP_YEAR = 1
GROUP_MONTH = 2
GROUP_DAY = 3
GROUP_HOUR = 4
GROUP_MINUTE = 5
GROUP_SECOND = 6

# Define a regex up to and including the packet length.
LENGTH_REGEX = r'\xFF\x00\xFF\x00'  # all packets start with 0xFF00FF00
LENGTH_REGEX += BINARY_SHORT        # packet length not incl checksum or pad
LENGTH_MATCHER = re.compile(START_GROUP + LENGTH_REGEX + END_GROUP)

# Define a regex for the fixed part of the packet
# which is up to and including the number of wavelengths.
WAVELENGTH_REGEX = LENGTH_REGEX
WAVELENGTH_REGEX += BINARY_BYTE           # packet type
WAVELENGTH_REGEX += UNUSED_BINARY_BYTE    # reserved
WAVELENGTH_REGEX += BINARY_BYTE           # meter type
WAVELENGTH_REGEX += r'([\x00-\xFF]{3})'   # serial number (3 bytes)
WAVELENGTH_REGEX += BINARY_SHORT          # A reference dark count
WAVELENGTH_REGEX += BINARY_SHORT          # pressure count
WAVELENGTH_REGEX += BINARY_SHORT          # A signal dark count
WAVELENGTH_REGEX += BINARY_SHORT          # raw external temperature
WAVELENGTH_REGEX += BINARY_SHORT          # raw internal temperature
WAVELENGTH_REGEX += BINARY_SHORT          # C reference dark count
WAVELENGTH_REGEX += BINARY_SHORT          # C signal dark count
WAVELENGTH_REGEX += BINARY_LONG           # time since power-up
WAVELENGTH_REGEX += UNUSED_BINARY_BYTE    # reserved
WAVELENGTH_REGEX += BINARY_BYTE           # number of wavelengths
WAVELENGTH_MATCHER = re.compile(START_GROUP + WAVELENGTH_REGEX + END_GROUP)

# Group numbers to be used in match.group(GROUP_xxx)
GROUP_CHECKSUM_REGION = 1
GROUP_PACKET_LENGTH = 2
GROUP_PACKET_TYPE = 3
GROUP_METER_TYPE = 4
GROUP_SERIAL_NUMBER = 5
GROUP_A_REFERENCE = 6
GROUP_PRESSURE_COUNT = 7
GROUP_A_SIGNAL = 8
GROUP_EXTERNAL_TEMP = 9
GROUP_INTERNAL_TEMP = 10
GROUP_C_REFERENCE = 11
GROUP_C_SIGNAL = 12
GROUP_POWER_UP_TIME = 13
GROUP_WAVELENGTHS = 14
GROUP_MEASUREMENTS = 15
GROUP_CHECKSUM = 16

BYTES_PER_MEASUREMENT = 2
MEASUREMENTS_PER_SET = 4    # number of signal measurements per set
BYTES_PER_SET = BYTES_PER_MEASUREMENT * MEASUREMENTS_PER_SET

# Indices into raw_data for Instrument particles.
RAW_INDEX_A_REFERENCE_DARK = 0
RAW_INDEX_PRESSURE_COUNT = 1
RAW_INDEX_A_SIGNAL_DARK = 2
RAW_INDEX_EXTERNAL_TEMP = 3
RAW_INDEX_INTERNAL_TEMP = 4
RAW_INDEX_C_REFERENCE_DARK = 5
RAW_INDEX_C_SIGNAL_DARK = 6
RAW_INDEX_POWER_UP_TIME = 7
RAW_INDEX_WAVELENGTHS = 8
RAW_INDEX_C_REFERENCE = 9
RAW_INDEX_A_REFERENCE = 10
RAW_INDEX_C_SIGNAL = 11
RAW_INDEX_A_SIGNAL = 12

# Indices into raw_data for Metadata particles.
RAW_INDEX_START_DATE = 0
RAW_INDEX_PACKET_TYPE = 1
RAW_INDEX_METER_TYPE = 2
RAW_INDEX_SERIAL_NUMBER = 3

# This table is used in the generation of the instrument data particle.
# Column 1 - particle parameter name
# Column 2 - index into raw_data
# Column 3 - data encoding function (conversion required - int, float, etc)
INSTRUMENT_PARTICLE_MAP = [
    ('a_reference_dark_counts',  RAW_INDEX_A_REFERENCE_DARK, int),
    ('pressure_counts',          RAW_INDEX_PRESSURE_COUNT,   int),
    ('a_signal_dark_counts',     RAW_INDEX_A_SIGNAL_DARK,    int),
    ('external_temp_raw',        RAW_INDEX_EXTERNAL_TEMP,    int),
    ('internal_temp_raw',        RAW_INDEX_INTERNAL_TEMP,    int),
    ('c_reference_dark_counts',  RAW_INDEX_C_REFERENCE_DARK, int),
    ('c_signal_dark_counts',     RAW_INDEX_C_SIGNAL_DARK,    int),
    ('elapsed_run_time',         RAW_INDEX_POWER_UP_TIME,    int),
    ('num_wavelengths',          RAW_INDEX_WAVELENGTHS,      int),
    ('c_reference_counts',       RAW_INDEX_C_REFERENCE,      list),
    ('a_reference_counts',       RAW_INDEX_A_REFERENCE,      list),
    ('c_signal_counts',          RAW_INDEX_C_SIGNAL,         list),
    ('a_signal_counts',          RAW_INDEX_A_SIGNAL,         list)
]

# This table is used in the generation of the metadata data particle.
# Column 1 - particle parameter name
# Column 2 - index into raw_data
# Column 3 - data encoding function (conversion required - int, float, etc)
METADATA_PARTICLE_MAP = [
    ('start_date',               RAW_INDEX_START_DATE,       str),
    ('packet_type',              RAW_INDEX_PACKET_TYPE,      int),
    ('meter_type',               RAW_INDEX_METER_TYPE,       int),
    ('serial_number',            RAW_INDEX_SERIAL_NUMBER,    int)
]


def build_packet_matcher(wavelengths):
    """
    This function builds a matcher for the entire packet.
    Once the number of wavelengths (set of measurements) is known,
    the matcher is built.
    """
    regex = START_GROUP           # Start of the checksum region group
    regex += WAVELENGTH_REGEX     # Include up to the number of wavelengths
    regex += START_GROUP          # all wavelength measurements go in one group
    regex += ANY_BYTE             # each wavelength measurement is 2 bytes
    regex += '{%d}' % (wavelengths * BYTES_PER_SET)
    regex += END_GROUP            # end of the wavelength measurements group
    regex += END_GROUP            # end of the checksum region group
    regex += BINARY_SHORT         # checksum
    regex += UNUSED_BINARY_BYTE   # pad

    return re.compile(regex)


class OptaaStateKey(BaseEnum):
    POSITION = 'position'                      # position within the input file
    METADATA_GENERATED = 'metadata_generated'  # has metadata particle been generated?
    TIME_SINCE_POWER_UP = 'time_since_power_up'  # relative clock for record 1


class DataParticleType(BaseEnum):
    REC_INSTRUMENT_PARTICLE = 'optaa_dj_dcl_instrument_recovered'
    REC_METADATA_PARTICLE = 'optaa_dj_dcl_metadata_recovered'
    TEL_INSTRUMENT_PARTICLE = 'optaa_dj_dcl_instrument'
    TEL_METADATA_PARTICLE = 'optaa_dj_dcl_metadata'
    

class OptaaDjDclInstrumentDataParticle(DataParticle):
    """
    Class for generating the Optaa_dj instrument particle.
    """

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        super(OptaaDjDclInstrumentDataParticle, self).__init__(raw_data,
                                                          port_timestamp,
                                                          internal_timestamp,
                                                          preferred_timestamp,
                                                          quality_flag,
                                                          new_sequence)

    def _build_parsed_values(self):
        """
        Build parsed values for Recovered and Telemetered Instrument Data Particle.
        """

        # Generate a particle by calling encode_value for each entry
        # in the Instrument Particle Mapping table,
        # where each entry is a tuple containing the particle field name,
        # an index into match.group (which is what has been stored in raw_data),
        # and a function to use for data conversion.

        return [self._encode_value(name, self.raw_data[group], function)
            for name, group, function in INSTRUMENT_PARTICLE_MAP]


class OptaaDjDclRecoveredInstrumentDataParticle(OptaaDjDclInstrumentDataParticle):
    """
    Class for generating Offset Data Particles from Recovered data.
    """
    _data_particle_type = DataParticleType.REC_INSTRUMENT_PARTICLE


class OptaaDjDclTelemeteredInstrumentDataParticle(OptaaDjDclInstrumentDataParticle):
    """
    Class for generating Offset Data Particles from Telemetered data.
    """
    _data_particle_type = DataParticleType.TEL_INSTRUMENT_PARTICLE


class OptaaDjDclMetadataDataParticle(DataParticle):
    """
    Class for generating the Optaa_dj Metadata particle.
    """

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        super(OptaaDjDclMetadataDataParticle, self).__init__(raw_data,
                                                          port_timestamp,
                                                          internal_timestamp,
                                                          preferred_timestamp,
                                                          quality_flag,
                                                          new_sequence)

    def _build_parsed_values(self):
        """
        Build parsed values for Recovered and Telemetered Metadata Data Particle.
        """

        # Generate a particle by calling encode_value for each entry
        # in the Metadata Particle Mapping table,
        # where each entry is a tuple containing the particle field name,
        # an index into match.group (which is what has been stored in raw_data),
        # and a function to use for data conversion.

        return [self._encode_value(name, self.raw_data[group], function)
            for name, group, function in METADATA_PARTICLE_MAP]


class OptaaDjDclRecoveredMetadataDataParticle(OptaaDjDclMetadataDataParticle):
    """
    Class for generating Metadata Data Particles from Recovered data.
    """
    _data_particle_type = DataParticleType.REC_METADATA_PARTICLE


class OptaaDjDclTelemeteredMetadataDataParticle(OptaaDjDclMetadataDataParticle):
    """
    Class for generating Metadata Data Particles from Telemetered data.
    """
    _data_particle_type = DataParticleType.TEL_METADATA_PARTICLE


class OptaaDjDclParser(BufferLoadingParser):
    """
    Parser for Optaa_dj_dcl data.
    In addition to the standard constructor parameters,
    this constructor takes the following additional parameters:
      filename - Name of file being parsed
      instrument particle class
      metadata particle class.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 filename,
                 instrument_particle_class,
                 metadata_particle_class,
                 *args, **kwargs):

        super(OptaaDjDclParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)

        # Default the position within the file to the beginning
        # and metadata particle not having been generated.

        self._read_state = {
            OptaaStateKey.POSITION: 0,
            OptaaStateKey.METADATA_GENERATED: False,
            OptaaStateKey.TIME_SINCE_POWER_UP: 0.0
        }
        self.input_file = stream_handle

        # If there's an existing state, update to it.

        if state is not None:
            self.set_state(state)

        # Save the names of the particle classes to be generated.

        self.instrument_particle_class = instrument_particle_class
        self.metadata_particle_class = metadata_particle_class

        # Extract the start date and time from the filename.
        # Calculate the ntp_time timestamp, the number of seconds since Jan 1, 1900.

        filename_match = FILENAME_MATCHER.match(filename)
        if filename_match is not None:
            self.start_date = filename_match.group(0)
            timestamp = (
                int(filename_match.group(GROUP_YEAR)),
                int(filename_match.group(GROUP_MONTH)),
                int(filename_match.group(GROUP_DAY)),
                int(filename_match.group(GROUP_HOUR)),
                int(filename_match.group(GROUP_MINUTE)),
                int(filename_match.group(GROUP_SECOND)),
                0, 0, 0)

            elapsed_seconds = calendar.timegm(timestamp)
            self.ntp_time = ntplib.system_to_ntp_time(elapsed_seconds) - \
                self._read_state[OptaaStateKey.TIME_SINCE_POWER_UP]

        else:
            error_message = 'Invalid filename %s' % filename
            log.warn(error_message)
            raise DatasetParserException(error_message)

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
        self._read_state[OptaaStateKey.POSITION] += bytes_read

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

            # Perform a pattern match so that the number of wavelengths
            # can be determined.

            wavelength_match = WAVELENGTH_MATCHER.match(chunk)
            if wavelength_match is not None:
                wavelengths = struct.unpack('>B',
                    wavelength_match.group(GROUP_WAVELENGTHS))[0]

                # Build the packet matcher now that the number of
                # wavelengths is known.

                packet_matcher = build_packet_matcher(wavelengths)

                # Perform a pattern match for entire packet.

                packet_match = packet_matcher.match(chunk)

                # Extract the expected checksum.

                expected_checksum = struct.unpack('>H',
                    packet_match.group(GROUP_CHECKSUM))[0]

                # Calculate the checksum.
                # Sum each byte, resulting in a 16-bit value.

                actual_checksum = reduce(lambda x, y: x + y,
                    map(ord, packet_match.group(GROUP_CHECKSUM_REGION))) & 0xFFFF

                # If the checksums match, the packet is good.
                # Generate the particle for this packet.

                if actual_checksum == expected_checksum:

                    # Extract the number of milliseconds since power-up.

                    time_since_power_up = float(struct.unpack('>I',
                        packet_match.group(GROUP_POWER_UP_TIME))[0]) / 1000.0

                    # Generate the metadata particle before the first
                    # instrument particle.

                    if not self._read_state[OptaaStateKey.METADATA_GENERATED]:
                        self._read_state[OptaaStateKey.METADATA_GENERATED] = True

                        # Save Record 1 time on since power-up value.

                        self._read_state[OptaaStateKey.TIME_SINCE_POWER_UP] = \
                            time_since_power_up

                        # Create a tuple containing all the data for the
                        # metadata particle.
                        # Order is important and must follow the RAW_INDEX
                        # values for metadata particles.

                        fields = (
                            self.start_date,
                            struct.unpack('>B',
                                packet_match.group(GROUP_PACKET_TYPE))[0],
                            struct.unpack('>B',
                                packet_match.group(GROUP_METER_TYPE))[0],
                            struct.unpack('>I',
                                '\x00' + packet_match.group(GROUP_SERIAL_NUMBER))[0]
                        )

                        #log.debug('META %f', self.ntp_time)

                        particle = self._extract_sample(self.metadata_particle_class,
                            None, fields, self.ntp_time)

                        if particle is not None:
                            result_particles.append((particle,
                                                     copy.copy(self._read_state)))

                        # Adjust the ntp_time at power-up by
                        # the time since power-up of the first record.

                        self.ntp_time -= time_since_power_up

                    # Create a tuple containing all the data for the
                    # instrument particle.
                    # Order is important and must follow the RAW_INDEX values
                    # for instrument particles.
                    #
                    # All the measurements have been put into a single group
                    # as a result of the packet_matcher.
                    # In the input file they're in this order:
                    #   c_ref1 a_ref1 c_sig1 a_sig1
                    #   c_ref2 a_ref2 c_sig2 a_sig2
                    #   c_ref3 a_ref3 c_sig3 a_sig3
                    #   ...
                    #   c_refN a_refN c_sigN a_sigN
                    #
                    # In the output particle, they're in this order:
                    #   c_ref1 c_ref2 c_ref3 ... c_refN
                    #   c_sig1 c_sig2 c_sig3 ... c_sigN
                    #   a_ref1 a_ref2 a_ref3 ... a_refN
                    #   a_sig1 a_sig2 a_sig3 ... a_sigN

                    measurements = packet_match.group(GROUP_MEASUREMENTS)

                    fields = (
                        struct.unpack('>H',
                            packet_match.group(GROUP_A_REFERENCE))[0],
                        struct.unpack('>H',
                            packet_match.group(GROUP_PRESSURE_COUNT))[0],
                        struct.unpack('>H',
                            packet_match.group(GROUP_A_SIGNAL))[0],
                        struct.unpack('>H',
                            packet_match.group(GROUP_EXTERNAL_TEMP))[0],
                        struct.unpack('>H',
                            packet_match.group(GROUP_INTERNAL_TEMP))[0],
                        struct.unpack('>H',
                            packet_match.group(GROUP_C_REFERENCE))[0],
                        struct.unpack('>H',
                            packet_match.group(GROUP_C_SIGNAL))[0],
                        struct.unpack('>I',
                            packet_match.group(GROUP_POWER_UP_TIME))[0],
                        wavelengths,
                        [struct.unpack('>H', measurements[x : x+2])[0]
                            for x in range(0, len(measurements), BYTES_PER_SET)],

                        [struct.unpack('>H', measurements[x : x+2])[0]
                            for x in range(2, len(measurements), BYTES_PER_SET)],

                        [struct.unpack('>H', measurements[x : x+2])[0]
                            for x in range(4, len(measurements), BYTES_PER_SET)],

                        [struct.unpack('>H', measurements[x : x+2])[0]
                            for x in range(6, len(measurements), BYTES_PER_SET)]
                    )

                    # log.debug('INST %f, %s',
                    #           self.ntp_time + time_since_power_up,
                    #           fields)

                    particle = self._extract_sample(self.instrument_particle_class,
                        None, fields, self.ntp_time + time_since_power_up)

                    if particle is not None:
                        result_particles.append((particle,
                                                 copy.copy(self._read_state)))
                else:
                    self._exception_callback(RecoverableSampleException(
                        'Checksum error.  Actual %d vs Expected %d' %
                        (actual_checksum, expected_checksum)))

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

        if not (OptaaStateKey.POSITION in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         OptaaStateKey.POSITION)

        if not (OptaaStateKey.METADATA_GENERATED in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         OptaaStateKey.METADATA_GENERATED)

        if not (OptaaStateKey.TIME_SINCE_POWER_UP in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         OptaaStateKey.TIME_SINCE_POWER_UP)

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        self.input_file.seek(state_obj[OptaaStateKey.POSITION])

    def sieve_function(self, input_buffer):
        """
        Look through the input buffer to see if there is a complete optaa_dj record.
        A complete record is defined as:
          0xFF00FF00 which marks the start of the packet
          2 byte length field
          correct number of bytes based on the length field
        """
        indices_list = []       # initialize the return list to empty
        start_index = 0
        while start_index < len(input_buffer):

            # Search for the start of a packet.

            length_found = False
            while not length_found and start_index < len(input_buffer):
                length_match = LENGTH_MATCHER.match(input_buffer[start_index : ])

                if length_match is not None:
                    length_found = True
                else:
                    start_index += 1

            if length_found:

                # Extract the packet length.
                # This is the number of bytes in the packet except for
                # the checksum and trailing pad byte.

                packet_length = struct.unpack('>H',
                    length_match.group(GROUP_PACKET_LENGTH))[0]

                # Calculate the end of packet.

                end_index = start_index + packet_length + SIZE_CHECKSUM + SIZE_PAD

                # If the input buffer has enough bytes for the entire packet,
                # add the start,end pair to the list of indices.
                # If not enough room, we're done for now.

                if end_index <= len(input_buffer):
                    indices_list.append((start_index, end_index))
                    start_index = end_index
                else:
                    break

        return indices_list
    

class OptaaDjDclRecoveredParser(OptaaDjDclParser):
    """
    This is the entry point for the Recovered Optaa_dj_dcl parser.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 filename,
                 *args, **kwargs):

        super(OptaaDjDclRecoveredParser, self).__init__(config,
                                         stream_handle,
                                         state,
                                         state_callback,
                                         publish_callback,
                                         exception_callback,
                                         filename,
                                         OptaaDjDclRecoveredInstrumentDataParticle,
                                         OptaaDjDclRecoveredMetadataDataParticle,
                                         *args,
                                         **kwargs)


class OptaaDjDclTelemeteredParser(OptaaDjDclParser):
    """
    This is the entry point for the Telemetered Optaa_dj_dcl parser.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 filename,
                 *args, **kwargs):

        super(OptaaDjDclTelemeteredParser, self).__init__(config,
                                           stream_handle,
                                           state,
                                           state_callback,
                                           publish_callback,
                                           exception_callback,
                                           filename,
                                           OptaaDjDclTelemeteredInstrumentDataParticle,
                                           OptaaDjDclTelemeteredMetadataDataParticle,
                                           *args,
                                           **kwargs)
