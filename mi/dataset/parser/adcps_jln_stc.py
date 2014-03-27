#!/usr/bin/env python

"""
@package mi.dataset.parser.adcps_jln_stc
@file marine-integrations/mi/dataset/parser/adcps_jln_stc.py
@author Maria Lutz
@brief Parser for the ADCPS_JLN__stc_imodem dataset driver
Release notes:

Initial Release
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import struct
import time
import binascii
import calendar

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import BinaryChunker
from functools import partial
from dateutil import parser

# *** Defining regexes for this parser ***
HEADER_REGEX = b'#UIMM Status.+DateTime: (\d{8}\s\d{6}).+#ID=(\d+).+#SN=(\d+).+#Volts=(\d+\.\d{2}).+#Records=(\d+).+#Length=(\d+).+#Events=(\d+).+UIMM Data\r\n'
HEADER_MATCHER = re.compile(HEADER_REGEX, re.DOTALL)

FOOTER_REGEX = b'#End UIMM Data, (\d+) samples written\r\n'
FOOTER_MATCHER = re.compile(FOOTER_REGEX)

HEADER_FOOTER_REGEX =  b'#UIMM Status.+DateTime: (\d{8}\s\d{6}).+#ID=(\d+).+#SN=(\d+).+#Volts=(\d+\.\d{2}).+#Records=(\d+).+#Length=(\d+).+#Events=(\d+).+UIMM Data\r\n#End UIMM Data, (\d+) samples written\r\n'
HEADER_FOOTER_MATCHER = re.compile(HEADER_FOOTER_REGEX, re.DOTALL)

DATA_REGEX = b'Record\[\d+\]:([\x00-\xFF]+?)(Record|#End U)'
DATA_MATCHER = re.compile(DATA_REGEX)
DATA_REGEX_B = b'Record\[\d+\]:([\x00-\xFF]+)'
DATA_MATCHER_B = re.compile(DATA_REGEX_B)

RX_FAILURE_REGEX = b'Record\[\d+\]:ReceiveFailure'
RX_FAILURE_MATCHER = re.compile(RX_FAILURE_REGEX)

HEADER_BYTES = 1024 
FOOTER_BYTES = 1024

class DataParticleType(BaseEnum):
    ADCPS_JLN_INS = 'adcps_jln_stc_instrument'
    ADCPS_JLN_META = 'adcps_jln_stc_metadata'

class Adcps_jln_stc_instrumentParserDataParticleKey(BaseEnum):
    # params collected for adcps_jln_stc_instrument stream:
    ADCPS_JLN_RECORD = 'adcps_jln_record'
    ADCPS_JLN_NUMBER = 'adcps_jln_number'
    ADCPS_JLN_UNIT_ID = 'adcps_jln_unit_id'
    ADCPS_JLN_FW_VERS = 'adcps_jln_fw_vers'
    ADCPS_JLN_FW_REV = 'adcps_jln_fw_rev'
    ADCPS_JLN_YEAR = 'adcps_jln_year'
    ADCPS_JLN_MONTH = 'adcps_jln_month'
    ADCPS_JLN_DAY = 'adcps_jln_day'
    ADCPS_JLN_HOUR = 'adcps_jln_hour'
    ADCPS_JLN_MINUTE = 'adcps_jln_minute'
    ADCPS_JLN_SECOND = 'adcps_jln_second'
    ADCPS_JLN_HSEC = 'adcps_jln_hsec'
    ADCPS_JLN_HEADING = 'adcps_jln_heading'
    ADCPS_JLN_ROLL = 'adcps_jln_roll'
    ADCPS_JLN_TEMP = 'adcps_jln_temp'
    ADCPS_JLN_PRESSURE = 'adcps_jln_pressure'
    ADCPS_JLN_STARTBIN = 'adcps_jln_startbin'
    ADCPS_JLN_BINS = 'adcps_jln_bins'
    ADCPS_JLN_VEL_ERROR = 'adcps_jln_vel_error'
    ADCPS_JLN_VEL_UP = 'adcps_jln_vel_up'
    ADCPS_JLN_VEL_NORTH = 'adcps_jln_vel_north'
    ADCPS_JLN_VEL_EAST = 'adcps_jln_vel_east'

class StateKey(BaseEnum):
    POSITION = "position"

class Adcps_jln_stc_instrumentParserDataParticle(DataParticle):
    """
    Class for parsing data from the Adcps_jln_stc data set
    """
    _data_particle_type = DataParticleType.ADCPS_JLN_INS
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        
        match = DATA_MATCHER.search(self.raw_data)
            
        if not match:
            raise SampleException("Adcps_jln_stcParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:
            asciiFields = struct.unpack('<13s', match.group(0)[0:12]) 
            asciiRecordNumber = int(asciiFields[7:10]) 
            match = match.strip('Record\[....\]:') 
            fields = struct.unpack('<HhIBBBdhhhhIbBB', match.group(0)[0:34])
            
            # ID field should always be 7F6E
            log.debug('ID field: %s', fields[0])
            if fields[0] != '0x7F6E':
                raise ValueError('ID field does not equal 7F6E.')
            
            num_bytes = fields[1]
            if len(match.group(0)) - 2 != num_bytes:
                raise ValueError('num bytes %d does not match data length %d'
                          % (num_bytes, len(match.group(0))))
            
            nbins = fields[14]
            if len(match.group(0)) < (36+(nbins*8)):
                raise ValueError('Number of bins %d does not fit in data length %d'%(nbins,
                                                                                     len(match.group(0))))
            date_fields = struct.unpack('HBBBBBB', match.group(0)[11:19])
            
            # create a string with the right number of shorts to unpack
            struct_format = '>'
            for i in range(0,nbins):
                struct_format = struct_format + 'h'
            
            bin_len = nbins*2
            adcps_jln_vel_error = struct.unpack(struct_format, match.group(0)[34:[34+bin_len]])
            adcps_jln_vel_up = struct.unpack(struct_format, match.group(0)[(34+bin_len):(34+(bin_len*2))])
            adcps_jln_vel_north = struct.unpack(struct_format, match.group(0)[(34+(bin_len*2)):(34+(bin_len*3))])
            adcps_jln_vel_east = struct.unpack(struct_format, match.group(0)[(34+(bin_len*3)):(34+(bin_len*4))])        
                          
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))
        result = [{DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_RECORD,
                   DataParicleKey.VALUE: asciiRecordNumber},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_NUMBER,
                 DataParicleKey.VALUE: int(fields[2])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_UNIT_ID,
                 DataParicleKey.VALUE: int(fields[3])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_FW_VERS,
                 DataParicleKey.VALUE: int(fields[4])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_FW_REV,
                 DataParicleKey.VALUE: (fields[5])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_YEAR,
                 DataParicleKey.VALUE: int(date_fields[0])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_MONTH,
                 DataParicleKey.VALUE: int(date_fields[1])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_DAY,
                 DataParicleKey.VALUE: int(date_fields[2])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_HOUR,
                 DataParicleKey.VALUE: int(date_fields[3])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_MINUTE,
                 DataParicleKey.VALUE: int(date_fields[4])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_SECOND,
                 DataParicleKey.VALUE: int(date_fields[5])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_HSEC,
                 DataParicleKey.VALUE: int(date_fields[6])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_HEADING,
                 DataParicleKey.VALUE: int(fields[7])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_ROLL,
                 DataParicleKey.VALUE: int(fields[9])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_TEMP,
                 DataParicleKey.VALUE: int(fields[10])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_PRESSURE,
                 DataParicleKey.VALUE: int(fields[11])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_STARTBIN,
                 DataParicleKey.VALUE: int(fields[13])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_BINS,
                 DataParicleKey.VALUE: int(fields[14])},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_VEL_ERROR,
                 DataParicleKey.VALUE: list(adcps_jln_vel_error)},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_VEL_UP,
                 DataParicleKey.VALUE: list(adcps_jln_vel_up)},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_VEL_NORTH,
                 DataParicleKey.VALUE: list(adcps_jln_vel_north)},
                {DataParticleKey.VALUE_ID: Adcps_jln_stc_instrumentParserDataParticleKey.ADCPS_JLN_VEL_EAST,
                 DataParicleKey.VALUE: list(adcps_jln_vel_east)},]
        
        return result

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
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            return False
        
    @staticmethod
    def unpack_date(data):
        fields = struct.unpack('HBBBBBB', data)
        zulu_ts = "%04d-%02d-%02dT%02d:%02d:%02d.%02dZ" % (
            fields[0], fields[1], fields[2], fields[3],
            fields[4], fields[5], fields[6])
        return zulu_ts
    
class Adcps_jln_stc_metadataParserDataParticleKey(BaseEnum):
    # params collected for adcps_jln_stc_metatdata stream:
    ADCPS_JLN_TIMESTAMP = 'adcps_jln_timestamp'
    ADCPS_JLN_ID = 'adcps_jln_id'
    ADCPS_JLN_SERIAL_NUMBER = 'adcps_jln_serial_number'
    ADCPS_JLN_VOLTS = 'adcps_jln_volts'
    ADCPS_JLN_RECORDS = 'adcps_jln_records'
    ADCPS_JLN_LENGTH = 'adcps_jln_length'
    ADCPS_JLN_EVENTS = 'adcps_jln_events'
    ADCPS_JLN_SAMPLES_WRITTEN = 'adcps_jln_samples_written'
    
class Adcps_jln_stc_metadataParserDataParticle(DataParticle):
    _data_particle_type = DataParticleType.ADCPS_JLN_META
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = HEADER_FOOTER_MATCHER.search(self.raw_data) 
        if not match:
            raise SampleException("Adcps_jln_stc_metadataParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:
            timestamp = match.group(1)   
            id_number = int(match.group(2))
            serial_number = int(match.group(3))
            voltage = float(match.group(4))  # this needs to be output with two decimal places
            num_records = int(match.group(5))
            length = int(match.group(6))
            num_events = int(match.group(7))
            samples_written = int(match.group(8))
    
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))
        result = [{DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_TIMESTAMP,
                        DataParicleKey.VALUE: timestamp},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_ID,
                     DataParicleKey.VALUE: id_number},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_SERIAL_NUMBER,
                     DataParicleKey.VALUE: serial_number},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_VOLTS,
                     DataParicleKey.VALUE: voltage},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_RECORDS,
                     DataParicleKey.VALUE: num_records},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_LENGTH,
                     DataParicleKey.VALUE: length},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_EVENTS,
                     DataParicleKey.VALUE: num_events},
                    {DataParticleKey.VALUE_ID: Adcps_jln_stc_metadataParserDataParticleKey.ADCPS_JLN_SAMPLES_WRITTEN,
                     DataParicleKey.VALUE: samples_written}]
            
        return result

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
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            return False


class Adcps_jln_stcParser(BufferLoadingParser):
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        self._saved_header = None
        self._timestamp = 0.0 # need this? yes!
        self._record_buffer = [] # holds tuples of (record, state)`
        self._read_state = {StateKey.POSITION: 0}
        super(Adcps_jln_stcParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function, 
                                          state_callback,
                                          publish_callback,
                                          *args,
                                          **kwargs)
        if state:
	    self.set_state(state)
	    if state[StateKey.POSITION] == 0:
		self._parse_header()
	else:
	    self._parse_header()     
    
    def set_state(self, state_obj):
        """
        initialize the state
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not (StateKey.POSITION in state_obj):
            raise DatasetParserException("Invalid state keys")
	self._chunker.clean_all_chunks()
	self._record_buffer = []
	self._saved_header = None
        self._state = state_obj
        self._read_state = state_obj
        self._stream_handle.seek(state_obj[StateKey.POSITION])
        
    def sieve_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        @param raw_data The raw data to search
        @retval list of matched start,end index found in raw_data
        """
        return_list = []
        st_idx = 0
        while st_idx < len(raw_data): 
            # Find a match, then advance
            match = DATA_MATCHER.match(raw_data[st_idx:])
            if match:
                end_packet_idx = match.end(0) - 6 + st_idx # string "Record" is length 6
                
                if end_packet_idx < len(raw_data):
                    # Skip record if "ReceiveFailure" marking exists.
                    match_rx_failure = RX_FAILURE_MATCHER.match(raw_data[st_idx:])
                    if not match_rx_failure and self.compare_checksum(match.group(1)[0:-2]):
                        return_list.append((match.start(0)+ st_idx, end_packet_idx))
                    if match_rx_failure:
                        log.debug("Record is marked with ReceiveFailure. Skipping record.")
                    if  not self.compare_checksum(match.group(1)[0:-2]):
                        # Extra noise is possible, so when checksums do not match, we log a message and continue parsing.
                        log.debug("Calculated checksum != received checksum")                     
                st_idx = end_packet_idx         
            else:
                st_idx += 1    
        return return_list
    
    def compare_checksum(self, raw_bytes):
        rcv_chksum = struct.unpack('<H', raw_bytes[-2:])
        calc_chksum = self.calc_checksum(raw_bytes[:-2])
        if rcv_chksum[0] == calc_chksum:
            return True
        return False
    
    def calc_checksum(self, raw_bytes):
        n_bytes = len(raw_bytes)
        # unpack raw bytes into unsigned chars
        unpack_str = '<'
        for i in range(0, n_bytes):
            unpack_str = unpack_str + 'B'
        fields = struct.unpack(unpack_str, raw_bytes)
        sum_fields = sum(fields)
        # since we are summing as unsigned short, limit range to 0 to 65535
        while sum_fields > 65535:
            sum_fields -= 65536
        return sum_fields

    def _parse_header(self):
        """
        Parse required parameters from the header and the footer.
        """
	# read the first bytes from the file
	header = self._stream_handle.read(HEADER_BYTES)

        # read the last 1024 bytes from the file       
        self._stream_handle.seek(-FOOTER_BYTES,2)
        footer = self._stream_handle.read() 
        footer_match = FOOTER_MATCHER.search(footer)
        
	# parse the header to get the timestamp
        if HEADER_MATCHER.search(header):
            header_match = HEADER_MATCHER.search(header)
            self._stream_handle.seek(len(header_match.group(0)))        
            timestamp_struct = time.strptime(header_match.group(1), "%Y%m%d %H%M%S") 
            timestamp_s = calendar.timegm(timestamp_struct) 
            self._timestamp = float(ntplib.system_to_ntp_time(timestamp_s))
            
            header_footer = header_match.group(0) + footer_match.group(0) 
            
            sample = self._extract_sample(Adcps_jln_stc_metadataParserDataParticle, HEADER_FOOTER_MATCHER,
                                          header_footer, self._timestamp)  
            
            if sample:
                # increment by the length of the matched header and save the header          
		self._increment_state(len(header_match.group(0)))
                self._saved_header = (sample, copy.copy(self._read_state))
        else:
            raise SampleException("File header does not match header regex")
        
    def _increment_state(self, increment):
        """
        Increment the parser position by the given increment in bytes.
        This indicates what has been read from the file, not what has
        been published.
        @ param increment number of bytes to increment parser position
        """
        self._read_state[StateKey.POSITION] += increment
        

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        
        # header gets read in initialization, but need to send it back from parse_chunks
	if self._saved_header:
	    result_particles.append(self._saved_header)
	    self._saved_header = None
        
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        non_data_flag = False
        if non_data is not None and non_end <= start:
            log.debug('start setting non_data_flag')
            non_data_flag = True
    
        while (chunk != None):
            
            data_match = DATA_MATCHER_B.match(chunk)
            if data_match:
                
                # pull out the date string from the data
                date_str = Adcps_jln_stc_instrumentParserDataParticle.unpack_date(data_match.group(1)[11:19])
                
                # convert to ntp
                converted_time = float(parser.parse(date_str).strftime("%s.%f"))
                adjusted_time = converted_time - time.timezone
                self._timestamp = ntplib.system_to_ntp_time(adjusted_time)
                # round to ensure the timestamps match
                self._timestamp = round(self._timestamp*100)/100
                log.debug("Converted time \"%s\" (unix: %10.9f) into %10.9f", date_str, adjusted_time, self._timestamp)
                
                # particle-ize the data block received, return the record
                # set timestamp here, converted to ntp64. pull out timestamp for this record               
                sample = self._extract_sample(Adcps_jln_stc_instrumentParserDataParticle, DATA_MATCHER_B, chunk, self._timestamp)
                       
                if sample:
                    # create particle
                    log.trace("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)
                    if non_data == None:
                        non_data_length = 0
                    else:
                        non_data_length = len(non_data)
                    self._increment_state(len(chunk) + non_data_length)
                    result_particles.append((sample, copy.copy(self._read_state)))
                    
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

            # need to set a flag in case we read a chunk not matching the instrument ID and overwrite the non_data                    
            if non_data is not None and non_end <= start:
                log.debug('setting non_data_flag')
                non_data_flag = True
                
        return result_particles



