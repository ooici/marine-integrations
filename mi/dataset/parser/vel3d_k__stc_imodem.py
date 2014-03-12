#!/usr/bin/env python

"""
@package mi.dataset.parser.vel3d_k__stc_imodem
@file marine-integrations/mi/dataset/parser/vel3d_k__stc_imodem.py
@author Steve Myerson (Raytheon)
@brief Parser for the VEL3D_K__stc_imodem dataset driver
Release notes:

Initial Release
"""

##
## The VEL3D input file is a binary file.
## The first record is the Flag record that indicates which of the data
## fields are to be expected in the Velocity data records.
## Following the Flag record are some number of Velocity data records,
## terminated by a Velocity data record with all fields set to zero.
## Following the all zero Velocity data record is a Time record.
## This design assumes that only one set of data records
## (Flag, N * Velocity, Time) is in each file.
##

__author__ = 'Steve Myerson (Raytheon)'
__license__ = 'Apache 2.0'

import copy
import re

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.dataset_parser import BufferLoadingParser

import array
from functools import partial
import math
import os
import struct
from struct import * 
import sys
import time
from time import gmtime, strftime

FLAG_RECORD_SIZE = 26                   # bytes
FLAG_RECORD_REGEX = b'(\x00|\x01){26}'  # 26 bytes of zeroes or ones
FLAG_FORMAT = '<26?'                    # 26 booleans
FLAG_RECORD_MATCHER = re.compile(FLAG_RECORD_REGEX)
INDEX_FLAG_Time = 0                     # Index into the flags for time field
OUTPUT_TIME_SIZE = 6                    # 6 bytes for the output time field

TIME_RECORD_SIZE = 8                   # bytes
TIME_RECORD_REGEX = b'[\x00-\xFF]{8}'  # 8 bytes of any hex value
TIME_FORMAT = '>2I'                    # 2 32-bit unsigned integers big endian
TIME_RECORD_MATCHER = re.compile(TIME_RECORD_REGEX)

INDEX_TIME_ON = 0            # field number within Time record
INDEX_TIME_OFF = 1           # field number within Time record
INDEX_RECORDS = 2

SAMPLE_RATE = .5             # Velocity records sample rate
TIMESTAMP_FORMAT = "%m/%d/%Y %H:%M:%S"   # mm/dd/yyyy hh:mm:ss

##
## vel3d_parameters is a table containing the following parameters
## for the VEL3D data:
##   The actual True/False flag from the received flag record.
##   The number of bytes for the field.
##   A format expression component to be added to the velocity data
##     format if that data item is to be collected.
##   A text string (key) used when generating the output data particle.
##
INDEX_ACTUAL_FLAG = 0
INDEX_DATA_BYTES = 1
INDEX_FORMAT = 2
INDEX_KEY = 3

vel3d_parameters = \
[ 
  ## Actual Bytes Format Key
    [False,  6,   '6b',  'date_time_array'], 
    [False,  2,   'H',   'vel3d_k_soundSpeed'], 
    [False,  2,   'h',   'vel3d_k_temp_c'], 
    [False,  2,   'H',   'vel3d_k_heading'], 
    [False,  2,   'h',   'vel3d_k_pitch'], 
    [False,  2,   'h',   'vel3d_k_roll'], 
    [False,  2,   'h',   'vel3d_k_mag_x'], 
    [False,  2,   'h',   'vel3d_k_mag_y'], 
    [False,  2,   'h',   'vel3d_k_mag_z'], 
    [False,  1,   'B',   'vel3d_k_beams'], 
    [False,  1,   'B',   'vel3d_k_cells'], 
    [False,  1,   'B',   'vel3d_k_beam1'], 
    [False,  1,   'B',   'vel3d_k_beam2'], 
    [False,  1,   'B',   'vel3d_k_beam3'], 
    [False,  1,   'B',   'vel3d_k_beam4'], 
    [False,  1,   'B',   'vel3d_k_beam5'], 
    [False,  1,   'b',   'vel3d_k_v_scale'], 
    [False,  2,   'h',   'vel3d_k_vel0'], 
    [False,  2,   'h',   'vel3d_k_vel1'], 
    [False,  2,   'h',   'vel3d_k_vel2'], 
    [False,  1,   'B',   'vel3d_k_amp0'], 
    [False,  1,   'B',   'vel3d_k_amp1'], 
    [False,  1,   'B',   'vel3d_k_amp2'], 
    [False,  1,   'B',   'vel3d_k_cor0'], 
    [False,  1,   'B',   'vel3d_k_cor1'], 
    [False,  1,   'B',   'vel3d_k_cor2']
]


class StateKey(BaseEnum):
    POSITION = 'position'    # number of bytes read


class DataParticleType(BaseEnum):
    TIME_PARTICLE = 'vel3d_k__stc_imodem_metadata '
    VELOCITY_PARTICLE = 'vel3d_k__stc_imodem_instrument'


class Vel3d_k__stc_imodemTimeDataParticleKey(BaseEnum):
    NUMBER_OF_RECORDS = 'vel3d_k_number_of_records'
    TIME_OFF = 'vel3d_k_time_off'
    TIME_ON = 'vel3d_k_time_on'


class Vel3d_k__stc_imodemTimeDataParticle(DataParticle):
    """
    Class for parsing TIME data from the VEL3D_K__stc_imodem data set
    """

    _data_particle_type = DataParticleType.TIME_PARTICLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """

        ## 
        ## Generate a time data particle.
        ## Note that raw_data already contains the individual fields
        ## extracted and unpacked from the time data record.
        ##
        particle = [
          {
            DataParticleKey.VALUE_ID: 
              Vel3d_k__stc_imodemTimeDataParticleKey.TIME_ON, 
            DataParticleKey.VALUE: self.raw_data[INDEX_TIME_ON]
          },
          {
            DataParticleKey.VALUE_ID: 
              Vel3d_k__stc_imodemTimeDataParticleKey.TIME_OFF,
            DataParticleKey.VALUE: self.raw_data[INDEX_TIME_OFF]
          },
          {
            DataParticleKey.VALUE_ID: 
              Vel3d_k__stc_imodemTimeDataParticleKey.NUMBER_OF_RECORDS, 
            DataParticleKey.VALUE: self.raw_data[INDEX_RECORDS]
          }
        ]

        return particle

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] == \
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Time Raw data %s does not match %s',
                  self.raw_data, arg.raw_data)
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Time Timestamp %f does not match %f',
                  self.contents[DataParticleKey.INTERNAL_TIMESTAMP],
                  arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])
            return False


class Vel3d_k__stc_imodemVelocityDataParticle(DataParticle):
    """
    Class for parsing VELOCITY data from the VEL3D_K__stc_imodem data set
    """

    _data_particle_type = DataParticleType.VELOCITY_PARTICLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """

        ## 
        ## Generate a velocity data particle.
        ## Note that raw_data already contains the individual fields
        ## extracted and unpacked from the velocity data record.
        ##
        particle = []
        field = 0
        for flag in range(0, FLAG_RECORD_SIZE):
            ##
            ## If the flags indicated that this field is to be expected,
            ## store the next unpacked value into the data particle.
            ##
            key = vel3d_parameters[flag][INDEX_KEY]
            if vel3d_parameters[flag][INDEX_ACTUAL_FLAG]:
                if flag == INDEX_FLAG_Time:
                    particle.append({DataParticleKey.VALUE_ID: key,
                       DataParticleKey.VALUE: 
                         self.raw_data[field:field + OUTPUT_TIME_SIZE]})
                    field += OUTPUT_TIME_SIZE
                else:
                    particle.append({DataParticleKey.VALUE_ID: key,
                       DataParticleKey.VALUE: self.raw_data[field]})
                    field += 1

            ##
            ## If flags indicate that this field is not present,
            ## output a value of None.
            ##
            else:
                particle.append({DataParticleKey.VALUE_ID: key,
                  DataParticleKey.VALUE: None})

        return particle

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] == \
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Velocity Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Velocity Timestamp %f does not match %f',
                  self.contents[DataParticleKey.INTERNAL_TIMESTAMP],
                  arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])
            return False


class Vel3d_k__stc_imodemParser(BufferLoadingParser):

    end_of_velocity_records = False
    velocity_format = ''        # Unpacking format for Velocity data fields
    velocity_record_size = 0    # Number of bytes in a Velocity data record
    velocity_record_matcher = re.compile('')
    velocity_end_record_matcher = re.compile('')
    time_on = 0
    _timestamp = 0.0

    def __init__(self, config, infile, state, 
      state_callback, publish_callback, exception_callback):
        ##
        ## From the input file, get the parameters which define the inputs.
        ## 
        self._read_state = state

        (valid_flag_record, velocity_regex, end_of_velocity_regex, 
          self.velocity_format, self.velocity_record_size, 
          time_fields) = self.get_file_parameters(infile)

        ##
        ## Save the timestamp that will go into the data particles.
        ## Initialize key variables.
        ## Create the pattern matcher for a velocity records.
        ##
        if valid_flag_record:
            self.time_on = int(time_fields[INDEX_TIME_ON])
            self._timestamp = 0.0
            self._record_buffer = []

            self.velocity_record_matcher = re.compile(velocity_regex)
            self.velocity_end_record_matcher = \
              re.compile(end_of_velocity_regex)

        super(Vel3d_k__stc_imodemParser, self).__init__(config, infile,
          state, self.sieve_function, state_callback, publish_callback,
          exception_callback)

     calculate_record_number(self):
        ##
        ## This function calculates the record number
        ## based on the current position in the file 
        ## and the size of each velocity data record.
        ##
        return (self._read_state[StateKey.POSITION] - FLAG_RECORD_SIZE) / \
          self.velocity_record_size

    def calculate_timestamp(self):
        ##
        ## This function calculates the timestamp 
        ## based on the current position in the file 
        ## and the size of each velocity data record.
        ##
        return ((self.calculate_record_number() - 1) * SAMPLE_RATE) + \
          self.time_on

    def get_file_parameters(self, infile):
        ##
        ## This function reads the Flag record and Time record
        ## from the input file.
        ## The Flag record determines the record length and format of
        ## the Velocity data records.
        ##
        record_size = 0
        regex_velocity_record = ''
        regex_end_velocity_record = ''
        times = []
        format_unpack_velocity = ''

        ##
        ## Read the Flag record.
        ##
        infile.seek(0, 0)  # 0 = from start of file
        record = infile.read(FLAG_RECORD_SIZE)

        ##
        ## Check for end of file.
        ## If not reached, check for and parse a Flag record.
        ##
        if len(record) != FLAG_RECORD_SIZE:
            log.debug("EOF reading for flag record")
            raise SampleException("EOF reading for flag record")
        
        (valid_record, regex_velocity_record, 
          regex_end_velocity_record, format_unpack_velocity, 
          record_size) = self.parse_flag_record(record)

        ##
        ## If there is a valid Flag record, process the Time record.
        ##
        if valid_record:
            ##
            ## Read the Time record which is at the very end of the file.
            ## Note that we don't care if the number of bytes between the
            ## Flag record and the Time record is consistent with
            ## the flags from the Flag record.
            ##
            infile.seek(0 - TIME_RECORD_SIZE, 2)  # 2 = from end of file
            record = infile.read(TIME_RECORD_SIZE)
            times = self.parse_time_record(record)

            ##
            ## Restore the file to where it was before we stared reading it.
            ## 0 = from start of file.
            ##
            infile.seek(self._read_state[StateKey.POSITION], 0)  

        ##
        ## If the Flag record is invalid, we're done.
        ##
        else:
            ##
            ## Restore the file to where it was before we stared reading it.
            ## 0 = from start of file.
            ##
            infile.seek(self._read_state[StateKey.POSITION], 0)  
            log.debug("Invalid Flag record")
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
        self._state = state_obj
        self._read_state = state_obj
        ## log.debug('SET POSITION %d', self._read_state[StateKey.POSITION])

    def _increment_state(self, bytes_read):
        """
        Increment the parser state
        @param bytes_read The number of bytes just read
        """
        self._read_state[StateKey.POSITION] += bytes_read
        ## log.debug('INCR POSITION %d', self._read_state[StateKey.POSITION])

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

        while chunk is not None:
            ##
            ## Discard the Flag record since it has already been processed.
            ##
            if FLAG_RECORD_MATCHER.match(chunk):
                self._increment_state(FLAG_RECORD_SIZE)
            ##
            ## If we haven't reached the end of the velocity records,
            ## see if this next record is the last one (all zeroes).
            ##
            elif not self.end_of_velocity_records:
                velocity_end = self.velocity_end_record_matcher.match(chunk)
                self._increment_state(self.velocity_record_size)

                ##
                ## A velocity data record of all zeroes does not generate
                ## a data particle.
                ##
                if velocity_end:
                    self.end_of_velocity_records = True
                    ## log.debug("Match Velocity end test OK")
                else:
                    ##
                    ## It wasn't an end of velocity record.
                    ## Generate a data particle for this record and add
                    ## it to the end of the particles collected so far.
                    ##
                    velocity_fields = self.parse_velocity_record(chunk)
                    ### log.info('XXX %s XXX)', velocity_fields)

                    particle = self._extract_sample(
                      Vel3d_k__stc_imodemVelocityDataParticle,
                      None, velocity_fields, self.calculate_timestamp())

                    result_particles.append((particle,
                      copy.copy(self._read_state)))

            ##
            ## If we have read the end of velocity data records,
            ## the next record is the Time data record.
            ## Generate the data particle and
            ## add it to the end of the particles collected so far.
            ##
            else:
                time_fields = self.parse_time_record(chunk)
                if time_fields is not None:
                    ##
                    ## Convert the tuple to a list, add the number of
                    ## velocity records received (not counting the end of
                    ## Velocity record, and convert back to a tuple.
                    ##
                    time_list = list(time_fields)
                    time_list.append(self.calculate_record_number() - 1)
                    time_fields = tuple(time_list)
                    ### log.info('XXX %s XXX)', time_fields)
                    particle = self._extract_sample(
                      Vel3d_k__stc_imodemTimeDataParticle, 
                      None, time_fields, self.time_on)

                    ## log.debug("Time particle %s", particle.raw_data)
                    self._increment_state(TIME_RECORD_SIZE)
                    result_particles.append((particle,
                      copy.copy(self._read_state)))

            (timestamp, chunk, start, 
              end) = self._chunker.get_next_data_with_index()
            (nd_timestamp, 
              non_data) = self._chunker.get_next_non_data(clean=True)

        ## log.debug("Generated %d particles", len(result_particles))
        return result_particles

    ##
    ## This function parses the Flag record.
    ## A Flag record consists of 26 binary bytes, 
    ## with each byte being either 0 or 1.
    ## Each byte corresponds to a data item in the Velocity record.
    ## Then we use the received Flag record fields to override
    ## the expected flag fields.
    ## Returns:
    ##   True/False indicating whether or not the flag record is valid.
    ##   A regular expression based on the received flag fields,
    ##     (not expected flags) to be used in pattern matching.
    ##   A regular expression for detecting end of velocity records.
    ##   A format based on the flag fields, to be used to unpack the data.
    ##   The number of bytes expected in each velocity data record.
    ##
    def parse_flag_record(self, record):
        ##
        ## See if we've got a valid flag record.
        ##
        flag_record = FLAG_RECORD_MATCHER.match(record)
        if not flag_record:
            log.debug("Not a flag record")
            valid_flag_record = False
            regex_velocity_record = None
            regex_end_velocity_record = None
            format_unpack_velocity = None
            record_length = 0
        else:
            ##
            ## If the flag record is valid,
            ## interpret each field as a boolean value.
            ##
            valid_flag_record = True
            flags = struct.unpack(FLAG_FORMAT, 
              flag_record.group(0)[0:FLAG_RECORD_SIZE])
            ## log.debug("Flag record %s", flags)

            ##
            ## The format string for unpacking the velocity data record
            ## fields must be constructed based on which fields the Flag
            ## record indicates we'll be receiving.
            ## Start with the little endian symbol for the format.
            ## We also compute the record length for each velocity data 
            ## record, again based on the Flag record.
            ##
            format_unpack_velocity = '<'
            record_length = 0

            ##
            ## Check each field from the input Flag record.
            ##
            for x in range(0, FLAG_RECORD_SIZE):
                ##
                ## IDD says to indicate if received flags don't match the
                ## expected.  Currently there is no way to issue to a warning.
                ## Either the record is accepted or it isn't.
                ##
                vel3d_parameters[x][INDEX_ACTUAL_FLAG] = flags[x]

                ##
                ## If the flag field is True,
                ## increment the total number of bytes expected in each
                ## velocity data record and add the corresponding text to 
                ## the format.
                ##
                if flags[x]:
                    record_length += vel3d_parameters[x][INDEX_DATA_BYTES]
                    format_unpack_velocity = format_unpack_velocity + \
                      vel3d_parameters[x][INDEX_FORMAT]

            ##
            ## Create the velocity data record regular expression
            ## (some number of any hex digits)
            ## and the end of velocity data record indicator
            ## (the same number of all zeroes).
            ## Note that the backslash needs to be doubled because
            ## we're not using the b'' syntax.
            ##
            regex_velocity_record = "[\\x00-\\xFF]{%d}" % record_length
            regex_end_velocity_record = "[\\x00]{%d}" % record_length
            ## log.debug("Vel regex %s", regex_velocity_record)

        return valid_flag_record, regex_velocity_record, \
          regex_end_velocity_record, format_unpack_velocity, record_length

    ##
    ## This function parses a Time record and returns 2 32-bit numbers.
    ## A Time record consists of 8 bytes.
    ## Offset  Bytes  Format  Field
    ##  0      4      uint32  Time_on
    ##  4      4      uint32  Time_off
    ##
    def parse_time_record(self, record):
        time_record = TIME_RECORD_MATCHER.match(record)
        if not time_record:
            time_data = None
        else:
            time_data = struct.unpack(TIME_FORMAT, 
              time_record.group(0)[0:TIME_RECORD_SIZE])

        return time_data

    ##
    ## This function parses a velocity data record.
    ## A velocity data record consists of up to 42 bytes.
    ## Valid fields are indicated by the flag record.
    ## Offset  Bytes  Format  Field
    ##  0      6      byte    Time
    ##  6      2      uint    SoundSpeed
    ##  8      2      int     TempC
    ## 10      2      uint    Heading
    ## 12      2      int     Pitch
    ## 14      2      int     Roll
    ## 16      2      int     magX
    ## 18      2      int     magY
    ## 20      2      int     magZ
    ## 22      1      ubyte   Beams
    ## 23      1      ubyte   Cells
    ## 24      1      ubyte   Beam1
    ## 25      1      ubyte   Beam2
    ## 26      1      ubyte   Beam3
    ## 27      1      ubyte   Beam4
    ## 28      1      ubyte   Beam5
    ## 29      1      byte    VScale
    ## 30      2      int     Vel0
    ## 32      2      int     Vel1
    ## 34      2      int     Vel2
    ## 36      1      ubyte   Amp0
    ## 37      1      ubyte   Amp1
    ## 38      1      ubyte   Amp2
    ## 39      1      ubyte   Cor0
    ## 40      1      ubyte   Cor1
    ## 41      1      ubyte   Cor2
    ##
    def parse_velocity_record(self, record):
        velocity_record = self.velocity_record_matcher.match(record)
        if not velocity_record:
            velocity_fields = None
        else:
            velocity_fields = struct.unpack(self.velocity_format,
              velocity_record.group(0)[0:self.velocity_record_size])

        return velocity_fields

    def sieve_function(self, raw_data):        
        """        
        Sort through the raw data to extract blocks of data that 
        need processing.        
        This is needed instead of a regex because blocks are 
        identified by specific lengths in this binary file.        
        This algorithm assumes that the velocity data records are longer than
        the time record.  
        """        

        return_list = []     # array of tuples (start index, end index)
        return_list.append((0, FLAG_RECORD_SIZE))

        data_index = FLAG_RECORD_SIZE
        raw_data_len = len(raw_data)
        valid_match = True
 
        while data_index < raw_data_len and valid_match:
            end = data_index + self.velocity_record_size
            if self.velocity_record_matcher.match(raw_data[data_index:end]):
                return_list.append((data_index, end))
                data_index += self.velocity_record_size
            else:
                end = data_index + TIME_RECORD_SIZE
                if TIME_RECORD_MATCHER.match(raw_data[data_index:end]):
                    return_list.append((data_index, end))
                    data_index += TIME_RECORD_SIZE
                else:
                    valid_match = False

        return return_list

