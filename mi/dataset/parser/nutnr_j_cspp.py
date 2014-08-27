#!/usr/bin/env python

"""
@package mi.dataset.parser.nutnr_j_cspp
@file marine-integrations/mi/dataset/parser/nutnr_j_cspp.py
@author Emily Hahn
@brief Parser for the nutnr_j_cspp dataset driver
Release notes:

initial release
"""

__author__ = 'Emily Hahn'
__license__ = 'Apache 2.0'

import copy
import re
import ntplib

from mi.core.log import get_logger ; log = get_logger()
from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.core.exceptions import RecoverableSampleException

from mi.dataset.dataset_parser import BufferLoadingParser
from mi.dataset.parser.cspp_base import CsppParser, CsppMetadataDataParticle, \
                                        MetadataRawDataKey, \
                                        FLOAT_REGEX, INT_REGEX, \
                                        Y_OR_N_REGEX, \
                                        END_OF_LINE_REGEX, \
                                        encode_y_or_n, \
                                        SAMPLE_START_REGEX

FLOAT_REGEX_NON_CAPTURE = r'[+-]?[0-9]*\.[0-9]+'
FLOAT_TAB_REGEX = FLOAT_REGEX_NON_CAPTURE + '\t'

# can't use groups for each parameter here since this is over the 100 group limit
# use groups to match repeated regexes, split by tabs to get parameter values instead
LINE_START_REGEX = FLOAT_TAB_REGEX + FLOAT_TAB_REGEX + Y_OR_N_REGEX + '\t'
DATA_REGEX = LINE_START_REGEX
DATA_REGEX += '[a-zA-Z]+\t' # Frame Type
DATA_REGEX += '\d+\t\d+\t' # year, day of year
DATA_REGEX += '(' + FLOAT_TAB_REGEX + '){6}' # match 6 floats separated by tabs
DATA_REGEX += '(?:\d+\t){259}' # match 259 ints separated by tabs, non capturing group due to number of groups
DATA_REGEX += '(' + FLOAT_TAB_REGEX + '){3}' # match 3 floats separated by tabs
DATA_REGEX += '(' + INT_REGEX + ')\t' # lamp time
DATA_REGEX += '(' + FLOAT_TAB_REGEX + '){10}' # match 10 floats separated by tabs
DATA_REGEX += '(\d+)\t' # ctd time
DATA_REGEX += '(' + FLOAT_TAB_REGEX + '){3}' # match 3 floats separated by tabs
DATA_REGEX += '[0-9a-fA-F]{2}' + END_OF_LINE_REGEX # checksum and line end

NUMBER_CHANNELS = 256
NUM_FIELDS = 33 + NUMBER_CHANNELS

# index into split string parameter values
GRP_PROFILER_TIMESTAMP = 0
GRP_SPECTRAL_START = 15
GRP_SPECTRAL_END = GRP_SPECTRAL_START + NUMBER_CHANNELS

# ignore lines matching the start (timestamp, depth, suspect timestamp),
# then any text not containing tabs
IGNORE_LINE_REGEX = LINE_START_REGEX + '[^\t]*' + END_OF_LINE_REGEX
IGNORE_MATCHER = re.compile(IGNORE_LINE_REGEX)


class DataParticleType(BaseEnum):
    SAMPLE = 'nutnr_j_cspp_instrument'
    SAMPLE_RECOVERED = 'nutnr_j_cspp_instrument_recovered'
    METADATA = 'nutnr_j_cspp_metadata'
    METADATA_RECOVERED = 'nutnr_j_cspp_metadata_recovered'

SPECTRAL_CHANNELS = 'spectral_channels'

PARAMETER_MAP = [
    ('profiler_timestamp',             0, float),
    ('pressure_depth',                 1, float),
    ('suspect_timestamp',              2, encode_y_or_n),
    ('frame_type',                     3, str),
    ('year',                           4, int),
    ('day_of_year',                    5, int),
    ('time_of_sample',                 6, float),
    ('nitrate_concentration',          7, float),
    ('nutnr_nitrogen_in_nitrate',      8, float),
    ('nutnr_absorbance_at_254_nm',     9, float),
    ('nutnr_absorbance_at_350_nm',    10, float),
    ('nutnr_bromide_trace',           11, float),
    ('nutnr_spectrum_average',        12, int),
    ('nutnr_dark_value_used_for_fit', 13, int),
    ('nutnr_integration_time_factor', 14, int),
    (SPECTRAL_CHANNELS,               GRP_SPECTRAL_START,    list),
    ('temp_interior',                 GRP_SPECTRAL_END,      float),
    ('temp_spectrometer',             GRP_SPECTRAL_END + 1,  float),
    ('temp_lamp',                     GRP_SPECTRAL_END + 2,  float),
    ('lamp_time',                     GRP_SPECTRAL_END + 3,  int),
    ('humidity',                      GRP_SPECTRAL_END + 4,  float),
    ('voltage_main',                  GRP_SPECTRAL_END + 5,  float),
    ('voltage_lamp',                  GRP_SPECTRAL_END + 6,  float),
    ('nutnr_voltage_int',             GRP_SPECTRAL_END + 7,  float),
    ('nutnr_current_main',            GRP_SPECTRAL_END + 8,  float),
    ('aux_fitting_1',                 GRP_SPECTRAL_END + 9,  float),
    ('aux_fitting_2',                 GRP_SPECTRAL_END + 10, float),
    ('nutnr_fit_base_1',              GRP_SPECTRAL_END + 11, float),
    ('nutnr_fit_base_2',              GRP_SPECTRAL_END + 12, float),
    ('nutnr_fit_rmse',                GRP_SPECTRAL_END + 13, float),
    ('ctd_time_uint32',               GRP_SPECTRAL_END + 14, int),
    ('ctd_psu',                       GRP_SPECTRAL_END + 15, float),
    ('ctd_temp',                      GRP_SPECTRAL_END + 16, float),
    ('ctd_dbar',                      GRP_SPECTRAL_END + 17, float)]


class NutnrJCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Class for parsing metadata from the nutnr_j_cspp data set
    """
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws RecoverableSampleException If there is a problem with sample creation
        """
        try:
            # this particle only contains common metdata values
            results = self._build_metadata_parsed_values()
            
            data_match = self.raw_data[MetadataRawDataKey.DATA_MATCH]

            # split raw data match by tabs to be able to isolate profiler timestamp
            params = data_match.group(0).split('\t')

            internal_timestamp_unix = float(params[GRP_PROFILER_TIMESTAMP])
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Error %s while building parsed values from data %s", ex, self.raw_data)
            raise RecoverableSampleException("Error %s while building parsed values from data %s" %
                                             (ex, self.raw_data))
        
        return results


class NutnrJCsppMetadataTelemeteredDataParticle(NutnrJCsppMetadataDataParticle):
    """ Class for building a telemetered data sample parser """
    _data_particle_type = DataParticleType.METADATA


class NutnrJCsppMetadataRecoveredDataParticle(NutnrJCsppMetadataDataParticle):
    """ Class for building a recovered data sample parser """
    _data_particle_type = DataParticleType.METADATA_RECOVERED


class NutnrJCsppDataParticle(DataParticle):
    """
    Class for parsing data from the nutnr_j_cspp data set
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
            # split the entire matched line by tabs, which will return each parameters
            # value as an array of string
            params = self.raw_data.group(0).split('\t')
            if len(params) < NUM_FIELDS:
                log.warn('Not enough fields could be parsed from the data %s', 
                         self.raw_data.group(0))
                raise RecoverableSampleException('Not enough fields could be parsed from the data %s' %
                                                 self.raw_data.group(0))

            for name, index, encode_function in PARAMETER_MAP:
                if name == SPECTRAL_CHANNELS:
                    # spectral channels is an array of ints, need to do the extra map 
                    results.append(self._encode_value(name,
                                                      map(int, params[index:GRP_SPECTRAL_END]),
                                                      encode_function))
                else:
                    results.append(self._encode_value(name, params[index], encode_function))

            internal_timestamp_unix = float(params[GRP_PROFILER_TIMESTAMP])
            self.set_internal_timestamp(unix_time=internal_timestamp_unix)

        except (ValueError, TypeError, IndexError) as ex:
            log.warn("Error %s while building parsed values from data %s", ex, self.raw_data)
            raise RecoverableSampleException("Error %s while building parsed values from data %s" %
                                             (ex, self.raw_data))

        return results


class NutnrJCsppTelemeteredDataParticle(NutnrJCsppDataParticle):
    """ Class for building a telemetered data sample parser """
    _data_particle_type = DataParticleType.SAMPLE


class NutnrJCsppRecoveredDataParticle(NutnrJCsppDataParticle):
    """ Class for building a recovered data sample parser """
    _data_particle_type = DataParticleType.SAMPLE_RECOVERED


class NutnrJCsppParser(CsppParser):

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 exception_callback,
                 *args, **kwargs):
        """
        This the contstructor which instantiates the NutnrJCsppParser
        """
    
        # call the superclass constructor
        super(NutnrJCsppParser, self).__init__(config,
                                               state,
                                               stream_handle,
                                               state_callback,
                                               publish_callback,
                                               exception_callback,
                                               DATA_REGEX,
                                               ignore_matcher=IGNORE_MATCHER,
                                               *args, **kwargs)


