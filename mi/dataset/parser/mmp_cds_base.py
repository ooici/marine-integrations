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

import gevent
import msgpack
import ntplib
import time

from mi.core.log import get_logger

log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import DatasetParserException, SampleException, NotImplementedException
from mi.dataset.dataset_parser import BufferLoadingParser

# The number of items in a list associated unpacked data within a McLane Moored Profiler cabled docking station
# data chunk
NUM_MMP_CDS_UNPACKED_ITEMS = 3

# A message to be reported when the state provided to the parser is missing PARTICLES_RETURNED
PARTICLES_RETURNED_MISSING_ERROR_MSG = "PARTICLES_RETURNED missing from state"

# A message to be reported when the mmp cds msgpack data cannot be parsed correctly
UNABLE_TO_PARSE_MSGPACK_DATA_MSG = "Unable to parse msgpack data into expected parameters"

# A message to be reported when unable to iterate through unpacked msgpack data
UNABLE_TO_ITERATE_THROUGH_UNPACKED_MSGPACK_MSG = "Unable to iterate through unpacked msgpack data"

# A message to be reported when the format of the unpacked msgpack data does nto match expected
UNEXPECTED_UNPACKED_MSGPACK_FORMAT_MSG = "Unexpected unpacked msgpack format"


class StateKey(BaseEnum):
    PARTICLES_RETURNED = 'particles_returned'  # holds the number of particles returned


class MmpCdsParserDataParticleKey(BaseEnum):
    RAW_TIME_SECONDS = 'raw_time_seconds'
    RAW_TIME_MICROSECONDS = 'raw_time_microseconds'


class MmpCdsParserDataParticle(DataParticle):
    """
    Class for building a data particle given parsed data as received from a McLane Moored Profiler connected to
    a cabled docking station.
    """

    def _get_mmp_cds_subclass_particle_params(self, subclass_specific_msgpack_unpacked_data):
        """
        This method is expected to be implemented by subclasses.  It is okay to let the implemented method to
        allow the following exceptions to propagate: ValueError, TypeError, IndexError, KeyError
        @param dict_data the dictionary data containing the specific particle parameter name value pairs
        @return a list of particle params specific to the subclass
        """

        # This implementation raises a NotImplementedException to enforce derived classes to implement
        # this method.
        raise NotImplementedException

    def _build_parsed_values(self):
        """
        This method generates a list of particle parameters using the self.raw_data which is expected to be
        a list of three items.  The first item is expected to be the "raw_time_seconds".  The second item
        is expected to be the "raw_time_microseconds".  The third item is an element type specific to the subclass.
        This method depends on an abstract method (_get_mmp_cds_subclass_particle_params) to generate the specific
        particle parameters from the third item element.
        @throws SampleException If there is a problem with sample creation
        """
        try:

            raw_time_seconds = self.raw_data[0]
            raw_time_microseconds = self.raw_data[1]
            raw_time_seconds_encoded = self._encode_value(MmpCdsParserDataParticleKey.RAW_TIME_SECONDS,
                                                          raw_time_seconds, int)
            raw_time_microseconds_encoded = self._encode_value(MmpCdsParserDataParticleKey.RAW_TIME_MICROSECONDS,
                                                               raw_time_microseconds, int)

            ntp_timestamp = ntplib.system_to_ntp_time(raw_time_seconds + raw_time_microseconds/1000000.0)

            log.debug("Calculated timestamp from raw %.10f", ntp_timestamp)

            self.set_internal_timestamp(ntp_timestamp)

            subclass_particle_params = self._get_mmp_cds_subclass_particle_params(self.raw_data[2])

        except (ValueError, TypeError, IndexError, KeyError) as ex:
            log.warn(UNABLE_TO_PARSE_MSGPACK_DATA_MSG)
            raise SampleException("Error (%s) while decoding parameters in data: [%s]"
                                  % (ex, self.raw_data))

        result = [raw_time_seconds_encoded,
                  raw_time_microseconds_encoded] + subclass_particle_params

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

        if state is None:
            state = {StateKey.PARTICLES_RETURNED: 0}

        # Call the superclass constructor
        super(MmpCdsParser, self).__init__(config,
                                           stream_handle,
                                           state,
                                           self.sieve_function,
                                           state_callback,
                                           publish_callback,
                                           *args, **kwargs)

        # If provided a state, set it.  This needs to be done post superclass __init__
        if state is not None:
            self.set_state(state)

    def set_state(self, state_obj):
        """
        This method will set the state of the MmpCdsParser to a given state
        @param state_obj the updated state to use
        """
        log.debug("Attempting to set state to: %s", state_obj)
        # First need to make sure the state type is a dict
        if not isinstance(state_obj, dict):
            log.warn("Invalid state structure")
            raise DatasetParserException("Invalid state structure")
        # Then we need to make sure that the provided state includes particles returned information
        if not (StateKey.PARTICLES_RETURNED in state_obj):
            log.debug(PARTICLES_RETURNED_MISSING_ERROR_MSG)
            raise DatasetParserException(PARTICLES_RETURNED_MISSING_ERROR_MSG)

        # Clear out any pre-existing chunks
        self._chunker.clean_all_chunks()

        self._record_buffer = []

        # Set the state and read state to the provide state
        self._state = state_obj

        # Always seek to the beginning of the buffer to read all records
        self._stream_handle.seek(0)

    def _yank_particles(self, num_records):
        """
        Get particles out of the buffer and publish them. Update the state
        of what has been published, too.
        @param num_records The number of particles to remove from the buffer
        @retval A list with num_records elements from the buffer. If num_records
        cannot be collected (perhaps due to an EOF), the list will have the
        elements it was able to collect.
        """
        particles_returned = 0

        if self._state is not None and StateKey.PARTICLES_RETURNED in self._state and \
                self._state[StateKey.PARTICLES_RETURNED] > 0:
            particles_returned = self._state[StateKey.PARTICLES_RETURNED]

        total_num_records = len(self._record_buffer)

        num_records_remaining = total_num_records - particles_returned

        if num_records_remaining < num_records:
            num_to_fetch = num_records_remaining
        else:
            num_to_fetch = num_records

        log.debug("Yanking %s records of %s requested",
                  num_to_fetch,
                  num_records)

        return_list = []

        end_range = particles_returned + num_to_fetch

        records_to_return = self._record_buffer[particles_returned:end_range]
        if len(records_to_return) > 0:

            log.info(records_to_return)

            # Update the number of particles returned
            self._state[StateKey.PARTICLES_RETURNED] = particles_returned+num_to_fetch

            # strip the state info off of them now that we have what we need
            for item in records_to_return:
                log.debug("Record to return: %s", item)
                return_list.append(item)

            self._publish_sample(return_list)
            log.trace("Sending parser state [%s] to driver", self._state)
            file_ingested = False
            if self.file_complete and total_num_records == self._state[StateKey.PARTICLES_RETURNED]:
                # file has been read completely and all records pulled out of the record buffer
                file_ingested = True
            self._state_callback(self._state, file_ingested)  # push new state to driver

        return return_list

    def get_block(self, size=1024):
        """
        This function overrides the get_block function in BufferLoadingParser
        to read the entire file rather than break it into chunks.
        @return The length of data retrieved.
        @throws EOFError when the end of the file is reached.
        """
        # Read in data in blocks so as to not tie up the CPU.
        eof = False
        data = ''
        while not eof:
            next_block = self._stream_handle.read(size)
            if next_block:
                data = data + next_block
                gevent.sleep(0)
            else:
                eof = True

        if data != '':
            self._timestamp = float(ntplib.system_to_ntp_time(time.time()))
            log.debug("Calculated current time timestamp %.10f", self._timestamp)
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
        return [(0, len(raw_data))]

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

        # We need to use the msgpack library and instantiate an Unpacker to process the chunk of data
        unpacker = msgpack.Unpacker()

        # Process each chunk as long as one exists
        if chunk is not None:

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

                        # Extract the sample an provide the particle class which could be different for each
                        # derived MmpCdsParser
                        sample = self._extract_sample(self._particle_class, None, unpacked_data, None)

                        # If we extracted a sample, add it to the list of samples to retrun
                        if sample:
                            samples.append(sample)

                    else:
                        log.debug(UNEXPECTED_UNPACKED_MSGPACK_FORMAT_MSG)
                        raise SampleException(UNEXPECTED_UNPACKED_MSGPACK_FORMAT_MSG)

                    # Let's call gevent.sleep with 0 to allow for the CPU to be used by another gevent thread just
                    # in case we are dealing with a large list of unpacked msgpack data
                    gevent.sleep(0)

            except TypeError:
                log.warn(UNABLE_TO_ITERATE_THROUGH_UNPACKED_MSGPACK_MSG)
                raise SampleException(UNABLE_TO_ITERATE_THROUGH_UNPACKED_MSGPACK_MSG)

            # For each sample we retrieved in the chunk, let's create a tuple containing the sample, and the parser's
            # current read state
            for sample in samples:
                result_particles.append(sample)

        return result_particles