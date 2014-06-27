#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdmo 
@file mi/dataset/parser/ctdmo.py
@author Emily Hahn (original telemetered), Steve Myerson (recovered)
@brief A CTDMO-specific data set agent parser

This file contains code for the CTDMO parsers and to produce data particles.
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

import array
import binascii
import copy
import string
import re
import struct
import time
import ntplib
from dateutil import parser
from mi.core.log import get_logger ; log = get_logger()

from mi.dataset.dataset_parser import \
    Parser, \
    BufferLoadingParser

from mi.dataset.parser.sio_mule_common import \
    SioParser, \
    SioMuleParser, \
    SIO_HEADER_MATCHER, \
    SIO_HEADER_GROUP_ID, \
    SIO_HEADER_GROUP_DATA_LENGTH, \
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

# Recovered CT Data record (hex ascii):
REC_CT_RECORD_END = b'\x0D'             # records separated by a new line

REC_CT_REGEX = b'([0-9a-fA-F]{6})'      # Temperature
REC_CT_REGEX += b'([0-9a-fA-F]{6})'     # Conductivity
REC_CT_REGEX += b'([0-9a-fA-F]{6})'     # Pressure
REC_CT_REGEX += b'([0-9a-fA-F]{4})'     # Pressure Temperature
REC_CT_REGEX += b'([0-9a-fA-F]{8})'     # Time since Jan 1, 2000
REC_CT_REGEX += REC_CT_RECORD_END       # CT Record separator

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

# Indices into raw_data tuples
RAW_INDEX_TEL_CT_SIO_TIMESTAMP = 0
RAW_INDEX_TEL_CT_ID = 1
RAW_INDEX_TEL_CT_SCIENCE = 2
RAW_INDEX_TEL_CT_TIME = 3

RAW_INDEX_REC_CT_SIO_TIMESTAMP = 0

RAW_INDEX_CO_SIO_TIMESTAMP = 0
RAW_INDEX_CO_ID = 1
RAW_INDEX_CO_TIME_OFFSET = 2


def convert_hex_ascii_to_int(int_val):
    """
    Use to convert from hex-ascii to int when encoding data particle values
    """
    return int(int_val, 16)


class CtdmoStateKey(BaseEnum):
    INDUCTIVE_ID = 'inductive_id'     # required for recovered and telemetered
    SERIAL_NUMBER = 'serial_number'   # required for recovered data only


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


class CtdmoInstrumentDataParticle(DataParticle):
    """
    Class for parsing data from the CTDMO instrument on a MSFM platform node.
    """

    def generate_particle_timestamp(self, time_2000):
        """
        This function calculates and returns a timestamp in epoch 1970
        based on a time in epoch 2000.
        Parameter:
          time_2000 - number of seconds since Jan 1, 2000
        Returns:
          number of seconds since Jan 1, 1970
        """
        gmt_dt_2000 = parser.parse("2000-01-01T00:00:00.00Z")
        elapse_2000 = float(gmt_dt_2000.strftime("%s.%f"))

        # convert from epoch in 2000 to epoch in 1970, GMT
        sec_since_1970 = int(time_2000, 16) + elapse_2000 - time.timezone

        return sec_since_1970


class CtdmoRecoveredInstrumentDataParticle(CtdmoInstrumentDataParticle):
    """
    Class for generating Instrument Data Particles from Recovered data.
    """
    _data_particle_type = DataParticleType.REC_CT_PARTICLE


class CtdmoTelemeteredInstrumentDataParticle(CtdmoInstrumentDataParticle):
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
                                port_timestamp=None,
                                internal_timestamp=None,
                                preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                                quality_flag=DataParticleValue.OK,
                                new_sequence=None)

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

        # convert from epoch in 2000 to epoch in 1970, GMT
        sec_since_1970 = self.generate_particle_timestamp(reversed_hex_time)

        self.set_internal_timestamp(unix_time=sec_since_1970)


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
                                                      port_timestamp=None,
                                                      internal_timestamp=None,
                                                      preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                                                      quality_flag=DataParticleValue.OK,
                                                      new_sequence=None)

        #
        # The particle timestamp for CO data is the SIO header timestamp.
        #
        timestamp = convert_hex_ascii_to_int(self.raw_data[RAW_INDEX_CO_SIO_TIMESTAMP])
        self.set_internal_timestamp(unix_time=timestamp)

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
        @param inductive ID to compare
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
        last_chunk_idx = len(chunk)
        start_chunk_idx = 0

        while start_chunk_idx < last_chunk_idx:
            #
            # Look for a match in the next group of bytes
            #
            co_match = CO_MATCHER.match(
                chunk[start_chunk_idx : start_chunk_idx+CO_SAMPLE_BYTES])

            if co_match:
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
                    if sample:
                        #
                        # Add this particle to the list of particles generated
                        # so far for this chunk of input data.
                        #
                        particles.append(sample)
                        sample_count += 1

                start_chunk_idx += CO_SAMPLE_BYTES
            #
            # If there wasn't a match, the input data is messed up.
            #
            else:
                log.error('unknown data found in CO chunk %s at %d, leaving out the rest',
                    binascii.b2a_hex(chunk), start_chunk_idx)
                self._exception_callback(SampleException(
                    'unknown data found in CO chunk at %d, leaving out the rest' % chunk_idx))
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
        # if non-data is expected, handle it here, otherwise it is an error
        if non_data is not None and non_end <= start:
            # if this non-data is an error, send an UnexpectedDataException and increment the state
            self._increment_position(len(non_data))
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" % (len(non_data), non_data)))

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
            self._increment_position(len(chunk))

            header_match = SIO_HEADER_MATCHER.match(chunk)
            header_timestamp = header_match.group(SIO_HEADER_GROUP_TIMESTAMP)

            #
            # Start processing at the end of the header.
            #
            chunk_idx = header_match.end(0)

            if header_match.group(SIO_HEADER_GROUP_ID) == ID_OFFSET:
                #log.debug("matched recovered CO header %s", chunk[1:chunk_idx - 1])
                (samples, particles) = self.parse_co_data(
                    CtdmoRecoveredOffsetDataParticle,
                    chunk[chunk_idx : -1], header_timestamp)

                if samples > 0:
                    for x in range(0, samples):
                        result_particles.append((particles[x],
                                                 copy.copy(self._read_state)))

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

        super(CtdmoRecoveredCtParser, self).__init__(config,
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

        if not CtdmoStateKey.SERIAL_NUMBER in config:
            raise DatasetParserException("Parser config is missing %s"
                                         % CtdmoStateKey.SERIAL_NUMBER)


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
                (samples, particles) = self.parse_ct_record(
                    CtdmoTelemeteredInstrumentDataParticle,
                    chunk[chunk_idx : -1], header_timestamp)

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

    def parse_ct_record(self, particle_class, chunk, sio_header_timestamp):
        """
        This function parses a Telemetered CT record and
        returns the number of particles found and a list of data particles.
        Parameters:
          particle class - class name of particle to be produced
          chunk - the input which is being parsed
          sio_header_timestamp - required for particle, passed through
        """
        particles = []
        sample_count = 0
        last_chunk_idx = len(chunk)
        start_chunk_idx = 0

        while start_chunk_idx < last_chunk_idx:
            #
            # Look for a match in the next group of bytes
            #
            ct_match = TEL_CT_MATCHER.match(
                chunk[start_chunk_idx : start_chunk_idx+TEL_CT_SAMPLE_BYTES])

            if ct_match:
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
                    sample = self._extract_sample(particle_class, None,
                        (sio_header_timestamp,
                            inductive_id,
                            ct_match.group(TEL_CT_GROUP_SCIENCE_DATA),
                            ct_match.group(TEL_CT_GROUP_TIME)),
                        None)
                    if sample:
                        #
                        # Add this particle to the list of particles generated
                        # so far for this chunk of input data.
                        #
                        particles.append(sample)
                        sample_count += 1

                start_chunk_idx += TEL_CT_SAMPLE_BYTES

            #
            # If there wasn't a match, the input data is messed up.
            #
            else:
                log.error('unknown data found in CT chunk %s at %d, leaving out the rest',
                    binascii.b2a_hex(chunk), start_chunk_idx)
                self._exception_callback(SampleException(
                    'unknown data found in CT chunk at %d, leaving out the rest' % chunk_idx))
                break

        #
        # Once we reach the end of the input data,
        # return the number of particles generated and the list of particles.
        #
        return sample_count, particles
