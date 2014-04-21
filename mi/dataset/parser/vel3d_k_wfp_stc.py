#!/usr/bin/env python

"""
@package mi.dataset.parser.vel3d_k_wfp_stc
@file marine-integrations/mi/dataset/parser/vel3d_k_wfp_stc.py
@author Steve Myerson (Raytheon)
@brief Parser for the Vel3dKWfpStc dataset driver
Release notes:

Initial Release
"""

#
# The VEL3D input file is a binary file.
# The first record is the Flag record that indicates which of the data
# fields are to be expected in the Velocity data records.
# Following the Flag record are some number of Velocity data records,
# terminated by a Velocity data record with all fields set to zero.
# Following the all zero Velocity data record is a Time record.
# This design assumes that only one set of data records
# (Flag, N * Velocity, Time) is in each file.
#

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import copy
import gevent
import ntplib
import re
import struct

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.log import get_logger; log = get_logger()
from mi.dataset.dataset_parser import BufferLoadingFilenameParser

FLAG_RECORD_SIZE = 26                   # bytes
FLAG_RECORD_REGEX = b'(\x00|\x01){26}'  # 26 bytes of zeroes or ones
FLAG_FORMAT = '<26?'                    # 26 booleans
FLAG_RECORD_MATCHER = re.compile(FLAG_RECORD_REGEX)
INDEX_FLAG_Time = 0                     # Index into the flags for time field
OUTPUT_TIME_SIZE = 6                    # 6 bytes for the output time field

TIME_RECORD_SIZE = 8                    # bytes
TIME_RECORD_REGEX = b'[\x00-\xFF]{8}'   # 8 bytes of any hex value
TIME_FORMAT = '>2I'                     # 2 32-bit unsigned integers big endian
TIME_RECORD_MATCHER = re.compile(TIME_RECORD_REGEX)

INDEX_TIME_ON = 0            # field number within Time record
INDEX_TIME_OFF = 1           # field number within Time record
INDEX_RECORDS = 2

SAMPLE_RATE = .5             # Velocity records sample rate

#
# VEL3D_PARAMETERS is a table containing the following parameters
# for the VEL3D data:
# The order of the entries corresponds to the order of the flags as
# described in the IDD.
#   The number of bytes for the field.
#   A format expression component to be added to the velocity data
#     format if that data item is to be collected.
#   A text string (key) used when generating the output data particle.
#
INDEX_DATA_BYTES = 0
INDEX_FORMAT = 1
INDEX_KEY = 2

VEL3D_PARAMETERS = \
[ 
  # Bytes Format Key
    [6,    '6b',  'date_time_array'], 
    [2,    'H',   'vel3d_k_soundSpeed'], 
    [2,    'h',   'vel3d_k_temp_c'], 
    [2,    'H',   'vel3d_k_heading'], 
    [2,    'h',   'vel3d_k_pitch'], 
    [2,    'h',   'vel3d_k_roll'], 
    [2,    'h',   'vel3d_k_mag_x'], 
    [2,    'h',   'vel3d_k_mag_y'], 
    [2,    'h',   'vel3d_k_mag_z'], 
    [1,    'B',   'vel3d_k_beams'], 
    [1,    'B',   'vel3d_k_cells'], 
    [1,    'B',   'vel3d_k_beam1'], 
    [1,    'B',   'vel3d_k_beam2'], 
    [1,    'B',   'vel3d_k_beam3'], 
    [1,    'B',   'vel3d_k_beam4'], 
    [1,    'B',   'vel3d_k_beam5'], 
    [1,    'b',   'vel3d_k_v_scale'], 
    [2,    'h',   'vel3d_k_vel0'], 
    [2,    'h',   'vel3d_k_vel1'], 
    [2,    'h',   'vel3d_k_vel2'], 
    [1,    'B',   'vel3d_k_amp0'], 
    [1,    'B',   'vel3d_k_amp1'], 
    [1,    'B',   'vel3d_k_amp2'], 
    [1,    'B',   'vel3d_k_cor0'], 
    [1,    'B',   'vel3d_k_cor1'], 
    [1,    'B',   'vel3d_k_cor2']
]


class Vel3dKWfpStcStateKey(BaseEnum):
    FIRST_RECORD = 'first record'   # are we at the beginning of the file?
    POSITION = 'position'           # number of bytes read
    VELOCITY_END = 'velocity end'   # has end of velocity record been found?


class Vel3dKWfpStcDataParticleType(BaseEnum):
    TIME_PARTICLE = 'vel3d_k_wfp_stc_metadata'
    VELOCITY_PARTICLE = 'vel3d_k_wfp_stc_instrument'


class Vel3dKWfpStcTimeDataParticleKey(BaseEnum):
    NUMBER_OF_RECORDS = 'vel3d_k_number_of_records'
    TIME_OFF = 'vel3d_k_time_off'
    TIME_ON = 'vel3d_k_time_on'


class Vel3dKWfpStcTimeDataParticle(DataParticle):
    """
    Class for parsing TIME data from the VEL3D_K__stc_imodem data set
    """

    _data_particle_type = Vel3dKWfpStcDataParticleType.TIME_PARTICLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        """

        # 
        # Generate a time data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the time data record.
        #
        particle = [
          {
            DataParticleKey.VALUE_ID:
              Vel3dKWfpStcTimeDataParticleKey.TIME_ON, 
            DataParticleKey.VALUE: self.raw_data[INDEX_TIME_ON]
          },
          {
            DataParticleKey.VALUE_ID: 
              Vel3dKWfpStcTimeDataParticleKey.TIME_OFF,
            DataParticleKey.VALUE: self.raw_data[INDEX_TIME_OFF]
          },
          {
            DataParticleKey.VALUE_ID: 
              Vel3dKWfpStcTimeDataParticleKey.NUMBER_OF_RECORDS, 
            DataParticleKey.VALUE: self.raw_data[INDEX_RECORDS]
          }
        ]

        return particle


class Vel3dKWfpStcVelocityDataParticle(DataParticle):
    """
    Class for parsing VELOCITY data from the VEL3D_K__stc_imodem data set
    """

    _data_particle_type = Vel3dKWfpStcDataParticleType.VELOCITY_PARTICLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        """

        # 
        # Generate a velocity data particle.
        # Note that raw_data already contains the individual fields
        # extracted and unpacked from the velocity data record.
        #
        global flags
        particle = []
        field = 0
        for flag in range(0, FLAG_RECORD_SIZE):
            #
            # If the flags indicated that this field is to be expected,
            # store the next unpacked value into the data particle.
            #
            key = VEL3D_PARAMETERS[flag][INDEX_KEY]
            if flags[flag]:
                if flag == INDEX_FLAG_Time:
                    #
                    # This returns a tuple, but particle wants a list.
                    #
                    time_array = self.raw_data[field:field + OUTPUT_TIME_SIZE]

                    particle.append({DataParticleKey.VALUE_ID: key,
                       DataParticleKey.VALUE: list(time_array)})
                    field += OUTPUT_TIME_SIZE
                else:
                    particle.append({DataParticleKey.VALUE_ID: key,
                       DataParticleKey.VALUE: self.raw_data[field]})
                    field += 1

            #
            # If flags indicate that this field is not present,
            # output a value of None.
            #
            else:
                particle.append({DataParticleKey.VALUE_ID: key,
                  DataParticleKey.VALUE: None})

        return particle

class Vel3dKWfpStcParser(BufferLoadingFilenameParser):

    _timestamp = None
    _state = None
    _read_state = None

    #
    # Default all flags to False.
    # These will be overridden when the Flag record is read.
    #
    global flags
    flags = [False for x in range(FLAG_RECORD_SIZE)]

    def __init__(self, config, state, file_handle, file_name,
      state_callback, publish_callback, exception_callback):
        """
        Constructor for the Vel3d_k__stc_imodemParser class.
        Arguments:
          config - The parser configuration.
          state - The latest parser state.
          file_handle - A reference (handle) to the input file.
          file_name - Name of the file referenced by the file_handle.
          state_callback - Callback for state changes.
          publish_callback - Callback to publish a particle.
          exception_callback - Callback for an exception
        """

        #
        # From the input file, get the parameters which define the inputs.
        # 
        (valid_flag_record, velocity_regex, end_of_velocity_regex, 
          self.velocity_format, self.velocity_record_size, 
          time_fields) = self.get_file_parameters(file_handle)

        #
        # If the Flag record was valid,
        # save the timestamp that will go into the data particles and
        # create the pattern matchers for the Velocity record.
        #
        if valid_flag_record:
            self._timestamp = 0.0
            self.input_file = file_handle
            if state:
                self.set_state(state)
            else:
                initial_state = {Vel3dKWfpStcStateKey.FIRST_RECORD: True,
                                 Vel3dKWfpStcStateKey.POSITION: 0,
                                 Vel3dKWfpStcStateKey.VELOCITY_END: False}
                self.set_state(initial_state)

            self.time_on = int(time_fields[INDEX_TIME_ON])

            #
            # This one will match any Velocity record.
            #
            self.velocity_record_matcher = re.compile(velocity_regex)

            #
            # This one checks for the end of the Velocity record.
            #
            self.velocity_end_record_matcher = \
              re.compile(end_of_velocity_regex)

        super(Vel3dKWfpStcParser, self).__init__(config, file_handle, file_name,
            state, self.sieve_function, state_callback, publish_callback,
            exception_callback)

    def calculate_record_number(self):
        """
        This function calculates the record number based on the current 
        position in the file and the size of each velocity data record.
        """
        return (self._read_state[Vel3dKWfpStcStateKey.POSITION] - FLAG_RECORD_SIZE) \
          / self.velocity_record_size

    def calculate_timestamp(self):
        """
        This function calculates the timestamp based on the current 
        position in the file and the size of each velocity data record.
        """
        return ((self.calculate_record_number() - 1) * SAMPLE_RATE) + \
          self.time_on

    def get_block(self):
        """
        This function overwrites the get_block function in dataset_parser.py
        to  read the entire file rather than break it into chunks.
        Returns:
          The length of data retrieved.
        An EOFError is raised when the end of the file is reached.
        """
        # Read in data in blocks so as to not tie up the CPU.
        BLOCK_SIZE = 1024
        eof = False
        data = ''
        while not eof:
            next_block = self._stream_handle.read(BLOCK_SIZE)
            if next_block:
                data = data + next_block
                gevent.sleep(0)
            else:
                eof = True

        if data != '':
            self._chunker.add_chunk(data, self._timestamp)
            self.file_complete = True
            return len(data)
        else:  # EOF
            self.file_complete = True
            raise EOFError

    def get_file_parameters(self, input_file):
        """
        This function reads the Flag record and Time record
        from the input file.
        The Flag record determines the record length and format of
        the Velocity data records.
        The Time record is needed to get the initial timestamp.
        Arguments:
          input_file - A reference (handle) to the input file.
        """

        #
        # Read the Flag record.
        #
        input_file.seek(0, 0)  # 0 = from start of file
        record = input_file.read(FLAG_RECORD_SIZE)

        #
        # Check for end of file.
        # If not reached, check for and parse a Flag record.
        #
        if len(record) != FLAG_RECORD_SIZE:
            log.warn("EOF reading for flag record")
            raise SampleException("EOF reading for flag record")
        
        (valid_record, regex_velocity_record, 
          regex_end_velocity_record, format_unpack_velocity, 
          record_size) = self.parse_flag_record(record)

        #
        # If there is a valid Flag record, process the Time record.
        #
        if valid_record:
            #
            # Read the Time record which is at the very end of the file.
            # Note that we don't care if the number of bytes between the
            # Flag record and the Time record is consistent with
            # the flags from the Flag record.
            # Put the file back at the beginning.
            #
            input_file.seek(0 - TIME_RECORD_SIZE, 2)  # 2 = from end of file
            record = input_file.read(TIME_RECORD_SIZE)
            times = self.parse_time_record(record)
            input_file.seek(0, 0)  # 0 = from start of file

        #
        # If the Flag record is invalid, we're done.
        #
        else:
            log.warn("Invalid Flag record")
            raise SampleException("Invalid Flag record")

        return valid_record, regex_velocity_record, regex_end_velocity_record, \
          format_unpack_velocity, record_size, times

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. 
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not (Vel3dKWfpStcStateKey.FIRST_RECORD in state_obj) or \
           not (Vel3dKWfpStcStateKey.POSITION in state_obj) or \
           not (Vel3dKWfpStcStateKey.VELOCITY_END in state_obj):
            raise DatasetParserException("Invalid state keys")

        #
        # Initialize parent data.
        #
        self._timestamp = 0.0
        self._record_buffer = []

        self._state = state_obj
        self._read_state = state_obj
        self.input_file.seek(self._read_state[Vel3dKWfpStcStateKey.POSITION], 0)  

    def _increment_state(self, bytes_read):
        """
        Increment the parser state
        @param bytes_read The number of bytes just read
        """
        self._read_state[Vel3dKWfpStcStateKey.POSITION] += bytes_read

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

        while chunk is not None:
            #
            # Discard the Flag record since it has already been processed.
            # We also need to check for this being the first record, 
            # since an end of velocity record could result in a pattern match 
            # with a Flag record if the size of the velocity records are 
            # greater than or equal to the Flag record size.
            #
            if self._read_state[Vel3dKWfpStcStateKey.FIRST_RECORD] and \
              FLAG_RECORD_MATCHER.match(chunk):
                self._increment_state(FLAG_RECORD_SIZE)

            #
            # If we haven't reached the end of the Velocity record,
            # see if this next record is the last one (all zeroes).
            #
            elif not self._read_state[Vel3dKWfpStcStateKey.VELOCITY_END]:
                velocity_end = self.velocity_end_record_matcher.match(chunk)
                self._increment_state(self.velocity_record_size)

                #
                # A velocity data record of all zeroes does not generate
                # a data particle.
                #
                if velocity_end:
                    self._read_state[Vel3dKWfpStcStateKey.VELOCITY_END] = True
                else:
                    #
                    # If the file is missing an end of velocity record,
                    # meaning we'll exhaust the file and run off the end,
                    # this test will catch it.
                    #
                    velocity_fields = self.parse_velocity_record(chunk)
                    if velocity_fields:
                        #
                        # Generate a data particle for this record and add
                        # it to the end of the particles collected so far.
                        #
                        timestamp = self.calculate_timestamp()
                        ntp_time = ntplib.system_to_ntp_time(timestamp)

                        particle = self._extract_sample(
                            Vel3dKWfpStcVelocityDataParticle,
                            None, velocity_fields, ntp_time)

                        result_particles.append((particle,
                            copy.copy(self._read_state)))

                    #
                    # Ran off the end of the file.  Tell 'em the bad news.
                    #
                    else:
                        log.warn("EOF reading velocity records")
                        raise SampleException("EOF reading velocity records")

            #
            # If we have read the end of velocity data records,
            # the next record is the Time data record by definition.
            # Generate the data particle and
            # add it to the end of the particles collected so far.
            #
            else:
                #
                # Make sure there was enough data to comprise a Time record.
                # We can't verify the validity of the data,
                # only that we had enough data.
                #
                time_fields = self.parse_time_record(chunk)
                if time_fields:
                    #
                    # Convert the tuple to a list, add the number of
                    # Velocity record received (not counting the end of
                    # Velocity record, and convert back to a tuple.
                    #
                    time_list = list(time_fields)
                    time_list.append(self.calculate_record_number() - 1)
                    time_fields = tuple(time_list)
                    ntp_time = ntplib.system_to_ntp_time(self.time_on)

                    particle = self._extract_sample(
                        Vel3dKWfpStcTimeDataParticle, None, time_fields, ntp_time)

                    self._increment_state(TIME_RECORD_SIZE)
                    result_particles.append((particle, copy.copy(self._read_state)))

                else:
                    log.warn("EOF reading time record")
                    raise SampleException("EOF reading time record")

            self._read_state[Vel3dKWfpStcStateKey.FIRST_RECORD] = False

            (timestamp, chunk, start, 
                end) = self._chunker.get_next_data_with_index()

        return result_particles

    def parse_flag_record(self, record):
        """
        This function parses the Flag record.
        A Flag record consists of 26 binary bytes, 
        with each byte being either 0 or 1.
        Each byte corresponds to a data item in the Velocity record.
        Then we use the received Flag record fields to override
        the expected flag fields.
        Arguments:
          record - a buffer of binary bytes
        Returns:
          True/False indicating whether or not the flag record is valid.
          A regular expression based on the received flag fields,
            to be used in pattern matching.
          A regular expression for detecting end of Velocity record.
          A format based on the flag fields, to be used to unpack the data.
          The number of bytes expected in each velocity data record.
        """

        #
        # See if we've got a valid flag record.
        #
        global flags
        flag_record = FLAG_RECORD_MATCHER.match(record)
        if not flag_record:
            valid_flag_record = False
            regex_velocity_record = None
            regex_end_velocity_record = None
            format_unpack_velocity = None
            record_length = 0
        else:
            #
            # If the flag record is valid,
            # interpret each field as a boolean value.
            #
            valid_flag_record = True
            flags = struct.unpack(FLAG_FORMAT, 
                flag_record.group(0)[0:FLAG_RECORD_SIZE])

            #
            # The format string for unpacking the velocity data record
            # fields must be constructed based on which fields the Flag
            # record indicates we'll be receiving.
            # Start with the little endian symbol for the format.
            # We also compute the record length for each velocity data 
            # record, again based on the Flag record.
            #
            format_unpack_velocity = '<'
            record_length = 0

            #
            # Check each field from the input Flag record.
            #
            for x in range(0, FLAG_RECORD_SIZE):
                #
                # If the flag field is True,
                # increment the total number of bytes expected in each
                # velocity data record and add the corresponding text to 
                # the format.
                #
                if flags[x]:
                    record_length += VEL3D_PARAMETERS[x][INDEX_DATA_BYTES]
                    format_unpack_velocity = format_unpack_velocity + \
                        VEL3D_PARAMETERS[x][INDEX_FORMAT]

            #
            # Create the velocity data record regular expression
            # (some number of any hex digits)
            # and the end of velocity data record indicator
            # (the same number of all zeroes).
            # Note that the backslash needs to be doubled because
            # we're not using the b'' syntax.
            #
            regex_velocity_record = "[\\x00-\\xFF]{%d}" % record_length
            regex_end_velocity_record = "[\\x00]{%d}" % record_length

        return valid_flag_record, regex_velocity_record, \
            regex_end_velocity_record, format_unpack_velocity, record_length

    def parse_time_record(self, record):
        """
        This function parses a Time record and returns 2 32-bit numbers.
        A Time record consists of 8 bytes.
        Offset  Bytes  Format  Field
         0      4      uint32  Time_on
         4      4      uint32  Time_off
        Arguments:
          record - a buffer of binary bytes
        """

        time_record = TIME_RECORD_MATCHER.match(record)
        if not time_record:
            time_data = None
        else:
            time_data = struct.unpack(TIME_FORMAT, 
                time_record.group(0)[0:TIME_RECORD_SIZE])

        return time_data

    def parse_velocity_record(self, record):
        """
        This function parses a Velocity data record.
        Arguments:
          record - a buffer of binary bytes
        A Velocity data record consists of up to 42 bytes,
        with the actual size depending on which flags are set to True.
        Valid fields are indicated by the Flag record.

        Offset  Bytes  Format  Field
         0      6      byte    Time
         6      2      uint    SoundSpeed
         8      2      int     TempC
        10      2      uint    Heading
        12      2      int     Pitch
        14      2      int     Roll
        16      2      int     magX
        18      2      int     magY
        20      2      int     magZ
        22      1      ubyte   Beams
        23      1      ubyte   Cells
        24      1      ubyte   Beam1
        25      1      ubyte   Beam2
        26      1      ubyte   Beam3
        27      1      ubyte   Beam4
        28      1      ubyte   Beam5
        29      1      byte    VScale
        30      2      int     Vel0
        32      2      int     Vel1
        34      2      int     Vel2
        36      1      ubyte   Amp0
        37      1      ubyte   Amp1
        38      1      ubyte   Amp2
        39      1      ubyte   Cor0
        40      1      ubyte   Cor1:
        41      1      ubyte   Cor2
        """

        velocity_record = self.velocity_record_matcher.match(record)
        if not velocity_record:
            velocity_fields = None
        else:
            velocity_fields = struct.unpack(self.velocity_format,
                velocity_record.group(0)[0:self.velocity_record_size])

        return velocity_fields

    def sieve_function(self, source):        
        """        
        Sort through the input source to extract blocks of data that 
        need processing.        
        This is needed instead of a regex because blocks are 
        identified by specific lengths in this binary file.        
        This algorithm assumes that the velocity data records are 
        longer than the time record.  
        Arguments:
          source - the contents of the input file
        """        

        indices_list = []     # array of tuples (start index, end index)

        #
        # If the first record is a valid Flag record, add it to the list.
        # The first record might not be a Flag record 
        # if the parser is being restarted in the middle of the file.
        # Note: If this parser is restarted with a file position in the
        # middle of a Velocity record, results will be unpredictable.
        #
        start_index = 0
        flag_record = FLAG_RECORD_MATCHER.match(source)
        if flag_record:
            indices_list.append((0, FLAG_RECORD_SIZE))
            start_index += FLAG_RECORD_SIZE

        source_length = len(source)   # Total bytes to process
 
        #
        # While there is more data to process and we haven't found the
        # Time record yet, add a start,end pair for each Velocity record
        # to the return list.
        #
        while start_index < source_length:
            #
            # Compute the end index for the next Velocity record.
            #
            end_index = start_index + self.velocity_record_size

            #
            # If there are enough bytes to make a Velocity record,
            # add this start,end pair to the list.
            #
            if end_index < source_length:
                indices_list.append((start_index, end_index))
                start_index = end_index

            #
            # If not big enough to be a Velocity record,
            # assume it's a Time record and any left-over bytes
            # will be ignored.
            #
            else:
                end_index = start_index + TIME_RECORD_SIZE
                indices_list.append((start_index, end_index))
                start_index = end_index

        return indices_list

