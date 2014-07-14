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

from functools import partial
import copy
import re
import time
import string

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.exceptions import DatasetParserException, UnexpectedDataException, RecoverableSampleException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.dataset.dataset_driver import DataSetDriverConfigKeys

# The following defines a regular expression for one or more instances of a carriage return, line feed or both
CARRIAGE_RETURN_LINE_FEED_OR_BOTH = r'(?:\r\n|\r|\n)'
SIEVE_MATCHER = re.compile(r'.*' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH)

HEADER_PART_REGEX = r'(.*):\s+(.*)' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH
HEADER_PART_MATCHER = re.compile(HEADER_PART_REGEX)

TIMESTAMP_LINE_REGEX = r'Timestamp.*' + CARRIAGE_RETURN_LINE_FEED_OR_BOTH
TIMESTAMP_LINE_MATCHER = re.compile(TIMESTAMP_LINE_REGEX)

# A regex to capture a float value
FLOAT_REGEX = r'(?:[+-]?[0-9]|[1-9][0-9])+\.[0-9]+'
# A regex to capture an int value
INT_REGEX = r'[+-]?[0-9]+'
# A regex to match against one or more multiple consecutive whitespace characters
MULTIPLE_TAB_REGEX = r'\t+'

# The following two keys are keys to be used with the PARTICLE_CLASSES_DICT
# The key for the metadata particle class
METADATA_PARTICLE_CLASS_KEY = 'metadata_particle_class'
# The key for the data particle class
DATA_PARTICLE_CLASS_KEY = 'data_particle_class'


class HeaderPartMatchesGroupNumber(BaseEnum):
    """
    An enum used to access match group values
    """
    HEADER_PART_MATCH_GROUP_KEY = 1
    HEADER_PART_MATCH_GROUP_VALUE = 2


class DefaultHeaderKey(BaseEnum):
    """
    An enum for the default set of header keys
    """
    SOURCE_FILE = 'Source File'
    PROCESSED = 'Processed'
    USING_VERSION = 'Using Version'
    DEVICE = 'Device'
    START_DATE = 'Start Date'


# The default set of header keys as a list
DEFAULT_HEADER_KEY_LIST = DefaultHeaderKey.list()


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


# The following are used to index into encoding rules tuple structures.  The HEADER_DICTIONARY_KEY_INDEX
# is the same value as the DATA_MATCHES_GROUP_NUMBER_INDEX because one is used for the metadata and the other
# is used for the data record.
PARTICLE_KEY_INDEX = 0
HEADER_DICTIONARY_KEY_INDEX = 1
DATA_MATCHES_GROUP_NUMBER_INDEX = 1
TYPE_ENCODING_INDEX = 2


# A group of metadata particle encoding rules used to simplify encoding using a loop
METADATA_PARTICLE_ENCODING_RULES = [
    (CsppMetadataParserDataParticleKey.SOURCE_FILE, DefaultHeaderKey.SOURCE_FILE, str),
    (CsppMetadataParserDataParticleKey.PREPROCESSING_SOFTWARE_VERSION, DefaultHeaderKey.USING_VERSION, str),
    (CsppMetadataParserDataParticleKey.START_DATE, DefaultHeaderKey.START_DATE, str),
]

# The following items are used to index into source file name string
LAST_CHARACTER_CONTROLLER_ID_SOURCE_FILE_CHAR_POSITION = 0
DAY_OF_YEAR_NUMBER_SOURCE_FILE_STARTING_CHAR_POSITION = 1
DAY_OF_YEAR_NUMBER_SOURCE_FILE_CHARS_END_RANGE = 4
FRACTION_OF_DAY_SOURCE_FILE_STARTING_CHAR_POSITION = 4
FRACTION_OF_DAY_SOURCE_FILE_CHARS_END_RANGE = 8


class MetadataRawDataKey(BaseEnum):
    """
    An enum for the state data applicable to a CsppParser
    """
    HEADER_DICTIONARY = 0
    DATA_MATCH = 1


class StateKey(BaseEnum):
    """
    An enum for the state data applicable to a CsppParser
    """
    POSITION = 'position'
    HEADER_STATE = 'header_state'
    METADATA_PUBLISHED = 'metadata_published'


class CsppMetadataDataParticle(DataParticle):
    """
    Class for parsing cspp metadata particle values
    """

    def _build_metadata_parsed_values(self):
        """
        This method builds and returns a list of encoded common metadata particle values from the raw_data which
        is expected to be regular expression match data.  This method would need to be overridden if the header
        items do not include what is in the DefaultHeaderKey enum
        @throws ValueError, TypeError, IndexError If there is a problem with particle parsing
        @returns result list of metadata parsed values
        """

        # Initialize the results to return
        results = []

        # Grab the header data dictionary, which is the first item in the raw_data tuple
        header_dict = self.raw_data[MetadataRawDataKey.HEADER_DICTIONARY]

        # Grab the source file path from the match raw_data's
        source_file_path = header_dict[DefaultHeaderKey.SOURCE_FILE]

        # Split the source file path.  The regex below supports splitting on a Windows or unix/linux file path.
        source_file_name_parts = re.split(r'\\|/', source_file_path)
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
        (processed_date, processed_time) = header_dict[DefaultHeaderKey.PROCESSED].split()

        # Encode the processing time which includes the processed date and time retrieved above
        results.append(self._encode_value(
            CsppMetadataParserDataParticleKey.PROCESSING_TIME,
            processed_date + " " + processed_time,
            str))

        # # Iterate through a set of metadata particle encoding rules to encode the remaining parameters
        for rule in METADATA_PARTICLE_ENCODING_RULES:

            results.append(self._encode_value(
                rule[PARTICLE_KEY_INDEX],
                header_dict[rule[HEADER_DICTIONARY_KEY_INDEX]],
                rule[TYPE_ENCODING_INDEX]))

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
                 data_record_regex,
                 header_key_list=None,
                 ignore_matcher=None,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an CsppParser object.
        @param config The configuration for this CsppParser parser
        @param state The state the CsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        @param data_record_regex The data regex that should be used to obtain data records
        @param header_key_list The list of header keys expected within a header
        @param ignore_regex A regex to use to ignore expected junk lines
        """

        self._data_record_matcher = None
        self._header_and_first_data_record_matcher = None
        self._ignore_matcher = ignore_matcher

        # Ensure that we have a data regex
        if data_record_regex is None:
            raise DatasetParserException("Must provide a data_record_regex")
        else:
            self._data_record_matcher = re.compile(data_record_regex)

        header_state = {}

        if header_key_list is None:
            header_key_list = DEFAULT_HEADER_KEY_LIST

        for header_key in header_key_list:
            header_state[header_key] = None
        log.debug("header state members: ", header_state)

        # Obtain the particle classes dictionary from the config data
        particle_classes_dict = config.get(DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT)
        # Set the metadata and data particle classes to be used later
        self._metadata_particle_class = particle_classes_dict.get(METADATA_PARTICLE_CLASS_KEY)
        self._data_particle_class = particle_classes_dict.get(DATA_PARTICLE_CLASS_KEY)

        # Initialize the record buffer to an empty list
        self._record_buffer = []

        # Initialize the read state POSITION to 0, and HEADER_STATE as an empty dictionary
        self._read_state = {StateKey.POSITION: 0,
                            StateKey.HEADER_STATE: header_state,
                            StateKey.METADATA_PUBLISHED: False}

        # Call the superclass constructor
        super(CsppParser, self).__init__(config,
                                         stream_handle,
                                         state,
                                         partial(StringChunker.regex_sieve_function,
                                                 regex_list=[SIEVE_MATCHER]),
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

            # See if the chunk matches a data record
            data_match = self._data_record_matcher.match(chunk)

            # If we found a data match, let's process it
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

                    if self._read_state[StateKey.METADATA_PUBLISHED] is False and \
                            None not in self._read_state[StateKey.HEADER_STATE].values():
                        metadata_particle = self._extract_sample(self._metadata_particle_class,
                                                                 None,
                                                                 (copy.copy(self._read_state[StateKey.HEADER_STATE]),
                                                                  data_match),
                                                                 None)
                        if metadata_particle:
                            # We're going to insert the metadata particle so that it is the first in the list
                            result_particles.insert(0, (metadata_particle, copy.copy(self._read_state)))
                            self._read_state[StateKey.METADATA_PUBLISHED] = True

                    self._update_positional_state(len(chunk))

            else:
                # Check for head part match
                header_part_match = HEADER_PART_MATCHER.match(chunk)

                if header_part_match is not None:

                    header_part_key = header_part_match.group(
                        HeaderPartMatchesGroupNumber.HEADER_PART_MATCH_GROUP_KEY)
                    header_part_value = header_part_match.group(
                        HeaderPartMatchesGroupNumber.HEADER_PART_MATCH_GROUP_VALUE)
                    if header_part_key in self._read_state[StateKey.HEADER_STATE].keys():
                        self._read_state[StateKey.HEADER_STATE][header_part_key] = string.rstrip(header_part_value)

                else:
                    # Check for the expected timestamp line we will ignore
                    timestamp_line_match = TIMESTAMP_LINE_MATCHER.match(chunk)

                    if timestamp_line_match is not None:
                        # Ignore
                        pass

                    else:

                        if self._ignore_matcher is not None and self._ignore_matcher.match(chunk):
                            # Ignore
                            pass
                        else:
                            # OK.  We got unexpected data
                            self._exception_callback(RecoverableSampleException("Found an invalid chunk: %s" % chunk))

            # Retrieve the next non data chunk
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)

            # Retrieve the next data chunk
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

            # Process the non data
            self.handle_non_data(non_data, non_end, start)

        log.debug("parser chunks returning: %s", result_particles)

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
