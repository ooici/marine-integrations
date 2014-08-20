#!/usr/bin/env python

"""
@package mi.dataset.parser.dostad
@file mi/dataset/parser/dostad.py
@author Emily Hahn
@brief An dosta-d specific dataset agent parser
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re
from datetime import datetime
import ntplib

from mi.core.log import get_logger; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.dataset.parser.sio_mule_common import SioMuleParser, SIO_HEADER_MATCHER
from mi.core.exceptions import SampleException, DatasetParserException, RecoverableSampleException

class DataParticleType(BaseEnum):
    SAMPLE = 'dosta_abcdjm_sio_instrument'
    METADATA = 'dosta_abcdjm_sio_metadata'

class StateKey(BaseEnum):
    UNPROCESSED_DATA = "unprocessed_data" # holds an array of start and end of unprocessed blocks of data
    IN_PROCESS_DATA = "in_process_data" # holds an array of start and end of packets of data,
        # the number of samples in that packet, how many packets have been pulled out currently
        # being processed
    FILE_SIZE = "file_size"
    METADATA_SENT = "metadata_sent" # store if the metadata particle has been sent

class DostadParserDataParticleKey(BaseEnum):
    CONTROLLER_TIMESTAMP = 'sio_controller_timestamp'
    ESTIMATED_OXYGEN = 'estimated_oxygen_concentration'
    ESTIMATED_SATURATION = 'estimated_oxygen_saturation'
    OPTODE_TEMPERATURE = 'optode_temperature'
    CALIBRATED_PHASE = 'calibrated_phase'
    TEMP_COMPENSATED_PHASE = 'temp_compensated_phase'
    BLUE_PHASE = 'blue_phase'
    RED_PHASE = 'red_phase'
    BLUE_AMPLITUDE = 'blue_amplitude'
    RED_AMPLITUDE = 'red_amplitude'
    RAW_TEMP = 'raw_temperature'

# regex to match the dosta data, header ID 0xff112511, 2 integers for product and serial number,
# followed by 10 floating point numbers all separated by tabs
DATA_REGEX = b'\xff\x11\x25\x11(\d+)\t(\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t' \
             '(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\x0d\x0a'
DATA_MATCHER = re.compile(DATA_REGEX)

# regex to match the timestamp from the sio header
TIMESTAMP_REGEX = b'[0-9A-Fa-f]{8}'
TIMESTAMP_MATCHER = re.compile(TIMESTAMP_REGEX)

class DostadParserDataParticle(DataParticle):
    """
    Class for parsing data from the DOSTA-D instrument on a MSFM platform node
    """

    _data_particle_type = DataParticleType.SAMPLE

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(DostadParserDataParticle, self).__init__(raw_data,
                                                      port_timestamp=None,
                                                      internal_timestamp=None,
                                                      preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                                                      quality_flag=DataParticleValue.OK,
                                                      new_sequence=None)
        # the raw data has the timestamp from the sio header pre-pended to it, match the first 8 bytes
        timestamp_match = TIMESTAMP_MATCHER.match(self.raw_data[:8])
        if not timestamp_match:
            raise RecoverableSampleException("DostaParserDataParticle: No regex match of " \
                                             "timestamp [%s]" % self.raw_data[:8])
        # now match the dosta data, excluding the sio header timestamp in the first 8 bytes
        self._data_match = DATA_MATCHER.match(self.raw_data[8:])
        if not self._data_match:
            raise RecoverableSampleException("DostaParserDataParticle: No regex match of " \
                                              "parsed sample data [%s]" % self.raw_data[8:])

        posix_time = int(timestamp_match.group(0), 16)
        self.set_internal_timestamp(unix_time=float(posix_time))

    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        throws SampleException If there is a problem with sample creation
        """
        result = []
        if self._data_match:
            result = [self._encode_value(DostadParserDataParticleKey.CONTROLLER_TIMESTAMP,
                                         self.raw_data[0:8],
                                         DostadParserDataParticle.encode_int_16),
                      self._encode_value(DostadParserDataParticleKey.ESTIMATED_OXYGEN,
                                         self._data_match.group(3), float),
                      self._encode_value(DostadParserDataParticleKey.ESTIMATED_SATURATION,
                                         self._data_match.group(4), float),
                      self._encode_value(DostadParserDataParticleKey.OPTODE_TEMPERATURE,
                                         self._data_match.group(5), float),
                      self._encode_value(DostadParserDataParticleKey.CALIBRATED_PHASE,
                                         self._data_match.group(6), float),
                      self._encode_value(DostadParserDataParticleKey.TEMP_COMPENSATED_PHASE,
                                         self._data_match.group(7), float),
                      self._encode_value(DostadParserDataParticleKey.BLUE_PHASE,
                                         self._data_match.group(8), float),
                      self._encode_value(DostadParserDataParticleKey.RED_PHASE,
                                         self._data_match.group(9), float),
                      self._encode_value(DostadParserDataParticleKey.BLUE_AMPLITUDE,
                                         self._data_match.group(10), float),
                      self._encode_value(DostadParserDataParticleKey.RED_AMPLITUDE,
                                         self._data_match.group(11), float),
                      self._encode_value(DostadParserDataParticleKey.RAW_TEMP,
                                         self._data_match.group(12), float)]

        return result

    @staticmethod
    def encode_int_16(hex_str):
        return int(hex_str, 16)
    
class DostadMetadataDataParticleKey(BaseEnum):
    PRODUCT_NUMBER = 'product_number'
    SERIAL_NUMBER = 'serial_number'

class DostadMetadataDataParticle(DataParticle):
    """
    Class for parsing data from the DOSTA-D instrument on a MSFM platform node
    """

    _data_particle_type = DataParticleType.METADATA
    
    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):
        super(DostadMetadataDataParticle, self).__init__(raw_data,
                                                      port_timestamp=None,
                                                      internal_timestamp=None,
                                                      preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                                                      quality_flag=DataParticleValue.OK,
                                                      new_sequence=None)
        # the raw data has the timestamp from the sio header pre-pended to it, match the first 8 bytes
        timestamp_match = TIMESTAMP_MATCHER.match(self.raw_data[:8])
        if not timestamp_match:
            raise RecoverableSampleException("DostaMetadataDataParticle: No regex match of " \
                                             "timestamp [%s]" % self.raw_data[:8])
        # now match the dosta data, excluding the sio header timestamp in the first 8 bytes
        self._data_match = DATA_MATCHER.match(self.raw_data[8:])
        if not self._data_match:
            raise RecoverableSampleException("DostaMetadataDataParticle: No regex match of " \
                                              "parsed sample data [%s]" % self.raw_data[8:])

        posix_time = int(timestamp_match.group(0), 16)
        self.set_internal_timestamp(unix_time=float(posix_time))
    
    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        throws SampleException If there is a problem with sample creation
        """
        result = []
        if self._data_match:
            result = [self._encode_value(DostadMetadataDataParticleKey.PRODUCT_NUMBER,
                                         self._data_match.group(1), int),
                      self._encode_value(DostadMetadataDataParticleKey.SERIAL_NUMBER,
                                         self._data_match.group(2), int)]
        return result

class DostadParser(SioMuleParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        super(DostadParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          exception_callback,
                                          *args,
                                          **kwargs)
        # initialize the metadata since sio mule common doesn't initialize this field
        if not StateKey.METADATA_SENT in self._read_state:
            self._read_state[StateKey.METADATA_SENT] = False

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

        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            log.debug('parsing header %s', header_match.group(0)[1:32])
            if header_match.group(1) == 'DO':

                data_match = DATA_MATCHER.search(chunk)
                if data_match:
                    log.debug('Found data match in chunk %s', chunk[1:32])

                    if not self._read_state.get(StateKey.METADATA_SENT):
                        # create the metadata particle
                        # prepend the timestamp from sio mule header to the dosta raw data,
                        # which is stored in header_match.group(3)
                        metadata_sample = self._extract_sample(DostadMetadataDataParticle, None,
                                                  header_match.group(3) + data_match.group(0),
                                                  None)
                        if metadata_sample:
                            result_particles.append(metadata_sample)
                            sample_count += 1
                            self._read_state[StateKey.METADATA_SENT] = True

                    # create the dosta data particle
                    # prepend the timestamp from sio mule header to the dosta raw data,
                    # which is stored in header_match.group(3)
                    sample = self._extract_sample(DostadParserDataParticle, None,
                                                  header_match.group(3) + data_match.group(0),
                                                  None)
                    if sample:
                        # create particle
                        result_particles.append(sample)
                        sample_count += 1

            self._chunk_sample_count.append(sample_count)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()

        return result_particles
