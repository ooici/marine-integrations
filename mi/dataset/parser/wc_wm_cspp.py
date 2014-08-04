#!/usr/bin/env python

"""
@package mi.dataset.parser.wc_wm_cspp
@file marine-integrations/mi/dataset/parser/wc_wm_cspp.py
@author Jeff Roy
@brief wc_wm Parser for the cspp_eng_cspp dataset driver
Release notes: This is one of 4 parsers that make up that driver

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

import numpy

from mi.core.log import get_logger
log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import RecoverableSampleException
from mi.core.instrument.data_particle import DataParticle

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

# Input Records are formatted as follows
# FORMAT    DATA Type       Field               Units       Notes
#
# string 	float64 	Profiler Timestamp 	    seconds 	Seconds since 1/1/70 with millisecond resolution
# string 	float32 	Depth 	                decibars
# string 	string 	    Suspect Timestamp 	    1 	        "y" or "n"
# string 	int32 	    Encoder Counts 	        counts 	    Keeps track of the net rotation done by the winch axle
# string 	float32 	Winch Current 	        A 	        Current drawn by the winch motor. Sign reflects direction
# string 	string 	    Winch Status 	        1
# string 	float32 	Velocity 	            counts/s 	How fast the winch is spooling rope
# string 	float32 	Temperature 	        deg_C 	    Temperature of winch assembly
# string 	float32 	Winch Voltage 	        volts 	    Voltage at the motor control module
# string 	int32 	    Time Counts 	        counts 	    Related to estimating battery energy
# string 	int32 	    Discharge Counts 	    counts 	    Related to estimating battery energy
# string 	float32 	Rope on Drum 	        meters 	    Amount of rope on the winch drum

STRING_REGEX = r'\S*'  # any non white space

DATA_REGEX = '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX    # Profiler Timestamp
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # Depth
DATA_REGEX += '(' + Y_OR_N_REGEX + ')' + MULTIPLE_TAB_REGEX  # Suspect Timestamp
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX     # Encoder Counts
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # Winch Current
DATA_REGEX += '(' + STRING_REGEX + ')' + MULTIPLE_TAB_REGEX  # Winch Status
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # Velocity
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # Temperature
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # Winch Voltage
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX     # Time Counts
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX     # Discharge Counts
DATA_REGEX += '(' + FLOAT_REGEX + ')' + END_OF_LINE_REGEX    # Rope on Drum


class WcWmDataTypeKey(BaseEnum):
    WC_WM_CSPP_TELEMETERED = 'wc_wm_cspp_telemetered'
    WC_WM_CSPP_RECOVERED = 'wc_wm_cspp_recovered'

class DataMatchesGroupNumber(BaseEnum):
    """
    An enum for group match indices for a data record chunk.
    Used to access the match groups in the particle raw data
    """
    PROFILER_TIMESTAMP = 1
    PRESSURE = 2
    SUSPECT_TIMESTAMP = 3
    HEADING = 4
    PITCH = 5
    ROLL = 6


class DataParticleType(BaseEnum):
    ENGINEERING_TELEMETERED = 'cspp_eng_cspp_wc_wm_eng'
    ENGINEERING_RECOVERED = 'cspp_eng_cspp_wc_wm_eng_recovered'
    METADATA_TELEMETERED = 'cspp_eng_cspp_wc_wm_metadata'
    METADATA_RECOVERED = 'cspp_eng_cspp_wc_wm_metadata_recovered'


class WcWmEngDataParticleKey(BaseEnum):
    """
    The data particle keys associated with wc_wm engineering data particle parameters
    """
    INSTRUMENT_ID = 'instrument_id'
    SERIAL_NUMBER = 'serial_number'
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    HEADING = 'heading'
    PITCH = 'pitch'
    ROLL = 'roll'

# A group of instrument data particle encoding rules used to simplify encoding using a loop
ENGINEERING_PARTICLE_ENCODING_RULES = [
    (WcWmEngDataParticleKey.PROFILER_TIMESTAMP, DataMatchesGroupNumber.PROFILER_TIMESTAMP, numpy.float),
    (WcWmEngDataParticleKey.PRESSURE, DataMatchesGroupNumber.PRESSURE, float),
    (WcWmEngDataParticleKey.SUSPECT_TIMESTAMP, DataMatchesGroupNumber.SUSPECT_TIMESTAMP, encode_y_or_n),
    (WcWmEngDataParticleKey.HEADING, DataMatchesGroupNumber.HEADING, float),
    (WcWmEngDataParticleKey.PITCH, DataMatchesGroupNumber.PITCH, float),
    (WcWmEngDataParticleKey.ROLL, DataMatchesGroupNumber.ROLL, float),
]


class WcWmMetadataDataParticle(CsppMetadataDataParticle):
    """
    Class for building a wc hmr metadata particle
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
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: [%s]"
                                             % (ex, self.raw_data))

        return results


class WcWmMetadataRecoveredDataParticle(WcWmMetadataDataParticle):
    """
    Class for building a wc hmr recovered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_RECOVERED


class WcWmMetadataTelemeteredDataParticle(WcWmMetadataDataParticle):
    """
    Class for building a wc hmr telemetered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_TELEMETERED


class WcWmEngDataParticle(DataParticle):
    """
    Class for parsing data from the wc hmr engineering data set
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
            for rule in ENGINEERING_PARTICLE_ENCODING_RULES:

                results.append(self._encode_value(
                    rule[PARTICLE_KEY_INDEX],
                    self.raw_data.group(rule[DATA_MATCHES_GROUP_NUMBER_INDEX]),
                    rule[TYPE_ENCODING_INDEX]))

            # # Set the internal timestamp
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


class WcWmEngRecoveredDataParticle(WcWmEngDataParticle):
    """
    Class for building a wc hmr recovered engineering data particle
    """

    _data_particle_type = DataParticleType.ENGINEERING_RECOVERED


class WcWmEngTelemeteredDataParticle(WcWmEngDataParticle):
    """
    Class for building a wc hmr telemetered engineering data particle
    """

    _data_particle_type = DataParticleType.ENGINEERING_TELEMETERED


class WcWmCsppParser(CsppParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an CsppEngCsppParser object.
        @param config The configuration for this CsppEngCsppParser parser
        @param state The state the CsppEngCsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the cspp_eng_cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        # Call the superclass constructor
        super(WcWmCsppParser, self).__init__(config,
                                              state,
                                              stream_handle,
                                              state_callback,
                                              publish_callback,
                                              exception_callback,
                                              DATA_REGEX,
                                              ignore_matcher=None,
                                              *args, **kwargs)
