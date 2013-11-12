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
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.parser.mflm import MflmParser, SIO_HEADER_MATCHER
from mi.core.exceptions import SampleException, DatasetParserException

class DataParticleType(BaseEnum):
    SAMPLE = 'dostad_parsed'

class DostadParserDataParticleKey(BaseEnum):
    PRODUCT_NUMBER = 'product_number'
    SERIAL_NUMBER = 'serial_number'
    ESTIMATED_OXYGEN = 'estimated_oxygen'
    AIR_SATURATION = 'air_saturation'
    OPTODE_TEMPERATURE = 'optode_temperature'
    CALIBRATED_PHASE = 'calibrated_phase'
    TEMP_COMPENSATED_PHASE = 'temp_compensated_phase'
    BLUE_PHASE = 'blue_phase'
    RED_PHASE = 'red_phase'
    BLUE_AMPLITUDE = 'blue_amplitude'
    RED_AMPLITUDE = 'red_amplitude'
    RAW_TEMP = 'raw_temp'
    
DATA_REGEX = b'\xff\x11\x25\x11(\d+)\t(\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t' \
             '(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\t(\d+.\d+)\x0d\x0a'
DATA_MATCHER = re.compile(DATA_REGEX)

class DostadParserDataParticle(DataParticle):
    """
    Class for parsing data from the DOSTA-D instrument on a MSFM platform node
    """

    _data_particle_type = DataParticleType.SAMPLE

    def _build_parsed_values(self):
        """
        Take something in the binary data values and turn it into a
        particle with the appropriate tag.
        throws SampleException If there is a problem with sample creation
        """
        # match the data inside the wrapper
        match = DATA_MATCHER.match(self.raw_data)
        if not match:
            raise SampleException("DostadParserDataParticle: No regex match of \
                                  parsed sample data [%s]", self.raw_data)
        try:
            prod_num = int(match.group(1))
            if prod_num != 4831:
                raise ValueError('Product number %d was not expected 4831' % prod_num)
            serial_num = int(match.group(2))
            est_oxygen = float(match.group(3))
            air_sat = float(match.group(4))
            optode_temp = float(match.group(5))
            calibrated_phase = float(match.group(6))
            if calibrated_phase < -360.0 or calibrated_phase > 360.0:
                raise ValueError('Calibrated phase %f it outside expected limits -360 to 360' % calibrated_phase)
            temp_compens_phase = float(match.group(7))
            if temp_compens_phase < -360.0 or temp_compens_phase > 360.0:
                raise ValueError('Temp compensated phase %f it outside expected limits -360 to 360' % temp_compens_phase)
            blue_phase = float(match.group(8))
            if blue_phase < -360.0 or blue_phase > 360.0:
                raise ValueError('Blue Phase %f it outside expected limits -360 to 360' % blue_phase)
            red_phase = float(match.group(9))
            if red_phase < -360.0 or red_phase > 360.0:
                raise ValueError('Red Phase %f it outside expected limits -360 to 360' % red_phase)
            blue_amp = float(match.group(10))
            red_amp = float(match.group(11))
            raw_temp = float(match.group(12))

        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))

        result = [{DataParticleKey.VALUE_ID: DostadParserDataParticleKey.PRODUCT_NUMBER,
                   DataParticleKey.VALUE: prod_num},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.SERIAL_NUMBER,
                   DataParticleKey.VALUE: serial_num},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.ESTIMATED_OXYGEN,
                   DataParticleKey.VALUE: est_oxygen},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.AIR_SATURATION,
                   DataParticleKey.VALUE: air_sat},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.OPTODE_TEMPERATURE,
                   DataParticleKey.VALUE: optode_temp},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.CALIBRATED_PHASE,
                   DataParticleKey.VALUE: calibrated_phase},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.TEMP_COMPENSATED_PHASE,
                   DataParticleKey.VALUE: temp_compens_phase},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.BLUE_PHASE,
                   DataParticleKey.VALUE: blue_phase},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.RED_PHASE,
                   DataParticleKey.VALUE: red_phase},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.BLUE_AMPLITUDE,
                   DataParticleKey.VALUE: blue_amp},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.RED_AMPLITUDE,
                   DataParticleKey.VALUE: red_amp},
                  {DataParticleKey.VALUE_ID: DostadParserDataParticleKey.RAW_TEMP,
                   DataParticleKey.VALUE: raw_temp}]

        log.debug('DostadParserDataParticle: particle=%s', result)
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this particle
        """
        if ((self.raw_data == arg.raw_data) and \
            (self.contents[DataParticleKey.INTERNAL_TIMESTAMP] == arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]) and \
            (self.contents[DataParticleKey.NEW_SEQUENCE] == arg.contents[DataParticleKey.NEW_SEQUENCE])):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif self.contents[DataParticleKey.INTERNAL_TIMESTAMP] != arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]:
                log.debug('Timestamp does not match')
            elif self.contents[DataParticleKey.NEW_SEQUENCE] != arg.contents[DataParticleKey.NEW_SEQUENCE]:
                log.debug('Sequence does not match')
            return False

class DostadParser(MflmParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        super(DostadParser, self).__init__(config,
                                          stream_handle,
                                          state,
                                          self.sieve_function,
                                          state_callback,
                                          publish_callback,
                                          'DO',
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
        # all non-data packets will be read along with all the data, so we can't just use the fact that
        # there is or is not non-data to determine when a new sequence should occur.  The non-data will
        # keep getting shifted lower as things get cleaned out, and when it reaches the 0 index the non-data
        # is actually next
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
        non_data_flag = False
        if non_data is not None and non_end <= start:
            log.debug('start setting non_data_flag')
            non_data_flag = True
            
        sample_count = 0
        new_seq = 0

        while (chunk != None):
            header_match = SIO_HEADER_MATCHER.match(chunk)
            sample_count = 0
            new_seq = 0
            log.debug('parsing header %s', header_match.group(0)[1:32])
            if header_match.group(1) == self._instrument_id:
                # Check for missing data between records
                if non_data_flag or self._new_seq_flag:
                    log.debug("Non matching data packet detected")
                    # reset non data flag and new sequence flags now
                    # that we have made a new sequence
                    non_data = None
                    non_data_flag = False
                    self._new_seq_flag = False
                    self.start_new_sequence()
                    # need to figure out if there is a new sequence the first time through,
                    # since if we are using in process data we don't read unprocessed again
                    new_seq = 1

                # need to do special processing on data to handle escape sequences
                # replace 0x182b with 0x2b and 0x1858 into 0x18
                processed_match = chunk.replace(b'\x182b', b'\x2b')
                processed_match = processed_match.replace(b'\x1858', b'\x18')
                log.debug("matched chunk header %s", processed_match[1:32])

                data_match = DATA_MATCHER.search(processed_match)
                if data_match:
                    log.debug('Found data match in chunk %s', processed_match[1:32])
                    # get the time from the header
                    posix_time = int(header_match.group(3), 16)
                    # convert from posix to local time
                    log.debug('utc timestamp %s', datetime.utcfromtimestamp(posix_time))
                    self._timestamp = ntplib.system_to_ntp_time(float(posix_time))
                    log.debug("Converted time \"%s\" (unix: %s) into %s", header_match.group(3),
                              posix_time, self._timestamp)

                    # particle-ize the data block received, return the record
                    sample = self._extract_sample(DostadParserDataParticle,
                                                  DATA_MATCHER,
                                                  data_match.group(0),
                                                  self._timestamp)
                    if sample:
                        # create particle
                        result_particles.append(sample)
                        sample_count += 1

            self._chunk_sample_count.append(sample_count)
            self._chunk_new_seq.append(new_seq)

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index()
            # need to set a flag in case we read a chunk not matching the instrument ID and overwrite the non_data                    
            if non_data is not None and non_end <= start:
                log.debug('setting non_data_flag')
                non_data_flag = True

        return result_particles
