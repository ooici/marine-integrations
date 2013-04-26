"""
@package mi.instrument.seabird.sbe16plus_v2.ooicore.driver
@file mi/instrument/seabird/sbe16plus_v2/ooicore/driver.py
@author David Everett 
@brief Driver class for sbe16plus V2 CTD instrument.
"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

import mi.instrument.seabird.sbe16plus_v2.driver
from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue

from mi.instrument.seabird.sbe16plus_v2.driver import SBE16InstrumentDriver

class InstrumentDriver(SBE16InstrumentDriver):
    pass

