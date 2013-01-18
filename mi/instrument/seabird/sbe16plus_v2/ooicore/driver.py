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

from mi.instrument.seabird.sbe16plus_v2.driver import PACKET_CONFIG
from mi.instrument.seabird.sbe16plus_v2.driver import DataParticle
from mi.instrument.seabird.sbe16plus_v2.driver import InstrumentDriver
from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolState
from mi.instrument.seabird.sbe16plus_v2.driver import Parameter
from mi.instrument.seabird.sbe16plus_v2.driver import ProtocolEvent
from mi.instrument.seabird.sbe16plus_v2.driver import Capability
from mi.instrument.seabird.sbe16plus_v2.driver import Prompt
from mi.instrument.seabird.sbe16plus_v2.driver import SBE16Protocol

"""
import time
import datetime
import re
import string
from threading import Timer

from mi.core.common import BaseEnum
from mi.core.time import get_timestamp_delayed
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.instrument_driver import ResourceAgentEvent
from mi.core.instrument.chunker import StringChunker
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException

from mi.core.log import get_logger
log = get_logger()
"""

###############################################################################
# Module-wide values
###############################################################################

###############################################################################
# Static enumerations for this class
###############################################################################

# Device specific parameters.
# Device prompts.
# Packet config for SBE16Plus_v2 DOSTA data granules.

###############################################################################
# Seabird Electronics 16plus V2 MicroCAT w/DOSTA Driver.
###############################################################################

