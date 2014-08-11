#!/usr/bin/env python

"""
@package mi.dataset.parser.velpt_j_cspp
@file marine-integrations/mi/dataset/parser/velpt_j_cspp.py
@author Jeremy Amundson
@brief Parser for the velpt_j_cspp dataset driver
Release notes:

Initial Release
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'

import numpy

from mi.core.log import get_logger
from mi.core.exceptions import RecoverableSampleException
log = get_logger()
from mi.core.common import BaseEnum


from mi.core.instrument.data_particle import DataParticle
from mi.dataset.parser.cspp_base import CsppParser, FLOAT_REGEX, INT_REGEX, MULTIPLE_TAB_REGEX, \
    END_OF_LINE_REGEX, \
    CsppMetadataDataParticle, MetadataRawDataKey, PARTICLE_KEY_INDEX, \
    DATA_MATCHES_GROUP_NUMBER_INDEX, TYPE_ENCODING_INDEX, \
    Y_OR_N_REGEX, encode_y_or_n


# A regular expression that should match a velpt_j data record
DATA_REGEX = '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX    # profiler timestamp
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # pressure depth
DATA_REGEX += '(' + Y_OR_N_REGEX + ')' + MULTIPLE_TAB_REGEX  # suspect timestamp
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # speed of sound
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # heading
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # pitch
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # roll
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # pressure
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # temperature
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # velocity beam 1
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # velocity beam 2
DATA_REGEX += '(' + FLOAT_REGEX + ')' + MULTIPLE_TAB_REGEX   # velocity beam 3
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX     # amplitude beam 1
DATA_REGEX += '(' + INT_REGEX + ')' + MULTIPLE_TAB_REGEX     # amplitude beam 2
DATA_REGEX += '(' + INT_REGEX + ')' + END_OF_LINE_REGEX      # amplitude beam 3


class DataMatchesGroupNumber(BaseEnum):
    """
    An enum for group match indices for a data record only chunk.
    """

    PROFILER_TIMESTAMP = 1
    PRESSURE_DEPTH = 2
    SUSPECT_TIMESTAMP = 3
    SOUND_SPEED = 4
    HEADING = 5
    PITCH = 6
    ROLL = 7
    PRESSURE = 8
    TEMPERATURE = 9
    VELOCITY_BEAM_1 = 10
    VELOCITY_BEAM_2 = 11
    VELOCITY_BEAM_3 = 12
    AMPLITUDE_BEAM_1 = 13
    AMPLITUDE_BEAM_2 = 14
    AMPLITUDE_BEAM_3 = 15


class DataParticleType(BaseEnum):
    """
    The data particle types that a velpt_j_cspp parser could generate
    """
    METADATA_RECOVERED = 'velpt_j_cspp_metadata_recovered'
    INSTRUMENT_RECOVERED = 'velpt_j_cspp_instrument_recovered'
    METADATA_TELEMETERED = 'velpt_j_cspp_metadata'
    INSTRUMENT_TELEMETERED = 'velpt_j_cspp_instrument'


class VelptJCsppParserDataParticleKey(BaseEnum):
    """
    The data particle keys associated with velpt_j_cspp data particle parameters
    """
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE_DEPTH = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    SOUND_SPEED = 'speed_of_sound'
    HEADING = 'heading'
    PITCH = 'pitch'
    ROLL = 'roll'
    PRESSURE = 'velpt_pressure'
    TEMPERATURE = 'temperature'
    VELOCITY_BEAM_1 = 'velocity_beam1_m_s'
    VELOCITY_BEAM_2 = 'velocity_beam2_m_s'
    VELOCITY_BEAM_3 = 'velocity_beam3_m_s'
    AMPLITUDE_BEAM_1 = 'amplitude_beam1'
    AMPLITUDE_BEAM_2 = 'amplitude_beam2'
    AMPLITUDE_BEAM_3 = 'amplitude_beam3'

# A group of instrument data particle encoding rules used to simplify encoding using a loop
INSTRUMENT_PARTICLE_ENCODING_RULES = [
    (VelptJCsppParserDataParticleKey.PROFILER_TIMESTAMP, DataMatchesGroupNumber.PROFILER_TIMESTAMP, numpy.float),
    (VelptJCsppParserDataParticleKey.PRESSURE_DEPTH, DataMatchesGroupNumber.PRESSURE_DEPTH, float),
    (VelptJCsppParserDataParticleKey.SUSPECT_TIMESTAMP, DataMatchesGroupNumber.SUSPECT_TIMESTAMP, encode_y_or_n),
    (VelptJCsppParserDataParticleKey.SOUND_SPEED, DataMatchesGroupNumber.SOUND_SPEED, float),
    (VelptJCsppParserDataParticleKey.HEADING, DataMatchesGroupNumber.HEADING, float),
    (VelptJCsppParserDataParticleKey.PITCH, DataMatchesGroupNumber.PITCH, float),
    (VelptJCsppParserDataParticleKey.ROLL, DataMatchesGroupNumber.ROLL, float),
    (VelptJCsppParserDataParticleKey.PRESSURE, DataMatchesGroupNumber.PRESSURE, float),
    (VelptJCsppParserDataParticleKey.TEMPERATURE, DataMatchesGroupNumber.TEMPERATURE, float),
    (VelptJCsppParserDataParticleKey.VELOCITY_BEAM_1, DataMatchesGroupNumber.VELOCITY_BEAM_1, float),
    (VelptJCsppParserDataParticleKey.VELOCITY_BEAM_2, DataMatchesGroupNumber.VELOCITY_BEAM_2, float),
    (VelptJCsppParserDataParticleKey.VELOCITY_BEAM_3, DataMatchesGroupNumber.VELOCITY_BEAM_3, float),
    (VelptJCsppParserDataParticleKey.AMPLITUDE_BEAM_1, DataMatchesGroupNumber.AMPLITUDE_BEAM_1, int),
    (VelptJCsppParserDataParticleKey.AMPLITUDE_BEAM_2, DataMatchesGroupNumber.AMPLITUDE_BEAM_2, int),
    (VelptJCsppParserDataParticleKey.AMPLITUDE_BEAM_3, DataMatchesGroupNumber.AMPLITUDE_BEAM_3, int)
]


class VelptJCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Class for building a velpt_j_cspp metadata particle
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

            internal_timestamp_unix = numpy.float(data_match.group(
                DataMatchesGroupNumber.PROFILER_TIMESTAMP))
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Exception when building parsed values")
            raise RecoverableSampleException("Error (%s) while decoding parameters in data: %s" % (ex, self.raw_data))
        return results


class VelptJCsppMetadataRecoveredDataParticle(VelptJCsppMetadataDataParticle):
    """
    Class for building a velpt_j_cspp recovered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_RECOVERED


class VelptJCsppMetadataTelemeteredDataParticle(VelptJCsppMetadataDataParticle):
    """
    Class for building a velpt_j_cspp telemetered metadata particle
    """

    _data_particle_type = DataParticleType.METADATA_TELEMETERED


class VelptJCsppInstrumentDataParticle(DataParticle):
    """
    Class for building a velpt_j_cspp instrument data particle
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

        return results


class VelptJCsppInstrumentRecoveredDataParticle(VelptJCsppInstrumentDataParticle):
    """
    Class for building a velpt_j_cspp recovered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_RECOVERED


class VelptJCsppInstrumentTelemeteredDataParticle(VelptJCsppInstrumentDataParticle):
    """
    Class for building a velpt_j_cspp telemetered instrument data particle
    """

    _data_particle_type = DataParticleType.INSTRUMENT_TELEMETERED


class VelptJCsppParser(CsppParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate an VelptJCsppParser object.
        @param config The configuration for this VelptJCsppParser parser
        @param state The state the VelptJCsppParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the velpt_j_cspp data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        @param exception_callback The function to call to report exceptions
        """

        # Call the superclass constructor
        super(VelptJCsppParser, self).__init__(config,
                                                state,
                                                stream_handle,
                                                state_callback,
                                                publish_callback,
                                                exception_callback,
                                                DATA_REGEX,
                                                *args, **kwargs)
