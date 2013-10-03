#!/usr/bin/env python

"""
@package mi.dataset.parser.mflm MFLM common data set parser
@file mi/dataset/parser/mflm.py
@author Emily Hahn
This module contains classes that handle parsing MFLM instruments
from the common MFLM control file.
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import re

from mi.core.common import BaseEnum
from mi.core.log import get_logger; log = get_logger()
from mi.core.instrument.chunker import StringChunker
from mi.core.exceptions import DatasetParserException
from mi.core.instrument.data_particle import DataParticleKey

# SIO Main controller header and data for ctdmo in binary
# groups: ID, Number of Data Bytes, POSIX timestamp, block number, data
HEADER_REGEX = b'\x01([A-Z0-9]{2})[0-9]{7}_([0-9A-F]{4})[a-z]([0-9A-F]{8})_([0-9A-F]{2})_[0-9A-F]{4}\x02([\x00-\xFF]*?)\x03'
HEADER_MATCHER = re.compile(HEADER_REGEX)

# blocks can be uniquely identified a combination of block number and timestamp,
# since block numbers roll over after 255
# each block may contain multiple data samples
class StateKey(BaseEnum):
    TIMESTAMP = "timestamp" # holds the most recent data sample timestamp
    PROCESSED_BLOCKS = "processed_blocks" # holds a tuple of all processed block numbers and their associated block timestamps 
    IN_PROCESS_BLOCKS = "in_process_blocks" # holds a tuple of block numbers in process now and their associated block timestamps

class MflmParser(object):

    def __init__(self, config, stream_handle, state, sieve_fn,
                 state_callback, publish_callback, instrument_id):
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
        @param instrument_id the text string indicating the instrument to
           monitor, can be 'CT', 'AD', 'FL', 'DO', or 'PH'
        """
        self._chunker = StringChunker(self.sieve_function)
        self._stream_handle = stream_handle
        self._state = state
        self._state_callback = state_callback
        self._publish_callback = publish_callback
        self._config = config
        if instrument_id not in ['CT', 'AD', 'FL', 'DO', 'PH']:
            raise DatasetParserException('instrument id %s is not recognized', instrument_id)
        self._instrument_id = instrument_id

        #build class from module and class name, then set the state
        self._particle_module = __import__(config.get("particle_module"), fromlist = [config.get("particle_class")])
        self._particle_class = getattr(self._particle_module, config.get("particle_class"))

        self._timestamp = 0.0
        self._record_buffer = [] # holds list of records
        self._read_state = {StateKey.TIMESTAMP:0.0, StateKey.PROCESSED_BLOCKS:[], StateKey.IN_PROCESS_BLOCKS:[]}

        if state:
            self.set_state(self._state)

    def sieve_function(self, raw_data):
        """
        Sort through the raw data to identify new blocks of data that need processing.
        This sieve identifies the SIO header and returns just the data block identified
        inside the header.  This does a check to make sure the instrument id matches
        the selected instrument, and checks the state processed blocks to see if
        a block has been processed already.  
        """
        return_list = []

        for match in HEADER_MATCHER.finditer(raw_data):
            id_str = match.group(1)
            log.debug('found match for instrument %s', id_str)
            if id_str == self._instrument_id:
                data_len = int(match.group(2), 16)
                timestamp = match.group(3)
                block_number = int(match.group(4), 16)

                if len(match.group(5)) != data_len:
                    log.warn('data length in header %d does not match data length %d',
                             data_len, len(match.group(5)))

                if not self.in_processed_block(block_number):
                    # this block is new, append it
                    log.debug('Appending block %d, processed_blocks %s', block_number,
                              self._state[StateKey.PROCESSED_BLOCKS])
                    self._state[StateKey.IN_PROCESS_BLOCKS].append((block_number, timestamp))
                    return_list.append((match.start(0), match.end(0)))
                elif self.in_processed_block(block_number):
                    # block number can wrap around 0-255, compare timestamp to find out
                    # if blocks are really different
                    block_idx = self.processed_block_idx(block_number)
                    prev_timestamp = self._state[StateKey.PROCESSED_BLOCKS][block_idx][1]
                    if prev_timestamp != timestamp:
                        log.debug("Appending block %d", block_number)
                        # same block number but different timestamps, this block is new
                        self._state[StateKey.IN_PROCESS_BLOCKS].append((block_number, timestamp))
                        return_list.append((match.start(0), match.end(0)))
        return return_list

    def in_processed_block(self, block_number):
        """
        Loop through each of the blocks and try to find a matching block_number
        """
        for block in self._state[StateKey.PROCESSED_BLOCKS]:
            if block[0] == block_number:
                log.debug("Found matching block number %d", block_number)
                return True

        return False

    def processed_block_idx(self, block_number):
        idx = -1
        for block in self._state[StateKey.PROCESSED_BLOCKS]:
            idx = idx + 1
            if block[0] == block_number:
                return idx
        return -1

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. Should be a list with
        a StateKey.POSITION value and StateKey.TIMESTAMP value. The position is
        number of bytes into the file, the timestamp is an NTP4 format timestamp.
        @throws DatasetParserException if there is a bad state structure
        """
        log.trace("Attempting to set state to: %s", state_obj)
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        if not ((StateKey.PROCESSED_BLOCKS in state_obj) and \
            (StateKey.IN_PROCESS_BLOCKS in state_obj) and (StateKey.TIMESTAMP in state_obj)):
            raise DatasetParserException("Invalid state keys")

        self._timestamp = state_obj[StateKey.TIMESTAMP]
        self._record_buffer = []
        self._state = state_obj
        self._read_state = state_obj

        # always start at the beginning of the file, need to re-read everything
        self._stream_handle.seek(0)

    def _increment_state(self, timestamp):
        """
        Increment which data blocks have been processed by moving the in process
        blocks to processed.  This keeps track of which blocks have been received,
        since blocks may come out of order or appear at a later time in an already
        processed file. 
        """
        log.trace("Incrementing current state: %s by moving in process blocks to processed",
                  self._read_state)

        for block in self._read_state[StateKey.IN_PROCESS_BLOCKS]:
            self._read_state[StateKey.PROCESSED_BLOCKS].append(block)
        self._read_state[StateKey.IN_PROCESS_BLOCKS] = []
        self._read_state[StateKey.TIMESTAMP] = timestamp

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

        # default byte size to read from the file
        size = 1024

        while len(self._record_buffer) < num_records:
            # read data from the file
            data = self._stream_handle.read(size)
            while data and len(self._record_buffer) < num_records:
                # first need to do special processing on data to handle escape sequences
                # replace 0x182b with 0x2b and 0x1858 into 0x18
                data = data.replace(b'\x182b', b'\x2b')
                data = data.replace(b'\x1858', b'\x18')
                # there is more data, add it to the chunker
                self._chunker.add_chunk(data, self._timestamp)

                # parse the chunks now that there is new data in the chunker
                result = self.parse_chunks()

                # this block has now been parsed, increment the state, using
                # last samples timestamp to update the state timestamp 
                self._increment_state(self._timestamp)

                # add the parsed chunks to the record_buffer
                self._record_buffer.extend(result)

                # see if there is more data
                data = self._stream_handle.read(size)

            # if there is no more data, it is the end of the file, stop looping
            if not data:
                break

        log.debug('found %d records', len(self._record_buffer))
        # pull particles out of record_buffer and publish        
        return self._yank_particles(num_records)

    def _yank_particles(self, num_records):
        """
        Get particles out of the buffer and publish them. Update the state
        of what has been published, too.
        @param num_records The number of particles to remove from the buffer
        @retval A list with num_records elements from the buffer. If num_records
        cannot be collected (perhaps due to an EOF), the list will have the
        elements it was able to collect.
        """
        if len(self._record_buffer) < num_records:
            num_to_fetch = len(self._record_buffer)
        else:
            num_to_fetch = num_records
        log.debug("Yanking %s records of %s requested",
                  num_to_fetch,
                  num_records)

        return_list = []
        records_to_return = self._record_buffer[:num_to_fetch]
        self._record_buffer = self._record_buffer[num_to_fetch:]
        if len(records_to_return) > 0:
            for item in records_to_return:
                return_list.append(item)
            self._publish_sample(return_list)
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

    def _publish_sample(self, samples):
        """
        Publish the samples with the given publishing callback.
        @param samples The list of data particle to publish up to the system
        """
        if isinstance(samples, list):
            self._publish_callback(samples)
        else:
            self._publish_callback([samples])

    @staticmethod
    def _extract_sample(particle_class, regex, line, timestamp):
        """
        Extract sample from a response line if present and publish
        parsed particle

        @param particle_class The class to instantiate for this specific
            data particle. Parameterizing this allows for simple, standard
            behavior from this routine
        @param regex The regular expression that matches a data sample
        @param line string to match for sample.
        @retval return a raw particle if a sample was found, else None
        """
        #parsed_sample = None
        particle = None
        if regex.match(line):
            particle = particle_class(line, internal_timestamp=timestamp,
                                      preferred_timestamp=DataParticleKey.INTERNAL_TIMESTAMP)
            #parsed_sample = particle.generate()

        return particle




