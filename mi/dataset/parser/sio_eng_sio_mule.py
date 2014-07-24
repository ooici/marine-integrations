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





ENG_REGEX = r'\x01CS([0-9]{5})[0-9]{2}_[0-9A-Fa-f]{4}[a-zA-Z]([0-9A-Fa-f]{8})_'\
            '[0-9A-Fa-f]{2}_[0-9A-Fa-f]{4}\x02\n([-\d]+\.\d+) '\
            '([-\d]+\.\d+) ([-\d]+) ([-\d]+) ([-\d]+)\n'

ENG_MATCHER = re.compile(ENG_REGEX)


class DataParticleType(BaseEnum):
    SAMPLE = 'sio_eng_control_status'

class SioEngSioMuleParserDataParticleKey(BaseEnum):
    # sio_eng_control_status
    SIO_CONTROLLER_ID = "sio_controller_id"
    SIO_CONTROLLER_TIMESTAMP = "sio_controller_timestamp"
    SIO_VOLTAGE_STRING = 'sio_eng_voltage'
    SIO_TEMPERATURE_STRING = 'sio_eng_temperature'
    SIO_ON_TIME = 'sio_eng_on_time'
    SIO_NUMBER_OF_WAKEUPS = 'sio_eng_number_of_wakeups'
    SIO_CLOCK_DRIFT = 'sio_eng_clock_drift'
    

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
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        

        
        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            log.debug('parsing header %s', header_match.group(0)[1:32])
            if header_match.group(1) == 'CS':
                log.debug('\n\nCS Header detected:::  %s\n\n', header_match.group(0)[1:32])
                data_match = ENG_MATCHER.match(chunk)
                if data_match:
                    # put timestamp from hex string to float:
                    posix_time = int(header_match.group(3), 16)
                    log.debug('utc timestamp %s', datetime.utcfromtimestamp(posix_time))
                    self._timestamp = ntplib.system_to_ntp_time(float(posix_time))
                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(self._particle_class, ENG_MATCHER, chunk, self._timestamp)
                    if sample:
                        # create particle
                        result_particles.append(sample)
                        sample_count +=1
                else:
                    log.warn('CS data does not match REGEX')
                    self._exception_callback(SampleException('CS data does not match REGEX'))
                    
            self._chunk_sample_count.append(sample_count)
            
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        return result_particles

