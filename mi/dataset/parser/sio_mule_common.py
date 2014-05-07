#!/usr/bin/env python

"""
@package mi.dataset.parser.sio_mule_common data set parser
@file mi/dataset/parser/sio_mule_common.py
@author Emily Hahn
This module contains classes that handle parsing instruments which pass through
sio which contain the common sio header.
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re
import struct
import binascii
import gevent

from mi.core.common import BaseEnum
from mi.core.log import get_logger; log = get_logger()
from mi.core.instrument.chunker import StringChunker
from mi.core.exceptions import DatasetParserException
from mi.core.instrument.data_particle import DataParticleKey
from mi.dataset.dataset_parser import Parser

# SIO Main controller header and data for ctdmo in binary
# groups: ID, Number of Data Bytes, POSIX timestamp, block number, data
# some instruments have \x03 within the data, need to check if header is
# followed by another header or not or zeros for blank data
SIO_HEADER_REGEX = b'\x01(CT|AD|FL|DO|PH|PS|CS|WA|WC|WE|CO|PS|CS)[0-9]{7}_([0-9A-Fa-f]{4})[a-zA-Z]' \
               '([0-9A-Fa-f]{8})_([0-9A-Fa-f]{2})_([0-9A-Fa-f]{4})\x02'
SIO_HEADER_MATCHER = re.compile(SIO_HEADER_REGEX)

# blocks can be uniquely identified a combination of block number and timestamp,
# since block numbers roll over after 255
# each block may contain multiple data samples
class StateKey(BaseEnum):
    TIMESTAMP = "timestamp" # holds the most recent data sample timestamp
    UNPROCESSED_DATA = "unprocessed_data" # holds an array of start and end of unprocessed blocks of data
    IN_PROCESS_DATA = "in_process_data" # holds an array of start and end of packets of data,
        # the number of samples in that packet, how many packets have been pulled out currently
        # being processed

class SioMuleParser(Parser):

    def __init__(self, config, stream_handle, state, sieve_fn,
                 state_callback, publish_callback, exception_callback):
        """
        @param config The configuration parameters to feed into the parser
        @param stream_handle An already open file-like filehandle
        @param state The location in the file to start parsing from.
           This reflects what has already been published.
        @param sieve_fn A sieve function that might be added to a handler
           to appropriate filter out the data
        @param state_callback The callback method from the agent driver
           (ultimately the agent) to call back when a state needs to be
           updated
        @param publish_callback The callback from the agent driver (and
           ultimately from the agent) where we send our sample particle to
           be published into ION
        @param exception_callback The callback from the agent driver to
           send an exception to
        @param instrument_id the text string indicating the instrument to
           monitor, can be 'CT', 'AD', 'FL', 'DO', 'PH', 'WA', 'WC', or 'WE'
        """
        super(SioMuleParser, self).__init__(config,
                                         stream_handle,
                                         state,
                                         self.sieve_function,
                                         state_callback,
                                         publish_callback,
                                         exception_callback)

        self._timestamp = 0.0
        self._position = [0,0] # store both the start and end point for this read of data within the file
        self._record_buffer = [] # holds list of records
        # determine the EOF index
        self._stream_handle.seek(0)
        all_data = self._stream_handle.read()
        EOF = len(all_data)
        self._stream_handle.seek(0)
        self._chunk_sample_count = []
        self._samples_to_throw_out = None
        self._mid_sample_packets = 0
        self._read_state = {StateKey.TIMESTAMP:0.0,
                            StateKey.UNPROCESSED_DATA:[[0,EOF]],
                            StateKey.IN_PROCESS_DATA:[]}

        if state:
            self.set_state(self._state)

    def sieve_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        This sieve identifies the SIO header and returns just the data block identified
        inside the header.
        @param raw_data The raw data to search
        @retval list of matched start,end index found in raw_data
        """
        return_list = []

        for match in SIO_HEADER_MATCHER.finditer(raw_data):
            data_len = int(match.group(2), 16)
            checksum = match.group(5)
            end_packet_idx = match.end(0) + data_len
            if end_packet_idx < len(raw_data):
                end_packet = raw_data[end_packet_idx]
                log.debug('Checking header %s, packet (%d, %d), start %d, data len %d',
                          match.group(0)[1:32], match.end(0), end_packet_idx,
                          match.start(0), data_len)
                if end_packet == '\x03':
                    packet_data = raw_data[match.end(0):end_packet_idx]
                    chksum = self.calc_checksum(packet_data)
                    if chksum == checksum:
                        # even if this is not the right instrument, keep track that
                        # this packet was processed
                        if not self.packet_exists(match.start(0), end_packet_idx+1):
                            self._read_state[StateKey.IN_PROCESS_DATA].append([match.start(0),
                                                                               end_packet_idx+1,
                                                                               None, 0])
                        return_list.append((match.start(0), end_packet_idx+1))
                    else:
                        log.debug("Calculated checksum %s != received checksum %s for header %s and packet %d to %d",
                                  chksum, checksum, match.group(0)[1:32], match.end(0), end_packet_idx)
                else:
                    log.debug('End packet at %d is not x03 for header %s',
                              end_packet_idx, match.group(0)[1:32])
        return return_list

    @staticmethod
    def calc_checksum(data):
        """
        Calculate SIO header checksum of data
        """
        crc = 65535
        if len(data) == 0:
            return '0000'
        for iData in range(0,len(data)):
            short = struct.unpack('H', data[iData] + '\x00')
            point = 255 & short[0]
            crc = crc ^ point
            for i in range(7, -1, -1):
                if crc & 1:
                    crc = (crc >> 1) ^ 33800
                else:
                    crc >>= 1
        crc = ~crc
        # convert to unsigned
        if crc < 0:
            crc += 65536
        # get rid of the '0x' from the hex string
        crc = "%s" % hex(crc)[2:].upper()
        # make sure we have the right format for comparing, must be 4 hex digits
        if len(crc) == 3:
            crc = '0' + crc
        elif len(crc) == 2:
            crc = '00' + crc
        elif len(crc) == 1:
            crc = '000' + crc
        log.trace("calculated checksum %s", crc)
        return crc

    def packet_exists(self, start, end):
        """
        Determine if this packet is already in the in process data
        """
        for packet in self._read_state[StateKey.IN_PROCESS_DATA]:
            if packet[0] == start + self._position[0] and packet[1] == end + self._position[0]:
                log.trace('Already added packet %s', packet)
                return True
        return False

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. Should be a list with
        a StateKey.UNPROCESSED_DATA value, a StateKey.IN_PROCESS_DATA value,
        and StateKey.TIMESTAMP value. The UNPROCESSED_DATA and IN_PROCESS_DATA
        are both arrays which contain an array of start and end indicies for their
        respective types of data.  The timestamp is an NTP4 format timestamp.
        @throws DatasetParserException if there is a bad state structure
        """
        log.debug("Setting state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not ((StateKey.UNPROCESSED_DATA in state_obj) and \
            (StateKey.IN_PROCESS_DATA in state_obj) and \
            (StateKey.TIMESTAMP in state_obj)):
            raise DatasetParserException("Invalid state keys")

        self._timestamp = state_obj[StateKey.TIMESTAMP]
        # store both the start and end point for this read of data within the file
        self._position = [state_obj[StateKey.UNPROCESSED_DATA][0][0],
                          state_obj[StateKey.UNPROCESSED_DATA][0][0]]
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        # it is possible to be in the middle of processing a packet.  Since we have to
        # process a whole packet, which may contain multiple samples, we have to
        # re-read the entire packet, then throw out the already received samples
        self._samples_to_throw_out = None
        self._mid_sample_packets = len(state_obj[StateKey.IN_PROCESS_DATA])
        if self._mid_sample_packets > 0 and state_obj[StateKey.IN_PROCESS_DATA][0][3] > 0:
            self._samples_to_throw_out = state_obj[StateKey.IN_PROCESS_DATA][0][3]

        # make sure we have cleaned the chunker out of old data so there are no wrap arounds
        self._chunker.clean_all_chunks()

        # seek to the first unprocessed position
        self._stream_handle.seek(state_obj[StateKey.UNPROCESSED_DATA][0][0])
        log.debug('Seeking to %d', state_obj[StateKey.UNPROCESSED_DATA][0][0])

    def _increment_state(self, timestamp, returned_records = 0):
        """
        Increment which data packets have been processed, and which are still
        unprocessed.  This keeps track of which data has been received,
        since blocks may come out of order or appear at a later time in an already
        processed file.
        @param timestamp The NTP4 timestamp
        """
        log.debug("Incrementing current state: %s", self._read_state)

        while self._mid_sample_packets > 0 and len(self._chunk_sample_count) > 0:
            # if we were in the middle of processing, we need to drop the parsed
            # packets sample count because that in process packet already exists
            self._chunk_sample_count.pop(0)
            # decrease the mid sample number remaining
            self._mid_sample_packets -= 1

        for packet_idx in range (0, len(self._read_state[StateKey.IN_PROCESS_DATA])):
            if self._read_state[StateKey.IN_PROCESS_DATA][packet_idx][2] is None and \
            len(self._chunk_sample_count) > 0:
                self._read_state[StateKey.IN_PROCESS_DATA][packet_idx][2] = self._chunk_sample_count.pop(0)
                # adjust for current file position, only do this once when filling in sample count
                self._read_state[StateKey.IN_PROCESS_DATA][packet_idx][0] += self._position[0]
                self._read_state[StateKey.IN_PROCESS_DATA][packet_idx][1] += self._position[0]

        n_removed = 0
        if returned_records > 0:
            # need to adjust position to be relative to the entire file, not just the
            # currently read section, so add the initial position to the in process packets
            log.debug('records to be returned %d', returned_records)
            total_remain = returned_records
            adj_packets = []
            for packet_idx in range(0, len(self._read_state[StateKey.IN_PROCESS_DATA])):
                adj_packet_idx = packet_idx - n_removed
                this_packet = self._read_state[StateKey.IN_PROCESS_DATA][adj_packet_idx]
                if this_packet[2] > 0:
                    # this packet has data samples in it
                    this_packet_remain = this_packet[2] - this_packet[3]
                    # increase the number of samples that have been pulled out
                    self._read_state[StateKey.IN_PROCESS_DATA][adj_packet_idx][3] += total_remain
                    # find out if packet is done, if so remove it
                    if self._read_state[StateKey.IN_PROCESS_DATA][adj_packet_idx][3] >= this_packet[2]:
                        # this packet has had all the samples pulled out from it, remove it from in process
                        adj_packets.append([this_packet[0], this_packet[1]])
                        ret = self._read_state[StateKey.IN_PROCESS_DATA].pop(adj_packet_idx)
                        n_removed += 1
                    elif self._read_state[StateKey.IN_PROCESS_DATA][adj_packet_idx][3] < 0:
                        self._read_state[StateKey.IN_PROCESS_DATA][adj_packet_idx][3] = 0

                    total_remain -= this_packet_remain

                else:
                    # this packet has no samples, no need to process further
                    adj_packets.append([this_packet[0], this_packet[1]])
                    ret = self._read_state[StateKey.IN_PROCESS_DATA].pop(adj_packet_idx)
                    n_removed += 1

            if len(adj_packets) > 0 and self._read_state[StateKey.IN_PROCESS_DATA] == []:
                # this is the last of the in process data, now process unprocessed data, so
                # go back to the beginning of the file
                log.debug('Resetting file to the start')
                self._stream_handle.seek(0)
                self._position = [0,0]
                # clear out the chunker so we don't wrap around data
                self._chunker.clean_all_chunks()

            log.trace('In process %s', self._read_state[StateKey.IN_PROCESS_DATA])

            # first combine the in process data packet indicies
            combined_packets = self._combine_adjacent_packets(adj_packets)
            # loop over combined packets and remove them from unprocessed data
            for packet in combined_packets:
                # find which unprocessed section this packet is in
                for unproc in self._read_state[StateKey.UNPROCESSED_DATA]:
                    if packet[0] >= unproc[0] and packet[1] <= unproc[1]:
                        # packet is within this unprocessed data, remove it
                        self._read_state[StateKey.UNPROCESSED_DATA].remove(unproc)
                        # add back any data still unprocessed on either side
                        if packet[0] > unproc[0]:
                            self._read_state[StateKey.UNPROCESSED_DATA].append([unproc[0], packet[0]])
                        if packet[1] < unproc[1]:
                            self._read_state[StateKey.UNPROCESSED_DATA].append([packet[1], unproc[1]])
                        # once we have found which unprocessed section this packet is in,
                        # move on to next packet
                        break;
                self._read_state[StateKey.UNPROCESSED_DATA] = sorted(self._read_state[StateKey.UNPROCESSED_DATA])
                self._read_state[StateKey.UNPROCESSED_DATA] = self._combine_adjacent_packets(
                    self._read_state[StateKey.UNPROCESSED_DATA])

        self._read_state[StateKey.TIMESTAMP] = timestamp

    def _combine_adjacent_packets(self, packets):
        """
        Combine packets which are adjacent and have the same start/end into one packet
        i.e [[a,b], [b,c]] -> [[a,c]]
        @param packets An array of packets, with the form [[start, end], [next_start, next_end], ...]
        @retval A new array of packets where adjacent packets will have their indicies combined into one 
        """
        combined_packets = []
        idx = 0
        while idx < len(packets):
            start_idx = packets[idx][0]
            # loop until the end of this packet doesn't equal the start of the following packet
            next_inc = 0
            while idx + next_inc + 1 < len(packets) and \
            packets[idx + next_inc][1] == packets[idx + next_inc + 1][0]:
                next_inc = next_inc + 1

            end_idx = packets[idx + next_inc][1]
            # append the new combined packet indices
            combined_packets.append([start_idx, end_idx])
            idx = idx + next_inc + 1
        return combined_packets

    def get_num_records(self, num_records):
        """
        Loop through all the in process or unprocessed data until the requested number of records are found
        """
        while len(self._record_buffer) < num_records:
            # read unprocessed data packet from the file, starting with in process data
            log.debug('have %d records, waiting for %d records, samples to throw out %s',
                      len(self._record_buffer), num_records, self._samples_to_throw_out)
            if len(self._read_state[StateKey.IN_PROCESS_DATA]) > 0:
                # there is in process data, read that first
                data = self._get_next_unprocessed_data(self._read_state[StateKey.IN_PROCESS_DATA])
            else:
                # there is no in process data, read the unprocessed data
                data = self._get_next_unprocessed_data(self._read_state[StateKey.UNPROCESSED_DATA])

            if data and len(self._record_buffer) < num_records:
                # there is more data, add it to the chunker after escaping acoustic modem characters
                data = data.replace(b'\x186b', b'\x2b')
                data = data.replace(b'\x1858', b'\x18')
                # there is more data, add it to the chunker
                self._chunker.add_chunk(data, self._timestamp)

                # parse the chunks now that there is new data in the chunker
                result = self.parse_chunks()

                # this unprocessed block has now been parsed, increment the state, using
                # last samples timestamp to update the state timestamp
                self._increment_state(self._timestamp)

                # clear out any non matching data.  Don't do this during parsing because
                # it cleans out actual data too because of the way the chunker works
                (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)
                while non_data is not None:
                    (nd_timestamp, non_data) = self._chunker.get_next_non_data(clean=True)

                # add the parsed chunks to the record_buffer
                self._record_buffer.extend(result)
            else:
                 # if there is no more data, it is the end of the file, stop looping
                break
            # sleep in case this is a long loop
            gevent.sleep(0)

    def get_records(self, num_records):
        """
        Go ahead and execute the data parsing loop up to a point. This involves
        getting data from the file, stuffing it in to the chunker, then parsing
        it and publishing.
        @param num_records The number of records to gather
        @retval Return the list of particles requested, [] if none available
        """
        if num_records <= 0:
            return []

        if self._samples_to_throw_out is not None:
            num_records += self._samples_to_throw_out
            log.debug('num records increased by %d', self._samples_to_throw_out)

        self.get_num_records(num_records)

        if self._samples_to_throw_out is not None:
            num_records -= self._samples_to_throw_out

        if self._samples_to_throw_out is not None:
            if len(self._record_buffer) < (num_records + self._samples_to_throw_out):
                num_to_fetch = len(self._record_buffer) - self._samples_to_throw_out
            else:
                num_to_fetch = num_records
        else:
            if len(self._record_buffer) < num_records:
                num_to_fetch = len(self._record_buffer)
            else:
                num_to_fetch = num_records
        log.debug("Yanking %s records of %s requested",
                  num_to_fetch,
                  num_records)
        # pull particles out of record_buffer and publish
        return_list = self._yank_particles(num_to_fetch)

        # this is a special case if we are switching from in process data to unprocessed data in
        # order to get all the records required
        if num_to_fetch < num_records and self._position == [0,0]:
            remain_records = num_records - num_to_fetch
            self.get_num_records(remain_records)
            if len(self._record_buffer) < remain_records:
                num_to_fetch = len(self._record_buffer)
            else:
                num_to_fetch = remain_records
            log.debug("Yanking extra %s records of %s requested",
                  num_to_fetch,
                  remain_records)
            return_list_2 = self._yank_particles(num_to_fetch)
            return_list.extend(return_list_2)
            log.debug('return list extended with %s, total len %d', return_list_2, len(return_list))

        return return_list

    def _get_next_unprocessed_data(self, unproc):
        """
        Using the UNPROCESSED_DATA state, determine if there are any more unprocessed blocks,
        and if there are read in the next one
        @retval The next unprocessed data packet, or [] if no more unprocessed data
        """
        # see if there is more unprocessed data at a later file position (don't go backwards)
        next_idx = 0
        log.debug('Getting next unprocessed from %s, last position %d', unproc, self._position[1])
        while len(unproc) > next_idx and unproc[next_idx][1] <= self._position[1]:
            next_idx = next_idx + 1

        if len(unproc) > next_idx:
            data_len = unproc[next_idx][1] - unproc[next_idx][0]
            # only seek forwards, if we have already read part of a unprocessed section
            # don't go back to the beginning
            if unproc[next_idx][0] > self._position[1]:
                log.debug("Seeking to %d", unproc[next_idx][0])
                self._stream_handle.seek(unproc[next_idx][0])
                self._position[0] = unproc[next_idx][0]
            data = self._stream_handle.read(data_len)
            self._position[1] = self._position[0] + data_len
            log.debug('read %d bytes starting at %d', data_len, self._position[0])
        else:
            log.debug('Found no data, %s, next_idx=%d', unproc, next_idx)
            data = []
        return data

    def _yank_particles(self, num_to_fetch):
        """
        Get particles out of the buffer and publish them. Update the state
        of what has been published, too.
        @param num_records The number of particles to remove from the buffer
        @retval A list with num_records elements from the buffer. If num_records
        cannot be collected (perhaps due to an EOF), the list will have the
        elements it was able to collect.
        """
        return_list = []
        if self._samples_to_throw_out is not None:
            records_to_return = self._record_buffer[self._samples_to_throw_out:(num_to_fetch+self._samples_to_throw_out)]
            self._record_buffer = self._record_buffer[(num_to_fetch+self._samples_to_throw_out):]
            # reset samples to throw out
            self._samples_to_throw_out = None
        else:
            records_to_return = self._record_buffer[:num_to_fetch]
            self._record_buffer = self._record_buffer[num_to_fetch:]
        if len(records_to_return) > 0:
            for item in records_to_return:
                return_list.append(item)
            self._publish_sample(return_list)
            # need to keep track of which records have actually been returned
            self._increment_state(self._timestamp, num_to_fetch)
            self._state = self._read_state
            log.debug("Sending parser state [%s] to driver", self._state)
            self._state_callback(self._state) # push new state to driver

        return return_list

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state (ie "(sample, state)"). An empty list of
            nothing was parsed.
        """            
        raise NotImplementedException("Must write parse_chunks()!")

