#!/usr/bin/env python

"""
@package mi.dataset.parser.flntu_x_mmp_cds
@file marine-integrations/mi/dataset/parser/flntu_x_mmp_cds.py
@author Jeremy Amundson
@brief Parser for the FlntuXMmpCds dataset driver
Release notes:

initial release
"""

__author__ = 'Jeremy Amundson'
__license__ = 'Apache 2.0'


from mi.core.log import get_logger

log = get_logger()
from mi.core.common import BaseEnum
from mi.dataset.parser.mmp_cds_base import MmpCdsParserDataParticle, MmpCdsParser
from mi.dataset.dataset_driver import DataSetDriverConfigKeys


class DataParticleType(BaseEnum):
    INSTRUMENT = 'flntu_x_mmp_cds_instrument'


class FlntuXMmpCdsParserDataParticleKey(BaseEnum):

    CHLAFLO = 'chlaflo'
    NTUFLO = 'ntuflo'


class FlntuXMmpCdsParserDataParticle(MmpCdsParserDataParticle):
    """
    Class for parsing data from the FlntuXMmpCds data set
    """

    _data_particle_type = DataParticleType.INSTRUMENT

    def _get_mmp_cds_subclass_particle_params(self, dict_data):
        """
        This method is required to be implemented by classes that extend the MmpCdsParserDataParticle class.
        This implementation returns the particle parameters specific for FlntuXMmpCds.
        @returns a list of particle params specific to FlntuXMmpCds
        """

        chlorophyll = self._encode_value(FlntuXMmpCdsParserDataParticleKey.CHLAFLO,
                                         dict_data[FlntuXMmpCdsParserDataParticleKey.CHLAFLO], int)

        ntuflo = self._encode_value(FlntuXMmpCdsParserDataParticleKey.NTUFLO,
                                    dict_data[FlntuXMmpCdsParserDataParticleKey.NTUFLO], int)

        return [chlorophyll, ntuflo]


class FlntuXMmpCdsParser(MmpCdsParser):
    """
    Class for parsing data obtain from a FLNTU-C/K/L instrument as received from a McLane Moored Profiler connected
    to a cabled docking station.
    """

    def __init__(self,
                 config,
                 state,
                 stream_handle,
                 state_callback,
                 publish_callback,
                 *args, **kwargs):
        """
        This method is a constructor that will instantiate a FlntuXMmpCdsParser object.
        @param config The configuration for this MmpCdsParser parser
        @param state The state the FlntuXMmpCdsParser should use to initialize itself
        @param stream_handle The handle to the data stream containing the MmpCds data
        @param state_callback The function to call upon detecting state changes
        @param publish_callback The function to call to provide particles
        """

        # Call the superclass constructor
        super(FlntuXMmpCdsParser, self).__init__(config,
                                                   state,
                                                   stream_handle,
                                                   state_callback,
                                                   publish_callback,
                                                   *args, **kwargs)