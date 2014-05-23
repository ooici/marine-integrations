#!/usr/bin/env python

"""
@package mi.dataset.parser.mopak_o_dcl
@file marine-integrations/mi/dataset/parser/mopak_o_dcl.py
@author Emily Hahn
@brief Parser for the mopak_o_dcl dataset driver
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib
import struct
import binascii
from datetime import datetime
import time
from functools import partial

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import SampleException, DatasetParserException, UnexpectedDataException
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import BinaryChunker


ACCEL_ID = b'\xcb'
RATE_ID = b'\xcf'
ACCEL_BYTES = 43
RATE_BYTES = 31

MAX_TIMER = 4294967296
TIMER_TO_SECONDS = 62500.0
TIMER_DIFF_FACTOR = 2.1

class StateKey(BaseEnum):
    POSITION='position'
    TIMER_ROLLOVER = 'timer_rollover'
    TIMER_START = 'timer_start'

class MopakDataParticleType(BaseEnum):
    ACCEL = 'mopak_o_dcl_accel'
    RATE = 'mopak_o_dcl_rate'

class MopakODclAccelParserDataParticleKey(BaseEnum):
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

class MopakODclAccelParserDataParticle(DataParticle):
    """
    Class for parsing data from the Mopak_o_stc data set
    """

    _data_particle_type = MopakDataParticleType.ACCEL

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        # match the data inside the wrapper
        if len(self.raw_data) < ACCEL_BYTES or self.raw_data[0] != ACCEL_ID:
            raise SampleException("MopakODclAccelParserDataParticle: Not enough bytes provided in [%s]",
                                  self.raw_data)
        fields = struct.unpack('>fffffffffI', self.raw_data[1:ACCEL_BYTES-2])

        result = [self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_ACCELX, fields[0], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_ACCELY, fields[1], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_ACCELZ, fields[2], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_ANG_RATEX, fields[3], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_ANG_RATEY, fields[4], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_ANG_RATEZ, fields[5], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_MAGX, fields[6], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_MAGY, fields[7], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_MAGZ, fields[8], float),
                  self._encode_value(MopakODclAccelParserDataParticleKey.MOPAK_TIMER, fields[9], int)]

        log.trace('MopakODclAccelParserDataParticle: particle=%s', result)
        return result

class MopakODclRateParserDataParticleKey(BaseEnum):
    MOPAK_ROLL = 'mopak_roll'
    MOPAK_PITCH = 'mopak_pitch'
    MOPAK_YAW = 'mopak_yaw'
    MOPAK_ANG_RATEX = 'mopak_ang_ratex'
    MOPAK_ANG_RATEY = 'mopak_ang_ratey'
    MOPAK_ANG_RATEZ = 'mopak_ang_ratez'
    MOPAK_TIMER = 'mopak_timer'

class MopakODclRateParserDataParticle(DataParticle):
    """
    Class for parsing data from the mopak_o_dcl data set
    """

    _data_particle_type = MopakDataParticleType.RATE
    
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        a particle with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        # match the data inside the wrapper
        if len(self.raw_data) < RATE_BYTES or self.raw_data[0] != RATE_ID:
            raise SampleException("MopakODclRateParserDataParticle: Not enough bytes provided in [%s]",
                                  self.raw_data)
        fields = struct.unpack('>ffffffI', self.raw_data[1:RATE_BYTES-2])

        result = [self._encode_value(MopakODclRateParserDataParticleKey.MOPAK_ROLL, fields[0], float),
                  self._encode_value(MopakODclRateParserDataParticleKey.MOPAK_PITCH, fields[1], float),
                  self._encode_value(MopakODclRateParserDataParticleKey.MOPAK_YAW, fields[2], float),
                  self._encode_value(MopakODclRateParserDataParticleKey.MOPAK_ANG_RATEX, fields[3], float),
                  self._encode_value(MopakODclRateParserDataParticleKey.MOPAK_ANG_RATEY, fields[4], float),
                  self._encode_value(MopakODclRateParserDataParticleKey.MOPAK_ANG_RATEZ, fields[5], float),
                  self._encode_value(MopakODclRateParserDataParticleKey.MOPAK_TIMER, fields[6], int)]

        log.trace('MopakOStcRateParserDataParticle: particle=%s', result)
        return result

class MopakODclParser(BufferLoadingParser):
    
    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 filename,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        self.timer_diff = None
        self._read_state = {StateKey.POSITION: 0, StateKey.TIMER_ROLLOVER: 0, StateKey.TIMER_START: None}
        # convert the date / time string from the file name to a starting time in seconds UTC
        file_datetime = datetime.strptime(filename[:15], "%Y%m%d_%H%M%S")
        local_seconds = time.mktime(file_datetime.timetuple())
        self._start_time_utc = local_seconds - time.timezone

        super(MopakODclParser, self).__init__(config,
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
                if (data_index + ACCEL_BYTES) <= raw_data_len:
                    # start of accel record
                    if self.compare_checksum(raw_data[data_index:data_index+ACCEL_BYTES]):
                        return_list.append((data_index, data_index + ACCEL_BYTES))
                        data_index += ACCEL_BYTES
                    else:
                        log.debug('checking accel for ID in 0x%s since checksums didnt match',
                                  binascii.hexlify(raw_data[data_index:data_index+ACCEL_BYTES]))
                        another_accel = raw_data[data_index+1:data_index+ACCEL_BYTES].find(ACCEL_ID)
                        another_rate = raw_data[data_index+1:data_index+ACCEL_BYTES].find(RATE_ID)
                        if another_accel == -1 and another_rate == -1:
                            # no other possible starts in here, add to chunk so we know this is processed
                            return_list.append((data_index, data_index + ACCEL_BYTES))
                            data_index += ACCEL_BYTES
                        elif another_accel != -1:
                            data_index += (another_accel + 1)
                        elif another_rate != -1:
                            data_index += (another_rate + 1)
                else:
                    # not enough bytes for accel yet, jump to end
                    data_index = raw_data_len
            elif raw_data[data_index] == RATE_ID:
                if (data_index + RATE_BYTES) <= raw_data_len:
                    # start of rate record
                    if self.compare_checksum(raw_data[data_index:data_index+RATE_BYTES]):
                        return_list.append((data_index, data_index + RATE_BYTES))
                        data_index += RATE_BYTES
                    else:
                        log.debug('checking rate for ID in 0x%s since checksums didnt match',
                                  binascii.hexlify(raw_data[data_index:data_index+RATE_BYTES]))
                        another_accel = raw_data[data_index+1:data_index+RATE_BYTES].find(ACCEL_ID)
                        another_rate = raw_data[data_index+1:data_index+RATE_BYTES].find(RATE_ID)
                        if another_accel == -1 and another_rate == -1:
                            # no other possible starts in here, add to chunk so we know this is processed
                            return_list.append((data_index, data_index + RATE_BYTES))
                            data_index += RATE_BYTES
                        elif another_accel != -1:
                            data_index += (another_accel + 1)
                        elif another_rate != -1:
                            data_index += (another_rate + 1)
                else:
                    # not enough bytes for rate yet, jump to end
                    data_index = raw_data_len
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
        log.debug('checksum received %d does not match calculated %d', rcv_chksum[0], calc_chksum)
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
        if not (StateKey.POSITION in state_obj) or \
           not (StateKey.TIMER_ROLLOVER in state_obj) or \
           not (StateKey.TIMER_START in state_obj):
            raise DatasetParserException("Invalid state keys: %s" % state_obj)
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
        it is a valid data piece, build a particle, update the position.
        Go until the chunker has no more valid data.
        If the timer rolls over account for this in the state, and raise an
        exception if the timer is reset in the middle.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """
        result_particles = []
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
        self.handle_non_data(non_data, non_end, start)

        last_timer = 0

        while (chunk != None):
            sample = None
            fields = None
            if chunk[0] == ACCEL_ID:
                if self.compare_checksum(chunk[:ACCEL_BYTES]):
                    # particle-ize the data block received, return the record
                    fields = struct.unpack('>I', chunk[37:41])
                else:
                    log.info("Ignoring accel record whose checksum doesn't match")
            elif chunk[0] == RATE_ID and self.compare_checksum(chunk[:RATE_BYTES]):
                if self.compare_checksum(chunk[:RATE_BYTES]):
                    # particle-ize the data block received, return the record
                    fields = struct.unpack('>I', chunk[25:29])
                else:
                    log.info("Ignoring rate record whose checksum doesn't match")

            if fields:
                timer = int(fields[0])
                # store the first timer value so we can subtract it to zero out the count at the
                # start of the file
                if self._read_state[StateKey.TIMER_START] == None:
                    self._read_state[StateKey.TIMER_START] = timer
                # keep track of the timer rolling over or being reset
                if timer < last_timer:
                    # check that the timer was not reset instead of rolling over, there should be
                    # a large difference between the times, give it a little leeway with the 2.1
                    # this is unlikely to happen in the first place, but there is still a risk of
                    # rolling over on the second sample and not having timer_diff calculated yet,
                    # or rolling in the last sample of the file within the fudge factor
                    if self.timer_diff and (last_timer - timer) < (MAX_TIMER - self.timer_diff*TIMER_DIFF_FACTOR):
                        # timer was reset before it got to the end
                        log.warn('Timer was reset, time of particles unknown')
                        raise SampleException('Timer was reset, time of particle now unknown')
                    log.info("Timer has rolled")
                    self._read_state[StateKey.TIMER_ROLLOVER] += 1
                timestamp = self.timer_to_timestamp(int(fields[0]))
                # use the timer diff to determine if the timer has been reset instead of rolling over
                # at the end
                if last_timer != 0 and self.timer_diff == None:
                    # get an idea of interval used in this file
                    self.timer_diff = timer - last_timer
                last_timer = timer

                if chunk[0] == ACCEL_ID:
                    sample = self._extract_sample(MopakODclAccelParserDataParticle, None, chunk, timestamp)
                    # increment state
                    self._increment_state(ACCEL_BYTES)
                elif chunk[0] == RATE_ID:
                    sample = self._extract_sample(MopakODclRateParserDataParticle, None, chunk, timestamp)
                    # increment state
                    self._increment_state(RATE_BYTES)

                if sample:
                    result_particles.append((sample, copy.copy(self._read_state)))

            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    def handle_non_data(self, non_data, non_end, start):
        """
        handle data in the non_data chunker queue
        @param non_data data in the non data chunker queue
        @param non_end ending index of the non_data chunk
        @param start start index of the next data chunk
        """
        # we can get non_data after our current chunk, check that this chunk is before that chunk
        if non_data is not None and non_end <= start:
            # there should never be any non-data, send a sample exception to indicate we have unexpected data in the file
            # if there are more chunks we want to keep processing this file, so directly call the exception callback
            # rather than raising the error here
            non_data_len = len(non_data)
            log.error("Found %d bytes of unexpected non-data:0x%s", non_data_len, binascii.hexlify(non_data))
            self._increment_state(non_data_len)
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data:0x%s" %
                                                             (non_data_len, binascii.hexlify(non_data))))

    def timer_to_timestamp(self, timer):
        """
        convert a timer value to a ntp formatted timestamp
        """
        # if the timer has rolled over, multiply by the maximum value for timer so the time keeps increasing
        rollover_offset = self._read_state[StateKey.TIMER_ROLLOVER] * MAX_TIMER
        # make sure the timer starts at 0 for the file by subtracting the first timer
        # divide timer by 62500 to go from counts to seconds
        offset_secs = float(timer + rollover_offset - self._read_state[StateKey.TIMER_START])/TIMER_TO_SECONDS
        # add in the utc start time
        time_secs = float(self._start_time_utc) + offset_secs
        # convert to ntp64
        return float(ntplib.system_to_ntp_time(time_secs))

