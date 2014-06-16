#!/usr/bin/env pythonmrg

"""
@package mi.dataset.parser A collection of parsers that strip data blocks
out of files and feed them into the system.
@file mi/dataset/parser.py
@author Steve Foley
@brief Base classes for data set agent parsers
"""

__author__ = 'Steve Foley'
__license__ = 'Apache 2.0'

import time
import ntplib

from mi.core.log import get_logger ; log = get_logger()
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.exceptions import SampleException, RecoverableSampleException, SampleEncodingException
from mi.core.exceptions import NotImplementedException, UnexpectedDataException

class Parser(object):
    """ abstract class to show API needed for plugin poller objects """

    def __init__(self, config, stream_handle, state, sieve_fn,
                 state_callback, publish_callback, exception_callback = None):
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
        @param exception_callback The callback from the agent driver (and
           ultimately from the agent) where we send our error events to
           be published into ION
        """
        self._chunker = StringChunker(sieve_fn)
        self._stream_handle = stream_handle
        self._state = state
        self._state_callback = state_callback
        self._publish_callback = publish_callback
        self._exception_callback = exception_callback
        self._config = config
        #self._new_sequence = True

        # It was originally thought that we wanted to start a new sequence for every new file
        # But that has changed.  If we want this behavior back then we need to change
        # this back to true
        self._new_sequence = False

        #build class from module and class name, then set the state
        if config.get("particle_module"):
            self._particle_module = __import__(config.get("particle_module"), fromlist = [config.get("particle_class")])
            # if there is more than one particle class for this parser, this cannot be used, need to hard code the
            # particle class in the driver
            try:
                self._particle_class = getattr(self._particle_module, config.get("particle_class"))
            except TypeError:
                self._particle_class = None
        else:
            log.warn("No particle module specified in config")

    def start_new_sequence(self):
        """
        Reset the seqeunce flag to true
        """
        self._new_sequence = True

    def get_records(self, max_count):
        """
        Returns a list of particles (following the instrument driver structure).
        """
        raise NotImplementedException("get_records() not overridden!")

    def set_state(self, state):
        """
        Set the state of the last published data block.
        @param state The structure that indicates what state the parser should
           be in for this state. This structure should look like what was
           published for the last state.
        """
        raise NotImplementedException("set_state() not overridden!")
    
    def _publish_sample(self, samples):
        """
        Publish the samples with the given publishing callback.
        @param samples The list of data particle to publish up to the system
        """
        if isinstance(samples, list):
            self._publish_callback(samples)
        else:
            self._publish_callback([samples])
        
    def _extract_sample(self, particle_class, regex, raw_data, timestamp):
        """
        Extract sample from a response line if present and publish
        parsed particle

        @param particle_class The class to instantiate for this specific
            data particle. Parameterizing this allows for simple, standard
            behavior from this routine
        @param regex The regular expression that matches a data sample if regex
                     is none then process every line
        @param raw_data data to input into this particle.
        @retval return a raw particle if a sample was found, else None
        """
        particle = None

        try:
            if regex is None or regex.match(raw_data):
                particle = particle_class(raw_data, internal_timestamp=timestamp,
                                          preferred_timestamp=DataParticleKey.INTERNAL_TIMESTAMP,
                                          new_sequence=self._new_sequence)
                if self._new_sequence:
                    self._new_sequence = False

                # need to actually parse the particle fields to find out of there are errors
                particle.generate()
                encoding_errors = particle.get_encoding_errors()
                if encoding_errors:
                    log.warn("Failed to encode: %s", encoding_errors)
                    raise SampleEncodingException("Failed to encode: %s" % encoding_errors)

        except (RecoverableSampleException, SampleEncodingException) as e:
            log.error("Sample exception detected: %s raw data: %s", e, raw_data)
            if self._exception_callback:
                self._exception_callback(e)
            else:
                raise e

        return particle

class BufferLoadingParser(Parser):
    """
    This class loads data values into a record buffer, then offers up
    records from this buffer as they are requested. Parsers dont have
    to operate this way, but it can keep memory in check and smooth out
    stream inputs if they dont all come at once.
    """

    def __init__(self, config, stream_handle, state, sieve_fn,
                 state_callback, publish_callback, exception_callback = None):
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
        @param exception_callback The callback from the agent driver (and
           ultimately from the agent) where we send our error events to
           be published into ION
        """
        self._record_buffer = []
        self._timestamp = 0.0
        self.file_complete = False

        super(BufferLoadingParser, self).__init__(config, stream_handle, state,
                                                  sieve_fn, state_callback,
                                                  publish_callback,
                                                  exception_callback)

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
        try:
            while len(self._record_buffer) < num_records:
                self._load_particle_buffer()        
        except EOFError:
            self._process_end_of_file()
        return self._yank_particles(num_records)

    def _process_end_of_file(self):
        """
        Confirm that the chunker does not have any extra bytes left at the end of the file
        """
        (nd_timestamp, non_data) = self._chunker.get_next_non_data()
        (timestamp, chunk) = self._chunker.get_next_data()
        if (non_data and len(non_data) > 0):
            log.warn("Have extra unexplained non-data bytes at the end of the file:%s", non_data)
            raise UnexpectedDataException("Have extra unexplained non-data bytes at the end of the file:%s" % non_data)
        elif (chunk and len(chunk) > 0):
            log.warn("Have extra unexplained data chunk bytes at the end of the file:%s", chunk)
            raise UnexpectedDataException("Have extra unexplained data chunk bytes at the end of the file:%s" % chunk)

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
        log.trace("Yanking %s records of %s requested",
                  num_to_fetch,
                  num_records)

        return_list = []
        records_to_return = self._record_buffer[:num_to_fetch]
        self._record_buffer = self._record_buffer[num_to_fetch:]
        if len(records_to_return) > 0:
            self._state = records_to_return[-1][1] # state side of tuple of last entry
            # strip the state info off of them now that we have what we need
            for item in records_to_return:
                log.debug("Record to return: %s", item)
                return_list.append(item[0])
            self._publish_sample(return_list)
            log.trace("Sending parser state [%s] to driver", self._state)
            file_ingested = False
            if self.file_complete and len(self._record_buffer) == 0:
                # file has been read completely and all records pulled out of the record buffer
                file_ingested = True
            self._state_callback(self._state, file_ingested) # push new state to driver

        return return_list

    def _load_particle_buffer(self):
        """
        Load up the internal record buffer with some particles based on a
        gather from the get_block method.
        """
        while self.get_block():
            result = self.parse_chunks()
            self._record_buffer.extend(result)

    def get_block(self, size=1024):
        """
        Get a block of characters for processing
        @param size The size of the block to try to read
        @retval The length of data retreived
        @throws EOFError when the end of the file is reached
        """
        # read in some more data
        data = self._stream_handle.read(size)
        if data:
            self._chunker.add_chunk(data, ntplib.system_to_ntp_time(time.time()))
            return len(data)
        else: # EOF
            self.file_complete = True
            raise EOFError

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
