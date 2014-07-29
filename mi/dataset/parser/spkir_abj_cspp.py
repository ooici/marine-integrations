#!/usr/bin/env python

"""
@package mi.dataset.parser.spkir_abj_cspp
@file marine-integrations/mi/dataset/parser/spkir_abj_cspp.py
@author Jeff Roy
@brief Parser for the spkir_abj_cspp dataset driver
Release notes:

initial release
"""

__author__ = 'Jeff Roy'
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
    PARTICLE_KEY_INDEX, \
    DATA_MATCHES_GROUP_NUMBER_INDEX, \
    TYPE_ENCODING_INDEX, \
    encode_y_or_n

INSTRUMENT_ID_REGEX = r'SAT\w+'  # instrument ids all begin with SAT
CHECKSUM_REGEX = r'[0-9a-fA-F]{2}'  # hex characters

# Input Records are formatted as follows
# FORMAT    DATA Type       Field               Units       Notes
#
# string 	float64 	    Profiler Timestamp 	seconds 	Seconds since 1/1/70 with millisecond resolution
# string 	float32 	    Depth 	            decibars
# string    string          Suspect Timestamp   1           "y" or "n"
# string 	string 	        Instrument ID    	1 	        "SAT" + instrument type
# string 	string 	        Serial Number 	    1
# string 	float64 	    Timer (On Secs) 	seconds 	This field is left padded with zeros
# string 	int16 	        Sample Delay 	    ms 	        number of milliseconds to offset the Timer
# string 	uint32 	        Channel 1 	        counts 	    sampled A/D counts from the first optical channel
# string 	uint32 	        Channel 2 	        counts 	    sampled A/D counts from the second optical channel
# string 	uint32 	        Channel 3 	        counts 	    sampled A/D counts from the third optical channel
# string 	uint32 	        Channel 4 	        counts 	    sampled A/D counts from the fourth optical channel
# string 	uint32 	        Channel 5 	        counts 	    sampled A/D counts from the fifth optical channel
# string 	uint32 	        Channel 6 	        counts 	    sampled A/D counts from the sixth optical channel
# string 	uint32 	        Channel 7 	        counts 	    sampled A/D counts from the seventh optical channel
# string 	uint16 	        Vin 	            counts 	    regulated input voltage
# string 	uint16 	        Va 	                counts 	    analog rail voltage of the instrument
# string 	uint16 	        Internal Temperature counts 	internal temperature of the instrument
# string 	uint8 	        Frame Counter 	    counts 	    maintains a count of each frame transmitted
# string 	string 	        Checksum 	        1 	        ASCII-Hex formatted Checksum

DATA_REGEX = r'(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Profiler Timestamp
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Depth
DATA_REGEX += '(' + Y_OR_N_REGEX + ')' + MULTIPLE_TAB_REGEX  # Suspect Timestamp
DATA_REGEX += '(' + INSTRUMENT_ID_REGEX + ')' + MULTIPLE_TAB_REGEX  # Instrument ID
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Serial Number
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Timer
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Sample Delay
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Channel 1
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Channel 2
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Channel 3
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Channel 4
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Channel 5
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Channel 6
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Channel 7
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Vin
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Va
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Internal Temperature
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX  # Frame Counter
DATA_REGEX += '(' + CHECKSUM_REGEX + ')' + END_OF_LINE_REGEX  # Checksum

# IDD states the configuration rows after the header as well as occasional malformed data rows
# can be ignored.
#
# Ignore any rows that begin with the timestamp and depth but
# do not match the data record or the header rows formats

IGNORE_REGEX = FLOAT_REGEX + MULTIPLE_TAB_REGEX  # Profiler Timestamp
IGNORE_REGEX += FLOAT_REGEX + MULTIPLE_TAB_REGEX  # Depth
IGNORE_REGEX += Y_OR_N_REGEX + MULTIPLE_TAB_REGEX  # Suspect Timestamp
IGNORE_REGEX += r'[^\t]*' + END_OF_LINE_REGEX  # any text after the Depth

IGNORE_MATCHER = re.compile(IGNORE_REGEX)


class DataMatchesGroupNumber(BaseEnum):
    """
    An enum for group match indices for a data record chunk.
    Used to access the match groups in the particle raw data
    """
    PROFILER_TIMESTAMP = 1
    PRESSURE = 2
    SUSPECT_TIMESTAMP = 3
    MODEL = 4
    SERIAL_NUMBER = 5
    TIMER = 6
    SAMPLE_DELAY = 7
    CHANNEL_1 = 8
    CHANNEL_2 = 9
    CHANNEL_3 = 10
    CHANNEL_4 = 11
    CHANNEL_5 = 12
    CHANNEL_6 = 13
    CHANNEL_7 = 14
    VIN = 15
    VA = 16
    INTERNAL_TEMPERATURE = 17
    FRAME_COUNTER = 18
    CHECKSUM = 19


class DataParticleType(BaseEnum):
    """
    The data particle types that a spkir_abj_cspp parser could generate
    """
    INSTRUMENT_TELEMETERED = 'spkir_abj_cspp_instrument'
    INSTRUMENT_RECOVERED = 'spkir_abj_cspp_instrument_recovered'
    METADATA_TELEMETERED = 'spkir_abj_cspp_metadata'
    METADATA_RECOVERED = 'spkir_abj_cspp_metadata_recovered'


class SpkirAbjCsppParserDataParticleKey(BaseEnum):
    """
    The data particle keys associated with spkir_abj_cspp data particle parameters
    """

    INSTRUMENT_ID = 'instrument_id'
    SERIAL_NUMBER = 'serial_number'
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    TIMER = 'timer'
    SAMPLE_DELAY = 'sample_delay'
    CHANNEL_ARRAY = 'channel_array'
    VIN_SENSE = 'vin_sense'
    VA_SENSE = 'va_sense'
    INTERNAL_TEMPERATURE = 'internal_temperature'
    FRAME_COUNTER = 'frame_counter'

# A group of non common metadata particle encoding rules used to simplify encoding using a loop
NON_COMMON_METADATA_PARTICLE_ENCODING_RULES = [
    (SpkirAbjCsppParserDataParticleKey.INSTRUMENT_ID, DataMatchesGroupNumber.MODEL, str),
    (SpkirAbjCsppParserDataParticleKey.SERIAL_NUMBER, DataMatchesGroupNumber.SERIAL_NUMBER, str)
]


class SpkirAbjCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Base Class for building a spkir_abj_cspp metadata particle
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

            # Process each of the non common metadata particle parameters
            for rule in NON_COMMON_METADATA_PARTICLE_ENCODING_RULES:

                results.append(self._encode_value(
                    rule[PARTICLE_KEY_INDEX],
                    data_match.group(rule[DATA_MATCHES_GROUP_NUMBER_INDEX]),
                    rule[TYPE_ENCODING_INDEX]))

            # Set the internal timestamp
            internal_timestamp_unix = numpy.float(data_match.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, self.raw_data))

        return results


class SpkirAbjCsppMetadataRecoveredDataParticle(SpkirAbjCsppMetadataDataParticle):
    """
    Class for building a spkir_abj_cspp recovered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_RECOVERED


class SpkirAbjCsppMetadataTelemeteredDataParticle(SpkirAbjCsppMetadataDataParticle):
    """
    Class for building a spkir_abj_cspp telemetered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_TELEMETERED


class SpkirAbjCsppInstrumentDataParticle(DataParticle):
    """
    Base Class for building a spkir_abj_cspp instrument data particle
    """

    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
        """
        results = []
        channel_array = []

        try:

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.PROFILER_TIMESTAMP,
                                              self.raw_data.group(DataMatchesGroupNumber.PROFILER_TIMESTAMP),
                                              numpy.float))

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.PRESSURE,
                                              self.raw_data.group(DataMatchesGroupNumber.PRESSURE),
                                              float))

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.SUSPECT_TIMESTAMP,
                                              self.raw_data.group(DataMatchesGroupNumber.SUSPECT_TIMESTAMP),
                                              encode_y_or_n))

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.TIMER,
                                              self.raw_data.group(DataMatchesGroupNumber.TIMER),
                                              numpy.float))

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.SAMPLE_DELAY,
                                              self.raw_data.group(DataMatchesGroupNumber.SAMPLE_DELAY),
                                              int))

            try:

                channel_array = [int(self.raw_data.group(DataMatchesGroupNumber.CHANNEL_1)),
                                 int(self.raw_data.group(DataMatchesGroupNumber.CHANNEL_2)),
                                 int(self.raw_data.group(DataMatchesGroupNumber.CHANNEL_3)),
                                 int(self.raw_data.group(DataMatchesGroupNumber.CHANNEL_4)),
                                 int(self.raw_data.group(DataMatchesGroupNumber.CHANNEL_5)),
                                 int(self.raw_data.group(DataMatchesGroupNumber.CHANNEL_6)),
                                 int(self.raw_data.group(DataMatchesGroupNumber.CHANNEL_7))]

                results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.CHANNEL_ARRAY,
                                                  channel_array,
                                                  list))
            except ValueError:
                log.error("Data particle error encoding. Name:%s Value:%s",
                          SpkirAbjCsppParserDataParticleKey.CHANNEL_ARRAY, channel_array)
                self._encoding_errors.append({SpkirAbjCsppParserDataParticleKey.CHANNEL_ARRAY: channel_array})

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.VIN_SENSE,
                                              self.raw_data.group(DataMatchesGroupNumber.VIN),
                                              int))

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.VA_SENSE,
                                              self.raw_data.group(DataMatchesGroupNumber.VA),
                                              int))

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.INTERNAL_TEMPERATURE,
                                              self.raw_data.group(DataMatchesGroupNumber.VA),
                                              int))

            results.append(self._encode_value(SpkirAbjCsppParserDataParticleKey.FRAME_COUNTER,
                                              self.raw_data.group(DataMatchesGroupNumber.FRAME_COUNTER),
                                              int))

            # # Set the internal timestamp
            internal_timestamp_unix = numpy.float(self.raw_data.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, self.raw_data))

        #log.debug('*** instrument particle result %s', results)
        return results


class SpkirAbjCsppInstrumentRecoveredDataParticle(SpkirAbjCsppInstrumentDataParticle):
    """
    Class for building a spkir_abj_cspp recovered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_RECOVERED


class SpkirAbjCsppInstrumentTelemeteredDataParticle(SpkirAbjCsppInstrumentDataParticle):
    """
    Class for building a spkir_abj_cspp telemetered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_TELEMETERED


class SpkirAbjCsppParser(CsppParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an SpkirAbjCsppParser object.
        @param config The configuration for this SpkirAbjCsppParser parser
        @param state The state the SpkirAbjCsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the spkir_abj_cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        # Call the superclass constructor
        super(SpkirAbjCsppParser, self).__init__(config,
                                                 state,
                                                 stream_handle,
                                                 state_callback,
                                                 publish_callback,
                                                 exception_callback,
                                                 DATA_REGEX,
                                                 ignore_matcher=IGNORE_MATCHER,
                                                 *args, **kwargs)
