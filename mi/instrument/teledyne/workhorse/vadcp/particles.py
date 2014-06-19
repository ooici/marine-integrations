"""
@package mi.instrument.teledyne.workhorse.vadcp.particles
@file marine-integrations/mi/instrument/teledyne/workhorse/vadcp/driver.py
@author Sung Ahn
@brief Driver particle code for the teledyne workhorse adcp
Release notes:
"""

__author__ = 'Sung Ahn'
__license__ = 'Apache 2.0'

from mi.core.log import get_logger
log = get_logger()

from mi.instrument.teledyne.particles import DataParticleType


###############################################################################
# Data Particles
###############################################################################
class VADCPDataParticleType(DataParticleType):
    """
    VADCP Stream types of data particles
    """

    VADCP_4BEAM_SYSTEM_CONFIGURATION = "vadcp_4beam_system_configuration"
    VADCP_5THBEAM_SYSTEM_CONFIGURATION = "vadcp_5thbeam_system_configuration"

    VADCP_ANCILLARY_SYSTEM_DATA = "vadcp_ancillary_system_data"
    VADCP_TRANSMIT_PATH = "vadcp_transmit_path"

    VADCP_PD0_PARSED_BEAM = 'vadcp_5thbeam_pd0_beam_parsed'
    VADCP_PD0_PARSED_EARTH = 'vadcp_5thbeam_pd0_earth_parsed'
    VADCP_COMPASS_CALIBRATION = 'vadcp_5thbeam_compass_calibration'
