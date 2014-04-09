#!/usr/bin/env python

"""
@package mi.dataset.parser.wfp_c_file_common
@file marine-integrations/mi/dataset/parser/wfp_c_file_common.py
@author Emily Hahn
@brief Parser for the c file type for the wfp
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import struct

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException

from mi.dataset.dataset_parser import BufferLoadingParser

EOP_REGEX = b'\xFF{11}([\x00-\xFF]{8})'
EOP_MATCHER = re.compile(EOP_REGEX)

DATA_RECORD_BYTES = 11
TIME_RECORD_BYTES = 8
FOOTER_BYTES = DATA_RECORD_BYTES + TIME_RECORD_BYTES

class StateKey(BaseEnum):
    POSITION = 'position' # holds the file position
    TIMESTAMP = 'timestamp' # holds the timestamp
    RECORDS_READ = 'records_read' # holds the number of records read so far
    METADATA_SENT = 'metadata_sent' # holds a flag indicating if the footer has been sent

class WfpMetadataParserDataParticleKey(BaseEnum):
    WFP_TIME_ON = 'wfp_time_on'
    WFP_TIME_OFF = 'wfp_time_off'
    WFP_NUMBER_SAMPLES = 'wfp_number_samples'

class WfpCFileCommonParser(BufferLoadingParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 filesize,
                 *args, **kwargs):
        self._start_time = 0.0
        self._time_increment = 0.0
        self._filesize = filesize
        if filesize < FOOTER_BYTES:
            raise SampleException('File must be at least %d bytes to read the timestamp' % FOOTER_BYTES)
        self._read_state = {StateKey.POSITION: 0,
                            StateKey.TIMESTAMP: 0.0,
                            StateKey.RECORDS_READ: 0,
                            StateKey.METADATA_SENT: False}
        super(WfpCFileCommonParser, self).__init__(config,
                                                   stream_handle,
                                                   state,
                                                   self.sieve_function,
                                                   state_callback,
                                                   publish_callback,
                                                   exception_callback,
                                                   *args, **kwargs)

        # need to read the footer every time to calculate start time and time increment
        self.read_footer()
        if state:
            self.set_state(state)

    def sieve_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        This is needed instead of a regex because blocks are identified by position
        in this binary file.
        @param raw_data The raw data read from the file
        """
        data_index = 0
        return_list = []
        raw_data_len = len(raw_data)

        while data_index < raw_data_len:
            # check if this is a status or data sample message
            if EOP_MATCHER.match(raw_data[data_index:data_index+DATA_RECORD_BYTES+TIME_RECORD_BYTES]):
                # do not return this record as chunk it marks the end of all chunks
                break
            else:
                return_list.append((data_index, data_index + DATA_RECORD_BYTES))
                data_index += DATA_RECORD_BYTES

            # if the remaining bytes are less than the data sample bytes, we will just have the
            # timestamp which is parsed in __init__
            if (raw_data_len - data_index) < DATA_RECORD_BYTES:
                break
        return return_list

    def extract_metadata_particle(self, raw_data, timestamp):
        """
        Class for extracting metadata for a particular data particle, need to override this 
        """
        ##something like this:
        #sample = self._extract_sample(WfpMetadataParserDataParticle, None, raw_data, timestamp)
        #return sample
        raise NotImplementedError("extract_metadata_particle must be overridden")

    def extract_data_particle(self, raw_data, timestamp):
        """
        Class for extracting the data sample data particle, need to override this 
        """
        ##something like this:
        #sample = self._extract_sample(DofstKWfpParserDataParticle, None, raw_data, timestamp)
        #return sample
        raise NotImplementedError("extract_data_particle must be overridden")

    def read_footer(self):
        """
        Read the footer of the file including the end of profile marker (a record filled with \xFF), and
        the on and off timestamps for the profile.  Use these to calculate the time increment, which is
        needed to be able to calculate the timestamp for each data sample record.
        @throws SampleException if the number of samples is not an even integer
        """
        pad_bytes = 10
        # seek backwards from end of file, give us extra 10 bytes padding in case 
        # end of profile / timestamp is not right at the end of the file
        if self._filesize > (FOOTER_BYTES + pad_bytes):
            self._stream_handle.seek(-(FOOTER_BYTES+pad_bytes), 2)
        else:
            # if this file is too short, use a smaller number of pad bytes
            pad_bytes = self._filesize - FOOTER_BYTES
            self._stream_handle.seek(0)

        footer = self._stream_handle.read(FOOTER_BYTES+pad_bytes)
        # make sure we are at the end of the profile marker
        match = EOP_MATCHER.search(footer)
        if match:
            timefields = struct.unpack('>II', match.group(1))
            self._start_time = int(timefields[0])
            end_time = int(timefields[1])
            extra_end_bytes = pad_bytes - match.start(0)
            number_samples = float(self._filesize - FOOTER_BYTES - extra_end_bytes) / float(DATA_RECORD_BYTES)
            if number_samples > 0:
                self._time_increment = float(end_time - self._start_time) / number_samples
            else:
                self._time_increment = 0.0

            if not number_samples.is_integer():
                raise SampleException("File does not evenly fit into number of samples")
            if not self._read_state[StateKey.METADATA_SENT]:
                # only need to create the particle if it has not been sent previously
                timestamp = float(ntplib.system_to_ntp_time(self._start_time))
                sample = self.extract_metadata_particle((match.group(1), number_samples), timestamp)
                if sample:
                    self._saved_metadata = sample
            # reset the file handle to the beginning of the file
            self._stream_handle.seek(0)
        else:
            raise SampleException("Unable to find end of profile and timestamps, this file is no good!")

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. 
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not (StateKey.POSITION in state_obj) or not \
        (StateKey.TIMESTAMP in state_obj) or not \
        (StateKey.RECORDS_READ in state_obj) or not \
        (StateKey.METADATA_SENT in state_obj):
            raise DatasetParserException("Invalid state keys")
        self._chunker.clean_all_chunks()
        self._record_buffer = []
        self._saved_header = None
        self._timestamp = state_obj[StateKey.TIMESTAMP]
        self._state = state_obj
        self._read_state = state_obj
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment, timestamp, records_read):
        """
        Increment the parser state
        @param increment the number of bytes to increment the file position 
        @param timestamp The timestamp completed up to that position
        @param records_read The number of new records that have been read
        """
        self._timestamp = timestamp
        self._read_state[StateKey.TIMESTAMP] = timestamp
        self._read_state[StateKey.POSITION] += increment
        self._read_state[StateKey.RECORDS_READ] += records_read

    def calc_timestamp(self, record_number):
        """
        calculate the timestamp for a specific record
        @param record_number The number of the record to calculate the timestamp for
        @retval A floating point NTP64 formatted timestamp
        """
        timestamp = self._start_time + (self._time_increment * record_number)
        return float(ntplib.system_to_ntp_time(timestamp))

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """     
        result_particles = []
        
        if not self._read_state[StateKey.METADATA_SENT] and not self._saved_metadata is None:
            self._read_state[StateKey.METADATA_SENT] = True
            result_particles.append((self._saved_metadata, copy.copy(self._read_state)))

        (timestamp, chunk) = self._chunker.get_next_data()

        while (chunk != None):
            # particle-ize the data block received, return the record
            timestamp = self.calc_timestamp(self._read_state[StateKey.RECORDS_READ])
            sample = self.extract_data_particle(chunk, timestamp)
            if sample:
                # create particle
                self._increment_state(DATA_RECORD_BYTES, timestamp, 1)
                result_particles.append((sample, copy.copy(self._read_state)))

            (timestamp, chunk) = self._chunker.get_next_data()

        return result_particles