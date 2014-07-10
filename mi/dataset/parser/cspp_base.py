#!/usr/bin/env python

"""
@package mi.dataset.parser.dosta_abcdjm_cspp
@file marine-integrations/mi/dataset/parser/dosta_abcdjm_cspp.py
@author Mark Worden
@brief Parser for the dosta_abcdjm_cspp dataset driver
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

import copy
import re
import time

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.exceptions import DatasetParserException, UnexpectedDataException
from mi.core.instrument.data_particle import DataParticle
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

# The following defines a regular expression for one or more instances of a carriage return, line feed or both
CARRIAGE_RETURN_LINE_FEED_OR_BOTH = r'(?:\r\n|\r|\n)'

# The HEADER_REGEX below is used to capture a header that looks like the following:
#   Source File: C:\data\ooi\CSPP\uCSPP_2014_04_14_deploy\recoveredData\11079894.PPB
#   Processed: 06/12/2014 20:07:45
#   Using Version: 1.10
#   Device: OPT
#   Start Date: 04/17/2014
#   Timestamp (s)	Depth (m)	Data
HEADER_REGEX = r'^Source File:\s+([^\s]+)' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH + \
               'Processed:\s+([^\s]+)\s+([^\s]+)' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH + \
               'Using Version:\s+([^\s]+)' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH + \
               'Device:\s+([^\s]+)' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH +\
               'Start Date:\s+([^\s]+)' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH + \
               'Timestamp.+' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH

# A regex to capture a float value
FLOAT_REGEX = r'(?:[0-9]|[1-9][0-9])+\.[0-9]+'
# A regex to capture an int value
INT_REGEX = r'[1-9][0-9]*'
# A regex to match against one or more multiple consecutive whitespace characters
MULTIPLE_TAB_REGEX = r'\t+'

# A kwargs key used to access the data regular expression
DATA_REGEX_KWARGS_KEY = 'data_regex_kwargs_key'

# The following two keys are keys to be used with the PARTICLE_CLASSES_DICT
# The key for the metadata particle class
METADATA_PARTICLE_CLASS_KEY = 'metadata_particle_class'
# The key for the data particle class
DATA_PARTICLE_CLASS_KEY = 'data_particle_class'


class HeaderMatchesGroupNumber(BaseEnum):
    """
    An enum used to access match group values
    """
    SOURCE_FILE_PATH = 1
    PROCESSED_DATE = 2
    PROCESSED_TIME = 3
    PREPROCESSING_SOFTWARE_VERSION = 4
    DEVICE = 5
    START_DATE = 6

# An offset used to access the additional non-meta data match group values upon matching the header and first
# data record
DATA_MATCHES_GROUP_NUMBER_OFFSET = HeaderMatchesGroupNumber.START_DATE


class CsppMetadataParserDataParticleKey(BaseEnum):
    """
    An enum for the base cspp metadata particle parameters
    """
    LAST_CHARACTER_CONTROLLER_ID = 'last_character_controller_id'
    DAY_OF_YEAR_NUMBER = 'day_of_year_number'
    FRACTION_OF_DAY = 'fraction_of_day'
    SOURCE_FILE = 'source_file'
    PROCESSING_TIME = 'processing_time'
    PREPROCESSING_SOFTWARE_VERSION = 'preprocessing_software_version'
    START_DATE = 'start_date'


class EncodingRuleIndex(BaseEnum):
    """
    An enum used to access encoding rule tuple members
    """
    PARTICLE_KEY_INDEX = 0
    MATCHES_GROUP_NUMBER_INDEX = 1
    TYPE_ENCODING_INDEX = 2


# A group of metadata particle encoding rules used to simplify encoding using a loop
METADATA_PARTICLE_ENCODING_RULES = [
    (CsppMetadataParserDataParticleKey.SOURCE_FILE, HeaderMatchesGroupNumber.SOURCE_FILE_PATH, str),
    (CsppMetadataParserDataParticleKey.PREPROCESSING_SOFTWARE_VERSION, HeaderMatchesGroupNumber.DEVICE, str),
    (CsppMetadataParserDataParticleKey.START_DATE, HeaderMatchesGroupNumber.START_DATE, str),
]

# The following items are used to index into source file name string
LAST_CHARACTER_CONTROLLER_ID_SOURCE_FILE_CHAR_POSITION = 0
DAY_OF_YEAR_NUMBER_SOURCE_FILE_STARTING_CHAR_POSITION = 1
DAY_OF_YEAR_NUMBER_SOURCE_FILE_CHARS_END_RANGE = 4
FRACTION_OF_DAY_SOURCE_FILE_STARTING_CHAR_POSITION = 4
FRACTION_OF_DAY_SOURCE_FILE_CHARS_END_RANGE = 8


class StateKey(BaseEnum):
    """
    An enum for the state data applicable to a CsppParser
    """
    POSITION = 'position'  # holds the file position
    HEADER_AND_FIRST_DATA_RECORD_FOUND = 'header_and_first_data_record_found'


class CsppMetadataDataParticle(DataParticle):
    """
    Class for parsing cspp metadata particle values
    """

    def _build_metadata_parsed_values(self):
        """
        This method builds and returns a list of encoded common metadata particle values from the raw_data which
        is expected to be regular expression match data
        @throws ValueError, TypeError, IndexError If there is a problem with particle parsing
        @returns result list of metadata parsed values
        """

        # Initialize the results to return
        results = []

        # Grab the source file path from the match raw_data
        source_file_path = self.raw_data.group(HeaderMatchesGroupNumber.SOURCE_FILE_PATH)

        # Split the source file path using an escaped backslash.  The path is expected to be a Windows based
        # file path.
        source_file_name_parts = source_file_path.split('\\')
        # Obtain the list of source file name parts
        num_source_name_file_parts = len(source_file_name_parts)
        # Grab the last part of the source file name
        last_part_of_source_file_name = source_file_name_parts[num_source_name_file_parts - 1]

        # Encode the last character controller ID which consists of one character within the source file name
        results.append(self._encode_value(
            CsppMetadataParserDataParticleKey.LAST_CHARACTER_CONTROLLER_ID,
            last_part_of_source_file_name[LAST_CHARACTER_CONTROLLER_ID_SOURCE_FILE_CHAR_POSITION],
            str))

        # Encode the day of year number which consists of three characters within the source file name
        results.append(self._encode_value(
            CsppMetadataParserDataParticleKey.DAY_OF_YEAR_NUMBER,
            last_part_of_source_file_name[
                DAY_OF_YEAR_NUMBER_SOURCE_FILE_STARTING_CHAR_POSITION:DAY_OF_YEAR_NUMBER_SOURCE_FILE_CHARS_END_RANGE],
            int))

        # Encode the fraction of day which consists of four characters within the source file name
        results.append(self._encode_value(
            CsppMetadataParserDataParticleKey.FRACTION_OF_DAY,
            last_part_of_source_file_name[
                FRACTION_OF_DAY_SOURCE_FILE_STARTING_CHAR_POSITION:FRACTION_OF_DAY_SOURCE_FILE_CHARS_END_RANGE],
            int))

        # Grab the processed date and time from the match raw_data
        processed_date = self.raw_data.group(HeaderMatchesGroupNumber.PROCESSED_DATE)
        processed_time = self.raw_data.group(HeaderMatchesGroupNumber.PROCESSED_TIME)

        # Encode the processing time which includes the processed date and time retrieved above
        results.append(self._encode_value(
            CsppMetadataParserDataParticleKey.PROCESSING_TIME,
            time.mktime(time.strptime(processed_date + " " + processed_time, "%m/%d/%Y %H:%M:%S")),
            str))

        # Iterate through a set of metadata particle encoding rules to encode the remaining parameters
        for rule in METADATA_PARTICLE_ENCODING_RULES:

            results.append(self._encode_value(
                rule[EncodingRuleIndex.PARTICLE_KEY_INDEX],
                self.raw_data.group(rule[EncodingRuleIndex.MATCHES_GROUP_NUMBER_INDEX]),
                rule[EncodingRuleIndex.TYPE_ENCODING_INDEX]))

        log.debug('CsppMetadataDataParticle: particle=%s', results)
        return results


class CsppParser(BufferLoadingParser):
    """
    Class for a common cspp data file parser
    """

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an CsppParser object.
        @param config The configuration for this CsppParser parser
        @param state The state the CsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        self._data_record_matcher = None
        self._header_and_first_data_record_matcher = None

        # Ensure that we have a DATA_REGEX_KWARGS_KEY in the kwargs
        if DATA_REGEX_KWARGS_KEY not in kwargs:
            raise DatasetParserException("Must provide a " + DATA_REGEX_KWARGS_KEY)
        else:
            # Obtain the data record regex from the kwargs
            data_record_regex = kwargs.pop(DATA_REGEX_KWARGS_KEY)
            # Compile each of the regular expressions to be used later
            self._header_and_first_data_record_matcher = re.compile(HEADER_REGEX + data_record_regex)
            self._data_record_matcher = re.compile(data_record_regex)

        # Obtain the particle classes dictionary from the config data
        particle_classes_dict = config.get(DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT)
        # Set the metadata and data particle classes to be used later
        self._metadata_particle_class = particle_classes_dict.get(METADATA_PARTICLE_CLASS_KEY)
        self._data_particle_class = particle_classes_dict.get(DATA_PARTICLE_CLASS_KEY)

        # Initialize the record buffer to an empty list
        self._record_buffer = []

        # Initialize the read state POSITION to 0
        self._read_state = {StateKey.POSITION: 0, StateKey.HEADER_AND_FIRST_DATA_RECORD_FOUND: False}

        # Call the superclass constructor
        super(CsppParser, self).__init__(config,
                                         stream_handle,
                                         state,
                                         self.sieve_function,
                                         state_callback,
                                         publish_callback,
                                         exception_callback,
                                         *args, **kwargs)

        # If provided a state, set it.  This needs to be done post superclass __init__
        if state:
            self.set_state(state)

    def set_state(self, state_obj):
        """
        Set the value of the state object for this parser
        @param state_obj The object to set the state to. 
        @throws DatasetParserException if there is a bad state structure
        """
        if not isinstance(state_obj, dict):
            raise DatasetParserException("Invalid state structure")
        self._state = state_obj
        self._read_state = state_obj

    def _update_positional_state(self, increment):
        """
        Increment the parser state
        @param increment The offset for the file position
        """
        self._read_state[StateKey.POSITION] += increment

    def sieve_function(self, data_buffer):
        """
        This method sorts through the raw data to identify new blocks of data that need processing.
        @param data_buffer the data from a cspp data file for which to return the chunk location information
        @return the list of tuples containing the start index and range for each chunk
        """

        indices_list = []    # initialize the return list to empty

        # Keep searching until the data buffer is exhausted.
        search_index = 0
        while search_index < len(data_buffer):

            # If we have not already found the header and first data record, let's see if we can find it in the data
            # buffer
            if not self._read_state[StateKey.HEADER_AND_FIRST_DATA_RECORD_FOUND]:

                # Perform a regular expression match search within the input data_buffer
                header_and_first_data_match = self._header_and_first_data_record_matcher.search(
                    data_buffer[search_index:])

                # See if we found a header and first data record match
                if header_and_first_data_match is not None:

                    # We found it, let's indicate as such in our state
                    self._read_state[StateKey.HEADER_AND_FIRST_DATA_RECORD_FOUND] = True

                    # Compute the start of the chunk
                    chunk_start = header_and_first_data_match.start() + search_index

                    # Compute the chunk range
                    chunk_range = chunk_start + len(header_and_first_data_match.group(0))

                    # Add the chunk start and end range to the indices_list to return
                    indices_list.append((chunk_start, chunk_range))

                    # Update the search index to the end chunk range
                    search_index = chunk_range

                else:
                    # Update the search index by offsetting it by one byte
                    search_index += 1

            # We already found the header and first data record, so let's see if we can find a data record match
            else:
                data_match = self._data_record_matcher.search(data_buffer[search_index:])

                if data_match is not None:

                    # Compute the start of the chunk
                    chunk_start = data_match.start() + search_index

                    # Compute the chunk range
                    chunk_range = chunk_start + len(data_match.group(0))

                    # Add the chunk start and end range to the indices_list to return
                    indices_list.append((chunk_start, chunk_range))

                    # Update the search index to the end chunk range
                    search_index = chunk_range

                else:
                    # Update the search index by offsetting it by one byte
                    search_index += 1

        log.debug("Returning indices_list: %s", indices_list)

        return indices_list

    def parse_chunks(self):
        """
        Parse out any pending data chunks in the chunker. If
        it is a valid data piece, build a particle, update the position and
        timestamp. Go until the chunker has no more valid data.
        @retval a list of tuples with sample particles encountered in this
            parsing, plus the state. An empty list of nothing was parsed.
        """

        # Initialize the result particles list we will return
        result_particles = []

        # Retrieve the next non data chunk
        (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)

        # Retrieve the next data chunk
        (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

        # Process the non data
        self.handle_non_data(non_data, non_end, start)

        # While the data chunk is not None, process the data chunk
        while chunk is not None:

            # See if the chunk matches the header and first data record
            header_and_first_data_match = self._header_and_first_data_record_matcher.match(chunk)

            # If we found a header and first data record, let's process it
            if header_and_first_data_match:

                # Extract the metadata particle
                metadata_particle = self._extract_sample(self._metadata_particle_class,
                                                         None,
                                                         header_and_first_data_match,
                                                         None)

                data_particle = self._extract_sample(self._data_particle_class,
                                                     None,
                                                     self._data_record_matcher.search(
                                                         header_and_first_data_match.group(0)),
                                                     None)

                # If we crated the metadata and data particle, let's append each particle to the result particles
                # to return and increment the state data positioning
                if metadata_particle and data_particle:                    
                    result_particles.append((metadata_particle, copy.copy(self._read_state)))
                    result_particles.append((data_particle, copy.copy(self._read_state)))
                    self._update_positional_state(len(chunk))

            else:
                # See if the chunk matches a data record
                data_match = self._data_record_matcher.match(chunk)

                # If we found a match, let's process it
                if data_match:
                    
                    # Extract the data record particle 
                    data_particle = self._extract_sample(self._data_particle_class,
                                                         None,
                                                         data_match,
                                                         None)
                    
                    # If we created a data particle, let's append the particle to the result particles
                    # to return and increment the state data positioning
                    if data_particle:
                        result_particles.append((data_particle, copy.copy(self._read_state)))
                        self._update_positional_state(len(chunk))

            # Retrieve the next non data chunk
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)

            # Retrieve the next data chunk
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

            # Process the non data
            self.handle_non_data(non_data, non_end, start)

        log.debug(result_particles)

        return result_particles

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # if non-data is expected, handle it here, otherwise it is an error
        if non_data is not None and non_end <= start:
            log.debug("non_data: %s", non_data)
            # if this non-data is an error, send an UnexpectedDataException and increment the state
            self._update_positional_state(len(non_data))
            # if non-data is a fatal error, directly call the exception, if it is not use the _exception_callback
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data %s" %
                                                             (len(non_data), non_data)))
