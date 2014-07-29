#!/usr/bin/env python

"""
@package mi.dataset.parser.parad_j_cspp
@file marine-integrations/mi/dataset/parser/parad_j_cspp.py
@author Joe Padula
@brief Parser for the parad_j_cspp dataset driver
Release notes:

initial release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

import re
import numpy

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import RecoverableSampleException

from mi.dataset.parser.cspp_base import \
    CsppParser, \
    FLOAT_REGEX, \
    INT_REGEX, \
    Y_OR_N_REGEX, \
    MULTIPLE_TAB_REGEX, \
    END_OF_LINE_REGEX, \
    CsppMetadataDataParticle, \
    MetadataRawDataKey, \
    encode_y_or_n

# Date is in format MM/DD/YY, example 04/17/14
DATE_REGEX = r'\d{2}/\d{2}/\d{2}'
# Time is in format HH:MM:SS, example 15:22:31
TIME_REGEX = r'\d{2}:\d{2}:\d{2}'

# regex for the data record
DATA_REGEX = r'(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Profiler Timestamp
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Depth
DATA_REGEX += '(' + Y_OR_N_REGEX + ')' + MULTIPLE_TAB_REGEX     # Suspect Timestamp
DATA_REGEX += '(' + DATE_REGEX + ')' + MULTIPLE_TAB_REGEX     # Date
DATA_REGEX += '(' + TIME_REGEX + ')' + MULTIPLE_TAB_REGEX     # Time
DATA_REGEX += '(' + INT_REGEX + ')' + END_OF_LINE_REGEX    # par

# IDD states the configuration rows after the header as well as occasional malformed data rows
# can be ignored.
#
# Ignore any rows that begin with the timestamp and depth but
# do not match the data record or the header rows formats
IGNORE_REGEX = FLOAT_REGEX + MULTIPLE_TAB_REGEX     # Profiler Timestamp
IGNORE_REGEX += FLOAT_REGEX + MULTIPLE_TAB_REGEX    # Depth
IGNORE_REGEX += Y_OR_N_REGEX + MULTIPLE_TAB_REGEX     # Suspect Timestamp
IGNORE_REGEX += r'[^\t]*' + END_OF_LINE_REGEX    # any text (excluding tabs) after the Suspect Timestamp

IGNORE_MATCHER = re.compile(IGNORE_REGEX)


class DataMatchesGroupNumber(BaseEnum):
    """
    An enum for group match indices for a data record chunk.
    Used to access the match groups in the particle raw data
    """
    PROFILER_TIMESTAMP = 1
    DEPTH = 2
    SUSPECT_TIMESTAMP = 3
    DATE = 4
    TIME = 5
    PAR = 6


class DataParticleType(BaseEnum):
    """
    The data particle types that a parad_j_cspp parser could generate
    """
    METADATA_RECOVERED = 'parad_j_cspp_metadata_recovered'
    INSTRUMENT_RECOVERED = 'parad_j_cspp_instrument_recovered'
    METADATA_TELEMETERED = 'parad_j_cspp_metadata'
    INSTRUMENT_TELEMETERED = 'parad_j_cspp_instrument'


class ParadJCsppParserDataParticleKey(BaseEnum):
    """
    The data particle keys associated with parad_j_cspp data instrument particle parameters
    """
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE_DEPTH = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    DATE_STRING = 'date_string'
    TIME_STRING = 'time_string'
    PAR = 'par'


class ParadJCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Base Class for building a parad_j_cspp metadata particle
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
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
            raise RecoverableSampleException(
                "Error (%s) while decoding parameters in data: [%s]"
                % (ex, self.raw_data))

        return results


class ParadJCsppMetadataRecoveredDataParticle(ParadJCsppMetadataDataParticle):
    """
    Class for building a parad_j_cspp recovered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_RECOVERED


class ParadJCsppMetadataTelemeteredDataParticle(ParadJCsppMetadataDataParticle):
    """
    Class for building a parad_j_cspp telemetered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_TELEMETERED


class ParadJCsppInstrumentDataParticle(DataParticle):
    """
    Base Class for building a parad_j_cspp instrument data particle
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        results = []

        try:
            results.append(self._encode_value(ParadJCsppParserDataParticleKey.PROFILER_TIMESTAMP,
                                              self.raw_data.group(DataMatchesGroupNumber.PROFILER_TIMESTAMP),
                                              numpy.float))

            results.append(self._encode_value(ParadJCsppParserDataParticleKey.PRESSURE_DEPTH,
                                              self.raw_data.group(DataMatchesGroupNumber.DEPTH),
                                              float))

            results.append(self._encode_value(ParadJCsppParserDataParticleKey.SUSPECT_TIMESTAMP,
                                              self.raw_data.group(DataMatchesGroupNumber.SUSPECT_TIMESTAMP),
                                              encode_y_or_n))

            results.append(self._encode_value(ParadJCsppParserDataParticleKey.DATE_STRING,
                                              self.raw_data.group(DataMatchesGroupNumber.DATE),
                                              str))

            results.append(self._encode_value(ParadJCsppParserDataParticleKey.TIME_STRING,
                                              self.raw_data.group(DataMatchesGroupNumber.TIME),
                                              str))

            results.append(self._encode_value(ParadJCsppParserDataParticleKey.PAR,
                                              self.raw_data.group(DataMatchesGroupNumber.PAR),
                                              int))

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(self.raw_data.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException(
                "Error (%s) while decoding parameters in data: [%s]"
                % (ex, self.raw_data))

        return results


class ParadJCsppInstrumentRecoveredDataParticle(ParadJCsppInstrumentDataParticle):
    """
    Class for building a parad_j_cspp recovered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_RECOVERED


class ParadJCsppInstrumentTelemeteredDataParticle(ParadJCsppInstrumentDataParticle):
    """
    Class for building a parad_j_cspp telemetered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_TELEMETERED


class ParadJCsppParser(CsppParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an ParadJCsppParser object.
        @param config The configuration for this ParadJCsppParser parser
        @param state The state the ParadJCsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the parad_j_cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        # Call the superclass constructor
        super(ParadJCsppParser, self).__init__(config,
                                                 state,
                                                 stream_handle,
                                                 state_callback,
                                                 publish_callback,
                                                 exception_callback,
                                                 DATA_REGEX,
                                                 ignore_matcher=IGNORE_MATCHER,
                                                 *args, **kwargs)