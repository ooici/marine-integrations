#!/usr/bin/env python

"""
@package mi.dataset.parser.adcps_jln
@file marine-integrations/mi/dataset/parser/adcps_jln.py
@author Jeff Roy
@brief Particle classes for the adcps_jln dataset driver
These particles are parsed by the common PD0 Parser and
Abstract particle class in file adcp_pd0.py
Release notes:

initial release
"""

__author__ = 'Jeff Roy'
__license__ = 'Apache 2.0'

from mi.core.common import BaseEnum
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue

from mi.dataset.parser.adcp_pd0 import AdcpFileType, AdcpPd0DataParticle


class DataParticleType(BaseEnum):
    # Data particle types for the  ADCPS JLN
    # PD0 format recovered data files
    ADCPS_JLN_INSTRUMENT = 'adcps_jln_instrument'


class AdcpsJlnParticle(AdcpPd0DataParticle):

    #set the data_particle_type for the DataParticle class
    #note: this must be done outside of the constructor because
    #_data_particle_type is used by the class method type(cls)
    #in the DataParticle class
    _data_particle_type = DataParticleType.ADCPS_JLN_INSTRUMENT

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        # set the file type for use by the AdcpPd0DataParticle class
        file_type = AdcpFileType.ADCPS_File
        # file_type must be set to a value in AdcpFileType

        super(AdcpsJlnParticle, self).__init__(raw_data,
                                               port_timestamp,
                                               internal_timestamp,
                                               preferred_timestamp,
                                               quality_flag,
                                               new_sequence,
                                               file_type)
