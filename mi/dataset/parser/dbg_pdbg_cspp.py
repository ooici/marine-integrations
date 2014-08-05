#!/usr/bin/env python

"""
@package mi.dataset.parser.dbg_pdbg_cspp
@file marine-integrations/mi/dataset/parser/dbg_pdbg_cspp.py
@author Jeff Roy
@brief Parser for the cspp_eng_cspp dataset driver
Release notes:

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import copy
import re
from functools import partial
import string
import numpy

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
    METADATA_PARTICLE_CLASS_KEY, \
    SIEVE_MATCHER, \
    StateKey, \
    HeaderPartMatchesGroupNumber, \
    TIMESTAMP_LINE_MATCHER, \
    HEADER_PART_MATCHER, \
    INT_REGEX, \
    FLOAT_REGEX, \
    Y_OR_N_REGEX, \
    MULTIPLE_TAB_REGEX, \
    END_OF_LINE_REGEX, \
    CsppMetadataDataParticle, \
    MetadataRawDataKey, \
    PARTICLE_KEY_INDEX, \
    DATA_MATCHES_GROUP_NUMBER_INDEX, \
    TYPE_ENCODING_INDEX, \
    encode_y_or_n

# *** Need to define data regex for this parser ***
STRING_REGEX = r'.*'  # any characters except new line

COMMON_DATA_REGEX = '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX    # Profiler Timestamp
COMMON_DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # Depth
COMMON_DATA_REGEX += '(' + Y_OR_N_REGEX + ')' + MULTIPLE_TAB_REGEX  # Suspect Timestamp

BATTERY_STATUS_REGEX = r'&' + '(' + INT_REGEX + ')'          # Battery Number
BATTERY_STATUS_REGEX += r'q0 d- ' + '(' + FLOAT_REGEX + ')'  # Battery Voltage
BATTERY_STATUS_REGEX += STRING_REGEX                         # other crap to be ignored

GPS_ADJUSTMENT_REGEX = 'GPS adjustment ' + '(' + INT_REGEX + ')'  # GPS Adjustment

BATTERY_DATA_REGEX = COMMON_DATA_REGEX + BATTERY_STATUS_REGEX + END_OF_LINE_REGEX
BATTERY_DATA_MATCHER = re.compile(BATTERY_DATA_REGEX)

GPS_DATA_REGEX = COMMON_DATA_REGEX + GPS_ADJUSTMENT_REGEX + END_OF_LINE_REGEX
GPS_DATA_MATCHER = re.compile(GPS_DATA_REGEX)

IGNORE_REGEX = COMMON_DATA_REGEX + STRING_REGEX + END_OF_LINE_REGEX  # most of the status messages are ignored
IGNORE_MATCHER = re.compile(IGNORE_REGEX)


class DataMatchesGroupNumber(BaseEnum):
    """
    An enum for group match indices for a data record chunk.
    Used to access the match groups in the particle raw data
    """
    PROFILER_TIMESTAMP = 1
    PRESSURE = 2
    SUSPECT_TIMESTAMP = 3
    BATTERY_NUMBER = 4
    BATTERY_VOLTAGE = 5
    GPS_ADJUSTMENT = 4


class DbgPdbgDataTypeKey(BaseEnum):
    DBG_PDBG_CSPP_TELEMETERED = 'dbg_pdbg_cspp_telemetered'
    DBG_PDBG_CSPP_RECOVERED = 'dbg_pdbg_cspp_recovered'


BATTERY_STATUS_CLASS_KEY = 'battery_status_class'
GPS_ADJUSTMENT_CLASS_KEY = 'gps_adjustment_class'


class DataParticleType(BaseEnum):
    BATTERY_TELEMETERED = 'cspp_eng_cspp_dbg_pdbg_batt_eng'
    BATTERY_RECOVERED = 'cspp_eng_cspp_dbg_pdbg_batt_eng_recovered'
    GPS_TELEMETERED = 'cspp_eng_cspp_dbg_pdbg_gps_eng'
    GPS_RECOVERED = 'cspp_eng_cspp_dbg_pdbg_gps_eng_recovered'
    METADATA_TELEMETERED = 'cspp_eng_cspp_dbg_pdbg_metadata'
    METADATA_RECOVERED = 'cspp_eng_cspp_dbg_pdbg_metadata_recovered'


class DbgPdbgBatteryParticleKey(BaseEnum):
    """
    The data particle keys associated with dbg_pdbg battery status particle parameters
    """
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    BATTERY_NUMBER = 'battery_number_uint8'
    BATTERY_VOLTAGE = 'battery_voltage_flt32'


class DbgPdbgGpsParticleKey(BaseEnum):
    """
    The data particle keys associated with dbg_pdbg battery status particle parameters
    """
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    GPS_ADJUSTMENT = 'gps_adjustment'

# A group of encoding rules common to the battery and gps status particles
# used to simplify encoding using a loop

COMMON_PARTICLE_ENCODING_RULES = [
    (DbgPdbgGpsParticleKey.PROFILER_TIMESTAMP, DataMatchesGroupNumber.PROFILER_TIMESTAMP, numpy.float),
    (DbgPdbgGpsParticleKey.PRESSURE, DataMatchesGroupNumber.PRESSURE, float),
    (DbgPdbgGpsParticleKey.SUSPECT_TIMESTAMP, DataMatchesGroupNumber.SUSPECT_TIMESTAMP, encode_y_or_n),
]


class DbgPdbgMetadataDataParticle(CsppMetadataDataParticle):
    """
    Class for building a wc hmr metadata particle
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

            # Append the base metadata parsed values to the results to return
            results += self._build_metadata_parsed_values()

            data_match = self.raw_data[MetadataRawDataKey.DATA_MATCH]

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(data_match.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, self.raw_data))

        return results


class DbgPdbgMetadataRecoveredDataParticle(DbgPdbgMetadataDataParticle):
    """
    Class for building a wc hmr recovered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_RECOVERED


class DbgPdbgMetadataTelemeteredDataParticle(DbgPdbgMetadataDataParticle):
    """
    Class for building a wc hmr telemetered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_TELEMETERED


class DbgPdbgBatteryParticle(DataParticle):
    """
    Class for parsing data from the wc hmr engineering data set
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

            # Process each of the common particle parameters
            for rule in COMMON_PARTICLE_ENCODING_RULES:

                results.append(self._encode_value(
                    rule[PARTICLE_KEY_INDEX],
                    self.raw_data.group(rule[DATA_MATCHES_GROUP_NUMBER_INDEX]),
                    rule[TYPE_ENCODING_INDEX]))

            results.append(self._encode_value(DbgPdbgBatteryParticleKey.BATTERY_NUMBER,
                                              self.raw_data.group(DataMatchesGroupNumber.BATTERY_NUMBER),
                                              int))

            results.append(self._encode_value(DbgPdbgBatteryParticleKey.BATTERY_VOLTAGE,
                                              self.raw_data.group(DataMatchesGroupNumber.BATTERY_VOLTAGE),
                                              int))

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(self.raw_data.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        # We shouldn't end up with an exception due to the strongly specified regex, but we
        # will ensure we catch any potential errors just in case
        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, self.raw_data))

        return results


class DbgPdbgEngRecoveredBatteryParticle(DbgPdbgBatteryParticle):
    """
    Class for building a wc hmr recovered engineering data particle
    """

    _data_particle_type = DataParticleType.BATTERY_RECOVERED


class DbgPdbgEngTelemeteredBatteryParticle(DbgPdbgBatteryParticle):
    """
    Class for building a wc hmr telemetered engineering data particle
    """

    _data_particle_type = DataParticleType.BATTERY_TELEMETERED


class DbgPdbgGpsParticle(DataParticle):
    """
    Class for parsing data from the wc hmr engineering data set
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

            # Process each of the common particle parameters
            for rule in COMMON_PARTICLE_ENCODING_RULES:

                results.append(self._encode_value(
                    rule[PARTICLE_KEY_INDEX],
                    self.raw_data.group(rule[DATA_MATCHES_GROUP_NUMBER_INDEX]),
                    rule[TYPE_ENCODING_INDEX]))

            results.append(self._encode_value(DbgPdbgGpsParticleKey.GPS_ADJUSTMENT,
                                              self.raw_data.group(DataMatchesGroupNumber.GPS_ADJUSTMENT),
                                              int))

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(self.raw_data.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        # We shouldn't end up with an exception due to the strongly specified regex, but we
        # will ensure we catch any potential errors just in case
        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, self.raw_data))

        return results


class DbgPdbgEngRecoveredGpsParticle(DbgPdbgGpsParticle):
    """
    Class for building a wc hmr recovered engineering data particle
    """

    _data_particle_type = DataParticleType.GPS_RECOVERED


class DbgPdbgEngTelemeteredGpsParticle(DbgPdbgGpsParticle):
    """
    Class for building a wc hmr telemetered engineering data particle
    """

    _data_particle_type = DataParticleType.GPS_TELEMETERED


class DbgPdbgParser(BufferLoadingParser):
    """
    Parser for the dbg_pdbg engineering data part of the cspp_eng_cspp driver
    This Parser is based on the cspp_base parser, modified to handle
    the multiple data particles of the dbg_pdbg
    """

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback):
        """
        This method is a constructor that will instantiate an CsppParser object.
        @param config The configuration for this CsppParser parser
        @param state The state the CsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        # Build up the header state dictionary using the default her key list ot one that was provided
        self._header_state = {}

        header_key_list = DEFAULT_HEADER_KEY_LIST

        for header_key in header_key_list:
            self._header_state[header_key] = None

        # Obtain the particle classes dictionary from the config data
        particle_classes_dict = config.get(DataSetDriverConfigKeys.PARTICLE_CLASSES_DICT)
        # Set the metadata and data particle classes to be used later

        self._metadata_particle_class = particle_classes_dict.get(METADATA_PARTICLE_CLASS_KEY)

        self._battery_status_class = particle_classes_dict.get(BATTERY_STATUS_CLASS_KEY)
        self._gps_adjustment_class = particle_classes_dict.get(GPS_ADJUSTMENT_CLASS_KEY)

        # Initialize the record buffer to an empty list
        self._record_buffer = []


        # Call the superclass constructor
        super(DbgPdbgParser, self).__init__(config,
                                            stream_handle,
                                            state,
                                            partial(StringChunker.regex_sieve_function,
                                                    regex_list=[SIEVE_MATCHER]),
                                            state_callback,
                                            publish_callback,
                                            exception_callback)

        # If provided a state, set it.  Otherwise initialize it
        # This needs to be done post superclass __init__
        if state:
            self.set_state(state)
        else:
            # Initialize the read state
            self._read_state = {StateKey.POSITION: 0, StateKey.METADATA_EXTRACTED: False}


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
        This method processes a data match.  It will extract a metadata particle and insert it into
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

    def _process_header_part_match(self, header_part_match):
        """
        This method processes a header part match.  It will process one row within a cspp header
        that matched a provided regex.  The match groups should be processed and the _header_state
        will be updated  with the obtained header values.
        @param header_part_match A regular expression match object for a cspp header row
        """

        header_part_key = header_part_match.group(
            HeaderPartMatchesGroupNumber.HEADER_PART_MATCH_GROUP_KEY)
        header_part_value = header_part_match.group(
            HeaderPartMatchesGroupNumber.HEADER_PART_MATCH_GROUP_VALUE)

        if header_part_key in self._header_state.keys():
            self._header_state[header_part_key] = string.rstrip(header_part_value)

    def _process_chunk_not_containing_data_record_or_header_part(self, chunk):
        """
        This method processes a chunk that does not contain a data record or header.  This case is
        not applicable to "non_data".  For cspp file streams, we expect some lines in the file that
        we do not care about, and we will not consider them "non_data".
        @param chunk A regular expression match object for a cspp header row
        """

        # Check for the expected timestamp line we will ignore
        timestamp_line_match = TIMESTAMP_LINE_MATCHER.match(chunk)
        # Check for other status messages we can ignore
        ignore_match = IGNORE_MATCHER.match(chunk)

        if timestamp_line_match is not None or ignore_match is not None:
            # Ignore
            pass

        else:

            # OK.  We got unexpected data
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

            battery_match = BATTERY_DATA_MATCHER.match(chunk)

            gps_match = GPS_DATA_MATCHER.match(chunk)

            # If we found a data match, let's process it
            if battery_match is not None:
                self._process_data_match(self._battery_status_class, battery_match, result_particles)

            elif gps_match is not None:
                self._process_data_match(self._gps_adjustment_class, gps_match, result_particles)

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

    def handle_non_data(self, non_data, non_end, start):
        """
        Handle any non-data that is found in the file
        """
        # if non-data is expected, handle it here, otherwise it is an error
        if non_data is not None and non_end <= start:
            log.debug("non_data: %s", non_data)
            # if this non-data is an error, send an UnexpectedDataException and increment the state
            self._increment_read_state(len(non_data))
            # if non-data is a fatal error, directly call the exception, if it is not use the _exception_callback
            self._exception_callback(UnexpectedDataException("Found %d bytes of un-expected non-data %s" %
                                                             (len(non_data), non_data)))
