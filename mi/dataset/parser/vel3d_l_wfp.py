#!/usr/bin/env python

"""
@package mi.dataset.parser.vel3d_l_wfp
@file marine-integrations/mi/dataset/parser/vel3d_l_wfp.py
@author Steve Myerson (Raytheon)
@brief Parser for the vel3d_l_wfp dataset driver"
This file contains classes for both the vel3d_l_wfp parser (recovered data)
and the vel3d_l_wfp_sio_mule parser (telemetered data wrapped in SIO blocks).
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import copy
import ntplib
#import re
import struct
import time

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import \
    DatasetParserException, \
    SampleException, \
    UnexpectedDataException

from mi.dataset.dataset_parser import \
    Parser, \
    BufferLoadingFilenameParser, \
    BufferLoadingParser
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER

ID_VEL3D_L_WFP_SIO_MULE = 'WA'    # The type of instrument for telemetered data

SIO_HEADER_GROUP_ID = 1           # Header group number for instrument ID
SIO_HEADER_GROUP_DATA_LENGTH = 2  # Header group number for data length
SIO_HEADER_GROUP_TIMESTAMP = 3    # Header group number for timestamp

#
# File format (this does not include the SIO header)
# Data bytes (4 bytes)
# FSI Header (279 bytes)
# FSI Record (47 bytes * N instances)
# Sensor start time (4 bytes)
# Sensor stop time (4 bytes)
# Decimation (2 bytes, optional)
#
DATA_BYTES_SIZE = 4            # byte in the Data bytes field
FSI_HEADER_SIZE = 279          # bytes in the FSI header
FSI_RECORD_SIZE = 47           # bytes in each FSI record

FSI_HEADER_SERIAL_NUMBER_OFFSET = 3    # byte offset into FSI Header
FSI_HEADER_SERIAL_NUMBER_SIZE = 4      # bytes in the serial number field

#
# FSI Record Format
# Offset  Bytes  Format   Field
#  0      1      uint8    hour
#  1      1      uint8    minute
#  2      1      uint8    second
#  3      1      uint8    month
#  4      1      uint8    day
#  5      2      uint16   year
#  7      4      float32  heading
# 11      4      float32  tx
# 15      4      float32  ty
# 19      4      float32  hx
# 23      4      float32  hy
# 27      4      float32  hz
# 31      4      float32  vp1
# 35      4      float32  vp2
# 39      4      float32  vp3
# 43      4      float32  vp4
#
FSI_RECORD_FORMAT = '<5BH10f'  # format for unpacking data from FSI records

#
# Keys to be used when generating particles.
# Instrument values are extracted from the FSI Record.
# Metadata values are extracted from the Time Record and the FSI Header.
# They are listed in order corresponding to the data record payload.
# Particles are the same for both recovered and telemetered data.
#
INDEX_PARTICLE_KEY = 0    # Index into the xxx_PARTICLE_KEYS tables
INDEX_VALUE_TYPE = 1      # Index into the xxx_PARTICLE_KEYS tables

INSTRUMENT_PARTICLE_KEYS = \
[
    ['vel3d_l_date_time_array', list],
    ['vel3d_l_heading',         float],
    ['vel3d_l_tx',              float],
    ['vel3d_l_ty',              float],
    ['vel3d_l_hx',              float],
    ['vel3d_l_hy',              float],
    ['vel3d_l_hz',              float],
    ['vel3d_l_vp1',             float],
    ['vel3d_l_vp2',             float],
    ['vel3d_l_vp3',             float],
    ['vel3d_l_vp4',             float]
]

METADATA_PARTICLE_KEYS = \
[
    ['vel3d_l_time_on',           int],
    ['vel3d_l_time_off',          int],
    ['vel3d_l_decimation_factor', int],
    ['vel3d_l_serial_number',     int],
    ['vel3d_l_number_of_records', int]
]
DATE_TIME_ARRAY = 'vel3d_l_date_time_array'  # This one needs to be special-cased
DATE_TIME_SIZE = 6                     # 6 bytes for the output date time field

DECIMATION_RECORD_SIZE = 10  # bytes in time fields plus decimation field
DECIMATION_FORMAT = '>2IH'   # 2 uint32, 1 uint16
TIME_RECORD_SIZE = 8         # bytes in time fields
TIME_FORMAT = '>2I'          # 2 uint32
FIELD_TIME_ON = 0
FIELD_TIME_OFF = 1
FIELD_DECIMATION = 2
FIELD_SERIAL_NUMBER = 3
FIELD_NUMBER_OF_RECORDS = 4
FIELD_METADATA_TIMESTAMP = 5

PARTICLE_TYPE_INSTRUMENT = 1
PARTICLE_TYPE_METADATA = 2


class Vel3dLWfpStateKey(BaseEnum):
    POSITION = 'position'  # holds the file position
    TIMESTAMP = 'timestamp'


class Vel3dLWfpDataParticleType(BaseEnum):
    INSTRUMENT_PARTICLE = 'vel3d_l_wfp_instrument'
    METADATA_PARTICLE = 'vel3d_l_wfp_metadata'


class Vel3dLWfpInstrumentParticle(DataParticle):
    """
    Class for generating vel3d_l_wfp instrument particles.
    """

    _data_particle_type = Vel3dLWfpDataParticleType.INSTRUMENT_PARTICLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        #
        # Generate an Instrument data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the data record.
        #
        particle = []
        field_index = 0
        fields = self.raw_data

        for x in range(0, len(INSTRUMENT_PARTICLE_KEYS)):
            key = INSTRUMENT_PARTICLE_KEYS[x][INDEX_PARTICLE_KEY]
            data_type = INSTRUMENT_PARTICLE_KEYS[x][INDEX_VALUE_TYPE]

            #
            # The date time array data must be special-cased since multiple
            # values from the parsed values are used for a single particle value.
            #
            if key == DATE_TIME_ARRAY:

                #
                # When generating the date time array field in the data particle,
                # use these same values to generate the timestamp for this particle.
                #
                hour = fields[field_index]
                minute = fields[field_index + 1]
                second = fields[field_index + 2]
                month = fields[field_index + 3]
                day = fields[field_index + 4]
                year = fields[field_index + 5]

                timestamp = (year, month, day, hour, minute, second, 0, 0, 0)
                elapsed_seconds = time.mktime(timestamp)
                ntp_time = ntplib.system_to_ntp_time(elapsed_seconds)
                self.set_internal_timestamp(timestamp=ntp_time)
                log.info("INST ntp_time %f", ntp_time)

                #
                # Generate the date time array to be stored in the particle.
                #
                date_time_array = [year, month, day, hour, minute, second]
                particle_value = self._encode_value(key, date_time_array, data_type)
                field_index += DATE_TIME_SIZE

            else:
                #
                # Other particle values are extracted directly from the
                # previously parsed fields.
                #
                particle_value = self._encode_value(key, fields[field_index], data_type)
                field_index += 1

            particle.append(particle_value)

        return particle


class Vel3dLWfpMetadataParticle(DataParticle):
    """
    Class for generating vel3d_l_wfp metadata particles.
    """

    _data_particle_type = Vel3dLWfpDataParticleType.METADATA_PARTICLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        #
        # Generate a Metadata data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the metadata record.
        #
        particle = []
        field_index = 0
        fields = self.raw_data

        #
        # The timestamp for the Metadata particle varies depending on whether
        # this is recovered or telemetered data.
        # This determination is made when the input file is parsed.
        #
        seconds = fields[FIELD_METADATA_TIMESTAMP]
        ntp_time = ntplib.system_to_ntp_time(seconds)
        self.set_internal_timestamp(timestamp=ntp_time)
        log.info("META ntp_time %f", ntp_time)

        #
        # Extract the metadata particle fields from the parsed values.
        #
        for x in range(0, len(METADATA_PARTICLE_KEYS)):
            key = METADATA_PARTICLE_KEYS[x][INDEX_PARTICLE_KEY]

            #
            # There is a bug in encode_value in the parent class.
            # If the value is 'None', encode_value chokes.
            # Apparently this bug is not important enough to fix in the parent class,
            # so it is incumbent on each child class to generate a work-around.
            #
            if fields[field_index] is None:
                particle.append({DataParticleKey.VALUE_ID: key,
                                 DataParticleKey.VALUE: None})
            else:
                particle_value = self._encode_value(key, fields[field_index],
                    METADATA_PARTICLE_KEYS[x][INDEX_VALUE_TYPE])
                particle.append(particle_value)
            field_index += 1

        return particle


class Vel3dLParser(Parser):
    """
    This class contains functions that are common to both the Vel3dLWfp and
    Vel3dLWfpSioMule parsers.
    """
    def generate_particles(self, fields):
        """
        Given a list of groups of particle fields, generate particles for each group.
        """
        result_particles = []
        sample_count = 0

        if len(fields) > 0:
            for x in range(0, len(fields)):
                particle_type = fields[x][0]
                #log.info("XXX Particle %d", particle_type)
                #log.info("%s", str(fields[x][1]))

                if particle_type == PARTICLE_TYPE_INSTRUMENT:
                    particle_class = Vel3dLWfpInstrumentParticle
                else:
                    particle_class = Vel3dLWfpMetadataParticle

                # particle-ize the data block received, return the record
                sample = self._extract_sample(particle_class, None, fields[x][1], 0)
                if sample:
                    #
                    # Add the particle to the list of particles
                    #
                    result_particles.append(sample)
                    sample_count += 1

        return sample_count, result_particles

    def parse_vel3d_data(self, chunk, time_stamp=None):
        """
        This function parses the Vel3d data, including the FSI Header,
        FSI Records, and Metadata.
        Parameters:
          chunk - Vel3d data, starting with the data_bytes field.
        Returns:
          particle_fields - The fields resulting from parsing the FSI Header,
            FSI records, and Metadata.
        """
        particle_fields = []    # Initialize return parameter to empty

        #
        # Skip past the Data Bytes field to get to the start of the FSI Header.
        # We don't care about the Data Bytes field'.
        #
        start_index = DATA_BYTES_SIZE

        #
        # Extract the serial number from the FSI Header.
        #
        serial_number_start = start_index + FSI_HEADER_SERIAL_NUMBER_OFFSET
        serial_number = struct.unpack('<I',
            chunk[serial_number_start :
                  serial_number_start + FSI_HEADER_SERIAL_NUMBER_SIZE])[0]

        #
        # Skip past the FSI Header to get to the first FSI record.
        #
        start_index += FSI_HEADER_SIZE

        #
        # Calculate the number of bytes remaining to be processed.
        #
        bytes_remaining = len(chunk) - start_index

        #
        # Calculate the expected number of FSI records.
        #
        expected_records = bytes_remaining / FSI_RECORD_SIZE

        #
        # As long as there is more data in the chunk.
        #
        records_processed = 0
        metadata_found = False
        while bytes_remaining > 0:

            fields = []

            #
            # If there are enough bytes to comprise an FSI record,
            # extract the fields from the FSI record.
            #
            if bytes_remaining >= FSI_RECORD_SIZE:
                particle_type = PARTICLE_TYPE_INSTRUMENT
                fields.append(particle_type)

                fields.append(struct.unpack(FSI_RECORD_FORMAT,
                    chunk[start_index : start_index + FSI_RECORD_SIZE]))
                bytes_remaining -= FSI_RECORD_SIZE
                start_index += FSI_RECORD_SIZE
                records_processed += 1

            #
            # Once all the FSI records have been processed,
            # check for a decimation or time record (Metadata).
            # If there are enough bytes to comprise a decimation record
            # or a time record, extract the fields from the record.
            #
            elif records_processed == expected_records and \
                not metadata_found and \
                (bytes_remaining == DECIMATION_RECORD_SIZE or
                bytes_remaining == TIME_RECORD_SIZE):

                #
                # If it's a decimation record, extract time on, time off
                # and the decimation factor.
                #
                particle_type = PARTICLE_TYPE_METADATA
                fields.append(particle_type)

                if bytes_remaining == DECIMATION_RECORD_SIZE:
                    metadata = struct.unpack(DECIMATION_FORMAT,
                        chunk[start_index : start_index + bytes_remaining])
                    metadata_list = list(metadata)
                    bytes_remaining -= DECIMATION_RECORD_SIZE

                #
                # If it's a time record, extract time on and time off,
                # and set decimation to None.
                #
                else:
                    metadata = struct.unpack(TIME_FORMAT,
                        chunk[start_index : start_index + bytes_remaining])
                    metadata_list = list(metadata)
                    metadata_list.append(None)
                    bytes_remaining -= TIME_RECORD_SIZE

                #
                # Add remaining fields (serial number, number of records,
                # POSIX timestamp) to the list, then turn it into a tuple
                # and add it to the other fields.
                #
                metadata_list.append(serial_number)
                metadata_list.append(records_processed)

                #
                # If there is a timestamp specified,
                # use it for the Metadata timestamp field.
                # If not, use the time_off field.
                #
                if time_stamp is None:
                    time_stamp = metadata[FIELD_TIME_OFF]
                metadata_list.append(time_stamp)

                metadata = tuple(metadata_list)
                fields.append(metadata)
                metadata_found = True

            #
            # It's an error if we don't recognize any type of record.
            #
            else:
                self.report_error(SampleException,
                    '%d bytes remaining at end of record' % bytes_remaining)
                bytes_remaining = 0
                particle_type = None

            if particle_type is not None:
                particle_fields.append(fields)

        return particle_fields

    def report_error(self, exception, error_message):
        """
        This function reports an error condition by issuing a warning
        and raising an exception.
        Parameters:
          exception - type of exception to raise
          error_message - accompanying text
        """
        log.warn(error_message)
        raise exception(error_message)


#class Vel3dLWfpParser(BufferLoadingFilenameParser, Vel3dLParser):
class Vel3dLWfpParser(BufferLoadingParser, Vel3dLParser):


    _state = None
    _read_state = None

    def __init__(self, config, state, file_handle, file_name,
                 state_callback, publish_callback, exception_callback):
        """
        @param config The configuration parameters to feed into the parser
        @param state The location in the file to start parsing from.
           This reflects what has already been published.
        @param file_handle An already open file-like file handle
        @param state_callback The callback method from the agent driver
           (ultimately the agent) to call back when a state needs to be
           updated
        @param publish_callback The callback from the agent driver (and
           ultimately from the agent) where we send our sample particle to
           be published into ION
        @param exception_callback The callback from the agent driver to
           send an exception to
        """
        self.input_file = file_handle

        if state is not None:
            if not (Vel3dLWfpStateKey.POSITION in state):
                state[Vel3dLWfpStateKey.POSITION] = 0
            self.set_state(state)

        else:
            initial_state = {Vel3dLWfpStateKey.POSITION: 0}
            self.set_state(initial_state)

        super(Vel3dLWfpParser, self).__init__(config, file_handle, # file_name,
            state,  self.sieve_function, state_callback, publish_callback,
            exception_callback)

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # if non-data is expected, handle it here, otherwise it is an error
        if non_data is not None and non_end <= start:
            # if this non-data is an error, send an UnexpectedDataException and increment the state
            self._increment_position(len(non_data))
            # if non-data is a fatal error, directly call the exception, if it is not use the _exception_callback
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" % (len(non_data), non_data)))

    def _increment_position(self, bytes_read):
        """
        Increment the parser position
        @param bytes_read The number of bytes just read
        """
        self._read_state[Vel3dLWfpStateKey.POSITION] += bytes_read

    def parse_chunks(self):
        """
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

        while chunk is not None:
            fields = self.parse_recovered_data(chunk)
            self._increment_position(len(chunk))
            #log.info('FIELDS %s', fields)

            #
            # Generate the particles for this chunk.
            # Add them to the return list of particles.
            #
            (samples, particles) = self.generate_particles(fields)
            for x in range(0,len(particles)):
                result_particles.append((particles[x], copy.copy(self._read_state)))

            #log.info("COUNT %d", samples)
            self._increment_position(len(chunk))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        #log.info("PARSE CHUNKS %d", len(result_particles))
        return result_particles

    def parse_recovered_data(self, chunk):
        """
        This function processes a chunk received from the chunker.
        Parameters:
          chunk - the input chunk from the chunker
        Returns:
          A list of tuples containing the parsed values from the chunk.
        """
        #
        # Parse the Vel3d data.
        #
        particle_fields = self.parse_vel3d_data(chunk)
        return particle_fields

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to.
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")

        if not (Vel3dLWfpStateKey.POSITION in state_obj):

            raise DatasetParserException("Invalid state keys")

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj
        self.input_file.seek(state_obj[Vel3dLWfpStateKey.POSITION])

    def sieve_function(self, input_buffer):
        """
        Sort through the input buffer looking for Recovered data records.
        Arguments:
          input_buffer - the contents of the input stream
        Returns:
          A list of start,end tuples
        """

        indices_list = []    # initialize the return list to empty

        start_index = 0
        while start_index < len(input_buffer):

            #
            # Extract the number of data_bytes.
            # This is the number of bytes in the FSI Header and FSI records,
            # and excludes the data_bytes field and the time fields.
            #
            data_bytes = struct.unpack('>I',
                input_buffer[start_index : start_index + DATA_BYTES_SIZE])[0]

            #
            # Calculate the end of packet.
            # This includes the data_bytes field, the FSI Header,
            # some number of FSI records, and the 2 time fields.
            #
            end_index = start_index + DATA_BYTES_SIZE + data_bytes + TIME_RECORD_SIZE

            #
            # If the input buffer has enough bytes for the entire packet,
            # add the start,end pair to the list of indices.
            # If not enough room, we're done for now.
            #
            if end_index <= len(input_buffer):
                indices_list.append((start_index, end_index))
                start_index = end_index
            else:
                break

        return indices_list


class Vel3dLWfpSioMuleParser(SioMuleParser, Vel3dLParser):

    def __init__(self, config, state, stream_handle,
                 state_callback, publish_callback, exception_callback):
        """
        @param config The configuration parameters to feed into the parser
        @param state The location in the file to start parsing from.
           This reflects what has already been published.
        @param stream_handle An already open file-like file handle
        @param state_callback The callback method from the agent driver
           (ultimately the agent) to call back when a state needs to be
           updated
        @param publish_callback The callback from the agent driver (and
           ultimately from the agent) where we send our sample particle to
           be published into ION
        @param exception_callback The callback from the agent driver to
           send an exception to
        """
        super(Vel3dLWfpSioMuleParser, self).__init__(config, stream_handle, state,
            self.sieve_function, state_callback, publish_callback,
            exception_callback)

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # if non-data is expected, handle it here, otherwise it is an error
        if non_data is not None and non_end <= start:
            # if this non-data is an error, send an UnexpectedDataException and increment the state
            self._increment_state(len(non_data))
            # if non-data is a fatal error, directly call the exception, if it is not use the _exception_callback
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" % (len(non_data), non_data)))

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        sample_count = 0
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        while chunk is not None:
            fields = self.parse_telemetered_data(chunk)

            #
            # Generate the particles for this chunk.
            # Add them to the return list of particles.
            #
            (samples, particles) = self.generate_particles(fields)
            sample_count += samples
            for x in range(0,len(particles)):
                result_particles.append(particles[x])

            # keep track of how many samples were found in this chunk
            self._chunk_sample_count.append(sample_count)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def parse_telemetered_data(self, chunk):
        """
        This function processes a chunk received from the chunker.
        Parameters:
          chunk - the input chunk from the chunker
        Returns:
          A list of tuples containing the parsed values from the chunk.
        """
        particle_fields = []

        #
        # Verify that the Instrument ID is the one that we want.
        #
        header = SIO_HEADER_MATCHER.match(chunk)
        if header.group(SIO_HEADER_GROUP_ID) == ID_VEL3D_L_WFP_SIO_MULE:

            #
            # Extract the POSIX timestamp from the SIO Header.
            #
            sio_timestamp = int(header.group(SIO_HEADER_GROUP_TIMESTAMP), 16)

            #
            # Process the remaining Vel3d data, starting from the end of the
            # SIO Header, but not including the trailing 0x03.
            #
            particle_fields = self.parse_vel3d_data(chunk[header.end(0) : -1],
                time_stamp=sio_timestamp)

        return particle_fields
