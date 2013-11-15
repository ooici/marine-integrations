#!/usr/bin/env python

"""
@package mi.dataset.parser.ctdpf SBE52 data set agent information
@file mi/dataset/parser/ctdpf.py
@author Roger Unwin
@brief A CTDPF-specific data set agent package
This module should contain classes that handle parsers used with CTDPF dataset
files. It initially holds SBE52-specific logic, ultimately more than that.
"""
__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import copy
import re
import time
import ntplib
from dateutil import parser
from functools import partial

from mi.core.log import get_logger ; log = get_logger()

from mi.core.common import BaseEnum
from mi.core.exceptions import SampleException, DatasetParserException
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticle, DataParticleKey
from mi.dataset.dataset_parser import BufferLoadingParser


class DataParticleType(BaseEnum):
    # Data particle types for the Wire Following Profiler E output files.
    WFP_PARADK = 'wfp_e_file_parad_k'
    WFP_FLORTK = 'wfp_e_file_flort_k'


class wfp_E_particle(DataParticle):


    def _parsed_values(self, key_list):
        log.debug("Build a particle with keys: %s", key_list)
        if not isinstance(self.raw_data, dict):
            raise SampleException(
                "%s: Object Instance is not a Glider Parsed Data \
                dictionary" % self._data_particle_type)

        result = []

        # find if any of the variables from the particle key list are in
        # the data_dict and keep it
        for key in key_list:
            if key in self.raw_data:
                # read the value from the gpd dictionary
                value = self.raw_data[key]['Data']

                # check to see that the value is not a 'NaN'
                if np.isnan(value):
                    log.trace("NaN Value: %s", key)
                    value = None

                # add the value to the record
                result.append({DataParticleKey.VALUE_ID: key,
                               DataParticleKey.VALUE: value})
                log.trace("Key: %s, value: %s", key, value)

            else:
                #log.warn("The particle defined in the" +
                #         "ParticleKey, %s, is not present in the current" % key +
                #         "data set. Confirm by checking the m, s, or tbdlist of " +
                #         "the glider to insure this is expected, or check the " +
                #         "standard lists and/or Particle Keys")
                SampleException("%s column missing from datafile, row ignored", key)

        return result


class WfpEParticleKey(BaseEnum):
    """
    Common glider particle parameters
    """
    DATE_STRING = 'date_string'
    TIME_STRING = 'time_string'

    @classmethod
    def science_parameter_list(cls):
        """
        Get a list of all science parameters
        """
        result = []
        for key in cls.list():
            if key not in WfpEParticleKey.list():
                result.append(key)

        return result


class WfpParadkDataParticleKey(WfpEParticleKey):
    PAR = 'photosynthetically_active_radiation'


class WfpParadkDataParticle(wfp_E_particle):
    _data_particle_type = DataParticleType.WFP_PARADK

    def _build_parsed_values(self):
        """
        Extracts CTDGV data from the glider data dictionary intiallized with
        the particle class and puts the data into a CTDGV Data Particle.

        @param result A returned list with sub dictionaries of the data
        """
        return self._parsed_values(WfpParadkDataParticleKey.list())


class EngineeringParticleKey(BaseEnum):
    CURRENT = 'current'
    VOLTAGE = 'voltage'
    PRESURE = 'pressure_dbar'


class WfpFlortkDataParticleKey(WfpEParticleKey):
    CDOM = 'colored_dissolved_organic_matter_concentration'
    CHL = 'fluorometric_chlorophyll_a_concentration'
    SCAT_SIG = 'total_volume_scattering_coefficient'


class WfpFlortkDataParticle(wfp_E_particle):
    _data_particle_type = DataParticleType.WFP_FLORTK

    def _build_parsed_values(self):
        """
        Extracts CTDGV data from the glider data dictionary intiallized with
        the particle class and puts the data into a CTDGV Data Particle.

        @param result A returned list with sub dictionaries of the data
        """
        return self._parsed_values(WfpFlortkDataParticleKey.list())







