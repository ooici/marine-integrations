#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdmo 
@file mi/dataset/parser/ctdmo.py
@author Emily Hahn (original telemetered), Steve Myerson (recovered)
@brief A CTDMO-specific data set agent parser

This file contains code for the CTDMO parsers and code to produce data particles.
For telemetered data, there is one parser which produces two data particles.
For recovered data, there are two parsers, with each parser producing one data particle.

There are two types of CTDMO data.
CT, aka instrument, sensor or science data.
CO, aka offset data.

For telemetered data, both types (CT, CO) of data are in SIO Mule files.
For recovered data, the CT data is stored in a separate file.
Additionally, both CT and CO data are stored in another file (SIO Controller file),
but only the CO data in the SIO Controller file is processed here,
with the CT data being ignored.
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import binascii
import copy
from functools import partial
import re
import struct

from mi.core.time import string_to_ntp_date_time

from mi.core.instrument.chunker import \
    StringChunker

from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_parser import \
    Parser, \
    BufferLoadingParser

from mi.dataset.parser.sio_mule_common import \
    SioParser, \
    SioMuleParser, \
    SIO_HEADER_MATCHER, \
    SIO_HEADER_GROUP_ID, \
    SIO_HEADER_GROUP_TIMESTAMP

from mi.core.common import BaseEnum
from mi.core.exceptions import \
    DatasetParserException, \
    RecoverableSampleException, \
    SampleException, \
    UnexpectedDataException

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue

ID_INSTRUMENT = 'CT'    # ID for instrument (science) data
ID_OFFSET = 'CO'        # ID for time offset data

# Recovered CT file format (file is ASCII, lines separated by new line):
#   Several lines of unformatted ASCII text and key value pairs (ignored here)
#   Configuration information in XML format (only serial number is of interest)
#   *END* record (IDD says *end* so we'll check for either)
#   Instrument data in HEX ASCII (need to extract these values)

NEW_LINE = r'[\n\r]+'             # Handle any type of new line

REC_CT_RECORD = r'.*'             # Any number of ASCII characters
REC_CT_RECORD += NEW_LINE         # separated by a new line
REC_CT_RECORD_MATCHER = re.compile(REC_CT_RECORD)

# For Recovered CT files, the serial number is in the Configuration XML section.
REC_CT_SERIAL_REGEX = r'^'        # At the beginning of the record
REC_CT_SERIAL_REGEX += r'\* <HardwareData DeviceType=\'SBE37-IM\' SerialNumber=\''
REC_CT_SERIAL_REGEX += r'(\d+)'   # Serial number is any number of digits
REC_CT_SERIAL_REGEX += r'\'>'     # the rest of the XML syntax
REC_CT_SERIAL_MATCHER = re.compile(REC_CT_SERIAL_REGEX)

# The REC_CT_SERIAL_MATCHER produces the following group:
REC_CT_SERIAL_GROUP_SERIAL_NUMBER = 1

# The end of the Configuration XML section is denoted by a *END* record.
REC_CT_CONFIGURATION_END = r'^'                    # At the beginning of the record
REC_CT_CONFIGURATION_END += r'\*END\*'             # *END*
REC_CT_CONFIGURATION_END += NEW_LINE               # separated by a new line
REC_CT_CONFIGURATION_END_MATCHER = re.compile(REC_CT_CONFIGURATION_END)

# Recovered CT Data record (hex ascii):
REC_CT_SAMPLE_BYTES = 31                # includes record separator

REC_CT_REGEX = b'([0-9a-fA-F]{6})'      # Temperature
REC_CT_REGEX += b'([0-9a-fA-F]{6})'     # Conductivity
REC_CT_REGEX += b'([0-9a-fA-F]{6})'     # Pressure
REC_CT_REGEX += b'([0-9a-fA-F]{4})'     # Pressure Temperature
REC_CT_REGEX += b'([0-9a-fA-F]{8})'     # Time since Jan 1, 2000
REC_CT_REGEX += NEW_LINE                # separated by a new line
REC_CT_MATCHER = re.compile(REC_CT_REGEX)

# The REC_CT_MATCHER produces the following groups:
REC_CT_GROUP_TEMPERATURE = 1
REC_CT_GROUP_CONDUCTIVITY = 2
REC_CT_GROUP_PRESSURE = 3
REC_CT_GROUP_PRESSURE_TEMP = 4
REC_CT_GROUP_TIME = 5

# Telemetered CT Data record (binary):
TEL_CT_RECORD_END = b'\x0D'           # records separated by a new line
TEL_CT_SAMPLE_BYTES = 13              # includes record separator

TEL_CT_REGEX = b'([\x00-\xFF])'       # Inductive ID
TEL_CT_REGEX += b'([\x00-\xFF]{7})'   # Temperature, Conductivity, Pressure (reversed)
TEL_CT_REGEX += b'([\x00-\xFF]{4})'   # Time since Jan 1, 2000 (bytes reversed)
TEL_CT_REGEX += TEL_CT_RECORD_END     # CT Record separator
TEL_CT_MATCHER = re.compile(TEL_CT_REGEX)

# The TEL_CT_MATCHER produces the following groups:
TEL_CT_GROUP_ID = 1
TEL_CT_GROUP_SCIENCE_DATA = 2
TEL_CT_GROUP_TIME = 3

# Recovered and Telemetered CO Data record (binary):
CO_RECORD_END = b'[\x13|\x0D]'     # records separated by sentinel 0x13 or 0x0D
CO_SAMPLE_BYTES = 6

CO_REGEX = b'([\x00-\xFF])'        # Inductive ID
CO_REGEX += b'([\x00-\xFF]{4})'    # Time offset in seconds
CO_REGEX += CO_RECORD_END          # CO Record separator
CO_MATCHER = re.compile(CO_REGEX)

# The CO_MATCHER produces the following groups:
CO_GROUP_ID = 1
CO_GROUP_TIME_OFFSET = 2

# Indices into raw_data tuples for recovered CT data
RAW_INDEX_REC_CT_ID = 0
RAW_INDEX_REC_CT_SERIAL = 1
RAW_INDEX_REC_CT_TEMPERATURE = 2
RAW_INDEX_REC_CT_CONDUCTIVITY = 3
RAW_INDEX_REC_CT_PRESSURE = 4
RAW_INDEX_REC_CT_PRESSURE_TEMP = 5
RAW_INDEX_REC_CT_TIME = 6

# Indices into raw_data tuples for telemetered CT data
RAW_INDEX_TEL_CT_SIO_TIMESTAMP = 0
RAW_INDEX_TEL_CT_ID = 1
RAW_INDEX_TEL_CT_SCIENCE = 2
RAW_INDEX_TEL_CT_TIME = 3

# Indices into raw_data tuples for recovered and telemetered CO data
RAW_INDEX_CO_SIO_TIMESTAMP = 0
RAW_INDEX_CO_ID = 1
RAW_INDEX_CO_TIME_OFFSET = 2


def convert_hex_ascii_to_int(int_val):
    """
    Use to convert from hex-ascii to int when encoding data particle values
    """
    return int(int_val, 16)

def generate_particle_timestamp(time_2000):
    """
    This function calculates and returns a timestamp in epoch 1900
    based on an ASCII hex time in epoch 2000.
    Parameter:
      time_2000 - number of seconds since Jan 1, 2000
    Returns:
      number of seconds since Jan 1, 1900
    """
    return int(time_2000, 16) + string_to_ntp_date_time("2000-01-01T00:00:00.00Z")


class CtdmoStateKey(BaseEnum):
    INDUCTIVE_ID = 'inductive_id'     # required for recovered and telemetered

    END_CONFIG = 'end_config'         # required for recovered CT parser only
    POSITION = 'position'             # required for recovered CT parser only
    SERIAL_NUMBER = 'serial_number'   # required for recovered CT parser only


class DataParticleType(BaseEnum):
    REC_CO_PARTICLE = 'ctdmo_ghqr_offset_recovered'
    REC_CT_PARTICLE = 'ctdmo_ghqr_instrument_recovered'
    TEL_CO_PARTICLE = 'ctdmo_ghqr_sio_offset'
    TEL_CT_PARTICLE = 'ctdmo_ghqr_sio_mule_instrument'

    
class CtdmoInstrumentDataParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = "sio_controller_timestamp"
    INDUCTIVE_ID = "inductive_id"
    SERIAL_NUMBER = "instrument_serial_number_u32"
    TEMPERATURE = "temperature"
    CONDUCTIVITY = "conductivity"
    PRESSURE = "pressure"
    PRESSURE_TEMP = "pressure_temp"
    CTD_TIME = "ctd_time"


class CtdmoRecoveredInstrumentDataParticle(DataParticle):
    """
    Class for generating Instrument Data Particles from Recovered data.
    """
    _data_particle_type = DataParticleType.REC_CT_PARTICLE

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        super(CtdmoRecoveredInstrumentDataParticle, self).__init__(raw_data,
                                port_timestamp,
                                internal_timestamp,
                                preferred_timestamp,
                                quality_flag,
                                new_sequence)

        #
        # The particle timestamp is the time contained in the CT instrument data.
        # This time field is number of seconds since Jan 1, 2000.
        # Convert from epoch in 2000 to epoch in 1900.
        #
        time_stamp = generate_particle_timestamp(self.raw_data[RAW_INDEX_REC_CT_TIME])
        self.set_internal_timestamp(timestamp=time_stamp)

    def _build_parsed_values(self):
        """
        Build parsed values for Telemetered Recovered Data Particle.
        Take something in the hex ASCII data values and turn it into a
        particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        #
        # Raw data for this particle consists of the following fields (hex ASCII
        # unless noted otherwise):
        #   inductive ID (hex)
        #   serial number (hex)
        #   temperature
        #   conductivity
        #   pressure
        #   pressure temperature
        #   time of science data
        #
        particle = [
            self._encode_value(CtdmoInstrumentDataParticleKey.INDUCTIVE_ID,
                               self.raw_data[RAW_INDEX_REC_CT_ID], int),
            self._encode_value(CtdmoInstrumentDataParticleKey.SERIAL_NUMBER,
                               self.raw_data[RAW_INDEX_REC_CT_SERIAL], int),
            self._encode_value(CtdmoInstrumentDataParticleKey.TEMPERATURE,
                               self.raw_data[RAW_INDEX_REC_CT_TEMPERATURE],
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoInstrumentDataParticleKey.CONDUCTIVITY,
                               self.raw_data[RAW_INDEX_REC_CT_CONDUCTIVITY],
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoInstrumentDataParticleKey.PRESSURE,
                               self.raw_data[RAW_INDEX_REC_CT_PRESSURE],
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoInstrumentDataParticleKey.PRESSURE_TEMP,
                               self.raw_data[RAW_INDEX_REC_CT_PRESSURE_TEMP],
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoInstrumentDataParticleKey.CTD_TIME,
                               self.raw_data[RAW_INDEX_REC_CT_TIME],
                               convert_hex_ascii_to_int)
        ]

        return particle


class CtdmoTelemeteredInstrumentDataParticle(DataParticle):
    """
    Class for generating Instrument Data Particles from Telemetered data.
    """
    _data_particle_type = DataParticleType.TEL_CT_PARTICLE

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        super(CtdmoTelemeteredInstrumentDataParticle, self).__init__(raw_data,
                                port_timestamp,
                                internal_timestamp,
                                preferred_timestamp,
                                quality_flag,
                                new_sequence)

        #
        # The particle timestamp is the time contained in the science data
        # (as opposed to the timestamp in the SIO header).
        # Extract the time field and convert from binary to ascii on a
        # byte by byte basis.
        #
        hex_time = binascii.b2a_hex(self.raw_data[RAW_INDEX_TEL_CT_TIME])

        #
        # The input Time field for telemetered CT data has bytes in reverse order.
        #
        reversed_hex_time = hex_time[6:8] + hex_time[4:6] + \
            hex_time[2:4] + hex_time[0:2]

        # convert from epoch in 2000 to epoch in 1900.
        time_stamp = generate_particle_timestamp(reversed_hex_time)
        self.set_internal_timestamp(timestamp=time_stamp)

    def _build_parsed_values(self):
        """
        Build parsed values for Telemetered Instrument Data Particle.
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        try:
            #
            # Convert binary science data to hex ascii string.
            # 7 binary bytes get turned into 14 hex ascii bytes.
            # The 2 byte pressure field is in reverse byte order.
            #
            science_data = binascii.b2a_hex(
                self.raw_data[RAW_INDEX_TEL_CT_SCIENCE])
            pressure = science_data[12:14] + science_data[10:12]

            #
            # Convert science data time to hex ascii.
            # The 4 byte time field is in reverse byte order.
            #
            hex_time = binascii.b2a_hex(self.raw_data[RAW_INDEX_TEL_CT_TIME])
            reversed_hex_time = hex_time[6:8] + hex_time[4:6] + \
                hex_time[2:4] + hex_time[0:2]

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Error (%s) while decoding parameters in data: [%s]", ex, self.raw_data)
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        particle = [
            self._encode_value(CtdmoInstrumentDataParticleKey.CONTROLLER_TIMESTAMP,
                               self.raw_data[RAW_INDEX_TEL_CT_SIO_TIMESTAMP],
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoInstrumentDataParticleKey.INDUCTIVE_ID,
                               struct.unpack('>B',
                                   self.raw_data[RAW_INDEX_TEL_CT_ID])[0],
                               int),
            self._encode_value(CtdmoInstrumentDataParticleKey.TEMPERATURE,
                               science_data[0:5],
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoInstrumentDataParticleKey.CONDUCTIVITY,
                               science_data[5:10],
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoInstrumentDataParticleKey.PRESSURE,
                               pressure,
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoInstrumentDataParticleKey.CTD_TIME,
                               reversed_hex_time,
                               convert_hex_ascii_to_int)
        ]

        return particle


class CtdmoOffsetDataParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = "sio_controller_timestamp"
    INDUCTIVE_ID = "inductive_id"
    CTD_OFFSET = "ctd_time_offset"


class CtdmoOffsetDataParticle(DataParticle):
    """
    Class for generating the Offset Data Particle from the CTDMO instrument
    on a MSFM platform node
    """

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        super(CtdmoOffsetDataParticle, self).__init__(raw_data,
                                                      port_timestamp,
                                                      internal_timestamp,
                                                      preferred_timestamp,
                                                      quality_flag,
                                                      new_sequence)

        #
        # The particle timestamp for CO data is the SIO header timestamp.
        #
        time_stamp = convert_hex_ascii_to_int(self.raw_data[RAW_INDEX_CO_SIO_TIMESTAMP])
        self.set_internal_timestamp(unix_time=time_stamp)

    def _build_parsed_values(self):
        """
        Build parsed values for Recovered and Telemetered Offset Data Particle.
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """

        particle = [
            self._encode_value(CtdmoOffsetDataParticleKey.CONTROLLER_TIMESTAMP,
                               self.raw_data[RAW_INDEX_CO_SIO_TIMESTAMP],
                               convert_hex_ascii_to_int),
            self._encode_value(CtdmoOffsetDataParticleKey.INDUCTIVE_ID,
                               struct.unpack('>B', self.raw_data[RAW_INDEX_CO_ID])[0],
                               int),
            self._encode_value(CtdmoOffsetDataParticleKey.CTD_OFFSET,
                               struct.unpack('>i',
                                   self.raw_data[RAW_INDEX_CO_TIME_OFFSET])[0],
                               int)
        ]

        return particle


class CtdmoRecoveredOffsetDataParticle(CtdmoOffsetDataParticle):
    """
    Class for generating Offset Data Particles from Recovered data.
    """
    _data_particle_type = DataParticleType.REC_CO_PARTICLE


class CtdmoTelemeteredOffsetDataParticle(CtdmoOffsetDataParticle):
    """
    Class for generating Offset Data Particles from Telemetered data.
    """
    _data_particle_type = DataParticleType.TEL_CO_PARTICLE


class CtdmoParser(Parser):

    def compare_inductive_id(self, inductive_id):
        """
        Compare the inductive id from the data with the configured inductive ID
        @param inductive_id to compare
        @returns True if IDs match, False if they don't
        """
        return inductive_id == self._config.get(CtdmoStateKey.INDUCTIVE_ID)

    def parse_co_data(self, particle_class, chunk, sio_header_timestamp):
        """
        This function parses a CO record and returns a list of samples.
        The CO input record is the same for both recovered and telemetered data.
        """
        particles = []
        sample_count = 0
        last_index = len(chunk)
        start_index = 0

        while start_index < last_index:
            #
            # Look for a match in the next group of bytes
            #
            co_match = CO_MATCHER.match(
                chunk[start_index : start_index+CO_SAMPLE_BYTES])

            if co_match is not None:
                #
                # If the inductive ID is the one we're looking for,
                # generate a data particle.
                # The ID needs to be converted from a byte string to an integer
                # for the comparison.
                #
                inductive_id = co_match.group(CO_GROUP_ID)
                if self.compare_inductive_id(struct.unpack('>B', inductive_id)[0]):
                    #
                    # Generate the data particle.
                    # Data stored for each particle is a tuple of the following:
                    #   SIO header timestamp (input parameter)
                    #   inductive ID (from chunk)
                    #   Time Offset (from chunk)
                    #
                    sample = self._extract_sample(particle_class, None,
                        (sio_header_timestamp, inductive_id,
                            co_match.group(CO_GROUP_TIME_OFFSET)),
                        None)
                    if sample is not None:
                        #
                        # Add this particle to the list of particles generated
                        # so far for this chunk of input data.
                        #
                        particles.append(sample)
                        sample_count += 1

                start_index += CO_SAMPLE_BYTES
            #
            # If there wasn't a match, the input data is messed up.
            #
            else:
                log.error('unknown data found in CO chunk %s at %d, leaving out the rest',
                    binascii.b2a_hex(chunk), start_index)
                self._exception_callback(SampleException(
                    'unknown data found in CO chunk at %d, leaving out the rest' % start_index))
                break

        #
        # Once we reach the end of the input data,
        # return the number of particles generated and the list of particles.
        #
        return sample_count, particles


class CtdmoRecoveredCoParser(SioParser, CtdmoParser):

    """
    Parser for Ctdmo recovered CO data.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        super(CtdmoRecoveredCoParser, self).__init__(config,
                                                     stream_handle,
                                                     state,
                                                     self.sieve_function,
                                                     state_callback,
                                                     publish_callback,
                                                     exception_callback,
                                                     *args,
                                                     **kwargs)

        #
        # Verify that the required parameters are in the parser configuration.
        #
        if not CtdmoStateKey.INDUCTIVE_ID in config:
            raise DatasetParserException("Parser config is missing %s"
                                         % CtdmoStateKey.INDUCTIVE_ID)

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # Handle non-data here.
        if non_data is not None and non_end <= start:
            # send an UnexpectedDataException and increment the state
            self._increment_state(len(non_data))
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" %
                (len(non_data), binascii.b2a_hex(non_data))))

    def parse_chunks(self):
        """
        Parse chunks for the Recovered CO parser.
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        self.handle_non_data(non_data, non_end, start)

        while chunk is not None:
            header_match = SIO_HEADER_MATCHER.match(chunk)
            header_timestamp = header_match.group(SIO_HEADER_GROUP_TIMESTAMP)

            #
            # Start processing at the end of the header.
            #
            chunk_idx = header_match.end(0)

            if header_match.group(SIO_HEADER_GROUP_ID) == ID_OFFSET:
                (samples, particles) = self.parse_co_data(
                    CtdmoRecoveredOffsetDataParticle,
                    chunk[chunk_idx : -1], header_timestamp)

                for x in range(0, samples):
                    result_particles.append(particles[x])

            else:
                samples = 0

            # keep track of how many samples were found in this chunk
            self._chunk_sample_count.append(samples)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            self.handle_non_data(non_data, non_end, start)

        return result_particles


class CtdmoRecoveredCtParser(BufferLoadingParser, CtdmoParser):

    """
    Parser for Ctdmo recovered CT data.
    """
    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        #
        # Verify that the required parameters are in the parser configuration.
        #
        if not CtdmoStateKey.INDUCTIVE_ID in config:
            raise DatasetParserException("Parser config is missing %s"
                                         % CtdmoStateKey.INDUCTIVE_ID)

        #
        # No fancy sieve function needed for this parser.
        # File is ASCII with records separated by newlines.
        #
        super(CtdmoRecoveredCtParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          partial(StringChunker.regex_sieve_function,
                                                  regex_list=[REC_CT_RECORD_MATCHER]),
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)

        #
        # Default the position within the file to the beginning
        # and set flags to indicate the end of Configuration has not been reached
        # and the serial number has not been found.
        #
        self._read_state = {
            CtdmoStateKey.POSITION: 0,
            CtdmoStateKey.END_CONFIG: False,
            CtdmoStateKey.SERIAL_NUMBER: None
        }
        self.input_file = stream_handle

        if state is not None:
            self.set_state(state)

    def check_for_config_end(self, chunk):
        """
        This function searches the input buffer for the end of Configuration record.
        If found, the read_state and state are updated.
        """
        match = REC_CT_CONFIGURATION_END_MATCHER.match(chunk)
        if match is not None:
            self._read_state[CtdmoStateKey.END_CONFIG] = True

    def check_for_serial_number(self, chunk):
        """
        This function searches the input buffer for a serial number.
        If found, the read_state and state are updated.
        """
        #
        # See if this record the serial number.
        # If found, convert from decimal ASCII and save in the state.
        #
        match = REC_CT_SERIAL_MATCHER.match(chunk)
        if match is not None:
            self._read_state[CtdmoStateKey.SERIAL_NUMBER] = \
                int(match.group(REC_CT_SERIAL_GROUP_SERIAL_NUMBER))

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # Handle non-data here.
        if non_data is not None and non_end <= start:
            # increment the state
            self._increment_position(len(non_data))
            # use the _exception_callback
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" %
                (len(non_data), binascii.b2a_hex(non_data))))

    def _increment_position(self, bytes_read):
        """
        Increment the parser position
        @param bytes_read The number of bytes just read
        """
        self._read_state[CtdmoStateKey.POSITION] += bytes_read

    def parse_chunks(self):
        """
        Parse chunks for the Recovered CT parser.
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        #
        # The first data item to be obtained is the serial number.
        # Once the serial number is received, we look for the end of XML record.
        # Following the end of XML record are the CT data records.
        #
        while chunk is not None:
            self._increment_position(len(chunk))

            #
            # Search for serial number if not already found.
            #
            if self._read_state[CtdmoStateKey.SERIAL_NUMBER] is None:
                self.check_for_serial_number(chunk)

            #
            # Once the serial number is found,
            # search for the end of the Configuration section.
            #
            elif not self._read_state[CtdmoStateKey.END_CONFIG]:
                self.check_for_config_end(chunk)

            #
            # Once the end of the configuration is reached, all remaining records
            # are supposedly CT data records.
            # Parse the record and generate the particle for this chunk.
            # Add it to the return list of particles.
            #
            else:
                particle = self.parse_ct_record(chunk)
                if particle is not None:
                    result_particles.append((particle, copy.copy(self._read_state)))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def parse_ct_record(self, ct_record):
        """
        This function parses a Recovered CT record and returns a data particle.
        Parameters:
          ct_record - the input which is being parsed
        """
        ct_match = REC_CT_MATCHER.match(ct_record)
        if ct_match is not None:
            #
            # If this is CT record, generate the data particle.
            # Data stored for each particle is a tuple of the following:
            #   inductive ID (obtained from configuration data)
            #   serial number
            #   temperature
            #   conductivity
            #   pressure
            #   pressure temperature
            #   time of science data
            #
            sample = self._extract_sample(CtdmoRecoveredInstrumentDataParticle,
                None,
                (self._config.get(CtdmoStateKey.INDUCTIVE_ID),
                    self._read_state[CtdmoStateKey.SERIAL_NUMBER],
                    ct_match.group(REC_CT_GROUP_TEMPERATURE),
                    ct_match.group(REC_CT_GROUP_CONDUCTIVITY),
                    ct_match.group(REC_CT_GROUP_PRESSURE),
                    ct_match.group(REC_CT_GROUP_PRESSURE_TEMP),
                    ct_match.group(REC_CT_GROUP_TIME)),
                None)

        #
        # If there wasn't a match, the input data is messed up.
        #
        else:
            error_message = 'unknown data found in CT chunk %s, leaving out the rest of chunk' \
                            % binascii.b2a_hex(ct_record)
            log.error(error_message)
            self._exception_callback(SampleException(error_message))
            sample = None

        return sample

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to.
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")

        if not (CtdmoStateKey.POSITION in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         CtdmoStateKey.POSITION)

        if not (CtdmoStateKey.END_CONFIG in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         CtdmoStateKey.END_CONFIG)

        if not (CtdmoStateKey.SERIAL_NUMBER in state_obj):
            raise DatasetParserException('%s missing in state keys' %
                                         CtdmoStateKey.SERIAL_NUMBER)

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        self.input_file.seek(state_obj[CtdmoStateKey.POSITION])


class CtdmoTelemeteredParser(SioMuleParser, CtdmoParser):
    """
    Parser for Ctdmo telemetered data (SIO Mule).
    This parser handles both CT and CO data from the SIO Mule.
    """

    def __init__(self,
                 config,
                 stream_handle,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):

        super(CtdmoTelemeteredParser, self).__init__(config,
                                                     stream_handle,
                                                     state,
                                                     self.sieve_function,
                                                     state_callback,
                                                     publish_callback,
                                                     exception_callback,
                                                     *args,
                                                     **kwargs)

        if not CtdmoStateKey.INDUCTIVE_ID in config:
            raise DatasetParserException("Parser config is missing %s"
                                         % CtdmoStateKey.INDUCTIVE_ID)

    def parse_chunks(self):
        """
        Parse chunks for the Telemetered parser.
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle.
        Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        while chunk is not None:
            header_match = SIO_HEADER_MATCHER.match(chunk)
            header_timestamp = header_match.group(SIO_HEADER_GROUP_TIMESTAMP)

            # start looping at the end of the header
            chunk_idx = header_match.end(0)

            samples = 0
            if header_match.group(SIO_HEADER_GROUP_ID) == ID_INSTRUMENT:
                #
                # Parse the CT record, up to but not including the end of SIO block.
                #
                (samples, particles) = self.parse_ct_record(chunk[chunk_idx : -1],
                                                            header_timestamp)

                if samples > 0:
                    for x in range(0, samples):
                        result_particles.append(particles[x])

            elif header_match.group(SIO_HEADER_GROUP_ID) == ID_OFFSET:
                (samples, particles) = self.parse_co_data(
                    CtdmoTelemeteredOffsetDataParticle,
                    chunk[chunk_idx : -1], header_timestamp)
                
                if samples > 0:
                    for x in range(0, samples):
                        result_particles.append(particles[x])

            # keep track of how many samples were found in this chunk
            self._chunk_sample_count.append(samples)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        return result_particles

    def parse_ct_record(self, ct_record, sio_header_timestamp):
        """
        This function parses a Telemetered CT record and
        returns the number of particles found and a list of data particles.
        Parameters:
          chunk - the input which is being parsed
          sio_header_timestamp - required for particle, passed through
        """
        particles = []
        sample_count = 0
        last_index = len(ct_record)
        start_index = 0

        while start_index < last_index:
            #
            # Look for a match in the next group of bytes
            #
            ct_match = TEL_CT_MATCHER.match(
                ct_record[start_index : start_index+TEL_CT_SAMPLE_BYTES])

            if ct_match is not None:
                #
                # If the inductive ID is the one we're looking for,
                # generate a data particle.
                # The ID needs to be converted from a byte string to an integer
                # for the comparison.
                #
                inductive_id = ct_match.group(TEL_CT_GROUP_ID)
                if self.compare_inductive_id(struct.unpack('>B', inductive_id)[0]):
                    #
                    # Generate the data particle.
                    # Data stored for each particle is a tuple of the following:
                    #   SIO header timestamp (input parameter)
                    #   inductive ID
                    #   science data (temperature, conductivity, pressure)
                    #   time of science data
                    #
                    sample = self._extract_sample(
                        CtdmoTelemeteredInstrumentDataParticle,
                        None,
                        (sio_header_timestamp,
                            inductive_id,
                            ct_match.group(TEL_CT_GROUP_SCIENCE_DATA),
                            ct_match.group(TEL_CT_GROUP_TIME)),
                        None)
                    if sample is not None:
                        #
                        # Add this particle to the list of particles generated
                        # so far for this chunk of input data.
                        #
                        particles.append(sample)
                        sample_count += 1

                start_index += TEL_CT_SAMPLE_BYTES

            #
            # If there wasn't a match, the input data is messed up.
            #
            else:
                log.error('unknown data found in CT record %s at %d, leaving out the rest',
                    binascii.b2a_hex(ct_record), start_index)
                self._exception_callback(SampleException(
                    'unknown data found in CT record at %d, leaving out the rest' % start_index))
                break

        #
        # Once we reach the end of the input data,
        # return the number of particles generated and the list of particles.
        #
        return sample_count, particles
