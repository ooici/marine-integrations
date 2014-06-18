#!/usr/bin/env python

"""
@package mi.dataset.parser.adcpa_m_glider
@file marine-integrations/mi/dataset/parser/adcpa_m_glider.py
@author Jeff Roy
@brief Particle classes for the moas_gl_adcpa dataset driver
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
    # Data particle types for the  ADCPA M glider
    # PD0 format recovered data files
    ADCPA_M_GLIDER_INSTRUMENT = 'adcpa_m_glider_instrument'
    ADCPA_M_GLIDER_RECOVERED = 'adcpa_m_glider_recovered'


class AdcpaMGliderInstrumentParticle(AdcpPd0DataParticle):

    #set the data_particle_type for the DataParticle class
    #note: this must be done outside of the constructor because
    #_data_particle_type is used by the class method type(cls)
    #in the DataParticle class
    _data_particle_type = DataParticleType.ADCPA_M_GLIDER_INSTRUMENT

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        # set the file type for use by the AdcpPd0DataParticle class
        file_type = AdcpFileType.ADCPA_FILE
        # file_type must be set to a value in AdcpFileType

        super(AdcpaMGliderInstrumentParticle, self).__init__(raw_data,
                                                             port_timestamp,
                                                             internal_timestamp,
                                                             preferred_timestamp,
                                                             quality_flag,
                                                             new_sequence,
                                                             file_type)


class AdcpaMGliderRecoveredParticle(AdcpPd0DataParticle):

    #set the data_particle_type for the DataParticle class
    #note: this must be done outside of the constructor because
    #_data_particle_type is used by the class method type(cls)
    #in the DataParticle class
    _data_particle_type = DataParticleType.ADCPA_M_GLIDER_RECOVERED

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP,
                 quality_flag=DataParticleValue.OK,
                 new_sequence=None):

        # set the file type for use by the AdcpPd0DataParticle class
        file_type = AdcpFileType.ADCPA_FILE
        # file_type must be set to a value in AdcpFileType

        super(AdcpaMGliderRecoveredParticle, self).__init__(raw_data,
                                                            port_timestamp,
                                                            internal_timestamp,
                                                            preferred_timestamp,
                                                            quality_flag,
                                                            new_sequence,
                                                            file_type)

