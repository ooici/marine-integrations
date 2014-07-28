#!/usr/bin/env python

"""
@package mi.dataset.parser.dosta_abcdjm_mmp_cds
@file marine-integrations/mi/dataset/parser/dosta_abcdjm_mmp_cds.py
@author Mark Worden
@brief Parser for the DostaAbcdjmMmpCds dataset driver
Release notes:

initial release
"""

__author__ = 'Mark Worden'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger

log = get_logger()
from mi.core.common import BaseEnum
from mi.dataset.parser.mmp_cds_base import MmpCdsParserDataParticle, MmpCdsParser


class DataParticleType(BaseEnum):
    INSTRUMENT = 'dosta_abcdjm_mmp_cds_instrument'


class DostaAbcdjmMmpCdsParserDataParticleKey(BaseEnum):
    CALIBRATED_PHASE = 'calibrated_phase'
    OPTODE_TEMPERATURE = 'optode_temperature'


class DostaAbcdjmMmpCdsParserDataParticle(MmpCdsParserDataParticle):
    """
    Class for parsing data from the DostaAbcdjmMmpCds data set
    """

    _data_particle_type = DataParticleType.INSTRUMENT
    
    def _get_mmp_cds_subclass_particle_params(self, dict_data):
        """
        This method is required to be implemented by classes that extend the MmpCdsParserDataParticle class.
        This implementation returns the particle parameters specific for DostaAbcdjmMmpCds.  As noted in the
        base, it is okay to allow the following exceptions to propagate: ValueError, TypeError, IndexError, KeyError.
        @returns a list of particle params specific to DostaAbcdjmMmpCds
        """

        calibrated_phase = self._encode_value(DostaAbcdjmMmpCdsParserDataParticleKey.CALIBRATED_PHASE,
                                              dict_data['doconcs'], float)
        optode_temperature = self._encode_value(DostaAbcdjmMmpCdsParserDataParticleKey.OPTODE_TEMPERATURE,
                                                dict_data['t'], float)

        subclass_particle_params = [calibrated_phase, optode_temperature]

        return subclass_particle_params


class DostaAbcdjmMmpCdsParser(MmpCdsParser):

    """
    Class for parsing data obtain from a DOSTA sensor, series A, B, C, D, J and M, as received from a McLane Moored
    Profiler connected to the cabled docking station.
    """

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate a DostaAbcdjmMmpCdsParser object.
        @param config The configuration for this MmpCdsParser parser
        @param state The state the DostaAbcdjmMmpCdsParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the MmpCds data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        """

        # Call the superclass constructor
        super(DostaAbcdjmMmpCdsParser, self).__init__(config,
                                                      state,
                                                      stream_handle,
                                                      state_callback,
                                                      publish_callback,
                                                      *args, **kwargs)