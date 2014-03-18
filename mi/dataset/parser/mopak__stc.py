#!/usr/bin/env python

"""
@package mi.dataset.parser.mopak__stc
@file marine-integrations/mi/dataset/parser/mopak__stc.py
@author Emily Hahn
@brief Parser for the MOPAK__STC dataset driver
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import struct
from datetime import datetime
import time
from functools import partial

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import BinaryChunker


ACCEL_ID = b'\xcb'
RATE_ID = b'\xcf'
ACCEL_BYTES = 43
RATE_BYTES = 31

class StateKey(BaseEnum):
    POSITION='position'

class DataParticleType(BaseEnum):
    ACCEL = 'mopak_xx__stc_accel'
    RATE = 'mopak_xx__stc_rate'

class Mopak__stcAccelParserDataParticleKey(BaseEnum):
    MOPAK_ACCELX = 'mopak_accelx'
    MOPAK_ACCELY = 'mopak_accely'
    MOPAK_ACCELZ = 'mopak_accelz'
    MOPAK_ANG_RATEX = 'mopak_ang_ratex'
    MOPAK_ANG_RATEY = 'mopak_ang_ratey'
    MOPAK_ANG_RATEZ = 'mopak_ang_ratez'
    MOPAK_MAGX = 'mopak_magx'
    MOPAK_MAGY = 'mopak_magy'
    MOPAK_MAGZ = 'mopak_magz'
    MOPAK_TIMER = 'mopak_timer'

class Mopak__stcAccelParserDataParticle(DataParticle):
    """
    Class for parsing data from the MOPAK__STC data set
    """

    _data_particle_type = DataParticleType.ACCEL

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        # match the data inside the wrapper
        if len(self.raw_data) < ACCEL_BYTES or self.raw_data[0] != ACCEL_ID:
            raise SampleException("Mopak__stcAccelParserDataParticle: Not enough bytes provided in [%s]",
                                  self.raw_data)
        try:
            fields = struct.unpack('>fffffffffI', self.raw_data[1:ACCEL_BYTES-2])
            accelx = float(fields[0])
            accely = float(fields[1])
            accelz = float(fields[2])
            ratex = float(fields[3])
            ratey = float(fields[4])
            ratez = float(fields[5])
            magx = float(fields[6])
            magy = float(fields[7])
            magz = float(fields[8])
            timer = int(fields[9])
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))
        
        result = [{DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_ACCELX,
                   DataParticleKey.VALUE: accelx},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_ACCELY,
                   DataParticleKey.VALUE: accely},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_ACCELZ,
                   DataParticleKey.VALUE: accelz},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_ANG_RATEX,
                   DataParticleKey.VALUE: ratex},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_ANG_RATEY,
                   DataParticleKey.VALUE: ratey},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_ANG_RATEZ,
                   DataParticleKey.VALUE: ratez},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_MAGX,
                   DataParticleKey.VALUE: magx},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_MAGY,
                   DataParticleKey.VALUE: magy},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_MAGZ,
                   DataParticleKey.VALUE: magz},
                  {DataParticleKey.VALUE_ID: Mopak__stcAccelParserDataParticleKey.MOPAK_TIMER,
                   DataParticleKey.VALUE: timer}]

        log.trace('Mopak__stcAccelParserDataParticle: particle=%s', result)
        return result

    def __eq__(self, arg):
        """
        Quick equality check for testing purposes. If they have the same raw
        data, timestamp, and new sequence, they are the same enough for this 
        particle
        """
        allowed_diff = .000001
        if ((self.raw_data == arg.raw_data) and \
            (abs(self.contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
                 arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]) < allowed_diff)):
            return True
        else:
            if self.raw_data != arg.raw_data:
                log.debug('Raw data does not match')
            elif abs(self.contents[DataParticleKey.INTERNAL_TIMESTAMP] - \
                     arg.contents[DataParticleKey.INTERNAL_TIMESTAMP]) > allowed_diff:
                log.debug('Timestamp %s does not match %s', self.contents[DataParticleKey.INTERNAL_TIMESTAMP],
                          arg.contents[DataParticleKey.INTERNAL_TIMESTAMP])
            return False

class Mopak__stcRateParserDataParticleKey(BaseEnum):
    MOPAK_ROLL = 'mopak_roll'
    MOPAK_PITCH = 'mopak_pitch'
    MOPAK_YAW = 'mopak_yaw'
    MOPAK_ANG_RATEX = 'mopak_ang_ratex'
    MOPAK_ANG_RATEY = 'mopak_ang_ratey'
    MOPAK_ANG_RATEZ = 'mopak_ang_ratez'
    MOPAK_TIMER = 'mopak_timer'

class Mopak__stcRateParserDataParticle(DataParticle):
    """
    Class for parsing data from the MOPAK__STC data set
    """

    _data_particle_type = DataParticleType.RATE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        # match the data inside the wrapper
        if len(self.raw_data) < RATE_BYTES or self.raw_data[0] != RATE_ID:
            raise SampleException("Mopak__stcRateParserDataParticle: Not enough bytes provided in [%s]",
                                  self.raw_data)
        try:
            fields = struct.unpack('>ffffffI', self.raw_data[1:RATE_BYTES-2])
            roll = float(fields[0])
            pitch = float(fields[1])
            yaw = float(fields[2])
            ratex = float(fields[3])
            ratey = float(fields[4])
            ratez = float(fields[5])
            timer = int(fields[6])
        except (ValueError, TypeError, IndexError) as ex:
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, match.group(0)))
        
        result = [{DataParticleKey.VALUE_ID: Mopak__stcRateParserDataParticleKey.MOPAK_ROLL,
                   DataParticleKey.VALUE: roll},
                  {DataParticleKey.VALUE_ID: Mopak__stcRateParserDataParticleKey.MOPAK_PITCH,
                   DataParticleKey.VALUE: pitch},
                  {DataParticleKey.VALUE_ID: Mopak__stcRateParserDataParticleKey.MOPAK_YAW,
                   DataParticleKey.VALUE: yaw},
                  {DataParticleKey.VALUE_ID: Mopak__stcRateParserDataParticleKey.MOPAK_ANG_RATEX,
                   DataParticleKey.VALUE: ratex},
                  {DataParticleKey.VALUE_ID: Mopak__stcRateParserDataParticleKey.MOPAK_ANG_RATEY,
                   DataParticleKey.VALUE: ratey},
                  {DataParticleKey.VALUE_ID: Mopak__stcRateParserDataParticleKey.MOPAK_ANG_RATEZ,
                   DataParticleKey.VALUE: ratez},
                  {DataParticleKey.VALUE_ID: Mopak__stcRateParserDataParticleKey.MOPAK_TIMER,
                   DataParticleKey.VALUE: timer}]

        log.debug('Mopak__stcAccelParserDataParticle: particle=%s', result)
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

class Mopak__stcParser(BufferLoadingParser):
    
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 filename,
                 *args, **kwargs):
        self._timestamp = 0.0
        self._record_buffer = [] # holds tuples of (record,state)
        self._read_state = {StateKey.POSITION: 0}
        # convert the date / time string from the file name to a starting time in seconds UTC
        file_datetime = datetime.strptime(filename[:15], "%Y%m%d_%H%M%S")
        local_seconds = time.mktime(file_datetime.timetuple())
        self._start_time_utc = local_seconds - time.timezone
        log.debug("starting at time %s", self._start_time_utc)
        super(Mopak__stcParser, self).__init__(config,
                                               stream_handle,
                                               state,
                                               self.sieve_function,
                                               state_callback,
                                               publish_callback,
                                               exception_callback,
                                               *args, **kwargs)

        if state:
            self.set_state(state)

    def sieve_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        This is needed instead of a regex because blocks are identified by position
        in this binary file.
        """
        data_index = 0
        return_list = []
        raw_data_len = len(raw_data)

        while data_index < raw_data_len:
            # check if this is a status or data sample message
            if raw_data[data_index] == ACCEL_ID:
                # start of accel record
                if self.compare_checksum(raw_data[data_index:data_index+ACCEL_BYTES]):
                    return_list.append((data_index, data_index + ACCEL_BYTES))
                    data_index += ACCEL_BYTES
                else:
                    data_index += 1
            elif raw_data[data_index] == RATE_ID:
                # start of rate record
                if self.compare_checksum(raw_data[data_index:data_index+RATE_BYTES]):
                    return_list.append((data_index, data_index + RATE_BYTES))
                    data_index += RATE_BYTES
                else:
                    data_index += 1
            else:
                data_index += 1

            remain_bytes = raw_data_len - data_index
            # if the remaining bytes are less than the data rate bytes we're done
            if remain_bytes < RATE_BYTES:
                break
        return return_list
    
    def compare_checksum(self, raw_bytes):
        rcv_chksum = struct.unpack('>H', raw_bytes[-2:])
        calc_chksum = self.calc_checksum(raw_bytes[:-2])
        if rcv_chksum[0] == calc_chksum:
            return True
        return False
    
    def calc_checksum(self, raw_bytes):
        n_bytes = len(raw_bytes)
        # unpack raw bytes into unsigned chars
        unpack_str = '>'
        for i in range(0, n_bytes):
            unpack_str = unpack_str + 'B'
        fields = struct.unpack(unpack_str, raw_bytes)
        sum_fields = sum(fields)
        # since we are summing as unsigned short, limit range to 0 to 65535
        while sum_fields > 65535:
            sum_fields -= 65536
        return sum_fields

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. 
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        self._record_buffer = []
        self._chunker.clean_all_chunks()
        self._state = state_obj
        self._read_state = state_obj
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser state
        @param timestamp The timestamp completed up to that position
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
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        if non_data is not None and non_end <= start:
            # there should never be any non-data, send a sample exception to indicate we have unexpected data in the file
            # if there are more chunks we want to keep processing this file, so directly call the exception callback
            # rather than raising the error here
            self._increment_state(len(non_data))
            log.error("Found %d bytes of unexpected non-data", len(non_data))
            self._exception_callback(SampleException("Found %d bytes of un-expected non-data" % len(non_data)))

        while (chunk != None):
            sample = None
            if chunk[0] == ACCEL_ID:
                # particle-ize the data block received, return the record
                fields = struct.unpack('>I', chunk[37:41])
                self._timestamp = self.timer_to_timestamp(int(fields[0]))
                sample = self._extract_sample(Mopak__stcAccelParserDataParticle, None, chunk, self._timestamp)
                if sample:
                    # increment state
                    self._increment_state(ACCEL_BYTES)
            elif chunk[0] == RATE_ID:
                # particle-ize the data block received, return the record
                fields = struct.unpack('>I', chunk[25:29])
                self._timestamp = self.timer_to_timestamp(int(fields[0]))
                sample = self._extract_sample(Mopak__stcRateParserDataParticle, None, chunk, self._timestamp)
                if sample:
                    # increment state
                    self._increment_state(RATE_BYTES)
  
            if sample:
                result_particles.append((sample, copy.copy(self._read_state)))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            if non_data is not None and non_end <= start:
                # there should never be any non-data, send a sample exception to indicate we have unexpected data in the file
                # if there are more chunks we want to keep processing this file, so directly call the exception callback
                # rather than raising the error here
                self._increment_state(len(non_data))
                log.error("Found %d bytes of unexpected non-data", len(non_data))
                self._exception_callback(SampleException("Found %d bytes of un-expected non-data" % len(non_data)))

        return result_particles

    def timer_to_timestamp(self, timer):
        """
        convert a timer value to a ntp formatted timestamp
        """
        # first divide timer by 62500 to go from counts to seconds
        offset_secs = float(timer)/62500.0
        
        # add in the utc start time
        time_secs = float(self._start_time_utc) + offset_secs
        # convert to ntp64
        return float(ntplib.system_to_ntp_time(time_secs))

