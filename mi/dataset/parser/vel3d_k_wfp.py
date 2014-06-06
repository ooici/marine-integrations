#!/usr/bin/env python

"""
@package mi.dataset.parser.vel3d_k_wfp
@file marine-integrations/mi/dataset/parser/vel3d_k_wfp.py
@author Steve Myerson (Raytheon)
@brief Parser for the vel3d_k_wfp dataset driver
Release notes:

Initial Release
"""

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

#
# The VEL3D_K_WFP input file is a binary file.
# The file header is a 4 byte field which is the total size of all the data records.
# The file header is not used.
#
# The data records consist of 2 parts: a data header and a data payload.
# The data header contains a sync word, IDs, field lengths, and checksums.
# The data payload contains the parameters needed to generate instrument particles.
#
# The last record in the file is a time record containing the start and end times.
#

import copy
import ntplib
import re
import struct

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import \
    DatasetParserException, \
    RecoverableSampleException, \
    SampleException, \
    UnexpectedDataException

from mi.dataset.dataset_parser import BufferLoadingParser

FILE_HEADER_RECORD_SIZE = 4  # bytes

#
# Divide the data header into groups.
# Group Field           Size   Description
#       Sync            byte   Always 0xA5
#  1    Header Size     ubyte  Number of bytes in the header (should be 10)
#  2    ID              byte   Data type: 0x15 = Burst, 0x16 = CP, 0xA0 = string
#  3    Family          byte   Instrument Family: 0x10 = AD2CP
#  4    Data Size       uint16 Number of bytes in following data record
#  5    Data checksum   int16  Checksum of the following data record
#  6    Header checksum int16  Checksum of the data header, excluding itself
#
DATA_HEADER_REGEX = b'\xA5([\x00-\xFF])([\x00-\xFF])([\x00-\xFF])' \
                     '([\x00-\xFF]{2})([\x00-\xFF]{2})([\x00-\xFF]{2})'
DATA_HEADER_MATCHER = re.compile(DATA_HEADER_REGEX)

DATA_HEADER_SIZE = 10        # expected length in bytes
DATA_HEADER_FAMILY = 0x10    # expected instrument family
DATA_HEADER_ID_BURST_DATA = 0x15
DATA_HEADER_ID_CP_DATA = 0x16
DATA_HEADER_ID_STRING = 0xA0
DATA_HEADER_CHECKSUM_LENGTH = (DATA_HEADER_SIZE / 2) - 1  # sum of 16-bit values

GROUP_HEADER_SIZE = 1
GROUP_HEADER_ID = 2
GROUP_HEADER_FAMILY = 3
GROUP_HEADER_DATA_SIZE = 4
GROUP_HEADER_DATA_CHECKSUM = 5
GROUP_HEADER_CHECKSUM = 6

#
# Keys to be used when generating instrument particles.
# They are listed in order corresponding to the data record payload.
# Note that the ID field, extracted from the data record header,
# is added to the end of the list.
#
DATA_PAYLOAD_FORMAT = '<2bIh6B2HhIH2h7H7h2H2bI3h6b'
INSTRUMENT_PARTICLE_KEYS = \
[
    'vel3d_k_version',
    None,                      # offsetOfData not included in particle
    'vel3d_k_serial',
    'vel3d_k_configuration',
    'date_time_array',         # year, month, day, hour, minute, seconds
    'vel3d_k_micro_second',
    'vel3d_k_speed_sound',
    'vel3d_k_temp_c',
    'vel3d_k_pressure',
    'vel3d_k_heading',
    'vel3d_k_pitch',
    'vel3d_k_roll',
    'vel3d_k_error',
    'vel3d_k_status',
    'vel3d_k_beams_coordinate',
    'vel3d_k_cell_size',
    'vel3d_k_blanking',
    'vel3d_k_velocity_range',
    'vel3d_k_battery_voltage',
    'vel3d_k_mag_x',
    'vel3d_k_mag_y',
    'vel3d_k_mag_z',
    'vel3d_k_acc_x',
    'vel3d_k_acc_y',
    'vel3d_k_acc_z',
    'vel3d_k_ambiguity',
    'vel3d_k_data_set_description',
    'vel3d_k_transmit_energy',
    'vel3d_k_v_scale',
    'vel3d_k_power_level',
    None,                      # unused not included in particle
    'vel3d_k_vel0',
    'vel3d_k_vel1',
    'vel3d_k_vel2',
    'vel3d_k_amp0',
    'vel3d_k_amp1',
    'vel3d_k_amp2',
    'vel3d_k_corr0',
    'vel3d_k_corr1',
    'vel3d_k_corr2',
    'vel3d_k_id'
]
DATE_TIME_ARRAY = 'date_time_array'    # This one needs to be special-cased
DATE_TIME_SIZE = 6                     # 6 bytes for the output date time field
DATA_SET_DESCRIPTION = 'vel3d_k_data_set_description'    # special case

INDEX_STRING_ID = 0   # field number within a string record
INDEX_STRING = 1      # field number within a string record

TIME_RECORD_SIZE = 8  # bytes
TIME_FORMAT = '>2I'   # 2 32-bit unsigned integers big endian
INDEX_TIME_ON = 0     # field number within Time record and raw_data
INDEX_TIME_OFF = 1    # field number within Time record and raw_data
SAMPLE_RATE = .5      # data records sample rate


class Vel3dKWfpDataParticleType(BaseEnum):
    INSTRUMENT_PARTICLE = 'vel3d_k_wfp_instrument'
    METADATA_PARTICLE = 'vel3d_k_wfp_metadata'
    STRING_PARTICLE = 'vel3d_k_wfp_string'


class Vel3dKWfpStateKey(BaseEnum):
    POSITION = 'position'            # number of bytes read
    RECORD_NUMBER = 'record_number'  # record number within the file


class Vel3dKWfpMetadataParticleKey(BaseEnum):
    TIME_OFF = 'vel3d_k_time_off'
    TIME_ON = 'vel3d_k_time_on'


class Vel3dKWfpStringParticleKey(BaseEnum):
    STRING_ID = 'vel3d_k_str_id'
    STRING = 'vel3d_k_string'


class Vel3dKWfpInstrumentParticle(DataParticle):
    """
    Class for generating vel3d_k_wfp instrument particles.
    """

    _data_particle_type = Vel3dKWfpDataParticleType.INSTRUMENT_PARTICLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into an array of
        dictionaries defining the data in the particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        #
        # Generate an Instrument data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the data record.
        #
        particle = []
        field = 0
        for x in range(0, len(INSTRUMENT_PARTICLE_KEYS)):
            key = INSTRUMENT_PARTICLE_KEYS[x]
            if key is not None:
                if key == DATE_TIME_ARRAY:
                    time_array = self.raw_data[field : field + DATE_TIME_SIZE]
                    particle.append({DataParticleKey.VALUE_ID: key,
                        DataParticleKey.VALUE: list(time_array)})
                    field += DATE_TIME_SIZE

                elif key == DATA_SET_DESCRIPTION:
                    #
                    # The data set description field contains 5 3-bit values.
                    # We extract each 3-bit value and put them in the particle
                    # as an array.
                    #
                    value = self.raw_data[field]

                    particle.append({DataParticleKey.VALUE_ID: key,
                        DataParticleKey.VALUE: [value & 0x7,
                            (value >> 3) & 0x7,
                            (value >> 6) & 0x7,
                            (value >> 9) & 0x7,
                            (value >> 12) & 0x7]})

                    field += 1

                else:
                    key_value = self._encode_value(key, self.raw_data[field], int)
                    particle.append(key_value)
                    field += 1
            else:
                field += 1

        return particle


class Vel3dKWfpMetadataParticle(DataParticle):
    """
    Class for generating vel3d_k_wfp metadata particles.
    """

    _data_particle_type = Vel3dKWfpDataParticleType.METADATA_PARTICLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into an array of
        dictionaries defining the data in the particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        #
        # Generate a Metadata data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the data record.
        #
        particle = [
            self._encode_value(Vel3dKWfpMetadataParticleKey.TIME_ON,
                               self.raw_data[INDEX_TIME_ON], int),
            self._encode_value(Vel3dKWfpMetadataParticleKey.TIME_OFF,
                               self.raw_data[INDEX_TIME_OFF], int)
        ]

        return particle


class Vel3dKWfpStringParticle(DataParticle):
    """
    Class for generating vel3d_k_wfp string particles.
    """

    _data_particle_type = Vel3dKWfpDataParticleType.STRING_PARTICLE

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into an array of
        dictionaries defining the data in the particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        #
        # Generate a String data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the time data record.
        #
        particle = [
            self._encode_value(Vel3dKWfpStringParticleKey.STRING_ID,
                               self.raw_data[INDEX_STRING_ID], int),
            self._encode_value(Vel3dKWfpStringParticleKey.STRING,
                               self.raw_data[INDEX_STRING], str)
        ]

        return particle


class Vel3dKWfpParser(BufferLoadingParser):

    _read_state = None

    def __init__(self, config, state, file_handle,
                 state_callback, publish_callback, exception_callback):
        """
        Constructor for the Vel3dKWfpParser class.
        Arguments:
          config - The parser configuration.
          state - The latest parser state.
          file_handle - A reference (handle) to the input file.
          file_name - The name of the file referenced by the handle.
          state_callback - Callback for state changes.
          publish_callback - Callback to publish a particle.
          exception_callback - Callback for exceptions.
        """

        #
        # From the input file, get the time values which are used for the timestamp.
        #
        self.input_file = file_handle
        (self.times, file_position) = self.get_file_parameters(file_handle)

        if state is not None:
            if not (Vel3dKWfpStateKey.POSITION in state):
                state[Vel3dKWfpStateKey.POSITION] = file_position
            if not (Vel3dKWfpStateKey.RECORD_NUMBER in state):
                state[Vel3dKWfpStateKey.RECORD_NUMBER] = 0
            self.set_state(state)

        else:
            initial_state = {Vel3dKWfpStateKey.POSITION: file_position,
                             Vel3dKWfpStateKey.RECORD_NUMBER: 0}
            self.set_state(initial_state)

        super(Vel3dKWfpParser, self).__init__(config, file_handle,
            state, self.sieve_function, state_callback, publish_callback,
            exception_callback)

    def calculate_checksum(self, input_buffer, values):
        """
        This function calculates a 16-bit unsigned sum of 16-bit data.
        Parameters:
          input_buffer - Buffer containing the values to be summed
          values - Number of 16-bit values to sum
        Returns:
          Calculated checksum
        """

        checksum = 0xB58C  # initial value per Nortek's Integrator's Guide
        index = 0
        for x in range(0, values):
            checksum += struct.unpack('<H', input_buffer[index: index + 2])[0]
            index += 2

        #
        # Modulo 65535
        #
        return checksum & 0xFFFF

    def calculate_timestamp(self):
        """
        This function calculates the timestamp based on the current record number.
        """
        time_stamp = self.times[INDEX_TIME_ON] + \
            (self._read_state[Vel3dKWfpStateKey.RECORD_NUMBER] * SAMPLE_RATE)

        ntp_time = ntplib.system_to_ntp_time(time_stamp)
        return ntp_time

    def get_file_parameters(self, input_file):
        """
        This function reads the Time record from the input file.
        The Time record is needed to get the initial timestamp.
        Parameters:
          input_file - file handle
        Returns:
          times - time on, time off
          file position
        """

        #
        # Read the Time record which is at the very end of the file.
        # Check for end of file.
        # If not reached, parse the Time record.
        #
        input_file.seek(0 - TIME_RECORD_SIZE, 2)  # 2 = from end of file
        time_record = input_file.read(TIME_RECORD_SIZE)

        if len(time_record) != TIME_RECORD_SIZE:
            self.report_error(SampleException, 'EOF reading time record')

        times = self.parse_time_record(time_record)

        #
        # Put the file at a position just past the File Header record.
        #
        input_file.seek(FILE_HEADER_RECORD_SIZE, 0)

        return times, FILE_HEADER_RECORD_SIZE

    def handle_non_data(self, non_data, non_start, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # if non-data is expected, handle it here, otherwise it is an error
        if non_data is not None and non_end <= start:
            self._increment_position(len(non_data))

            log.warn("Found %d bytes (from %d to %d) of un-expected non-data" %
                (len(non_data), non_start, non_end))

            # if non-data is a fatal error, directly call the exception,
            # if it is not use the _exception_callback
            self._exception_callback(UnexpectedDataException(
                "Found %d bytes of un-expected non-data %s" %
                 (len(non_data), non_data)))

    def _increment_position(self, bytes_read):
        """
        Increment the parser position
        @param bytes_read The number of bytes just read
        """
        self._read_state[Vel3dKWfpStateKey.POSITION] += bytes_read

    def _increment_record_number(self):
        """
        Increment the parser record number
        """
        self._read_state[Vel3dKWfpStateKey.RECORD_NUMBER] += 1

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
        self.handle_non_data(non_data, non_start, non_end, start)

        while chunk is not None:
            #
            # Process the next record.
            # Move the file position to include what was just processed.
            #
            (particle_type, particle_fields) = self.process_record(chunk)
            self._increment_position(len(chunk))

            #
            # If valid particle type, generate the data particle.
            #
            if particle_type is not None:
                #
                # Get the internal timestamp.
                # For the metadata particle, the timestamp is the time_on field.
                # For other particles, the timestamp is calculated.
                #
                if particle_type == Vel3dKWfpMetadataParticle:
                    record_time = self.times[INDEX_TIME_ON]
                    ntp_time = ntplib.system_to_ntp_time(record_time)
                else:
                    ntp_time = self.calculate_timestamp()

                #
                # Create the particle.
                #
                sample = self._extract_sample(particle_type, None, particle_fields,
                    ntp_time)

                #
                # Increment the record number for Instrument particles only.
                #
                if particle_type == Vel3dKWfpInstrumentParticle:
                    self._increment_record_number()

                #
                # If a particle was created, add it to the list of particles.
                #
                if sample:
                    result_particles.append((sample, copy.copy(self._read_state)))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_start, non_end, start)

        return result_particles

    def parse_data_record(self, record):
        """
        This function parses Burst Data records and CP Data records.
        Parameters:
          record - data buffer to parse
        Returns:
          The data record payload, separated into fields.
        """

        #
        # Pattern match the header to get the header size and ID.
        #
        header = DATA_HEADER_MATCHER.match(record)
        header_size = struct.unpack('B', header.group(GROUP_HEADER_SIZE))[0]
        header_id = struct.unpack('B', header.group(GROUP_HEADER_ID))[0]

        payload_fields = struct.unpack(DATA_PAYLOAD_FORMAT, record[header_size : ])
        payload_list = list(payload_fields)
        payload_list.append(header_id)
        payload_fields = tuple(payload_list)

        return payload_fields

    def parse_string_record(self, record):
        """
        This function parses a string data record.
        Parameters:
          record - data buffer to parse
        Returns:
          The string record, separated into fields.
        """

        #
        # Pattern match the header to get the header size.
        #
        header = DATA_HEADER_MATCHER.match(record)
        header_size = struct.unpack('B', header.group(GROUP_HEADER_SIZE))[0]
        payload_size = struct.unpack('<H', header.group(GROUP_HEADER_DATA_SIZE))[0]

        #
        # The length of the string is the payload size minus the ID and the
        # trailing '\x00' byte.
        #
        string_format = '<B%ds' % (payload_size - 2)
        string_fields = struct.unpack(string_format, record[header_size : -1])
        return string_fields

    def parse_time_record(self, record):
        """
        This function parses a Time record and returns 2 32-bit numbers.
        A Time record consists of 8 bytes.
        Offset  Bytes  Format  Field
         0      4      uint32  Time_on
         4      4      uint32  Time_off
        Parameters:
          record - data buffer to parse
        Returns:
          The time record, separated into fields.
        """
        if len(record) != TIME_RECORD_SIZE:
            time_fields = None
        else:
            time_fields = struct.unpack(TIME_FORMAT, record)

        return time_fields

    def process_record(self, record):
        """
        This function determines what type of record (chunk) has been received
        and calls the appropriate function to parse the record.
        Parameters:
          record - data buffer to parse
        Returns:
          particle type
          particle fields
        """

        particle_fields = []
        particle_type = None

        #
        # See if there is a valid data header.
        #
        header = DATA_HEADER_MATCHER.match(record)
        if header is not None:
            #
            # Validate the parameters from the header.
            #
            header_is_valid = self.validate_header_parameters(header)

            #
            # Verify that the header checksum is correct.
            #
            header_checksum_matches = self.validate_header_checksum(header,
              record, True)

            #
            # Verify that the data payload checksum is correct.
            #
            payload_checksum_matches = self.validate_payload_checksum(header,
              record[DATA_HEADER_SIZE : ], True)

            #
            # If the header is valid and the checksums match,
            # parse the data record payload.
            #
            if header_is_valid and \
                header_checksum_matches and \
                payload_checksum_matches:

                header_id = struct.unpack('B', header.group(GROUP_HEADER_ID))[0]

                if header_id == DATA_HEADER_ID_BURST_DATA or \
                   header_id == DATA_HEADER_ID_CP_DATA:
                    particle_fields = self.parse_data_record(record)
                    particle_type = Vel3dKWfpInstrumentParticle

                else:
                    particle_fields = self.parse_string_record(record)
                    particle_type = Vel3dKWfpStringParticle

        #
        # It wasn't a data record.  See if this is the time record.
        #
        elif len(record) == TIME_RECORD_SIZE:
            particle_fields = self.parse_time_record(record)
            if particle_fields == self.times:
                particle_type = Vel3dKWfpMetadataParticle
            else:
                self.report_error(SampleException, 'Invalid Time Record')

        #
        # Not a data record and not a time record.
        #
        else:
            self.report_error(SampleException, 'Unknown Record')

        return particle_type, particle_fields

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

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to.
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")

        if not (Vel3dKWfpStateKey.POSITION in state_obj) or \
            not (Vel3dKWfpStateKey.RECORD_NUMBER in state_obj):

            raise DatasetParserException("Invalid state keys")

        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj
        self.input_file.seek(state_obj[Vel3dKWfpStateKey.POSITION])

    def sieve_function(self, input_buffer):
        """
        Sort through the input buffer looking for a data record.
        A data record is considered to be properly framed if there is a
        sync word and the 2 checksums match.
        Arguments:
          input_buffer - the contents of the input stream
        Returns:
          A list of start,end tuples
        """

        indices_list = []    # initialize the return list to empty

        #
        # Keep searching until the input buffer is exhausted.
        #
        search_index = 0
        while search_index < len(input_buffer):
            #
            # See if there's a data header anywhere in the buffer
            # starting from the current search index.
            #
            header = DATA_HEADER_MATCHER.search(input_buffer[search_index : ])
            if header is not None:
                #
                # Calculate at what position in the buffer the header starts.
                #
                header_index = header.start() + search_index

                #
                # Verify that the header checksum matches.
                #
                header_checksum_matches = self.validate_header_checksum(header,
                    input_buffer[header_index : ], False)

                if header_checksum_matches:
                    #
                    # Calculate end position of the data payload in the buffer.
                    #
                    payload_size = struct.unpack('<H',
                        header.group(GROUP_HEADER_DATA_SIZE))[0]
                    record_end = header_index + DATA_HEADER_SIZE + payload_size

                    #
                    # If the buffer has enough bytes for an entire data record,
                    # verify that the data payload checksum matches.
                    #
                    if record_end < len(input_buffer):
                        payload_checksum_matches = self.validate_payload_checksum(
                            header,
                            input_buffer[header_index + DATA_HEADER_SIZE : ],
                            False)

                        #
                        # If the payload checksum matches,
                        # add this start,end pair to the indices list.
                        #
                        if payload_checksum_matches:
                            indices_list.append((header_index, record_end))
                            search_index = record_end
                        else:
                            search_index += 1

                    #
                    # If there aren't enough bytes left in the buffer for the
                    # entire payload, we're done searching for now.
                    #
                    else:
                        break

                #
                # If the header checksum test fails, do another match
                # starting at the next byte in the input buffer.
                #
                else:
                    search_index += 1

            #
            # If there were no data headers in this buffer,
            # check to see if we're looking at the time record.
            #
            elif (len(input_buffer) - search_index) == TIME_RECORD_SIZE:
                time_data = self.parse_time_record(input_buffer[search_index : ])
                if time_data == self.times:
                    indices_list.append((search_index,
                        search_index + TIME_RECORD_SIZE))
                    search_index += TIME_RECORD_SIZE
                else:
                    search_index += 1

            #
            # No data records and no time record found.  We're done.
            #
            else:
                break

        return indices_list

    def validate_header_checksum(self, header, input_buffer, stop_on_error):
        """
        This function verifies that the header checksum is correct.
        Parameters:
          header - the fields from the header (extracted via pattern match)
          input_buffer - starting from the header
          stop_on_error - Stop (True) or Continue (False) if error detected
        Returns:
          checksum matches (True) or doesn't match (False)
        """

        expected_checksum = struct.unpack('<H',
            header.group(GROUP_HEADER_CHECKSUM))[0]

        actual_checksum = self.calculate_checksum(input_buffer,
            DATA_HEADER_CHECKSUM_LENGTH)

        if actual_checksum == expected_checksum:
            checksum_matches = True
        else:
            checksum_matches = False
            if stop_on_error:
                self.report_error(RecoverableSampleException,
                    'Invalid Data Header checksum. '
                    'Actual 0x%04X. Expected 0x%04X.' %
                    (actual_checksum, expected_checksum))

        return checksum_matches

    def validate_payload_checksum(self, header, input_buffer, stop_on_error):
        """
        This function verifies that the data payload checksum is correct.
        Parameters:
          header - the fields from the header (extracted via pattern match)
          input_buffer - starting from the payload
          stop_on_error - Stop (True) or Continue (False) if error detected
        Returns:
          checksum matches (True) or doesn't match (False)
        """

        expected_checksum = struct.unpack('<H',
            header.group(GROUP_HEADER_DATA_CHECKSUM))[0]

        #
        # Payload size is in bytes.  Checksum sums 16-bit values.
        #
        payload_size = struct.unpack('<H',
            header.group(GROUP_HEADER_DATA_SIZE))[0]
        actual_checksum = self.calculate_checksum(input_buffer, payload_size / 2)

        if actual_checksum == expected_checksum:
            checksum_matches = True
        else:
            checksum_matches = False
            if stop_on_error:
                self.report_error(RecoverableSampleException,
                    'Invalid Data Payload checksum. '
                    'Actual 0x%04X. Expected 0x%04X.' %
                    (actual_checksum, expected_checksum))

        return checksum_matches

    def validate_header_parameters(self, header):
        """
        This function performs data header validation.
        This includes the following:
          Verify that the header size is as expected.
          Verify that the header family is as expected.
          Verify that the header ID is a valid ID.
        Parameters:
          header - The header record, divided into groups
        Returns:
          True (header is valid) or False (header is not valid)
        """

        header_is_valid = True

        #
        # Verify that the header size is as expected.
        #
        header_size = struct.unpack('B', header.group(GROUP_HEADER_SIZE))[0]
        if header_size != DATA_HEADER_SIZE:
            header_is_valid = False
            self.report_error(UnexpectedDataException,
                'Invalid Data Header size. Actual %d. Expected %d.' %
                (header_size, DATA_HEADER_SIZE))

        #
        # Verify that the family size is as expected.
        #
        header_family = struct.unpack('B', header.group(GROUP_HEADER_FAMILY))[0]
        if header_family != DATA_HEADER_FAMILY:
            header_is_valid = False
            self.report_error(SampleException,
                'Invalid Data Header family. Actual 0x%X. Expected 0x%X.' %
                (header_family, DATA_HEADER_FAMILY))

        #
        # Verify that the header ID is as expected.
        #
        header_id = struct.unpack('B', header.group(GROUP_HEADER_ID))[0]
        if header_id != DATA_HEADER_ID_BURST_DATA and \
            header_id != DATA_HEADER_ID_CP_DATA and \
            header_id != DATA_HEADER_ID_STRING:

            header_is_valid = False
            self.report_error(SampleException,
                'Invalid Data Header ID. Actual 0x%02X. '
                'Expected 0x%02X, 0x%02X, or 0x%02X.' %
                (header_family, DATA_HEADER_ID_BURST_DATA,
                DATA_HEADER_ID_CP_DATA, DATA_HEADER_ID_STRING))

        return header_is_valid
