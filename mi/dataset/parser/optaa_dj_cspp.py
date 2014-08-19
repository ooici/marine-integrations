#!/usr/bin/env python

"""
@package mi.dataset.parser.optaa_dj_cspp
@file marine-integrations/mi/dataset/parser/optaa_dj_cspp.py
@author Joe Padula
@brief Parser for the optaa_dj_cspp dataset driver. This parser extends from certain classes
    in cspp_base.py but not all. For instance OptaaDjCsppParser is not extended from cspp_base,
    instead it is extended from BufferLoadingParser.
Release notes:

Initial Release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

import copy
import numpy
import re
from functools import partial
import string

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import \
    DatasetParserException, \
    UnexpectedDataException, \
    RecoverableSampleException, \
    ConfigurationException

from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import StringChunker

from mi.dataset.parser.cspp_base import \
    DefaultHeaderKey, \
    DEFAULT_HEADER_KEY_LIST, \
    DATA_PARTICLE_CLASS_KEY, \
    METADATA_PARTICLE_CLASS_KEY, \
    SIEVE_MATCHER, \
    StateKey, \
    HeaderPartMatchesGroupNumber, \
    TIMESTAMP_LINE_MATCHER, \
    HEADER_PART_MATCHER, \
    HEX_ASCII_LINE_MATCHER, \
    FLOAT_REGEX, \
    INT_REGEX, \
    Y_OR_N_REGEX, \
    END_OF_LINE_REGEX, \
    CsppMetadataDataParticle, \
    MetadataRawDataKey, \
    encode_y_or_n

TAB_REGEX = r'\t'
# This is the beginning part of the REGEX, the rest of it varies
BEGIN_REGEX = '(' + FLOAT_REGEX + ')' + TAB_REGEX     # Profiler Timestamp
BEGIN_REGEX += '(' + FLOAT_REGEX + ')' + TAB_REGEX    # Depth
BEGIN_REGEX += '(' + Y_OR_N_REGEX + ')' + TAB_REGEX   # Suspect Timestamp
BEGIN_REGEX += '(' + INT_REGEX + ')' + TAB_REGEX      # serial number
BEGIN_REGEX += '(' + FLOAT_REGEX + ')' + TAB_REGEX    # powered on seconds
BEGIN_REGEX += '(' + INT_REGEX + ')' + TAB_REGEX      # num wavelengths
BEGIN_MATCHER = re.compile(BEGIN_REGEX)


class DataMatchesGroupNumber(BaseEnum):
    """
    An enum for group match indices for a data record chunk.
    Used to access the match groups in the particle raw data
    """
    PROFILER_TIMESTAMP = 1
    DEPTH = 2
    SUSPECT_TIMESTAMP = 3
    SERIAL_NUMBER = 4
    ON_SECONDS = 5
    NUM_WAVELENGTHS = 6
    C_REF_DARK = 7
    C_REF_COUNTS = 8
    C_SIG_DARK = 9
    C_SIG_COUNTS = 10
    A_REF_DARK = 11
    A_REF_COUNTS = 12
    A_SIG_DARK = 13
    A_SIG_COUNTS = 14
    EXTERNAL_TEMP_COUNTS = 15
    INTERNAL_TEMP_COUNTS = 16
    PRESSURE_COUNTS = 17


class DataParticleType(BaseEnum):
    """
    The data particle types that this parser can generate
    """
    METADATA_RECOVERED = 'optaa_dj_cspp_metadata_recovered'
    INSTRUMENT_RECOVERED = 'optaa_dj_cspp_instrument_recovered'
    METADATA_TELEMETERED = 'optaa_dj_cspp_metadata'
    INSTRUMENT_TELEMETERED = 'optaa_dj_cspp_instrument'


class OptaaDjCsppParserDataParticleKey(BaseEnum):

    """
    The data particle keys associated with the metadata particle parameters
    """
    # non-common metadata particle key
    SERIAL_NUMBER = 'serial_number'

    # The data particle keys associated with the data instrument particle parameters
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE_DEPTH = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    ON_SECONDS = 'on_seconds'
    NUM_WAVELENGTHS = 'num_wavelengths'
    C_REFERENCE_DARK_COUNTS = 'c_reference_dark_counts'
    C_REFERENCE_COUNTS = 'c_reference_counts'
    C_SIGNAL_DARK_COUNTS = 'c_signal_dark_counts'
    C_SIGNAL_COUNTS = 'c_signal_counts'
    A_REFERENCE_DARK_COUNTS = 'a_reference_dark_counts'
    A_REFERENCE_COUNTS = 'a_reference_counts'
    A_SIGNAL_DARK_COUNTS = 'a_signal_dark_counts'
    A_SIGNAL_COUNTS = 'a_signal_counts'
    EXTERNAL_TEMP_RAW = 'external_temp_raw'
    INTERNAL_TEMP_RAW = 'internal_temp_raw'
    PRESSURE_COUNTS = 'pressure_counts'

# Two groups instrument particle encoding rules used to simplify encoding using a loop.

# This the beginning part of the encoding, before the lists.
INSTRUMENT_PARTICLE_ENCODING_RULES_BEGIN = [
    # Since 1/1/70 with millisecond resolution
    (OptaaDjCsppParserDataParticleKey.PROFILER_TIMESTAMP, DataMatchesGroupNumber.PROFILER_TIMESTAMP, numpy.float),
    # "Depth" from Record Structure section
    (OptaaDjCsppParserDataParticleKey.PRESSURE_DEPTH, DataMatchesGroupNumber.DEPTH, float),
    # Flag indicating a potential inaccuracy in the timestamp
    (OptaaDjCsppParserDataParticleKey.SUSPECT_TIMESTAMP, DataMatchesGroupNumber.SUSPECT_TIMESTAMP, encode_y_or_n),
    # Powered On Seconds
    (OptaaDjCsppParserDataParticleKey.ON_SECONDS, DataMatchesGroupNumber.ON_SECONDS, float),
    # Number of output wavelengths.
    (OptaaDjCsppParserDataParticleKey.NUM_WAVELENGTHS, DataMatchesGroupNumber.NUM_WAVELENGTHS, int)
]

# This the end part of the encoding, after the lists.
INSTRUMENT_PARTICLE_ENCODING_RULES_END = [
    # Temperature external to the instrument measured in counts.
    (OptaaDjCsppParserDataParticleKey.EXTERNAL_TEMP_RAW, DataMatchesGroupNumber.EXTERNAL_TEMP_COUNTS, int),
    # Temperature internal to the instrument measured in counts.
    (OptaaDjCsppParserDataParticleKey.INTERNAL_TEMP_RAW, DataMatchesGroupNumber.INTERNAL_TEMP_COUNTS, int),
    # Raw A/D counts from the pressure sensor
    (OptaaDjCsppParserDataParticleKey.PRESSURE_COUNTS, DataMatchesGroupNumber.PRESSURE_COUNTS, int)
]


class OptaaDjCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Base Class for building a metadata particle
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @returns results a list of encoded metadata particle (key/value pairs)
        @throws RecoverableSampleException If there is a problem with sample creation
        """
        metadata_particle = []

        try:

            # Call base class to append the base metadata parsed values to the particle to return
            metadata_particle += self._build_metadata_parsed_values()

            data_match = self.raw_data[MetadataRawDataKey.DATA_MATCH]

            # Process the non common metadata particle parameter

            # Instrument serial number (from first record)
            metadata_particle.append(self._encode_value(OptaaDjCsppParserDataParticleKey.SERIAL_NUMBER,
                                                        data_match.group(DataMatchesGroupNumber.SERIAL_NUMBER),
                                                        int))

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(data_match.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building metadata particle")
            raise RecoverableSampleException(
                "Error (%s) while decoding parameters in data: [%s]"
                % (ex, self.raw_data))

        # log.debug('metadata_particle: %s', metadata_particle)
        return metadata_particle


class OptaaDjCsppMetadataRecoveredDataParticle(OptaaDjCsppMetadataDataParticle):
    """
    Class for building a recovered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_RECOVERED


class OptaaDjCsppMetadataTelemeteredDataParticle(OptaaDjCsppMetadataDataParticle):
    """
    Class for building a telemetered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_TELEMETERED


class OptaaDjCsppInstrumentDataParticle(DataParticle):
    """
    Base Class for building a instrument data particle
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws RecoverableSampleException If there is a problem with sample creation
        """

        results = []

        try:
            # Process each of the non-list type instrument particle parameters that occur first
            for name, group, function in INSTRUMENT_PARTICLE_ENCODING_RULES_BEGIN:
                results.append(self._encode_value(name, self.raw_data.group(group), function))

            # The following is a mix if int, followed by a list.

            # C-channel reference dark counts, used for diagnostic purposes.
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_REFERENCE_DARK_COUNTS,
                                              self.raw_data.group(DataMatchesGroupNumber.C_REF_DARK),
                                              int))

            # Array of raw c-channel reference counts
            counts = self._build_list_for_encoding(DataMatchesGroupNumber.C_REF_COUNTS)
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_REFERENCE_COUNTS,
                                              counts,
                                              list))

            # C-signal reference dark counts, used for diagnostic purposes.
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_SIGNAL_DARK_COUNTS,
                                              self.raw_data.group(DataMatchesGroupNumber.C_SIG_DARK),
                                              int))

            # Array of raw c-channel signal counts
            counts = self._build_list_for_encoding(DataMatchesGroupNumber.C_SIG_COUNTS)
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_SIGNAL_COUNTS,
                                              counts,
                                              list))

            # A-channel reference dark counts, used for diagnostic purposes.
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.A_REFERENCE_DARK_COUNTS,
                                              self.raw_data.group(DataMatchesGroupNumber.A_REF_DARK),
                                              int))

            # Array of raw a-channel reference counts
            counts = self._build_list_for_encoding(DataMatchesGroupNumber.A_REF_COUNTS)
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.A_REFERENCE_COUNTS,
                                              counts,
                                              list))

            # A-signal reference dark counts, used for diagnostic purposes.
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.A_SIGNAL_DARK_COUNTS,
                                              self.raw_data.group(DataMatchesGroupNumber.A_SIG_DARK),
                                              int))

            # Array of raw a-channel signal counts
            counts = self._build_list_for_encoding(DataMatchesGroupNumber.A_SIG_COUNTS)
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.A_SIGNAL_COUNTS,
                                              counts,
                                              list))

            # Process each of the non-list instrument particle parameters that occur last
            for name, group, function in INSTRUMENT_PARTICLE_ENCODING_RULES_END:
                results.append(self._encode_value(name, self.raw_data.group(group), function))

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(self.raw_data.group(
                                                  DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building instrument parsed values")
            raise RecoverableSampleException(
                "Error (%s) while decoding parameters in data: [%s]"
                % (ex, self.raw_data))

        # log.debug("*** results: %s", results)

        return results

    def _build_list_for_encoding(self, group_num):
        """
        Helper method for building the list that is needed for encoding
        @param group_num the group number of the match
        @return the list of counts
        """

        # Load the tab separated string
        tab_str = self.raw_data.group(group_num)
        # Strip off the ending tab
        tab_str_stripped = tab_str.strip('\t')
        counts_list = tab_str_stripped.split('\t')

        # Load the counts array by getting value from counts_list as x is incremented
        # in the for loop
        counts = [int(counts_list[x], 10) for x in range(len(counts_list))]
        return counts


class OptaaDjCsppInstrumentRecoveredDataParticle(OptaaDjCsppInstrumentDataParticle):
    """
    Class for building a recovered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_RECOVERED


class OptaaDjCsppInstrumentTelemeteredDataParticle(OptaaDjCsppInstrumentDataParticle):
    """
    Class for building a telemetered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_TELEMETERED


class OptaaDjCsppParser(BufferLoadingParser):
    """
    Class for a optaa_dj_cspp data file parser
    """

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback):
        """
        This method is a constructor that will instantiate an OptaaDjCsppParser object.
        @param config The configuration for this OptaaDjCsppParser parser
        @param state The state the OptaaDjCsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the optaa_dj_cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        @throws ConfigurationException if the header state dictionary cannot be built
        """

        # Build up the header state dictionary using the default her key list ot one that was provided
        self._header_state = {}

        header_key_list = DEFAULT_HEADER_KEY_LIST

        for header_key in header_key_list:
            self._header_state[header_key] = None

        # Build up the header state dictionary using the default header key list
        if DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT in config:
            particle_classes_dict = config.get(DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT)
            # Set the metadata and data particle classes to be used later
            if METADATA_PARTICLE_CLASS_KEY in particle_classes_dict and \
                    DATA_PARTICLE_CLASS_KEY in particle_classes_dict:
                self._data_particle_class = particle_classes_dict.get(DATA_PARTICLE_CLASS_KEY)
                self._metadata_particle_class = particle_classes_dict.get(METADATA_PARTICLE_CLASS_KEY)
            else:
                log.warning(
                    'Configuration missing metadata or data particle class key in particle classes dict')
                raise ConfigurationException(
                    'Configuration missing metadata or data particle class key in particle classes dict')
        else:
            log.warning('Configuration missing particle classes dict')
            raise ConfigurationException('Configuration missing particle classes dict')

        # Initialize the record buffer to an empty list
        self._record_buffer = []

        # Initialize the read state
        self._read_state = {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: False}

        # Call the superclass constructor
        super(OptaaDjCsppParser, self).__init__(config,
                                                stream_handle,
                                                state,
                                                partial(StringChunker.regex_sieve_function,
                                                        regex_list=[SIEVE_MATCHER]),
                                                state_callback,
                                                publish_callback,
                                                exception_callback)

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
        if not (StateKey.POSITION in state_obj and StateKey.METADATA_EXTRACTED in state_obj):
            raise DatasetParserException("Provided state is missing position or metadata extracted")

        self._state = state_obj
        self._read_state = state_obj

        # Clear the record buffer
        self._record_buffer = []

        # Need to seek the correct position in the file stream using the read state position.
        self._stream_handle.seek(self._read_state[StateKey.POSITION])

        # make sure we have cleaned the chunker out of old data
        self._chunker.clean_all_chunks()

    def _increment_read_state(self, increment):
        """
        Increment the parser state
        @param increment The offset for the file position
        """
        self._read_state[StateKey.POSITION] += increment

    def _process_data_match(self, particle_class, data_match, result_particles):
        """
        This method processes a data match. It will extract a metadata particle and insert it into
        result_particles when we have not already extracted the metadata and all header values exist.
        This method will also extract a data particle and append it to the result_particles.
        @param particle_class is the class of particle to be created
        @param data_match A regular expression match object for a cspp data record
        @param result_particles A list which should be updated to include any particles extracted
        """

        # Extract the data record particle
        data_particle = self._extract_sample(particle_class,
                                             None,
                                             data_match,
                                             None)

        # If we created a data particle, let's append the particle to the result particles
        # to return and increment the state data positioning
        if data_particle:

            if not self._read_state[StateKey.METADATA_EXTRACTED]:
                # Once the first data particle is read, all available header lines will
                # have been read and inserted into the header state dictionary.
                # Only the source file is required to create a metadata particle.

                if self._header_state[DefaultHeaderKey.SOURCE_FILE] is not None:
                    metadata_particle = self._extract_sample(self._metadata_particle_class,
                                                             None,
                                                             (copy.copy(self._header_state),
                                                              data_match),
                                                             None)
                    if metadata_particle:
                        # We're going to insert the metadata particle so that it is
                        # the first in the list and set the position to 0, as it cannot
                        # have the same position as the non-metadata particle
                        result_particles.insert(0, (metadata_particle, {StateKey.POSITION: 0,
                                                                        StateKey.METADATA_EXTRACTED: True}))
                    else:
                        # metadata particle was not created successfully
                        log.warn('Unable to create metadata particle')
                        self._exception_callback(RecoverableSampleException(
                            'Unable to create metadata particle'))
                else:
                    # no source file path, don't create metadata particle
                    log.warn('No source file, not creating metadata particle')
                    self._exception_callback(RecoverableSampleException(
                        'No source file, not creating metadata particle'))

                # need to set metadata extracted to true so we don't keep creating
                # the metadata, even if it failed
                self._read_state[StateKey.METADATA_EXTRACTED] = True

            result_particles.append((data_particle, copy.copy(self._read_state)))

        # log.debug('result_particles: %s', result_particles)

    def _process_header_part_match(self, header_part_match):
        """
        This method processes a header part match. It will process one row within a cspp header
        that matched a provided regex. The match groups should be processed and the _header_state
        will be updated with the obtained header values.
        @param header_part_match A regular expression match object for a header row
        """
        header_part_key = header_part_match.group(
            HeaderPartMatchesGroupNumber.HEADER_PART_MATCH_GROUP_KEY)

        if header_part_key in self._header_state.keys():
            header_part_value = header_part_match.group(
                HeaderPartMatchesGroupNumber.HEADER_PART_MATCH_GROUP_VALUE)
            self._header_state[header_part_key] = string.rstrip(header_part_value)

    def _process_chunk_not_containing_data_record_or_header_part(self, chunk):
        """
        This method processes a chunk that does not contain a data record or header. This case is
        not applicable to "non_data". For cspp file streams, we expect some lines in the file that
        we do not care about, and we will not consider them "non_data".
        @param chunk A regular expression match object for a header row
        """

        if HEX_ASCII_LINE_MATCHER.match(chunk):
            # we found a line starting with the timestamp, depth, and
            # suspect timestamp, followed by all hex ascii chars
            log.warn('got hex ascii corrupted data %s at position %s', chunk,
                     self._read_state[StateKey.POSITION])
            self._exception_callback(RecoverableSampleException(
                "Found hex ascii corrupted data: %s" % chunk))

        # ignore the expected timestamp line and any lines matching the ignore regex,
        # otherwise data is unexpected
        elif not TIMESTAMP_LINE_MATCHER.match(chunk):
            # Unexpected data was found
            log.warn('got unrecognized row %s at position %s', chunk, self._read_state[StateKey.POSITION])
            self._exception_callback(RecoverableSampleException("Found an invalid chunk: %s" % chunk))

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

            # Increment the read state position now
            self._increment_read_state(len(chunk))

            # Look for match in beginning part of the regex
            match = BEGIN_MATCHER.match(chunk)

            if match is not None:

                count = match.group(DataMatchesGroupNumber.NUM_WAVELENGTHS)

                data_regex = self._build_data_regex(BEGIN_REGEX, count)

                fields = re.match(data_regex, chunk)

                if fields is not None:
                    self._process_data_match(self._data_particle_class, fields, result_particles)
                else:  # did not match the regex
                    log.warn("chunk did not match regex %s", chunk)
                    self._exception_callback(RecoverableSampleException("Found an invalid chunk: %s" % chunk))

            else:
                # Check for head part match
                header_part_match = HEADER_PART_MATCHER.match(chunk)

                if header_part_match is not None:
                    self._process_header_part_match(header_part_match)
                else:
                    self._process_chunk_not_containing_data_record_or_header_part(chunk)

            # Retrieve the next non data chunk
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)

            # Retrieve the next data chunk
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

            # Process the non data
            self.handle_non_data(non_data, non_end, start)

        return result_particles

    @staticmethod
    def _build_data_regex(regex, count):
        """
        Helper method for building up regex
        @param regex the beginning part of the regex that has already been determined
        @param count the number of items in the array
        """

        data_regex = regex
        array = r'((?:\d+\t){%s})' % count

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # C Ref Dark
        data_regex += array                                 # C Ref Counts

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # C Sig Dark
        data_regex += array                                 # C Sig Counts

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # A Ref Dark
        data_regex += array                                 # A Ref Counts

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # A Sig Dark
        data_regex += array                                 # A Sig Counts

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # External Temp Counts
        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # Internal Temp Counts
        data_regex += '(' + INT_REGEX + ')'                 # Pressure Counts

        data_regex += r'\t*' + END_OF_LINE_REGEX

        return data_regex

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # non-data is not expected, if found it is an error
        if non_data is not None and non_end <= start:
            # send an UnexpectedDataException and increment the state
            self._increment_read_state(len(non_data))
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data %s" %
                                                             (len(non_data), non_data)))