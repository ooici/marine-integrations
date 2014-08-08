#!/usr/bin/env python

"""
@package mi.dataset.parser.flort_dj_cspp
@file marine-integrations/mi/dataset/parser/flort_dj_cspp.py
@author Jeremy Amundson
@brief Parser for the flort_dj_cspp dataset driver
Release notes:

initial release
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'

import numpy

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.exceptions import RecoverableSampleException
import re

from mi.core.instrument.data_particle import DataParticle
from mi.dataset.parser.cspp_base import CsppParser, FLOAT_REGEX, INT_REGEX, MULTIPLE_TAB_REGEX, \
    END_OF_LINE_REGEX, \
    CsppMetadataDataParticle, MetadataRawDataKey, PARTICLE_KEY_INDEX, \
    DATA_MATCHES_GROUP_NUMBER_INDEX, TYPE_ENCODING_INDEX, \
    Y_OR_N_REGEX, encode_y_or_n

# A regex to match a date in MM/DD/YY format
FORMATTED_DATE_REGEX = r'\d{2}/\d{2}/\d{2}'

# A regex to match a time stamp in HH:MM:SS format
TIME_REGEX = r'\d{2}:\d{2}:\d{2}'

# A regular expression that should match a flort_dj data record
DATA_REGEX = '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Profiler Timestamp
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Depth
DATA_REGEX += '(' + Y_OR_N_REGEX + ')' + MULTIPLE_TAB_REGEX  # suspect timestamp
DATA_REGEX += '(' + FORMATTED_DATE_REGEX + ')' + MULTIPLE_TAB_REGEX  # date string
DATA_REGEX += '(' + TIME_REGEX + ')' + MULTIPLE_TAB_REGEX  # time string
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # measurement_wavelength_beta
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # raw_signal_beta
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # measurement_wavelength_chl
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # raw_signal_chl
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # measurement_wavelength_cdom
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # raw_signal_cdom
DATA_REGEX += '(' + INT_REGEX + ')' + END_OF_LINE_REGEX  # raw_internal_temp

IGNORE_REGEX = FLOAT_REGEX + MULTIPLE_TAB_REGEX # Profiler Timestamp
IGNORE_REGEX += FLOAT_REGEX + MULTIPLE_TAB_REGEX # Depth
IGNORE_REGEX += Y_OR_N_REGEX + MULTIPLE_TAB_REGEX # Suspect Timestamp
IGNORE_REGEX += r'[^\t]*' + END_OF_LINE_REGEX # any text after the Suspect

IGNORE_MATCHER = re.compile(IGNORE_REGEX)

class DataMatchesGroupNumber(BaseEnum):
    """
    An enum for group match indices for a data record only chunk.
    """

    PROFILER_TIMESTAMP = 1
    PRESSURE = 2
    SUSPECT_TIMESTAMP = 3
    DATE = 4
    TIME = 5
    BETA = 6
    RAW_BETA = 7
    CHLOROPHYLL = 8
    RAW_CHLOROPHYLL = 9
    CDOM = 10
    RAW_CDOM = 11
    TEMP = 12


class DataParticleType(BaseEnum):
    """
    The data particle types that a flort_dj_cspp parser could generate
    """
    METADATA_RECOVERED = 'flort_dj_cspp_metadata_recovered'
    INSTRUMENT_RECOVERED = 'flort_dj_cspp_instrument_recovered'
    METADATA_TELEMETERED = 'flort_dj_cspp_metadata'
    INSTRUMENT_TELEMETERED = 'flort_dj_cspp_instrument'


class FlortDjCsppParserDataParticleKey(BaseEnum):
    """
    The data particle keys associated with flort_dj_cspp data particle parameters
    """
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    DATE = 'date_string'
    TIME = 'time_string'
    BETA = 'measurement_wavelength_beta'
    RAW_BETA = 'raw_signal_beta'
    CHLOROPHYLL = 'measurement_wavelength_chl'
    RAW_CHLOROPHYLL = 'raw_signal_chl'
    CDOM = 'measurement_wavelength_cdom'
    RAW_CDOM = 'raw_signal_cdom'
    TEMP = 'raw_internal_temp'

# A group of instrument data particle encoding rules used to simplify encoding using a loop
INSTRUMENT_PARTICLE_ENCODING_RULES = [
    (FlortDjCsppParserDataParticleKey.PROFILER_TIMESTAMP, DataMatchesGroupNumber.PROFILER_TIMESTAMP, numpy.float),
    (FlortDjCsppParserDataParticleKey.PRESSURE, DataMatchesGroupNumber.PRESSURE, float),
    (FlortDjCsppParserDataParticleKey.SUSPECT_TIMESTAMP, DataMatchesGroupNumber.SUSPECT_TIMESTAMP, encode_y_or_n),
    (FlortDjCsppParserDataParticleKey.DATE, DataMatchesGroupNumber.DATE, str),
    (FlortDjCsppParserDataParticleKey.TIME, DataMatchesGroupNumber.TIME, str),
    (FlortDjCsppParserDataParticleKey.BETA, DataMatchesGroupNumber.BETA, int),
    (FlortDjCsppParserDataParticleKey.RAW_BETA, DataMatchesGroupNumber.RAW_BETA, int),
    (FlortDjCsppParserDataParticleKey.CHLOROPHYLL, DataMatchesGroupNumber.CHLOROPHYLL, int),
    (FlortDjCsppParserDataParticleKey.RAW_CHLOROPHYLL, DataMatchesGroupNumber.RAW_CHLOROPHYLL, int),
    (FlortDjCsppParserDataParticleKey.CDOM, DataMatchesGroupNumber.CDOM, int),
    (FlortDjCsppParserDataParticleKey.RAW_CDOM, DataMatchesGroupNumber.RAW_CDOM, int),
    (FlortDjCsppParserDataParticleKey.TEMP, DataMatchesGroupNumber.RAW_CDOM, int)
]


class FlortDjCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Class for building a flort_dj_cspp metadata particle
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

            internal_timestamp_unix = numpy.float(data_match.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: %s" % (ex, self.raw_data))

        return results


class FlortDjCsppMetadataRecoveredDataParticle(FlortDjCsppMetadataDataParticle):
    """
    Class for building a flort_dj_cspp recovered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_RECOVERED


class FlortDjCsppMetadataTelemeteredDataParticle(FlortDjCsppMetadataDataParticle):
    """
    Class for building a flort_dj_cspp telemetered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_TELEMETERED


class FlortDjCsppInstrumentDataParticle(DataParticle):
    """
    Class for building a flort_dj_cspp instrument data particle
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

            # Process each of the instrument particle parameters
            for rule in INSTRUMENT_PARTICLE_ENCODING_RULES:

                results.append(self._encode_value(
                    rule[PARTICLE_KEY_INDEX],
                    self.raw_data.group(rule[DATA_MATCHES_GROUP_NUMBER_INDEX]),
                    rule[TYPE_ENCODING_INDEX]))

            # # Set the internal timestamp
            internal_timestamp_unix = numpy.float(self.raw_data.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: %s" % (ex, self.raw_data))

        log.debug('FlortDjCsppInstrumentDataParticle: particle=%s', results)
        return results


class FlortDjCsppInstrumentRecoveredDataParticle(FlortDjCsppInstrumentDataParticle):
    """
    Class for building a flort_dj_cspp recovered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_RECOVERED


class FlortDjCsppInstrumentTelemeteredDataParticle(FlortDjCsppInstrumentDataParticle):
    """
    Class for building a flort_dj_cspp telemetered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_TELEMETERED


class FlortDjCsppParser(CsppParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an FlortDjCsppParser object.
        @param config The configuration for this FlortDjCsppParser parser
        @param state The state the FlortDjCsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the flort_dj_cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        # Call the superclass constructor
        super(FlortDjCsppParser, self).__init__(config,
                                                state,
                                                stream_handle,
                                                state_callback,
                                                publish_callback,
                                                exception_callback,
                                                DATA_REGEX,
                                                ignore_matcher=IGNORE_MATCHER,
                                                *args, **kwargs)
