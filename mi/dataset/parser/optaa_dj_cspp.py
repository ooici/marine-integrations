#!/usr/bin/env python

"""
@package mi.dataset.parser.optaa_dj_cspp
@file marine-integrations/mi/dataset/parser/optaa_dj_cspp.py
@author Joe Padula
@brief Parser for the optaa_dj_cspp dataset driver
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
    RecoverableSampleException

from mi.dataset.dataset_driver import DataSetDriverConfigKeys
from mi.dataset.dataset_parser import BufferLoadingParser
from mi.core.instrument.chunker import StringChunker

from mi.dataset.parser.cspp_base import \
    DEFAULT_HEADER_KEY_LIST, \
    DATA_PARTICLE_CLASS_KEY, \
    METADATA_PARTICLE_CLASS_KEY, \
    SIEVE_MATCHER, \
    StateKey, \
    HeaderPartMatchesGroupNumber, \
    TIMESTAMP_LINE_MATCHER, \
    HEADER_PART_MATCHER, \
    FLOAT_REGEX, \
    INT_REGEX, \
    Y_OR_N_REGEX, \
    MULTIPLE_TAB_REGEX, \
    END_OF_LINE_REGEX, \
    CsppMetadataDataParticle, \
    MetadataRawDataKey, \
    encode_y_or_n

TAB_REGEX = r'\t'
REGEX = '(' + FLOAT_REGEX + ')' + TAB_REGEX     # Profiler Timestamp
REGEX += '(' + FLOAT_REGEX + ')' + TAB_REGEX    # Depth
REGEX += '(' + Y_OR_N_REGEX + ')' + TAB_REGEX   # Suspect Timestamp
REGEX += '(' + INT_REGEX + ')' + TAB_REGEX      # serial number
REGEX += '(' + FLOAT_REGEX + ')' + TAB_REGEX    # powered on seconds
REGEX += '(' + INT_REGEX + ')' + TAB_REGEX      # num wavelengths
MATCHER = re.compile(REGEX)


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
    The data particle keys associated with the data instrument particle parameters
    """
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


class OptaaDjCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Base Class for building a metadata particle
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws RecoverableSampleException If there is a problem with sample creation
        """
        log.debug("build metadata parsed values")
        results = []

        try:

            # Append the base metadata parsed values to the results to return
            results += self._build_metadata_parsed_values()

            data_match = self.raw_data[MetadataRawDataKey.DATA_MATCH]

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(data_match.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building metadata parsed values")
            raise RecoverableSampleException(
                "Error (%s) while decoding parameters in data: [%s]"
                % (ex, self.raw_data))

        return results


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
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.PROFILER_TIMESTAMP,
                                              self.raw_data.group(DataMatchesGroupNumber.PROFILER_TIMESTAMP),
                                              numpy.float))

            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.PRESSURE_DEPTH,
                                              self.raw_data.group(DataMatchesGroupNumber.DEPTH),
                                              float))

            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.SUSPECT_TIMESTAMP,
                                              self.raw_data.group(DataMatchesGroupNumber.SUSPECT_TIMESTAMP),
                                              encode_y_or_n))

            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.ON_SECONDS,
                                              self.raw_data.group(DataMatchesGroupNumber.ON_SECONDS),
                                              float))

            num_wavelengths = self.raw_data.group(DataMatchesGroupNumber.NUM_WAVELENGTHS)
            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.NUM_WAVELENGTHS,
                                              num_wavelengths,
                                              int))

            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_REFERENCE_DARK_COUNTS,
                                              self.raw_data.group(DataMatchesGroupNumber.C_REF_DARK),
                                              int))

            # Encode as array
            idx = 0
            # Load the tab separated string
            c_ref_counts_tab_str = self.raw_data.group(DataMatchesGroupNumber.C_REF_COUNTS)
            log.debug("c_ref_counts_tab_str: %s", c_ref_counts_tab_str)
            c_ref_counts_tab_str_stripped = c_ref_counts_tab_str.strip('\t')
            c_ref_counts_list = c_ref_counts_tab_str_stripped.split('\t')
            log.debug("c_ref_counts_list: %s", c_ref_counts_list)
            log.debug("size of c_ref_counts_list: %s", len(c_ref_counts_list))
            c_ref_counts = [0 for x in range(len(c_ref_counts_list))]
            log.debug("c_ref_counts: %s", c_ref_counts)
            for record_set in range(0, len(c_ref_counts_list)):
                log.debug("int(c_ref_counts_list[idx]: %s",  int(c_ref_counts_list[idx]))

                # We cast to int here as _encode_value does not cast elements in the list
                c_ref_counts[record_set] = int(c_ref_counts_list[idx], 10)
                log.debug("int(c_ref_counts_array[idx], 10) %s", int(c_ref_counts_list[idx], 10))
                idx += 1

            results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_REFERENCE_COUNTS,
                                              c_ref_counts,
                                              list))

            # results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_REFERENCE_DARK_COUNTS,
            #                                   self.raw_data.group(DataMatchesGroupNumber.C_REF_DARK),
            #                                   int))
            #
            # results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_SIGNAL_DARK_COUNTS,
            #                                   self.raw_data.group(DataMatchesGroupNumber.C_SIG_DARK),
            #                                   int))
            #
            # results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.C_SIGNAL_COUNTS,
            #                                   self.raw_data.group(DataMatchesGroupNumber.C_SIG_COUNTS),
            #                                   int))
            #
            # results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.EXTERNAL_TEMP_RAW,
            #                                   self.raw_data.group(DataMatchesGroupNumber.EXTERNAL_TEMP_COUNTS),
            #                                   int))
            #
            # results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.INTERNAL_TEMP_RAW,
            #                                   self.raw_data.group(DataMatchesGroupNumber.INTERNAL_TEMP_COUNTS),
            #                                   int))
            #
            # results.append(self._encode_value(OptaaDjCsppParserDataParticleKey.PRESSURE_COUNTS,
            #                                   self.raw_data.group(DataMatchesGroupNumber.PRESSURE_COUNTS),
            #                                   int))

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(self.raw_data.group(
                                                  DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building instrument parsed values")
            raise RecoverableSampleException(
                "Error (%s) while decoding parameters in data: [%s]"
                % (ex, self.raw_data))

        log.debug("results: %s", results)

        return results


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
        """
        log.debug("OptaaDjCsppParser init")
        # Build up the header state dictionary using the default header key list
        self._header_state = {}

        header_key_list = DEFAULT_HEADER_KEY_LIST

        for header_key in header_key_list:
            self._header_state[header_key] = None

        # Obtain the particle classes dictionary from the config data
        particle_classes_dict = config.get(DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT)

        # Set the metadata and data particle classes to be used later
        self._metadata_particle_class = particle_classes_dict.get(METADATA_PARTICLE_CLASS_KEY)
        self._data_particle_class = particle_classes_dict.get(DATA_PARTICLE_CLASS_KEY)

        # Initialize the record buffer to an empty list
        self._record_buffer = []

        # Call the superclass constructor
        super(OptaaDjCsppParser, self).__init__(config,
                                                stream_handle,
                                                state,
                                                partial(StringChunker.regex_sieve_function,
                                                        regex_list=[SIEVE_MATCHER]),
                                                state_callback,
                                                publish_callback,
                                                exception_callback)

        # If provided a state, set it. Otherwise initialize it
        # This needs to be done post superclass __init__
        if state:
            self.set_state(state)
        else:
            # Initialize the read state
            self._read_state = {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: False}
        log.debug("OptaaDjCsppParser leaving init")

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

        log.debug('entered _process_data_match')
        # Extract the data record particle
        data_particle = self._extract_sample(particle_class,
                                             None,
                                             data_match,
                                             None)

        log.debug("data_particle: %s", data_particle)

        # If we created a data particle, let's append the particle to the result particles
        # to return and increment the state data positioning
        if data_particle:
            if not self._read_state[StateKey.METADATA_EXTRACTED] and None not in self._header_state.values():
                metadata_particle = self._extract_sample(self._metadata_particle_class,
                                                         None,
                                                         (copy.copy(self._header_state),
                                                         data_match),
                                                         None)
            if metadata_particle:
                self._read_state[StateKey.METADATA_EXTRACTED] = True
                # We're going to insert the metadata particle so that it is the first in the list
                # and set the position to 0, as it cannot have the same position as the non-metadata
                # particle
                result_particles.insert(0, (metadata_particle, {StateKey.POSITION: 0,
                                        StateKey.METADATA_EXTRACTED: True}))

            result_particles.append((data_particle, copy.copy(self._read_state)))

            log.debug('result_particles: %s', result_particles)

    def _process_header_part_match(self, header_part_match):
        """
        This method processes a header part match. It will process one row within a cspp header
        that matched a provided regex. The match groups should be processed and the _header_state
        will be updated with the obtained header values.
        @param header_part_match A regular expression match object for a cspp header row
        """
        log.debug("entered _process_header_part_match")
        header_part_key = header_part_match.group(
            HeaderPartMatchesGroupNumber.HEADER_PART_MATCH_GROUP_KEY)
        header_part_value = header_part_match.group(
            HeaderPartMatchesGroupNumber.HEADER_PART_MATCH_GROUP_VALUE)

        if header_part_key in self._header_state.keys():
            self._header_state[header_part_key] = string.rstrip(header_part_value)

    def _process_chunk_not_containing_data_record_or_header_part(self, chunk):
        """
        This method processes a chunk that does not contain a data record or header. This case is
        not applicable to "non_data". For cspp file streams, we expect some lines in the file that
        we do not care about, and we will not consider them "non_data".
        @param chunk A regular expression match object for a cspp header row
        """
        # Check for the expected timestamp line we will ignore
        timestamp_line_match = TIMESTAMP_LINE_MATCHER.match(chunk)

        # Check for other status messages we can ignore
        #ignore_match = IGNORE_MATCHER.match(chunk)

        #if timestamp_line_match is not None or ignore_match is not None:
        if timestamp_line_match is not None:
            # Ignore
            pass
        else:
            # OK. We got unexpected data
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
        log.debug("entering parse_chunks")
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

            log.debug("chunk: %s", chunk)

            # Increment the read state position now
            self._increment_read_state(len(chunk))

            match = MATCHER.match(chunk)
            log.debug('match: %s', match)

            if match is not None:

                count = match.group(6)   # num wavelengths

                data_regex = self.build_data_regex(REGEX, count)

                fields = re.match(data_regex, chunk)
                if fields is not None:
                    log.debug('Fields groups %s', fields.groups())
                    self._process_data_match(self._data_particle_class, fields, result_particles)
            else:
                log.debug('Match is None')
                # Check for head part match
                header_part_match = HEADER_PART_MATCHER.match(chunk)
                log.debug('header_part_match: %s', header_part_match)

                if header_part_match is not None:
                    log.debug("header_part_match is not None:")
                    self._process_header_part_match(header_part_match)
                else:
                    log.debug("header_part_match is None:")
                    self._process_chunk_not_containing_data_record_or_header_part(chunk)

            # Retrieve the next non data chunk
            (nd_timestamp, non_data, non_start, non_end) = self._chunker.get_next_non_data_with_index(clean=False)

            # Retrieve the next data chunk
            (timestamp, chunk, start, end) = self._chunker.get_next_data_with_index(clean=True)

            # Process the non data
            self.handle_non_data(non_data, non_end, start)

        log.debug("leaving parse_chunks")
        return result_particles

    def build_data_regex(self, regex, count):
        data_regex = regex
        array = r'((?:\d+\t){%s})' % count

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX   # C ref dark

        data_regex += array  # C Ref counts

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX  # C sig dark

        data_regex += array  # c sig counts
        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX      # A ref dark

        data_regex += array      # a ref counts

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # A sig dark

        data_regex += array      # a sig counts

        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # external temp
        data_regex += '(' + INT_REGEX + ')' + TAB_REGEX     # internal temp
        data_regex += '(' + INT_REGEX + ')'      # pressure counts

        data_regex += r'\t*' + END_OF_LINE_REGEX

        return data_regex

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # non-data is not expected, if found it is an error
        if non_data is not None and non_end <= start:
            log.debug("non_data: %s", non_data)
            # send an UnexpectedDataException and increment the state
            self._increment_read_state(len(non_data))
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data %s" %
                                                             (len(non_data), non_data)))