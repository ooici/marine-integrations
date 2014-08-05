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
from mi.core.exceptions import SampleException, DatasetParserException, \
                               UnexpectedDataException, RecoverableSampleException

from mi.dataset.dataset_parser import BufferLoadingParser
from mi.dataset.parser.cspp_base import CsppParser, CsppMetadataDataParticle, \
                                        MetadataRawDataKey, \
                                        FLOAT_REGEX, INT_REGEX, \
                                        Y_OR_N_REGEX, \
                                        END_OF_LINE_REGEX, \
                                        encode_y_or_n

FLOAT_TAB_REGEX = FLOAT_REGEX + '\t'

# a regex to match the profiler timestamp, depth, and suspect timestamp
LINE_START_REGEX = FLOAT_TAB_REGEX + FLOAT_TAB_REGEX + Y_OR_N_REGEX + '\t'

NUMBER_CHANNELS = 256
NUM_FIELDS = 33 + NUMBER_CHANNELS

# can't use groups for each parameter here since this is over the 100 group limit
# use groups to match repeated regexes, split by tabs to get parameter values instead
DATA_REGEX = LINE_START_REGEX
DATA_REGEX += '[a-zA-Z]+\t' # Frame Type
DATA_REGEX += '\d+\t\d+\t' # year, day of year
DATA_REGEX += '(' + FLOAT_TAB_REGEX + '){6}' # match 6 floats separated by tabs
DATA_REGEX += '[\d\t]+' # match any number or tabs to match a series of ints separated by tabs
DATA_REGEX += '(' + FLOAT_TAB_REGEX + '){3}' # match 3 floats separated by tabs
DATA_REGEX += '(' + INT_REGEX + ')\t' # lamp time
DATA_REGEX += '(' + FLOAT_TAB_REGEX + '){10}' # match 10 floats separated by tabs
DATA_REGEX += '(\d+)\t' # ctd time
DATA_REGEX += '(' + FLOAT_TAB_REGEX + '){3}' # match 3 floats separated by tabs
DATA_REGEX += '[0-9a-fA-F]{2}' + END_OF_LINE_REGEX # checksum and line end
DATA_MATCHER = re.compile(DATA_REGEX)

# index into split string parameter values
GRP_PROFILER_TIMESTAMP = 0
GRP_DEPTH = 1
GRP_SUSPECT_TIMESTAMP = 2
GRP_FRAME_TYPE = 3
GRP_YEAR = 4
GRP_DAY_OF_YEAR = 5
GRP_TIME_OF_SAMPLE = 6
GRP_NITRATE_CONCENTRATION = 7
GRP_NITROGEN_IN_NITRATE = 8
GRP_ABSORB_254 = 9
GRP_ABSORB_350 = 10
GRP_BROMIDE = 11
GRP_SPECTRUM_AVG = 12
GRP_DARK_FIT = 13
GRP_INTEG_TIME = 14
GRP_SPECTRAL_START = 15
GRP_SPECTRAL_END = GRP_SPECTRAL_START + NUMBER_CHANNELS
GRP_TEMP_INTERIOR = GRP_SPECTRAL_END
GRP_TEMP_SPECTRO = GRP_SPECTRAL_END + 1
GRP_TEMP_LAMP = GRP_SPECTRAL_END + 2
GRP_LAMP_TIME = GRP_SPECTRAL_END + 3
GRP_HUMID = GRP_SPECTRAL_END + 4
GRP_VOLT_MAIN = GRP_SPECTRAL_END + 5
GRP_VOLT_LAMP = GRP_SPECTRAL_END + 6
GRP_VOLT_INT = GRP_SPECTRAL_END + 7
GRP_CURRENT = GRP_SPECTRAL_END + 8
GRP_AUX_FIT_1 = GRP_SPECTRAL_END + 9
GRP_AUX_FIT_2 = GRP_SPECTRAL_END + 10
GRP_FIT_BASE_1 = GRP_SPECTRAL_END + 11
GRP_FIT_BASE_2 = GRP_SPECTRAL_END + 12
GRP_FIT_RMSE = GRP_SPECTRAL_END + 13
GRP_CTD_TIME = GRP_SPECTRAL_END + 14
GRP_CTD_PSU = GRP_SPECTRAL_END + 15
GRP_CTD_TEMP = GRP_SPECTRAL_END + 16
GRP_CTD_DBAR = GRP_SPECTRAL_END + 17

# ignore lines matching the start (timestamp, depth, suspect timestamp),
# then any text not containing tabs
IGNORE_LINE_REGEX = LINE_START_REGEX + '[^\t]*' + END_OF_LINE_REGEX
IGNORE_MATCHER = re.compile(IGNORE_LINE_REGEX)

class DataParticleType(BaseEnum):
    SAMPLE = 'nutnr_j_cspp_instrument'
    SAMPLE_RECOVERED = 'nutnr_j_cspp_instrument_recovered'
    METADATA = 'nutnr_j_cspp_metadata'
    METADATA_RECOVERED = 'nutnr_j_cspp_metadata_recovered'

class NutnrJCsppDataParticleKey(BaseEnum):
    PROFILER_TIMESTAMP = 'profiler_timestamp'
    PRESSURE_DEPTH = 'pressure_depth'
    SUSPECT_TIMESTAMP = 'suspect_timestamp'
    FRAME_TYPE = 'frame_type'
    YEAR = 'year'
    DAY_OF_YEAR = 'day_of_year'
    TIME_OF_SAMPLE = 'time_of_sample'
    NITRATE_CONCENTRATION = 'nitrate_concentration'
    NUTNR_NITROGEN_IN_NITRATE = 'nutnr_nitrogen_in_nitrate'
    NUTNR_ABSORBANCE_AT_254_NM = 'nutnr_absorbance_at_254_nm'
    NUTNR_ABSORBANCE_AT_350_NM = 'nutnr_absorbance_at_350_nm'
    NUTNR_BROMIDE_TRACE = 'nutnr_bromide_trace'
    NUTNR_SPECTRUM_AVERAGE = 'nutnr_spectrum_average'
    NUTNR_DARK_VALUE_USED_FOR_FIT = 'nutnr_dark_value_used_for_fit'
    NUTNR_INTEGRATION_TIME_FACTOR = 'nutnr_integration_time_factor'
    SPECTRAL_CHANNELS = 'spectral_channels'
    TEMP_INTERIOR = 'temp_interior'
    TEMP_SPECTROMETER = 'temp_spectrometer'
    TEMP_LAMP = 'temp_lamp'
    LAMP_TIME = 'lamp_time'
    HUMIDITY = 'humidity'
    VOLTAGE_MAIN = 'voltage_main'
    VOLTAGE_LAMP = 'voltage_lamp'
    NUTNR_VOLTAGE_INT = 'nutnr_voltage_int'
    NUTNR_CURRENT_MAIN = 'nutnr_current_main'
    AUX_FITTING_1 = 'aux_fitting_1'
    AUX_FITTING_2 = 'aux_fitting_2'
    NUTNR_FIT_BASE_1 = 'nutnr_fit_base_1'
    NUTNR_FIT_BASE_2 = 'nutnr_fit_base_2'
    NUTNR_FIT_RMSE = 'nutnr_fit_rmse'
    CTD_TIME_UINT32 = 'ctd_time_uint32'
    CTD_PSU = 'ctd_psu'
    CTD_TEMP = 'ctd_temp'
    CTD_DBAR = 'ctd_dbar'


class NutnrJCsppMetadataDataParticle(CsppMetadataDataParticle):
    """
    Class for parsing metadata from the nutnr_j_cspp data set
    """
    def _build_parsed_values(self):
        """
        Take something in the data format and turn it into
        an array of dictionaries defining the data in the particle
        with the appropriate tag.
        @throws SampleException If there is a problem with sample creation
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
        @throws SampleException If there is a problem with sample creation
        """        
        try:
            # split the entire matched line by tabs, which will return each parameters
            # value as an array of string
            params = self.raw_data.group(0).split('\t')
            if len(params) < NUM_FIELDS:
                log.warn('Not enough fields could be parsed from the data %s', 
                         self.raw_data.group(0))
                raise RecoverableSampleException('Not enough fields could be parsed from the data %s' %
                                                 self.raw_data.group(0))
            results = [self._encode_value(NutnrJCsppDataParticleKey.PROFILER_TIMESTAMP,
                                          params[GRP_PROFILER_TIMESTAMP], float),
                       self._encode_value(NutnrJCsppDataParticleKey.PRESSURE_DEPTH,
                                          params[GRP_DEPTH], float),
                       self._encode_value(NutnrJCsppDataParticleKey.SUSPECT_TIMESTAMP,
                                          params[GRP_SUSPECT_TIMESTAMP], encode_y_or_n),
                       self._encode_value(NutnrJCsppDataParticleKey.FRAME_TYPE,
                                          params[GRP_FRAME_TYPE], str),
                       self._encode_value(NutnrJCsppDataParticleKey.YEAR,
                                          params[GRP_YEAR], int),
                       self._encode_value(NutnrJCsppDataParticleKey.DAY_OF_YEAR,
                                          params[GRP_DAY_OF_YEAR], int),
                       self._encode_value(NutnrJCsppDataParticleKey.TIME_OF_SAMPLE,
                                          params[GRP_TIME_OF_SAMPLE], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NITRATE_CONCENTRATION,
                                          params[GRP_NITRATE_CONCENTRATION], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_NITROGEN_IN_NITRATE,
                                          params[GRP_NITROGEN_IN_NITRATE], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_ABSORBANCE_AT_254_NM,
                                          params[GRP_ABSORB_254], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_ABSORBANCE_AT_350_NM,
                                          params[GRP_ABSORB_350], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_BROMIDE_TRACE,
                                          params[GRP_BROMIDE], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_SPECTRUM_AVERAGE,
                                          params[GRP_SPECTRUM_AVG], int),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_DARK_VALUE_USED_FOR_FIT,
                                          params[GRP_DARK_FIT], int),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_INTEGRATION_TIME_FACTOR,
                                          params[GRP_INTEG_TIME], int),
                       # transform the array of strings into an array of ints
                       self._encode_value(NutnrJCsppDataParticleKey.SPECTRAL_CHANNELS,
                                          map(int, params[GRP_SPECTRAL_START:GRP_SPECTRAL_START + NUMBER_CHANNELS]),
                                          list),
                       self._encode_value(NutnrJCsppDataParticleKey.TEMP_INTERIOR,
                                          params[GRP_TEMP_INTERIOR], float),
                       self._encode_value(NutnrJCsppDataParticleKey.TEMP_SPECTROMETER,
                                          params[GRP_TEMP_SPECTRO], float),
                       self._encode_value(NutnrJCsppDataParticleKey.TEMP_LAMP,
                                          params[GRP_TEMP_LAMP], float),
                       self._encode_value(NutnrJCsppDataParticleKey.LAMP_TIME,
                                          params[GRP_LAMP_TIME], float),
                       self._encode_value(NutnrJCsppDataParticleKey.HUMIDITY,
                                          params[GRP_HUMID], float),
                       self._encode_value(NutnrJCsppDataParticleKey.VOLTAGE_MAIN,
                                          params[GRP_VOLT_MAIN], float),
                       self._encode_value(NutnrJCsppDataParticleKey.VOLTAGE_LAMP,
                                          params[GRP_VOLT_LAMP], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_VOLTAGE_INT,
                                          params[GRP_VOLT_INT], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_CURRENT_MAIN,
                                          params[GRP_CURRENT], float),
                       self._encode_value(NutnrJCsppDataParticleKey.AUX_FITTING_1,
                                          params[GRP_AUX_FIT_1], float),
                       self._encode_value(NutnrJCsppDataParticleKey.AUX_FITTING_2,
                                          params[GRP_AUX_FIT_2], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_FIT_BASE_1,
                                          params[GRP_FIT_BASE_1], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_FIT_BASE_2,
                                          params[GRP_FIT_BASE_2], float),
                       self._encode_value(NutnrJCsppDataParticleKey.NUTNR_FIT_RMSE,
                                          params[GRP_FIT_RMSE], float),
                       self._encode_value(NutnrJCsppDataParticleKey.CTD_TIME_UINT32,
                                          params[GRP_CTD_TIME], int),
                       self._encode_value(NutnrJCsppDataParticleKey.CTD_PSU,
                                          params[GRP_CTD_PSU], float),
                       self._encode_value(NutnrJCsppDataParticleKey.CTD_TEMP,
                                          params[GRP_CTD_TEMP], float),
                       self._encode_value(NutnrJCsppDataParticleKey.CTD_DBAR,
                                          params[GRP_CTD_DBAR], float)]

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

