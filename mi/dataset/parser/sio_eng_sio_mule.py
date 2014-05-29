#!/usr/bin/env python

"""
@package mi.dataset.parser.sio_eng_sio_mule
@file marine-integrations/mi/dataset/parser/sio_eng_sio_mule.py
@author Mike Nicoletti
@brief Parser for the sio_eng_sio_mule dataset driver
Release notes:

Starting SIO Engineering Driver
"""

__author__ = 'Mike Nicoletti'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import struct

from datetime import datetime

from mi.dataset.test.test_parser import ParserUnitTestCase
from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException, UnexpectedDataException

from dateutil import parser
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER



# *** Need to define data regex for this parser ***
#ENG_REGEX =  r'\x01CS.+\n([-\d]+\.\d+) ([-\d]+\.\d+) ([-\d]+) ([-\d]+) ([-\d]+)\n'
#ENG_REGEX = r'([-\d]+\.\d+) ([-\d]+\.\d+) ([-\d]+) ([-\d]+) ([-\d]+)\n'
ENG_REGEX = r'\x01CS([0-9]{5})[0-9]{2}_[0-9A-Fa-f]{4}[a-zA-Z]([0-9A-Fa-f]{8})_'\
            '[0-9A-Fa-f]{2}_[0-9A-Fa-f]{4}\x02\n([-\d]+\.\d+) '\
            '([-\d]+\.\d+) ([-\d]+) ([-\d]+) ([-\d]+)\n'

ENG_MATCHER = re.compile(ENG_REGEX)


class DataParticleType(BaseEnum):
    SAMPLE = 'sio_eng_sio_mule_parsed'

class SioEngSioMuleParserDataParticleKey(BaseEnum):
    # sio_eng_control_status
    SIO_CONTROLLER_ID = "controller_id"
    SIO_CONTROLLER_TIMESTAMP = "controller_timestamp"
    SIO_VOLTAGE_STRING = 'voltage_string'
    SIO_TEMPERATURE_STRING = 'temperature_string'
    SIO_ON_TIME = 'on_time'
    SIO_NUMBER_OF_WAKEUPS = 'number_of_wakeups'
    SIO_CLOCK_DRIFT = 'clock_drift'
    

class SioEngSioMuleParserDataParticle(DataParticle):
    """
    Class for parsing data from the sio_eng_sio_mule data set
    """

    _data_particle_type = DataParticleType.SAMPLE
    @staticmethod
    def encode_int_16(hex_str):
        return int(hex_str, 16)
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        match = ENG_MATCHER.match(self.raw_data)
        # Example Output ('1236501', '0018u51EC763C', '04', '8D91', '18.95', '15.9', '1456', '308', '-2')
        if not match:
            raise SampleException("SioEngSioMuleParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)

        result = [self._encode_value(SioEngSioMuleParserDataParticleKey.SIO_CONTROLLER_ID, match.group(1), int),
                  self._encode_value(SioEngSioMuleParserDataParticleKey.SIO_CONTROLLER_TIMESTAMP,
                                    match.group(2), SioEngSioMuleParserDataParticle.encode_int_16),
                  self._encode_value(SioEngSioMuleParserDataParticleKey.SIO_VOLTAGE_STRING, match.group(3), float),
                  self._encode_value(SioEngSioMuleParserDataParticleKey.SIO_TEMPERATURE_STRING, match.group(4), float),
                  self._encode_value(SioEngSioMuleParserDataParticleKey.SIO_ON_TIME, match.group(5), int),
                  self._encode_value(SioEngSioMuleParserDataParticleKey.SIO_NUMBER_OF_WAKEUPS, match.group(6), int),
                  self._encode_value(SioEngSioMuleParserDataParticleKey.SIO_CLOCK_DRIFT, match.group(7), int)]
        
        # Print Particle
        log.debug("SIO_CONTROLLER_ID: %d SIO_CONTROLLER_TIMESTAMP: %s SIO_VOLTAGE: %f SIO_TEMP: %f \n" \
                  "SIO_CONTROLLER_ON_TIME: %d SIO_CONTROLLER_WAKEUPS: %d SIO_CONTROLLER_DRIFT: %d",int(match.group(1)),
                    match.group(2), float(match.group(3)), float(match.group(4)), int(match.group(5)), int(match.group(6)), int(match.group(7)))

        return result

class SioEngSioMuleParser(SioMuleParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(SioEngSioMuleParser, self).__init__(config,
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
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        

        
        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            log.debug('parsing header %s', header_match.group(0)[1:32])
            if header_match.group(1) == 'CS':
                data_match = ENG_MATCHER.match(chunk)
                if data_match:
                    log.debug('Found data match in chunk: %s', chunk)
                    # put timestamp from hex string to float:
                    posix_time = int(header_match.group(3), 16)
                    log.debug('utc timestamp %s', datetime.utcfromtimestamp(posix_time))
                    self._timestamp = ntplib.system_to_ntp_time(float(posix_time))
                    log.debug("Converted time \"%s\" (unix: %s) into %s", header_match.group(3),
                              posix_time, self._timestamp)
                    
                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(self._particle_class, ENG_MATCHER, chunk, self._timestamp)
                    if sample:
                        # create particle
                        log.debug("Extracting sample chunk %s with read_state: %s", chunk, self._read_state)
                        result_particles.append(sample)
                        sample_count +=1
                        log.debug("_+_+_+__+_ Sample: %s _+_+__+_++_+ Sample Count: %s", sample, sample_count)
                        
            self._chunk_sample_count.append(sample_count)
            
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        return result_particles

