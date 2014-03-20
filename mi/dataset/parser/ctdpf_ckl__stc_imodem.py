#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf_ckl__stc_imodem
@file marine-integrations/mi/dataset/parser/ctdpf_ckl__stc_imodem.py
@author cgoodrich
@brief Parser for the CTDPF_CKL__STC_IMODEM dataset driver
Release notes:

Initial Release
"""

##
## The CTDPF_CKL input file is a binary file.
## It consists of multiple records, each 11 bytes long,
## with the "end of profile" indicated by 11 bytes of all 1's,
## i.e. b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff'.
## Following the end of profile record is a time record.
## This time record has 8 bytes, the first 4 are instrument start time,
## the last 4 are instrument stop time. Both are in number of seconds
## since 01 January 1970 00:00:00 format. For CTDPF_CKL only the first 9
## bytes of the data records are used. These represent conductivity,
## temperature and pressure.
##

__author__ = 'cgoodrich'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.dataset_parser import BufferLoadingParser
import struct

SAMPLE_REGEX = b'([\x00-\xFF]{11})'
DATA_SAMPLE_MATCHER = re.compile(SAMPLE_REGEX)

# Marks the end of the profile - 11 bytes of 0xFF
EOP_REGEX = b'(\xFF{11})'
EOP_MATCHER = re.compile(EOP_REGEX)

TIME_RECORD_SIZE = 8                   # bytes
TIME_RECORD_REGEX = b'[\x00-\xFF]{8}'  # 8 bytes of any hex value
TIME_FORMAT = '>2I'                    # 2 32-bit unsigned integers big endian
TIME_RECORD_MATCHER = re.compile(TIME_RECORD_REGEX)

DATA_RECORD_SIZE = 11
SAMPLE_RATE = 1


class StateKey(BaseEnum):
    POSITION = "position"


class DataParticleType(BaseEnum):
    CTDPF_CKL_INST = 'Ctdpf_ckl__stc_imodemInstDataParticle'
    CTDPF_CKL_META = 'Ctdpf_ckl__stc_imodemMetaDataParticle'


class Ctdpf_ckl__stc_imodemMetaDataParticleKey(BaseEnum):
    TIMESTAMP = 'timestamp'
    WFP_TIME_ON = 'wfp_time_on'
    WFP_TIME_OFF = 'wfp_time_off'
    WFP_SAMPLES = 'wfp_number_samples'


class Ctdpf_ckl__stc_imodemInstDataParticleKey(BaseEnum):
    TIMESTAMP = 'timestamp'
    CONDUCTIVITY = 'conductivity'
    TEMPERATURE = 'temperature'
    PRESSURE = 'pressure'


class Ctdpf_ckl__stc_imodemMetaDataParticle(DataParticle):
    """
    Class for parsing CTDPF_CKL metadata from the WFB C file data
    """
    _data_particle_type = DataParticleType.CTDPF_CKL_META

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        """
        ##
        ## Generate the metadata particle.
        ##
        particle = [
            {
                DataParticleKey.VALUE_ID: Ctdpf_ckl__stc_imodemMetaDataParticleKey.TIMESTAMP,
                DataParticleKey.VALUE: ntplib.system_to_ntp_time(self.raw_data[0])
            },
            {
                DataParticleKey.VALUE_ID: Ctdpf_ckl__stc_imodemMetaDataParticleKey.WFP_TIME_ON,
                DataParticleKey.VALUE: self.raw_data[1]
            },
            {
                DataParticleKey.VALUE_ID: Ctdpf_ckl__stc_imodemMetaDataParticleKey.WFP_TIME_OFF,
                DataParticleKey.VALUE: self.raw_data[2]
            },
            {
                DataParticleKey.VALUE_ID: Ctdpf_ckl__stc_imodemMetaDataParticleKey.WFP_SAMPLES,
                DataParticleKey.VALUE: self.raw_data[3]
            }
        ]

        return particle

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this
        particle
        """
        if ((self.raw_data == arg.raw_data) and
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] ==
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                    arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            return False


class Ctdpf_ckl__stc_imodemInstDataParticle(DataParticle):
    """
    Class for parsing CTDPF_CKL instrument data from the WFB C file data
    """

    _data_particle_type = DataParticleType.CTDPF_CKL_INST
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        """

        particle = [
            {
                DataParticleKey.VALUE_ID: Ctdpf_ckl__stc_imodemInstDataParticleKey.CONDUCTIVITY,
                DataParticleKey.VALUE: self.raw_data[0]
            },
            {
                DataParticleKey.VALUE_ID: Ctdpf_ckl__stc_imodemInstDataParticleKey.TEMPERATURE,
                DataParticleKey.VALUE: self.raw_data[1]
            },
            {
                DataParticleKey.VALUE_ID: Ctdpf_ckl__stc_imodemInstDataParticleKey.PRESSURE,
                DataParticleKey.VALUE: self.raw_data[2]
            }
        ]

        return particle

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        if ((self.raw_data == arg.raw_data) and
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] ==
             arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                    arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            return False


class Ctdpf_ckl__stc_imodemParser(BufferLoadingParser):

    time_on = 0
    time_off = 0
    particle_timestamp = 0
    _timestamp = 0.0

    def __init__(self,
                 config,
                 infile,
                 state,
                 state_callback,
                 publish_callback,
                 exception_callback):
        ##
        ## From the input file, get the parameters which define the inputs.
        ## Update the file position with the number of bytes which were read.
        ##
        time_fields = self.get_file_parameters(infile)

        ##
        ## Save the timestamp that will go into the data particles.
        ##
        self.time_on = int(time_fields[0])
        self._timestamp = 0.0
        self._read_state = state
        self.time_off = int(time_fields[1])
        self.particle_timestamp = self.time_on
        self._record_buffer = []

        super(Ctdpf_ckl__stc_imodemParser, self).__init__(config,
                                                          infile,
                                                          state,
                                                          self.sieve_function,
                                                          state_callback,
                                                          publish_callback,
                                                          exception_callback)

    def calculate_record_number(self):
        ##
        ## This function calculates the record number
        ## based on the current position in the file
        ## and the size of each data record.
        ##
        return self._read_state[StateKey.POSITION] / DATA_RECORD_SIZE

    def calculate_timestamp(self):
        ##
        ## This function calculates the timestamp
        ## based on the current position in the file
        ## and the size of each velocity data record.
        ##
        return ((self.calculate_record_number() - 1) * SAMPLE_RATE) + self.time_on

    def get_file_parameters(self, infile):
        ##
        ## Read the Time record which is at the very end of the file.
        ##
        infile.seek(0 - TIME_RECORD_SIZE, 2)  # 2 = from end of file
        record = infile.read(TIME_RECORD_SIZE)
        time_record = TIME_RECORD_MATCHER.match(record)
        
        # Return the file position back to the beginning of the file
        infile.seek(0, 0)
        
        if not time_record:
            time_data = None
        else:
            time_data = struct.unpack(TIME_FORMAT, time_record.group(0)[0:TIME_RECORD_SIZE])

        return time_data

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

    def _increment_state(self, bytes_read):
        """
        Increment the parser state
        @param bytes_read Where we're at in the file
        """
        self._read_state[StateKey.POSITION] += bytes_read

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
        parsing, plus the state. An empty list of nothing was parsed.
        @throws SampleException If there is a problem with sample creation
        """
        expecting_timestamp = False
        processing_is_not_complete = True
        result_particles = []
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        while chunk is not None:
            data_match = DATA_SAMPLE_MATCHER.match(chunk)
            eop_match = EOP_MATCHER.match(chunk)
            time_match = TIME_RECORD_MATCHER.match(chunk)
            if data_match and not eop_match:
                # Particle-ize the instrument data received, return the record
                bytes_read = DATA_RECORD_SIZE
                inst_fields = self.parse_inst_record(chunk)
                timestamp = self.calculate_timestamp()
                ntp_time = ntplib.system_to_ntp_time(timestamp)
                particle = self._extract_sample(Ctdpf_ckl__stc_imodemInstDataParticle, None, inst_fields, ntp_time)
                if particle:
                    # Create particle
                    log.trace("Extracting sample chunk %s with read_state: %s", particle, self._read_state)
                    self._increment_state(bytes_read)
                    result_particles.append((particle, copy.copy(self._read_state)))
            elif eop_match:
                # We're not going to produce a particle but we do want to increment the file position
                expecting_timestamp = True
                bytes_read = DATA_RECORD_SIZE
                self._increment_state(bytes_read)
            elif time_match:
                if not expecting_timestamp:
                    raise SampleException("Improperly formatted input file")

                # Particle-ize the metadata received, return the record
                bytes_read = TIME_RECORD_SIZE
                metadata_fields = self.parse_metadata_record(chunk)
                timestamp = self.calculate_timestamp()
                ntp_time = ntplib.system_to_ntp_time(timestamp)
                particle = self._extract_sample(Ctdpf_ckl__stc_imodemMetaDataParticle, None, metadata_fields, ntp_time)
                if particle:
                    # Create particle
                    log.trace("Extracting sample chunk %s with read_state: %s", particle, self._read_state)
                    self._increment_state(bytes_read)
                    result_particles.append((particle, copy.copy(self._read_state)))
                    
                processing_is_not_complete = False
                
            if processing_is_not_complete:
                (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            else:
                ##
                ## This has to be screwed up, why do I need this?
                ##
                chunk = None

        return result_particles

    def parse_inst_record(self, record):
        """
        An instrument data record was found, unpack it
        """
        inst_record = DATA_SAMPLE_MATCHER.match(record)
        if not inst_record:
            inst_fields = None
        else:
            inst_fields = struct.unpack('>I', '\x00' + record[0:3]) + \
                struct.unpack('>I', '\x00' + record[3:6]) + \
                struct.unpack('>I', '\x00' + record[6:9])

        return inst_fields

    def parse_metadata_record(self, record):
        """
        A time record was found, build metadata
        """
        time_record = TIME_RECORD_MATCHER.match(record)
        time_data = struct.unpack(TIME_FORMAT, time_record.group(0)[0:TIME_RECORD_SIZE])
        number_of_samples = (self._read_state[StateKey.POSITION] - DATA_RECORD_SIZE) / DATA_RECORD_SIZE
        
        metadata_fields = time_data[0], time_data[1], number_of_samples

        return metadata_fields

    def sieve_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        This is needed instead of a regex because blocks are identified by position
        in this binary file.
        """
        return_list = []     # array of tuples (start index, end index)
        start_index = 0
        raw_data_len = len(raw_data)

        while start_index < raw_data_len:
            end_index = start_index + DATA_RECORD_SIZE
            
            if DATA_SAMPLE_MATCHER.match(raw_data[start_index:end_index]):
                return_list.append((start_index, end_index))
                start_index += DATA_RECORD_SIZE
            else:
                end_index = start_index + TIME_RECORD_SIZE
                return_list.append((start_index, end_index))
                start_index += TIME_RECORD_SIZE
                
        return return_list
