#!/usr/bin/env python

"""
@package mi.dataset.parser.flord_l_wfp_sio_mule
@file marine-integrations/mi/dataset/parser/flord_l_wfp_sio_mule.py
@author Maria Lutz
@brief Parser for the flord_l_wfp_sio_mule dataset driver
Release notes:

Initial Release
"""

__author__ = 'Maria Lutz'
__license__ = 'Apache 2.0'

import copy
import re
import struct
import ntplib
import binascii
import gevent

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException, UnexpectedDataException
#from mi.dataset.parser.mflm import MflmParser, SIO_HEADER_MATCHER
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER # the names might change after emily finishes updating sio_mule_common.py
from mi.dataset.dataset_parser import BufferLoadingParser

E_HEADER_REGEX = b'(\x00\x01\x00{5,5}\x01\x00{7,7}\x01)([\x00-\xff]{8,8})' # E header regex for global sites
E_HEADER_MATCHER = re.compile(E_HEADER_REGEX)
STATUS_START_REGEX = b'\xff\xff\xff[\xfa-\xff]'
STATUS_START_MATCHER = re.compile(STATUS_START_REGEX)

SIO_HEADER_BYTES = 32
E_HEADER_BYTES = 24
E_GLOBAL_SAMPLE_BYTES = 30
STATUS_BYTES = 16
STATUS_BYTES_AUGMENTED = 18

class DataParticleType(BaseEnum):
    SAMPLE = 'flord_l_wfp_instrument'

class FlordLWfpSioMuleParserDataParticleKey(BaseEnum):
    # params collected for the flord_l_wfp_instrument stream
    RAW_SIGNAL_CHL = 'raw_signal_chl'
    RAW_SIGNAL_BETA = 'raw_signal_beta' # corresponds to 'ntu' from E file
    RAW_INTERNAL_TEMP = 'raw_internal_temp'
    WFP_TIMESTAMP = 'wfp_timestamp'

class FlordLWfpSioMuleParserDataParticle(DataParticle):
    """
    Class for parsing data from the flord_l_wfp_sio_mule data set
    """

    _data_particle_type = DataParticleType.SAMPLE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        
        if len(self.raw_data) != E_GLOBAL_SAMPLE_BYTES:
            raise SampleException("FlordLWfpSioMuleParserDataParticleKey: No regex match of parsed sample data: [%s]",
                                  self.raw_data)

        fields_prof = struct.unpack('>I f f f f f h h h', self.raw_data)     
        result = [self._encode_value(FlordLWfpSioMuleParserDataParticleKey.RAW_SIGNAL_CHL, fields_prof[6], int),
                  self._encode_value(FlordLWfpSioMuleParserDataParticleKey.RAW_SIGNAL_BETA, fields_prof[7], int),
                  self._encode_value(FlordLWfpSioMuleParserDataParticleKey.RAW_INTERNAL_TEMP, fields_prof[8], int),
                  self._encode_value(FlordLWfpSioMuleParserDataParticleKey.WFP_TIMESTAMP, fields_prof[0], int)]
        
        return result
    
class FlordLWfpSioMuleParser(SioMuleParser):
    
    #from adcps as example
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(FlordLWfpSioMuleParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function, 
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)
    
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
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        sample_count = 0
        
        while (chunk != None):   
            # Parse/match the SIO header
            sio_header_match = SIO_HEADER_MATCHER.match(chunk)               
                
            sample_count = 0       
            if sio_header_match.group(1) == 'WE':
                log.debug('read_state: %s', self._read_state)
                        
                # Parse/match the E file header     
                e_header_match = E_HEADER_MATCHER.search(chunk[SIO_HEADER_BYTES:SIO_HEADER_BYTES+E_HEADER_BYTES+1])
                
                if e_header_match:
                    payload = chunk[SIO_HEADER_BYTES+E_HEADER_BYTES+1:]
		    data_split = self.we_split_function(payload)
                    if data_split:
			for ii in range(0,len(data_split)):    
			    e_record = payload[data_split[ii][0]:data_split[ii][1]]
			    
                            if not STATUS_START_MATCHER.match(e_record[0:STATUS_BYTES]):				    
                                fields = struct.unpack('>I', e_record[0:4])
                                timestamp = float(fields[0])
                                self._timestamp = ntplib.system_to_ntp_time(timestamp)
			    
                                if len(e_record) == E_GLOBAL_SAMPLE_BYTES:
                                    sample = self._extract_sample(FlordLWfpSioMuleParserDataParticle,
			                                      None,
			                                      e_record,
			                                      self._timestamp)
				    if sample:
					# create particle
					result_particles.append(sample)
					sample_count += 1
                                    
                else: # no e header match
                    self._exception_callback(UnexpectedDataException("Found unexpected data."))

            self._chunk_sample_count.append(sample_count)    
	    (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        return result_particles

    def we_split_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        """	
        form_list = []
        raw_data_len = len(raw_data)	
	"""
	The Status messages can have an optional 2 bytes on the end, and since the
	rest of the data consists of relatively unformated packed binary records,
	detecting the presence of that optional 2 bytes can be difficult. The only
	pattern we have to detect is the STATUS_START field ( 4 bytes FF FF FF F[A-F]).
	We peel this appart by parsing backwards, using the end-of-record as an
	additional anchor point.
	"""
	# '-1' to remove the '\x03' end-of-record marker
	parse_end_point = raw_data_len - 1
        while parse_end_point > 0:
	    
	    # look for a status message at postulated message header position
	    
	    header_start = STATUS_BYTES_AUGMENTED	    
	    # look for an augmented status
            if STATUS_START_MATCHER.match(raw_data[parse_end_point-STATUS_BYTES_AUGMENTED:parse_end_point]):
		# A hit for the status message at the augmented offset
		# NOTE, we don't need the status messages and only deliver a stream of
		# samples to build_parsed_values
                parse_end_point = parse_end_point-STATUS_BYTES_AUGMENTED 
		
            # check if this is an unaugmented status
            elif STATUS_START_MATCHER.match(raw_data[parse_end_point-STATUS_BYTES:parse_end_point]):
		# A hit for the status message at the unaugmented offset
		# NOTE: same as above
                parse_end_point = parse_end_point-STATUS_BYTES	
            else:
		# assume if not a stat that hit above, we have a sample. Mis-parsing will result
		# in extra bytes at the end and a sample exception.
                form_list.append((parse_end_point-E_GLOBAL_SAMPLE_BYTES, parse_end_point))
                parse_end_point = parse_end_point-E_GLOBAL_SAMPLE_BYTES
 
            # if the remaining bytes are less than data sample bytes, all we might have left is a status sample
            if parse_end_point != 0 and parse_end_point < STATUS_BYTES and parse_end_point < E_GLOBAL_SAMPLE_BYTES  and parse_end_point < STATUS_BYTES_AUGMENTED:
		raise SampleException("Error sieving WE data, inferred sample/status alignment incorrect")
	    
	# Because we parsed this backwards, we need to reverse the list to deliver the data in the correct order    
	return_list = []    
	return_list = form_list[::-1]    
        log.debug("returning we sieve/split list %s", return_list)
        return return_list

 
    

    
    
   