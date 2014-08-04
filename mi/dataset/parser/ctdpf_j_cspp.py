#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf_j_cspp
@file marine-integrations/mi/dataset/parser/ctdpf_j_cspp.py
@author Joe Padula
@brief Parser for the ctdpf_j_cspp dataset driver
Release notes:

Initial Release
"""

__author__ = 'Joe Padula'
__license__ = 'Apache 2.0'

import numpy

from mi.core.log import get_logger
log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle
from mi.core.exceptions import RecoverableSampleException

from mi.dataset.parser.cspp_base import \
    CsppParser, \
    FLOAT_REGEX, \
    Y_OR_N_REGEX, \
    MULTIPLE_TAB_REGEX, \
    END_OF_LINE_REGEX, \
    CsppMetadataDataParticle, \
    MetadataRawDataKey, \
    encode_y_or_n

# regex for the data record
DATA_REGEX = r'(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Profiler Timestamp
DATA_REGEX += '(' + Y_OR_N_REGEX + ')' + MULTIPLE_TAB_REGEX     # Suspect Timestamp
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Temperature
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Conductivity
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Pressure
DATA_REGEX += '(' + FLOAT_REGEX + ')' + END_OF_LINE_REGEX   # Salinity


class DataMatchesGroupNumber(BaseEnum):
    """
    An enum for group match indices for a data record chunk.
    Used to access the match groups in the particle raw data
    """
    PROFILER_TIMESTAMP = 1
    SUSPECT_TIMESTAMP = 2
    TEMPERATURE = 3
    CONDUCTIVITY = 4
    PRESSURE = 5
    SALINITY = 6


class DataParticleType(BaseEnum):
    """
    The data particle types that this parser can generate
    """
    METADATA_RECOVERED = 'ctdpf_j_cspp_metadata_recovered'
    INSTRUMENT_RECOVERED = 'ctdpf_j_cspp_instrument_recovered'
    METADATA_TELEMETERED = 'ctdpf_j_cspp_metadata'
    INSTRUMENT_TELEMETERED = 'ctdpf_j_cspp_instrument'


class CtdpfJCsppParserDataParticleKey(BaseEnum):
    """
    The data particle keys associated with ctdpf_j_cspp data instrument particle parameters
    """
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    TEMPERATURE = 'temperature'
    CONDUCTIVITY = 'conductivity'
    PRESSURE = 'pressure'
    SALINITY = 'salinity'


class CtdpfJCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Base Class for building a ctdpf_j_cspp metadata particle
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
            raise RecoverableSampleException(
                "Error (%s) while decoding parameters in data: [%s]"
                % (ex, self.raw_data))

        return results


class CtdpfJCsppMetadataRecoveredDataParticle(CtdpfJCsppMetadataDataParticle):
    """
    Class for building a ctdpf_j_cspp recovered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_RECOVERED


class CtdpfJCsppMetadataTelemeteredDataParticle(CtdpfJCsppMetadataDataParticle):
    """
    Class for building a ctdpf_j_cspp telemetered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_TELEMETERED


class CtdpfJCsppInstrumentDataParticle(DataParticle):
    """
    Base Class for building a ctdpf_j_cspp instrument data particle
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
            results.append(self._encode_value(CtdpfJCsppParserDataParticleKey.PROFILER_TIMESTAMP,
                                              self.raw_data.group(DataMatchesGroupNumber.PROFILER_TIMESTAMP),
                                              numpy.float))

            results.append(self._encode_value(CtdpfJCsppParserDataParticleKey.SUSPECT_TIMESTAMP,
                                              self.raw_data.group(DataMatchesGroupNumber.SUSPECT_TIMESTAMP),
                                              encode_y_or_n))

            results.append(self._encode_value(CtdpfJCsppParserDataParticleKey.TEMPERATURE,
                                              self.raw_data.group(DataMatchesGroupNumber.TEMPERATURE),
                                              float))

            results.append(self._encode_value(CtdpfJCsppParserDataParticleKey.CONDUCTIVITY,
                                              self.raw_data.group(DataMatchesGroupNumber.CONDUCTIVITY),
                                              float))

            results.append(self._encode_value(CtdpfJCsppParserDataParticleKey.PRESSURE,
                                              self.raw_data.group(DataMatchesGroupNumber.PRESSURE),
                                              float))

            results.append(self._encode_value(CtdpfJCsppParserDataParticleKey.SALINITY,
                                              self.raw_data.group(DataMatchesGroupNumber.SALINITY),
                                              float))

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


class CtdpfJCsppInstrumentRecoveredDataParticle(CtdpfJCsppInstrumentDataParticle):
    """
    Class for building a ctdpf_j_cspp recovered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_RECOVERED


class CtdpfJCsppInstrumentTelemeteredDataParticle(CtdpfJCsppInstrumentDataParticle):
    """
    Class for building a ctdpf_j_cspp telemetered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_TELEMETERED


class CtdpfJCsppParser(CsppParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an CtdpfJCsppParser object.
        @param config The configuration for this CtdpfJCsppParser parser
        @param state The state the CtdpfJCsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the ctdpf_j_cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        # Call the superclass constructor
        super(CtdpfJCsppParser, self).__init__(config,
                                                 state,
                                                 stream_handle,
                                                 state_callback,
                                                 publish_callback,
                                                 exception_callback,
                                                 DATA_REGEX,
                                                 *args, **kwargs)