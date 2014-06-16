#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf_ckl_mmp_cds
@file marine-integrations/mi/dataset/parser/mmp_cds_base.py
@author Mark Worden
@brief Base Parser for the MmpCds dataset drivers
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import copy
import gevent
import msgpack
import ntplib
import time

from mi.core.log import get_logger

log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import DatasetParserException, SampleException
from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.dataset_parser import BufferLoadingParser

# The number of items in a list associated unpackaed data within a McLane Moored Profiler cabled docking station
# data chunk
NUM_MMP_CDS_UNPACKED_ITEMS = 3


class StateKey(BaseEnum):
    POSITION = 'position'  # holds the file position


class MmpCdsParserDataParticleKey(BaseEnum):
    RAW_TIME_SECONDS = 'raw_time_seconds'
    RAW_TIME_MICROSECONDS = 'raw_time_microseconds'


class MmpCdsParserDataParticle(DataParticle):
    """
    Class for building a data particle given parsed data as received from a McLane Moored Profiler connected to
    a cabled docking station.
    """

    def _get_mmp_cds_subclass_particle_params(self, dict_data):
        """
        This method is expected to be implemented by subclasses.
        @param dict_data the dictionary data containing the specific particle parameter name value pairs
        @return a list of particle params specific to the subclass
        """

        # This implementation raises a NotImplemented exception to enforce derived classes to implement
        # this method.
        raise NotImplemented

    def _build_parsed_values(self):
        """
        This method generates a list of particle parameters using the self.raw_data which is expected to be
        a list of three items.  The first item is expected to be the "raw_time_seconds".  The second item
        is expected to be the "raw_time_microseconds".  The third item is expected to be a dictionary.  This
        method depends on an abstract method (_get_mmp_cds_subclass_particle_params) to generate the specific
        particle parameters from the third list item dictionary content.
        @throws SampleException If there is a problem with sample creation
        """
        try:

            raw_time_seconds = self._encode_value(MmpCdsParserDataParticleKey.RAW_TIME_SECONDS,
                                                  self.raw_data[0], int)
            raw_time_microseconds = self._encode_value(MmpCdsParserDataParticleKey.RAW_TIME_MICROSECONDS,
                                                       self.raw_data[1], int)

            subclass_particle_params = self._get_mmp_cds_subclass_particle_params(self.raw_data[2])

        except (ValueError, TypeError, IndexError) as ex:
            log.debug("Raising SampleException as a result of unexpected msgpack data")
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        result = [raw_time_seconds,
                  raw_time_microseconds] + subclass_particle_params

        log.debug('MmpCdsParserDataParticle: particle=%s', result)
        return result


class MmpCdsParser(BufferLoadingParser):
    """
    Class for parsing data as received from a McLane Moored Profiler connected to a cabled docking station.
    """

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an MmpCdsParser object.
        @param config The configuration for this MmpCdsParser parser
        @param state The state the MmpCdsParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the MmpCds data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        """

        # Initialize the record buffer to an empty list
        self._record_buffer = []

        # Initialize the read state to the POSITION being 0
        self._read_state = {StateKey.POSITION: 0}

        # Pop off the kwargs the key value pairs associated with the DataSetDriverConfigKeys.PARTICLE_CLASS key
        self._particle_class = kwargs.pop(DataSetDriverConfigKeys.PARTICLE_CLASS)

        # Call the superclass constructor
        super(MmpCdsParser, self).__init__(config,
                                           stream_handle,
                                           state,
                                           self.sieve_function,
                                           state_callback,
                                           publish_callback,
                                           *args, **kwargs)

        # If provided a state, set it.  This needs to be done post superclass __init__
        if state:
            self.set_state(state)

    def set_state(self, state_obj):
        """
        This method will set or re-set the state of the MmpCdsParser to a given state
        @param state_obj the updated state to use
        """
        log.debug("Attempting to set state to: %s", state_obj)
        # First need to make sure the state type is a dict
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        # Then we need to make sure that the provided state includes position information
        if not (StateKey.POSITION in state_obj):
            raise DatasetParserException("Invalid state keys")

        # Clear out any pre-existing chunks
        self._chunker.clean_all_chunks()
        # Clear the record buffer
        self._record_buffer = []

        # Set the state and read state to the provide state
        self._state = state_obj
        self._read_state = state_obj

        # Change the pointer into the stream to the position specified within the provided state
        self._stream_handle.seek(state_obj[StateKey.POSITION])

    def _increment_state(self, increment):
        """
        Increment the parser state (i.e. position into the read state)
        @param increment The updated offset into the read state
        """
        self._read_state[StateKey.POSITION] += increment

    def get_block(self, size=1024):
        """
        This function overrides the get_block function in BufferLoadingParser
        to read the entire file rather than break it into chunks.
        @return The length of data retrieved.
        @throws EOFError when the end of the file is reached.
        """
        # Read in data in blocks so as to not tie up the CPU.
        block_size = 1024
        eof = False
        data = ''
        while not eof:
            next_block = self._stream_handle.read(block_size)
            if next_block:
                data = data + next_block
                gevent.sleep(0)
            else:
                eof = True

        if data != '':
            self._timestamp = float(ntplib.system_to_ntp_time(time.time()))
            self._chunker.add_chunk(data, self._timestamp)
            self.file_complete = True
            return len(data)
        else:  # EOF
            self.file_complete = True
            raise EOFError

    def sieve_function(self, raw_data):
        """
        This method sorts through the raw data to identify new blocks of data that need processing.  This method
        identifies the start index as 0 and the length of the input raw_data as the end.
        @param raw_data the raw msgpack data for which to return the chunk location information
        @return the list of tuples containing the start index and range for each chunk
        """

        # The raw_data provided as input is considered the full recovered file byte stream, and will be
        # considered a single chunk.  In a file containing msgpack serialized data, there are not multiple
        # headers and records.
        return_list = [(0, len(raw_data))]

        return return_list

    def parse_chunks(self):
        """
        This method parses each chunk and attempts to extract samples to return.
        @return for each discovered sample, a list of tuples containing each particle and associated state position
        # information
        """
        # Initialize the resultant particle list to return to an emtpy list
        result_particles = []

        # Obtain the next chunk to process
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        # Process each chunk as long as one exists
        while chunk is not None:

            # We need to use the msgpack library and instantiate an Unpacker to process the chunk of data
            unpacker = msgpack.Unpacker()

            # Feed the Unpacker instance the chunk of data
            unpacker.feed(chunk)

            # Initialize the list of samples for this chunk to an emtpy list
            samples = []

            # We need to put the following in a try block just in case the chunk of data provided is malformed
            try:
                # Let's iterate through each unpacked list item
                for unpacked_data in unpacker:

                    # The expectation is that an unpacked list item associated with a McLane Moored Profiler cabled
                    # docking station data chunk consists of a list of three items
                    if isinstance(unpacked_data, tuple) or isinstance(unpacked_data, list) and \
                            len(unpacked_data) == NUM_MMP_CDS_UNPACKED_ITEMS:

                        # Attempt to convert the raw time in seconds (unpacked_data[0]) and raw time in microseconds
                        # (unpacked_data[1]) to an NTP 64 timestamp
                        timestamp = ntplib.system_to_ntp_time(unpacked_data[0] + unpacked_data[1]/1000000.0)

                        # Extract the sample an provide the particle class which could be different for each
                        # derived MmpCdsParser
                        sample = self._extract_sample(self._particle_class, None, unpacked_data, timestamp)

                        # If we extracted a sample, add it to the list of samples to retrun
                        if sample:
                            samples.append(sample)

                    else:
                        log.debug("Raising SampleException as a result of a badly formed msgpack file")
                        raise SampleException("Invalid ctdpf_ckl_mmp_cds msgpack contents")

                    # Let's call gevent.sleep with 0 to allow for the CPU to be used by another gevent thread just
                    # in case we are dealing with a large list of unpacked msgpack data
                    gevent.sleep(0)

            except TypeError:
                log.debug("Raising SampleException as a result of not being able to iterate through the "
                          "unpacked msgpack data")
                raise SampleException("Invalid ctdpf_ckl_mmp_cds msgpack contents")

            # We're done with this chunk, let's offset the state
            self._increment_state(len(chunk))

            # For each sample we retrieved in the chunk, let's create a tuple containing the sample, and the parser's
            # current read state
            for sample in samples:
                result_particles.append((sample, copy.copy(self._read_state)))

            # Let's attempt to retrieve another chunk
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        return result_particles