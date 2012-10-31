"""
@package mi.instrument.seabird.sbe26plus.test.test_driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q

   * From pyon
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a UNIT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a INT
       $ bin/nosetests -s -v /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore -a QUAL


    @TODO negative testing with bogus values to detect failures.
    @TODO would be nice to modify driver to test paramater allowable range and throw exception on out of range.

"""






__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import time
import socket
import re
import numpy

import unittest
from mock import patch
from pyon.core.bootstrap import CFG

from nose.plugins.attrib import attr

from mi.core.log import get_logger ; log = get_logger()

# MI imports.
from mi.idk.unit_test import InstrumentDriverTestCase
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase

from interface.objects import AgentCommand
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes

from mi.core.instrument.instrument_driver import DriverState

from mi.instrument.seabird.sbe26plus.driver import PACKET_CONFIG
from mi.instrument.seabird.sbe26plus.driver import DataParticle
from mi.instrument.seabird.sbe26plus.driver import InstrumentDriver
from mi.instrument.seabird.sbe26plus.driver import ProtocolState
from mi.instrument.seabird.sbe26plus.driver import Parameter
from mi.instrument.seabird.sbe26plus.driver import ProtocolEvent
from mi.instrument.seabird.sbe26plus.driver import Capability
from mi.instrument.seabird.sbe26plus.driver import Prompt
from mi.instrument.seabird.sbe26plus.driver import Protocol
from mi.instrument.seabird.sbe26plus.driver import SBE26plusTideSampleDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusWaveBurstDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusStatisticsDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusTakeSampleDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceCalibrationDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceStatusDataParticle

from mi.instrument.seabird.sbe26plus.driver import InstrumentCmds
from mi.instrument.seabird.sbe26plus.driver import NEWLINE

from mi.core.instrument.instrument_driver import DriverConnectionState

from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentCommandException


from prototype.sci_data.stream_parser import PointSupplementStreamParser
from prototype.sci_data.constructor_apis import PointSupplementConstructor
from prototype.sci_data.stream_defs import ctd_stream_definition
#from prototype.sci_data.stream_defs import SBE37_CDM_stream_definition



from prototype.sci_data.stream_parser import PointSupplementStreamParser

from pyon.agent.agent import ResourceAgentClient
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from pyon.core.exception import BadRequest
from pyon.core.exception import Conflict
from pyon.agent.instrument_fsm import FSMStateError

from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverConnectionState
from mi.core.instrument.instrument_driver import DriverProtocolState

from mock import Mock
from mi.core.instrument.logger_client import LoggerClient
from mi.core.instrument.port_agent_client import PortAgentClient, PortAgentPacket
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue


# Globals
raw_stream_received = False
parsed_stream_received = False



###
#   Driver parameters for the tests
###

# 'will echo' command sequence to be sent from DA telnet server
# see RFCs 854 & 857
WILL_ECHO_CMD = '\xff\xfd\x03\xff\xfb\x03\xff\xfb\x01'
# 'do echo' command sequence to be sent back from telnet client
DO_ECHO_CMD   = '\xff\xfb\x03\xff\xfd\x03\xff\xfd\x01'

PARAMS = {
    # DS # parameters - contains all setsampling parameters
    Parameter.DEVICE_VERSION : str,
    Parameter.SERIAL_NUMBER : str,
    Parameter.DS_DEVICE_DATE_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python


    Parameter.USER_INFO : str,
    Parameter.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER : float,
    Parameter.QUARTZ_PRESSURE_SENSOR_RANGE : float,

    Parameter.EXTERNAL_TEMPERATURE_SENSOR : bool,

    Parameter.CONDUCTIVITY : bool,

    Parameter.IOP_MA : float,
    Parameter.VMAIN_V : float,
    Parameter.VLITH_V : float,

    Parameter.LAST_SAMPLE_P : float,
    Parameter.LAST_SAMPLE_T : float,
    Parameter.LAST_SAMPLE_S : float,

    Parameter.TIDE_INTERVAL : int,
    Parameter.TIDE_MEASUREMENT_DURATION : int,

    Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : float,

    Parameter.WAVE_SAMPLES_PER_BURST : int,
    Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float,

    Parameter.USE_START_TIME : bool,
    #Parameter.START_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python
    Parameter.USE_STOP_TIME : bool,
    #Parameter.STOP_TIME : str, # long, # ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python

    Parameter.TIDE_SAMPLES_PER_DAY : float,
    Parameter.WAVE_BURSTS_PER_DAY : float,
    Parameter.MEMORY_ENDURANCE : float,
    Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE : float,
    Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS : float,
    Parameter.TOTAL_RECORDED_WAVE_BURSTS : float,
    Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START : float,
    Parameter.WAVE_BURSTS_SINCE_LAST_START : float,
    Parameter.TXREALTIME : bool,
    Parameter.TXWAVEBURST : bool,
    Parameter.TXWAVESTATS : bool,
    Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : int,
    Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : bool,
    Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC : bool,
    Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR : float,
    Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR : float,
    Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM : float,
    Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : int,
    Parameter.MIN_ALLOWABLE_ATTENUATION : float,
    Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : float,
    Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : float,
    Parameter.HANNING_WINDOW_CUTOFF : float,
    Parameter.SHOW_PROGRESS_MESSAGES : bool,
    Parameter.STATUS : str,
    Parameter.LOGGING : bool,

    # DC # parameters verified to match 1:1 to DC output
    #Parameter.PCALDATE : tuple,
    #Parameter.PU0 : float,
    #Parameter.PY1 : float,
    #Parameter.PY2 : float,
    #Parameter.PY3 : float,
    #Parameter.PC1 : float,
    #Parameter.PC2 : float,
    #Parameter.PC3 : float,
    #Parameter.PD1 : float,
    #Parameter.PD2 : float,
    #Parameter.PT1 : float,
    #Parameter.PT2 : float,
    #Parameter.PT3 : float,
    #Parameter.PT4 : float,
    #Parameter.FACTORY_M : float,
    #Parameter.FACTORY_B : float,
    #Parameter.POFFSET : float,
    #Parameter.TCALDATE : tuple,
    #Parameter.TA0 : float,
    #Parameter.TA1 : float,
    #Parameter.TA2 : float,
    #Parameter.TA3 : float,

    #Parameter.CCALDATE : tuple,
    #Parameter.CG : float,
    #Parameter.CH : float,
    #Parameter.CI : float,
    #Parameter.CJ : float,
    #Parameter.CTCOR : float,
    #Parameter.CPCOR : float,
    #Parameter.CSLOPE : float,

    # End of DC
}
#################################### RULES ####################################
#                                                                             #
# Common capabilities in the base class                                       #
#                                                                             #
# Instrument specific stuff in the derived class                              #
#                                                                             #
# Generator spits out either stubs or comments describing test this here,     #
# test that there.                                                            #
#                                                                             #
# Qualification tests are driven through the instrument_agent                 #
#                                                                             #
###############################################################################

SAMPLE_DS = \
        "SBE 26plus" + NEWLINE +\
        "S>ds" + NEWLINE +\
        "ds" + NEWLINE +\
        "SBE 26plus V 6.1e  SN 1329    05 Oct 2012  17:19:27" + NEWLINE +\
        "user info=ooi" + NEWLINE +\
        "quartz pressure sensor: serial number = 122094, range = 300 psia" + NEWLINE +\
        "internal temperature sensor" + NEWLINE +\
        "conductivity = NO" + NEWLINE +\
        "iop =  7.4 ma  vmain = 16.2 V  vlith =  9.0 V" + NEWLINE +\
        "last sample: p = 14.5361, t = 23.8155" + NEWLINE +\
        "" + NEWLINE +\
        "tide measurement: interval = 3.000 minutes, duration = 60 seconds" + NEWLINE +\
        "measure waves every 6 tide samples" + NEWLINE +\
        "512 wave samples/burst at 4.00 scans/sec, duration = 128 seconds" + NEWLINE +\
        "logging start time = do not use start time" + NEWLINE +\
        "logging stop time = do not use stop time" + NEWLINE +\
        "" + NEWLINE +\
        "tide samples/day = 480.000" + NEWLINE +\
        "wave bursts/day = 80.000" + NEWLINE +\
        "memory endurance = 258.0 days" + NEWLINE +\
        "nominal alkaline battery endurance = 272.8 days" + NEWLINE +\
        "total recorded tide measurements = 5982" + NEWLINE +\
        "total recorded wave bursts = 4525" + NEWLINE +\
        "tide measurements since last start = 11" + NEWLINE +\
        "wave bursts since last start = 1" + NEWLINE +\
        "" + NEWLINE +\
        "transmit real-time tide data = YES" + NEWLINE +\
        "transmit real-time wave burst data = YES" + NEWLINE +\
        "transmit real-time wave statistics = YES" + NEWLINE +\
        "real-time wave statistics settings:" + NEWLINE +\
        "  number of wave samples per burst to use for wave statistics = 512" + NEWLINE +\
        "  use measured temperature for density calculation" + NEWLINE +\
        "  height of pressure sensor from bottom (meters) = 10.0" + NEWLINE +\
        "  number of spectral estimates for each frequency band = 5" + NEWLINE +\
        "  minimum allowable attenuation = 0.0025" + NEWLINE +\
        "  minimum period (seconds) to use in auto-spectrum = 0.0e+00" + NEWLINE +\
        "  maximum period (seconds) to use in auto-spectrum = 1.0e+06" + NEWLINE +\
        "  hanning window cutoff = 0.10" + NEWLINE +\
        "  show progress messages" + NEWLINE +\
        "" + NEWLINE +\
        "status = stopped by user" + NEWLINE +\
        "logging = NO, send start command to begin logging" + NEWLINE +\
        "S>" + NEWLINE

SAMPLE_DC = \
        "S>dc" + NEWLINE +\
        "dc" + NEWLINE +\
        "Pressure coefficients:  02-apr-12" + NEWLINE +\
        "    U0 = 5.827424e+00" + NEWLINE +\
        "    Y1 = -3.845795e+03" + NEWLINE +\
        "    Y2 = -1.082941e+04" + NEWLINE +\
        "    Y3 = 0.000000e+00" + NEWLINE +\
        "    C1 = 2.123771e+03" + NEWLINE +\
        "    C2 = 3.741653e+01" + NEWLINE +\
        "    C3 = -4.014654e+03" + NEWLINE +\
        "    D1 = 2.529400e-02" + NEWLINE +\
        "    D2 = 0.000000e+00" + NEWLINE +\
        "    T1 = 2.777282e+01" + NEWLINE +\
        "    T2 = 3.911380e-01" + NEWLINE +\
        "    T3 = 1.752851e+01" + NEWLINE +\
        "    T4 = 3.109619e+01" + NEWLINE +\
        "    M = 41943.0" + NEWLINE +\
        "    B = 2796.2" + NEWLINE +\
        "    OFFSET = -1.877000e-01" + NEWLINE +\
        "Temperature coefficients:  30-mar-12" + NEWLINE +\
        "    TA0 = 2.557341e-04" + NEWLINE +\
        "    TA1 = 2.493547e-04" + NEWLINE +\
        "    TA2 = -1.567218e-06" + NEWLINE +\
        "    TA3 = 1.508124e-07" + NEWLINE +\
        "S>"

SAMPLE_DATA =\
        "S>start" + NEWLINE +\
        "start" + NEWLINE +\
        "logging will start in 10 seconds" + NEWLINE +\
        "tide: start time = 05 Oct 2012 00:55:54, p = 14.5348, pt = 24.250, t = 23.9046" + NEWLINE +\
        "tide: start time = 05 Oct 2012 00:58:54, p = 14.5367, pt = 24.242, t = 23.8904" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:01:54, p = 14.5387, pt = 24.250, t = 23.8778" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:04:54, p = 14.5346, pt = 24.228, t = 23.8664" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:07:54, p = 14.5364, pt = 24.205, t = 23.8575" + NEWLINE +\
        "wave: start time = 05 Oct 2012 01:10:54" + NEWLINE +\
        "wave: ptfreq = 171791.359" + NEWLINE +\
        "  14.5102" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5078" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5078" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5188" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5097" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "wave: end burst" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:10:54, p = 14.5385, pt = 24.228, t = 23.8404" + NEWLINE +\
        "" + NEWLINE +\
        "deMeanTrend................" + NEWLINE +\
        "depth =    0.000, temperature = 23.840, salinity = 35.000, density = 1023.690" + NEWLINE +\
        "" + NEWLINE +\
        "fill array..." + NEWLINE +\
        "find minIndex." + NEWLINE +\
        "hanning...................." + NEWLINE +\
        "FFT................................................................................................" + NEWLINE +\
        "normalize....." + NEWLINE +\
        "band average......................................................." + NEWLINE +\
        "Auto-Spectrum Statistics:" + NEWLINE +\
        "   nAvgBand = 5" + NEWLINE +\
        "   total variance = 1.0896e-05" + NEWLINE +\
        "   total energy = 1.0939e-01" + NEWLINE +\
        "   significant period = 5.3782e-01" + NEWLINE +\
        "   significant wave height = 1.3204e-02" + NEWLINE +\
        "" + NEWLINE +\
        "calculate dispersion.................................................................................................................................................................................................................................................................................." + NEWLINE +\
        "IFFT................................................................................................" + NEWLINE +\
        "deHanning...................." + NEWLINE +\
        "move data.." + NEWLINE +\
        "zero crossing analysis............." + NEWLINE +\
        "Time Series Statistics:" + NEWLINE +\
        "   wave integration time = 128" + NEWLINE +\
        "   number of waves = 0" + NEWLINE +\
        "   total variance = 1.1595e-05" + NEWLINE +\
        "   total energy = 1.1640e-01" + NEWLINE +\
        "   average wave height = 0.0000e+00" + NEWLINE +\
        "   average wave period = 0.0000e+00" + NEWLINE +\
        "   maximum wave height = 1.0893e-02" + NEWLINE +\
        "   significant wave height = 0.0000e+00" + NEWLINE +\
        "   significant wave period = 0.0000e+00" + NEWLINE +\
        "   H1/10 = 0.0000e+00" + NEWLINE +\
        "   H1/100 = 0.0000e+00" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:13:54, p = 14.5384, pt = 24.205, t = 23.8363" + NEWLINE



BAD_SAMPLE_DATA =\
        "S>start" + NEWLINE +\
        "start" + NEWLINE +\
        "logging will start in 10 seconds" + NEWLINE +\
        "tide: start time = 05 Oct 2012 00:55:54, p = 14.5348, pt = 24.250, t = 23.9046" + NEWLINE +\
        "tide: start time = 05 Oct 2012 00:58:54, p = 14.5367,NERD HERDER  pt = 24.242, t = 23.8904" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:01:54, p = 14.5387, pt = 24.250, t = 23.8778" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:04:54, p = 14.5346, pt = 24.228, t = 23.8664" + NEWLINE +\
        "tide: start time = NERD HERDER05 Oct 2012 01:07:54, p = 14.5364, pt = 24.205, t = 23.8575" + NEWLINE +\
        "wave: start time = 05 Oct 2012 01:10:54" + NEWLINE +\
        "wave: ptfNERD HERDERreq = 171791.359" + NEWLINE +\
        "  14.5FR2" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5078" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5078" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5188" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5097" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5036" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5134" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "  14.5064" + NEWLINE +\
        "  14.5165" + NEWLINE +\
        "wave: end burst" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:10:54, p = 14.5385, pt = 24.228, t = 23.8404" + NEWLINE +\
        "" + NEWLINE +\
        "deMeanTrend................" + NEWLINE +\
        "depth =    0.000, temperature = 23.840, salinity = 35.000, density = 1023.690" + NEWLINE +\
        "" + NEWLINE +\
        "fill array..." + NEWLINE +\
        "find minIndex." + NEWLINE +\
        "hanning...................." + NEWLINE +\
        "FFT................................................................................................" + NEWLINE +\
        "normalize....." + NEWLINE +\
        "band average......................................................." + NEWLINE +\
        "Auto-Spectrum Statistics:" + NEWLINE +\
        "   nAvgBand = 5" + NEWLINE +\
        "   total variance = 1.0896e-05" + NEWLINE +\
        "   total energy = 1.0939e-01" + NEWLINE +\
        "   significant period = 5.3782e-01" + NEWLINE +\
        "   significant wave height = 1.3204e-02" + NEWLINE +\
        "" + NEWLINE +\
        "calculate dispersion.....................NERD HERDER............................................................................................................................................................................................................................................................." + NEWLINE +\
        "IFFT.......................................................NERD HERDER........................................." + NEWLINE +\
        "deHanning...................." + NEWLINE +\
        "move data.." + NEWLINE +\
        "zero crossing analysis....NERD HERDER........." + NEWLINE +\
        "Time Series Statistics:" + NEWLINE +\
        "   wave integration time = 128" + NEWLINE +\
        "   number of waves = 0" + NEWLINE +\
        "   total NERD HERDERvariance = 1.1595e-05" + NEWLINE +\
        "   total energy = 1.1640e-01" + NEWLINE +\
        "   average wave height = 0.0000e+00" + NEWLINE +\
        "   average wave period = 0.0000e+00" + NEWLINE +\
        "   maximum NERD HERDERwave height = 1.0893e-02" + NEWLINE +\
        "   significant wave height = 0.0000e+00" + NEWLINE +\
        "   significant NERD HERDERwave period = 0.0000e+00" + NEWLINE +\
        "   H1/10 = 0.0000e+00" + NEWLINE +\
        "   H1/100 = 0.0000e+00" + NEWLINE +\
        "tide: start time = 05 Oct 2012 01:13:54, p = 14.5384, pt = 24.205, t = 23.8363" + NEWLINE

class TcpClient():
    # for direct access testing
    buf = ""

    def __init__(self, host, port):
        self.buf = ""
        self.host = host
        self.port = port
        # log.debug("OPEN SOCKET HOST = " + str(host) + " PORT = " + str(port))
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.host, self.port))
        self.s.settimeout(0.0)

    def read_a_char(self):
        temp = self.s.recv(1024)
        if len(temp) > 0:
            log.debug("read_a_char got '" + str(repr(temp)) + "'")
            self.buf += temp
        if len(self.buf) > 0:
            c = self.buf[0:1]
            self.buf = self.buf[1:]
        else:
            c = None
        return c

    def peek_at_buffer(self):
        if len(self.buf) == 0:
            try:
                self.buf = self.s.recv(1024)
                log.debug("RAW READ GOT '" + str(repr(self.buf)) + "'")
            except:
                """
                Ignore this exception, its harmless
                """
        return self.buf

    def remove_from_buffer(self, remove):
        log.debug("BUF WAS " + str(repr(self.buf)))
        self.buf = self.buf.replace(remove, "")
        log.debug("BUF IS '" + str(repr(self.buf)) + "'")

    def get_data(self):
        data = ""
        try:
            ret = ""

            while True:
                c = self.read_a_char()
                if c == None:
                    break
                if c == '\n' or c == '':
                    ret += c
                    break
                else:
                    ret += c

            data = ret
        except AttributeError:
            log.debug("CLOSING - GOT AN ATTRIBUTE ERROR")
            self.s.close()
        except:
            data = ""

        if data:
            data = data.lower()
            log.debug("IN  [" + repr(data) + "]")
        return data

    def send_data(self, data, debug):
        try:
            log.debug("OUT [" + repr(data) + "]")
            self.s.sendall(data)
        except:
            log.debug("*** send_data FAILED [" + debug + "] had an exception sending [" + data + "]")



###############################################################################
#                                UNIT TESTS                                   #
#         Unit tests test the method calls and parameters using Mock.         #
###############################################################################
@attr('UNIT', group='mi')
class SBE26PlusUnitFromIDK(InstrumentDriverUnitTestCase):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    ###############################################################################
    #                                UNIT TESTS                                   #
    #         Unit tests test the method calls and parameters using Mock.         #
    # 1. Pick a single method within the class.                                   #
    # 2. Create an instance of the class                                          #
    # 3. If the method to be tested tries to call out, over-ride the offending    #
    #    method with a mock                                                       #
    # 4. Using above, try to cover all paths through the functions                #
    # 5. Negative testing if at all possible.                                     #
    ###############################################################################



    # Test enumerations. Verify no duplicates.

    def convert_enum_to_dict(self, obj):
        """
        @author Roger Unwin
        @brief  converts an enum to a dict
        """
        dic = {}
        for i in [v for v in dir(obj) if not callable(getattr(obj,v))]:
            if False == i.startswith('_'):
                dic[i] = getattr(obj, i)
        log.debug("enum dictionary = " + repr(dic))
        return dic

    def assert_enum_has_no_duplicates(self, obj):
        dic = self.convert_enum_to_dict(obj)
        occurances  = {}
        for k, v in dic.items():
            #v = tuple(v)
            occurances[v] = occurances.get(v,0) + 1

        for k in occurances:
            if occurances[k] > 1:
                log.error(str(obj) + " has ambigous duplicate values for '" + str(k) + "'")
                self.assertEqual(1, occurances[k])


    @unittest.skip('Need to figure out how this one works.')
    def test_prompts(self):
        """
        Verify that the prompts enumeration has no duplicate values that might cause confusion
        """
        prompts = Prompt()
        self.assert_enum_has_no_duplicates(prompts)


    def test_instrument_commands_for_duplicates(self):
        """
        Verify that the InstrumentCmds enumeration has no duplicate values that might cause confusion
        """
        cmds = InstrumentCmds()
        self.assert_enum_has_no_duplicates(cmds)

    def test_protocol_state_for_duplicates(self):
        """
        Verify that the ProtocolState enumeration has no duplicate values that might cause confusion
        """
        ps = ProtocolState()
        self.assert_enum_has_no_duplicates(ps)

    def test_protocol_event_for_duplicates(self):
        """
        Verify that the ProtocolEvent enumeration has no duplicate values that might cause confusion
        """
        pe = ProtocolEvent()
        self.assert_enum_has_no_duplicates(pe)

    def test_capability_for_duplicates(self):
        """
        Verify that the Capability enumeration has no duplicate values that might cause confusion
        """
        c = Capability()
        self.assert_enum_has_no_duplicates(c)

    def test_parameter_for_duplicates(self):
        # Test ProtocolState.  Verify no Duplications.
        p = Parameter()
        self.assert_enum_has_no_duplicates(p)

    def my_event_callback(self, event):
        log.debug("event = " + repr(event))
        event_type = event['type']

        if event_type == DriverAsyncEvent.SAMPLE:
            sample_value = event['value']
            # the event is coming back as a string


            if 'raw' in sample_value:
                # I hate using a global, but this self is not a shared self with the test
                global raw_stream_received
                raw_stream_received = True
                log.debug("GOT A RAW")
            elif 'parsed' in sample_value:
                global parsed_stream_received
                parsed_stream_received = True
                log.debug("GOT A PARSED")

    def test_instrument_driver_init_(self):
        """
        @brief Test that the InstrumentDriver constructors correctly build a Driver instance.
        # should call instrument/instrument_driver SingleConnectionInstrumentDriver.__init__
        # which will call InstrumentDriver.__init__, then create a _connection_fsm and start it.
        """

        ID = InstrumentDriver(self.my_event_callback)
        self.assertEqual(ID._connection, None)
        self.assertEqual(ID._protocol, None)
        self.assertTrue(isinstance(ID._connection_fsm, InstrumentFSM))
        self.assertEqual(ID._connection_fsm.current_state, DriverConnectionState.UNCONFIGURED)

    def test_instrument_driver_build_protocol(self):
        #@TODO add tests for ID._protocol._sample_regexs

        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()

        self.assertEqual(ID._protocol._newline, NEWLINE)
        self.assertEqual(ID._protocol._prompts, Prompt)
        self.assertEqual(ID._protocol._driver_event, ID._driver_event)
        self.assertEqual(ID._protocol._linebuf, '')
        self.assertEqual(ID._protocol._promptbuf, '')
        self.assertEqual(ID._protocol._datalines, [])



        for key in ['qs', 'set', 'stop', 'dc', 'ts', 'start', 'initlogging', 'ds']:
            self.assertTrue(key in ID._protocol._build_handlers.keys())

        for key in ['set', 'dc', 'ts','initlogging', 'ds']:
            self.assertTrue(key in ID._protocol._response_handlers.keys())

        self.assertEqual(ID._protocol._last_data_receive_timestamp, None)
        self.assertEqual(ID._protocol._connection, None)

        p = Parameter()
        for labels_value in ID._protocol._param_dict._param_dict.keys():
            log.debug("Verifying " + labels_value + " is present")
            match = False
            for i in [v for v in dir(p) if not callable(getattr(p,v))]:
                key = getattr(p, i)
                if key == labels_value:
                    match = True
            self.assertTrue(match)

        self.assertEqual(ID._protocol._protocol_fsm.enter_event, 'DRIVER_EVENT_ENTER')
        self.assertEqual(ID._protocol._protocol_fsm.exit_event, 'DRIVER_EVENT_EXIT')
        self.assertEqual(ID._protocol._protocol_fsm.previous_state, None)
        self.assertEqual(ID._protocol._protocol_fsm.current_state, 'DRIVER_STATE_UNKNOWN')
        self.assertEqual(repr(ID._protocol._protocol_fsm.states), repr(ProtocolState))
        self.assertEqual(repr(ID._protocol._protocol_fsm.events), repr(ProtocolEvent))

        state_handlers = {('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_STOP_AUTOSAMPLE'): '_handler_autosample_stop_autosample',
                          #('DRIVER_STATE_AUTOSAMPLE', 'PROTOCOL_EVENT_SEND_LAST'): '_handler_command_autosample_send_last',
                          #('DRIVER_STATE_AUTOSAMPLE', 'PROTOCOL_EVENT_SEND_LAST_AND_SLEEP'): '_handler_command_autosample_send_last_and_sleep',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_CLOCK_SYNC'): '_handler_command_clock_sync',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_ENTER'): '_handler_direct_access_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ENTER'): '_handler_command_enter',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_EXIT'): '_handler_unknown_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_INIT_LOGGING'): '_handler_command_init_logging',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ACQUIRE_SAMPLE'): '_handler_command_acquire_sample',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'EXECUTE_DIRECT'): '_handler_direct_access_execute_direct',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_EXIT'): '_handler_autosample_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_QUIT_SESSION'): '_handler_command_quit_session',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_STOP_DIRECT'): '_handler_direct_access_stop_direct',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_EXIT'): '_handler_direct_access_exit',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_FORCE_STATE'): '_handler_unknown_force_state',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_SET'): '_handler_command_set',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_START_DIRECT'): '_handler_command_start_direct',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_GET'): '_handler_command_autosample_test_get',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_SETSAMPLING'): '_handler_command_setsampling',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_START_AUTOSAMPLE'): '_handler_command_start_autosample',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_GET'): '_handler_command_autosample_test_get',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_DISCOVER'): '_handler_unknown_discover',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_ENTER'): '_handler_autosample_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_EXIT'): '_handler_command_exit',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_ENTER'): '_handler_unknown_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ACQUIRE_STATUS'): '_handler_command_aquire_status'}

        for key in ID._protocol._protocol_fsm.state_handlers.keys():
            self.assertEqual(ID._protocol._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in state_handlers)

        for key in state_handlers.keys():
            self.assertEqual(ID._protocol._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in ID._protocol._protocol_fsm.state_handlers)

        # no longer used
        #self.assertEqual(ID._protocol.parsed_sample, {})
        #self.assertEqual(ID._protocol.raw_sample, '')

    @unittest.skip('Need to figure out how this one works.')
    def test_data_particle(self):
        """
        """
        #@TODO need to see what a working data particle should do.

    @unittest.skip('Need to figure out how this one works.')
    def test_data_particle_build_parsed_values(self):
        """
        """
        #@TODO need to see what a working data particle should do.

    def test_protocol(self):
        """
        """
        #@TODO add tests for p._sample_regexs

        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)
        self.assertEqual(str(my_event_callback.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

        p._protocol_fsm

        self.assertEqual(p._protocol_fsm.enter_event, 'DRIVER_EVENT_ENTER')
        self.assertEqual(p._protocol_fsm.exit_event, 'DRIVER_EVENT_EXIT')
        self.assertEqual(p._protocol_fsm.previous_state, None)
        self.assertEqual(p._protocol_fsm.current_state, 'DRIVER_STATE_UNKNOWN')
        self.assertEqual(repr(p._protocol_fsm.states), repr(ProtocolState))
        self.assertEqual(repr(p._protocol_fsm.events), repr(ProtocolEvent))


        state_handlers = {('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_STOP_AUTOSAMPLE'): '_handler_autosample_stop_autosample',
                          #('DRIVER_STATE_AUTOSAMPLE', 'PROTOCOL_EVENT_SEND_LAST'): '_handler_command_autosample_send_last',
                          #('DRIVER_STATE_AUTOSAMPLE', 'PROTOCOL_EVENT_SEND_LAST_AND_SLEEP'): '_handler_command_autosample_send_last_and_sleep',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_CLOCK_SYNC'): '_handler_command_clock_sync',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_ENTER'): '_handler_direct_access_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ENTER'): '_handler_command_enter',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_EXIT'): '_handler_unknown_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_INIT_LOGGING'): '_handler_command_init_logging',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ACQUIRE_SAMPLE'): '_handler_command_acquire_sample',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'EXECUTE_DIRECT'): '_handler_direct_access_execute_direct',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_EXIT'): '_handler_autosample_exit',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_QUIT_SESSION'): '_handler_command_quit_session',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_STOP_DIRECT'): '_handler_direct_access_stop_direct',
                          ('DRIVER_STATE_DIRECT_ACCESS', 'DRIVER_EVENT_EXIT'): '_handler_direct_access_exit',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_FORCE_STATE'): '_handler_unknown_force_state',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_SET'): '_handler_command_set',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_START_DIRECT'): '_handler_command_start_direct',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_GET'): '_handler_command_autosample_test_get',
                          ('DRIVER_STATE_COMMAND', 'PROTOCOL_EVENT_SETSAMPLING'): '_handler_command_setsampling',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_START_AUTOSAMPLE'): '_handler_command_start_autosample',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_GET'): '_handler_command_autosample_test_get',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_DISCOVER'): '_handler_unknown_discover',
                          ('DRIVER_STATE_AUTOSAMPLE', 'DRIVER_EVENT_ENTER'): '_handler_autosample_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_EXIT'): '_handler_command_exit',
                          ('DRIVER_STATE_UNKNOWN', 'DRIVER_EVENT_ENTER'): '_handler_unknown_enter',
                          ('DRIVER_STATE_COMMAND', 'DRIVER_EVENT_ACQUIRE_STATUS'): '_handler_command_aquire_status'}

        for key in p._protocol_fsm.state_handlers.keys():
            log.debug("W*****>>> " + str(key))
            log.debug("X*****>>> " + str(p._protocol_fsm.state_handlers[key].__func__.func_name))
            log.debug("Y*****>>> " + str(state_handlers[key]))
            self.assertEqual(p._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in state_handlers)

        for key in state_handlers.keys():
            self.assertEqual(p._protocol_fsm.state_handlers[key].__func__.func_name,  state_handlers[key])
            self.assertTrue(key in p._protocol_fsm.state_handlers)

        # no longer used
        #self.assertEqual(p.parsed_sample, {})
        #self.assertEqual(p.raw_sample, '')

    def test_protocol_filter_capabilities(self):
        """
        This tests driver get capabilities
        """

        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)
        c = Capability()

        master_list = []
        for k in self.convert_enum_to_dict(c):
            ret = p._filter_capabilities([getattr(c, k)])
            log.debug(str(ret))
            master_list.append(getattr(c, k))
            self.assertEqual(len(ret), 1)
        self.assertEqual(len(p._filter_capabilities(master_list)), 5)

        # Negative Testing
        self.assertEqual(len(p._filter_capabilities(['BIRD', 'ABOVE', 'WATER'])), 0)
        try:
            self.assertEqual(len(p._filter_capabilities(None)), 0)
        except TypeError:
            pass

        self.assertEqual(str(my_event_callback.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

    def test_protocol_handler_unknown_enter(self):
        """
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)

        args = []
        kwargs =  {}
        p._handler_unknown_enter(*args, **kwargs)
        self.assertEqual(str(my_event_callback.call_args_list), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE'),\n call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

    def test_protocol_handler_unknown_exit(self):
        """
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        p = Protocol(Prompt, NEWLINE, my_event_callback)

        args = []
        kwargs =  {}
        p._handler_unknown_exit(*args, **kwargs)
        self.assertEqual(str(my_event_callback.call_args_list), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

    def test_protocol_handler_unknown_discover(self):
        """
        Test 3 paths through the func ( ProtocolState.UNKNOWN, ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE)
            For each test 3 paths of Parameter.LOGGING = ( True, False, Other )
        """


        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        #
        # current_state = ProtocolState.UNKNOWN
        #

        ID._protocol._protocol_fsm.current_state = ProtocolState.UNKNOWN

        args = []
        kwargs = ({'timeout': 30,})

        do_cmd_resp_mock = Mock(spec="do_cmd_resp_mock")
        p._do_cmd_resp = do_cmd_resp_mock
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock

        v = Mock(spec="val")
        v.value = None
        p._param_dict.set(Parameter.LOGGING, v)
        ex_caught = False
        try:
            (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        except InstrumentStateException:
            ex_caught = True
        self.assertTrue(ex_caught)
        self.assertEqual(str(_wakeup_mock.mock_calls), '[call(delay=0.5, timeout=30), call(30)]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()



        v.value = True
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[call(delay=0.5, timeout=30), call(30)]')

        self.assertEqual("[call('ds', timeout=30), call('dc', timeout=30)]", str(do_cmd_resp_mock.mock_calls))

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v.value = False
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[call(delay=0.5, timeout=30), call(30)]')
        self.assertTrue("[call('ds', timeout=30), call('dc', timeout=30)]" in str(do_cmd_resp_mock.mock_calls))

        #
        # current_state = ProtocolState.COMMAND
        #

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        p._protocol_fsm.current_state = ProtocolState.COMMAND

        args = []
        kwargs =  dict({'timeout': 30,})

        do_cmd_resp_mock = Mock(spec="do_cmd_resp_mock")
        p._do_cmd_resp = do_cmd_resp_mock
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock

        v = Mock(spec="val")
        v.value = None
        p._param_dict.set(Parameter.LOGGING, v)
        ex_caught = False
        try:
            (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        except InstrumentStateException:
            ex_caught = True
        self.assertTrue(ex_caught)
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v = Mock(spec="val")

        v.value = True
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v.value = False
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")



        #
        # current_state = ProtocolState.AUTOSAMPLE
        #

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        p._protocol_fsm.current_state = ProtocolState.COMMAND

        args = []
        kwargs =  dict({'timeout': 30,})

        do_cmd_resp_mock = Mock(spec="do_cmd_resp_mock")
        p._do_cmd_resp = do_cmd_resp_mock
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock

        v = Mock(spec="val")
        v.value = None
        p._param_dict.set(Parameter.LOGGING, v)
        ex_caught = False
        try:
            (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        except InstrumentStateException:
            ex_caught = True
        self.assertTrue(ex_caught)
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")
        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v = Mock(spec="val")

        v.value = True
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_AUTOSAMPLE')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_STREAMING')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")

        _wakeup_mock.reset_mock()
        do_cmd_resp_mock.reset_mock()

        v.value = False
        p._param_dict.set(Parameter.LOGGING, v)
        (next_state, result) = p._handler_unknown_discover(*args, **kwargs)
        self.assertEqual(next_state, 'DRIVER_STATE_COMMAND')
        self.assertEqual(result, 'RESOURCE_AGENT_STATE_IDLE')
        self.assertEqual(str(_wakeup_mock.mock_calls), '[]')
        self.assertEqual(str(do_cmd_resp_mock.mock_calls), "[call('ds', timeout=30), call('dc', timeout=30)]")

    def test_protocol_unknown_force_state(self):
        """
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        args = []
        kwargs =  dict({'timeout': 30,})
        ex_caught = False
        try:
            (next_state, result) = p._handler_unknown_force_state(*args, **kwargs)
        except InstrumentParameterException:
            ex_caught = True
        self.assertTrue(ex_caught)

        kwargs = dict({'timeout': 30,
                        'state': 'ARDVARK'})

        (next_state, result) = p._handler_unknown_force_state(*args, **kwargs)
        self.assertEqual(next_state, 'ARDVARK')
        self.assertEqual(result, 'ARDVARK')

    def test_protocol_handler_command_enter(self):
        """
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        _update_params_mock = Mock(spec="update_params")
        p._update_params = _update_params_mock

        _update_driver_event = Mock(spec="driver_event")
        p._driver_event = _update_driver_event
        args = []
        kwargs =  dict({'timeout': 30,})

        ret = p._handler_command_enter(*args, **kwargs)
        self.assertEqual(ret, None)
        self.assertEqual(str(_update_params_mock.mock_calls), "[call()]")
        self.assertEqual(str(_update_driver_event.mock_calls), "[call('DRIVER_ASYNC_EVENT_STATE_CHANGE')]")

    def test_protocol_parse_ts_response(self):
        """
        Exercise the various paths through _parse_ts_response verifying that a sample is correctly parsed
        """
        global raw_stream_received
        global parsed_stream_received

        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        # verify that it throws an exception if the wrong prompt is encountered

        response = 'silly irrelevent response'
        for prompt in (Prompt.BAD_COMMAND, Prompt.CONFIRMATION_PROMPT):
            ex_caught = False
            try:
                ret = p._parse_ts_response(response, prompt)
            except InstrumentProtocolException:
                ex_caught = True
            self.assertTrue(ex_caught)

        # verify we get a SampleException if the sample data is incorrect
        try:
            ret = p._parse_ts_response(response, Prompt.COMMAND)
        except SampleException:
            ex_caught = True
        self.assertTrue(ex_caught)

        # test with valid data
        response = "ts" + NEWLINE + \
                   " -158.9284 -8388.96  -3.2164" + NEWLINE +\
                   Prompt.COMMAND

        ret = p._parse_ts_response(response, Prompt.COMMAND)
        self.assertTrue(raw_stream_received)
        raw_stream_received = False            # RESET
        self.assertTrue(parsed_stream_received)
        parsed_stream_received = False         # RESET


        # test with slightly invalid data. should still work
        response = "ts" + NEWLINE +\
                   " -158.5166 -8392.30  -3.2164 -1.02535   0.0000" + NEWLINE +\
                   Prompt.COMMAND

        ret = p._parse_ts_response(response, Prompt.COMMAND)
        self.assertTrue(raw_stream_received)
        raw_stream_received = False            # RESET
        self.assertTrue(parsed_stream_received)
        parsed_stream_received = False         # RESET


    def test_protocol_got_data(self):
        """

        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        paPacket = PortAgentPacket()



        #
        # DIRECT_ACCESS mode, zero length data
        #

        p._protocol_fsm.current_state = ProtocolState.DIRECT_ACCESS
        self.assertEqual(p.get_current_state(), ProtocolState.DIRECT_ACCESS)

        data = ""
        paPacket = PortAgentPacket()
        paPacket.attach_data(data)
        paPacket.pack_header(1)


        # mock out _driver_event as we are only looking at got_data
        _driver_event_mock = Mock(spec="driver_event")
        p._driver_event = _driver_event_mock


        ret = p.got_data(paPacket)
        self.assertEqual(ret, None)
        self.assertEqual(str(_driver_event_mock.mock_calls), "[]")



        #
        # DIRECT_ACCESS mode, valid data
        #

        # mock out _driver_event as we are only looking at got_data
        _driver_event_mock = Mock(spec="driver_event")
        p._driver_event = _driver_event_mock

        p._sent_cmds = []
        p._sent_cmds.append('ts')
        self.assertTrue(len(p._sent_cmds) > 0)
        p._protocol_fsm.current_state = ProtocolState.DIRECT_ACCESS
        self.assertEqual(p.get_current_state(), ProtocolState.DIRECT_ACCESS)

        data = "ts" + NEWLINE +\
               " 14.5128 24.34 23.9912 111111" + NEWLINE +\
               Prompt.COMMAND
        paPacket = PortAgentPacket()
        paPacket.attach_data(data)
        paPacket.pack_header(1)

        ret = p.got_data(paPacket)
        self.assertEqual(ret, None)
        self.assertEqual(str(_driver_event_mock.mock_calls), "[call('DRIVER_ASYNC_EVENT_DIRECT_ACCESS', '\\r\\n 14.5128 24.34 23.9912 111111\\r\\nS>')]")





        #
        # AUTOSAMPLE mode, valid data
        #

        p._protocol_fsm.current_state = ProtocolState.AUTOSAMPLE
        self.assertEqual(p.get_current_state(), ProtocolState.AUTOSAMPLE)


        # mock out _extract_sample as we are only looking at got_data
        _extract_sample_mock = Mock(spec="extract_sample")
        p._extract_sample = _extract_sample_mock

        data = SAMPLE_DATA

        paPacket = PortAgentPacket()
        paPacket.attach_data(data)
        paPacket.pack_header(1)
        self.assertTrue(len(data) > 0)
        self.assertTrue(paPacket.get_data_size() > 0)
        self.assertTrue(len(paPacket.get_data()) > 0)
        ret = p.got_data(paPacket)
        self.assertEqual(ret, None)
        #@ TODO put below line back in and fix it once it is working
        #self.assertEqual(str(_extract_sample_mock.mock_calls), "3XXXXX")


        #
        # AUTOSAMPLE mode, no data
        #


        p._protocol_fsm.current_state = ProtocolState.AUTOSAMPLE
        self.assertEqual(p.get_current_state(), ProtocolState.AUTOSAMPLE)


        # mock out _extract_sample as we are only looking at got_data
        _extract_sample_mock = Mock(spec="extract_sample")
        p._extract_sample = _extract_sample_mock

        data = ""
        paPacket = PortAgentPacket()
        paPacket.attach_data(data)
        paPacket.pack_header(1)
        self.assertTrue(len(data) == 0)
        self.assertTrue(paPacket.get_data_size() == 0)
        self.assertTrue(len(paPacket.get_data()) == 0)

        ret = p.got_data(paPacket)
        self.assertEqual(ret, None)
        self.assertEqual(str(_extract_sample_mock.mock_calls), "[]")

        #
        # AUTOSAMPLE mode, corrupted data
        #

        p._protocol_fsm.current_state = ProtocolState.AUTOSAMPLE
        self.assertEqual(p.get_current_state(), ProtocolState.AUTOSAMPLE)


        # mock out _extract_sample as we are only looking at got_data
        _extract_sample_mock = Mock(spec="extract_sample")
        p._extract_sample = _extract_sample_mock

        data = BAD_SAMPLE_DATA

        paPacket = PortAgentPacket()
        paPacket.attach_data(data)
        paPacket.pack_header(1)
        self.assertTrue(len(data) > 0)
        self.assertTrue(paPacket.get_data_size() > 0)
        self.assertTrue(len(paPacket.get_data()) > 0)
        ret = p.got_data(paPacket)
        self.assertEqual(ret, None)

        #@TODO fix publishing.
        # INTERESTING. isusing SAMPLE_REGEX
        print _extract_sample_mock.mock_calls
        self.assertEqual(len(_extract_sample_mock.mock_calls), 35)
        #@ TODO put below line back in and fix it once it is working
        #self.assertEqual(str(_extract_sample_mock.mock_calls), "3XXXXX")

    @unittest.skip('re-enable once DataParticle is working.')
    def test_extract_sample(self):
        """
        Test that the _extract_sample method can parse data
        """

        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        _driver_event_mock = Mock(spec="driver_event")
        p._driver_event = _driver_event_mock

        data = SAMPLE_DATA

        for line in data.split(NEWLINE):
            ret = p._extract_sample(SBE26plusDataParticle, line)



        # Verify it published 2 packets
        self.assertEqual(len(_driver_event_mock.mock_calls), 2)
        """
        print _driver_event_mock.mock_calls
        [call('DRIVER_ASYNC_EVENT_SAMPLE', {'stream_name': 'raw', 'blob': '\r\nwave: ptfreq = 171791.359\r\ndepth =    0.000, temperature = 23.840, salinity = 35.000, density = 1023.690\r\n   nAvgBand = 5\r\n   total variance = 1.0896e-05\r\n   total energy = 1.0939e-01\r\n   significant period = 5.3782e-01\r\n   significant wave height = 1.3204e-02\r\n   wave integration time = 128\r\n   number of waves = 0\r\n   total variance = 1.1595e-05\r\n   total energy = 1.1640e-01\r\n   average wave height = 0.0000e+00\r\n   average wave period = 0.0000e+00\r\n   maximum wave height = 1.0893e-02\r\n   significant wave height = 0.0000e+00\r\n   significant wave period = 0.0000e+00\r\n   H1/10 = 0.0000e+00\r\n   H1/100 = 0.0000e+00', 'time': [1349456065.638729]}),
         call('DRIVER_ASYNC_EVENT_SAMPLE', {'stream_name': 'parsed', 'parsed': {'significant_period': '5.3782e-01', 'maximum_wave_height': '1.0893e-02', 'temperature': '23.840', 'significant_wave_period': '0.0000e+00', 'density': '1023.690', 'average_wave_height': '0.0000e+00', 'number_of_waves': '0', 'average_wave_period': '0.0000e+00', 'total_variance': '1.1595e-05', 'salinity': '35.000', 'depth': '0.000', 'total_energy': '1.1640e-01', 'height_highest_10_percent_waves': '0.0000e+00', 'nAvgBand': '5', 'height_highest_1_percent_waves': '0.0000e+00', 'wave_ptfreq': '171791.359', 'significant_wave_height': '0.0000e+00', 'wave_integration_time': '128'}, 'time': [1349456065.638729]})]
        """

    def test_parse_ds_response(self):
        """
        Verify that the driver can parse output from DS command.
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        ret = p._parse_ds_response(SAMPLE_DS, Prompt.COMMAND)

        # assert that we know of 46 params
        self.assertEqual(len(p._param_dict.get_keys()), 46)

        dic = self.convert_enum_to_dict(Parameter)

        self.assertEqual(str(p._param_dict.get('HANNING_WINDOW_CUTOFF')),'0.1')
        self.assertEqual(str(p._param_dict.get('TIDE_MEASUREMENTS_SINCE_LAST_START')),'11.0')
        self.assertEqual(str(p._param_dict.get('TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS')),'6.0')
        self.assertEqual(str(p._param_dict.get('USE_STOP_TIME')),'False')
        self.assertEqual(str(p._param_dict.get('DateTime')),'05 OCT 2012  17:19:27')
        self.assertEqual(str(p._param_dict.get('NOMINAL_ALKALINE_BATTERY_ENDURANCE')),'272.8')
        self.assertEqual(str(p._param_dict.get('TIDE_INTERVAL')),'3')
        self.assertEqual(str(p._param_dict.get('USE_START_TIME')),'False')
        self.assertEqual(str(p._param_dict.get('IOP_MA')),'7.4')
        self.assertEqual(str(p._param_dict.get('QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER')),'122094.0')
        self.assertEqual(str(p._param_dict.get('CONDUCTIVITY')),'False')
        self.assertEqual(str(p._param_dict.get('MEMORY_ENDURANCE')),'258.0')
        self.assertEqual(str(p._param_dict.get('WAVE_BURSTS_PER_DAY')),'80.0')
        self.assertEqual(str(p._param_dict.get('DEVICE_VERSION')),'6.1E')
        self.assertEqual(str(p._param_dict.get('WAVE_SAMPLES_PER_BURST')),'512')
        self.assertEqual(str(p._param_dict.get('PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM')),'10.0')
        self.assertEqual(str(p._param_dict.get('LAST_SAMPLE_T')),'23.8155')
        self.assertEqual(str(p._param_dict.get('NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS')),'512')
        self.assertEqual(str(p._param_dict.get('LAST_SAMPLE_P')),'14.5361')
        self.assertEqual(p._param_dict.get('LAST_SAMPLE_S'), None)
        self.assertEqual(str(p._param_dict.get('TIDE_SAMPLES_PER_DAY')),'480.0')
        self.assertEqual(str(p._param_dict.get('STATUS')),'STOPPED')
        self.assertEqual(p._param_dict.get('AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR'), None)
        self.assertEqual(str(p._param_dict.get('LOGGING')),'False')
        self.assertEqual(str(p._param_dict.get('TxTide')),'True')
        self.assertEqual(str(p._param_dict.get('TIDE_MEASUREMENT_DURATION')),'60')
        self.assertEqual(str(p._param_dict.get('ExternalTemperature')),'False')
        self.assertEqual(str(p._param_dict.get('MIN_PERIOD_IN_AUTO_SPECTRUM')),'0.0')
        self.assertEqual(str(p._param_dict.get('SHOW_PROGRESS_MESSAGES')),'True')
        self.assertEqual(str(p._param_dict.get('TxWave')),'True')
        self.assertEqual(str(p._param_dict.get('WAVE_BURSTS_SINCE_LAST_START')),'1.0')
        self.assertEqual(str(p._param_dict.get('MIN_ALLOWABLE_ATTENUATION')),'0.0025')
        self.assertEqual(str(p._param_dict.get('TXWAVESTATS')),'True')
        self.assertEqual(str(p._param_dict.get('USE_MEASURED_TEMP_FOR_DENSITY_CALC')),'False')
        self.assertEqual(str(p._param_dict.get('SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND')),'5')
        self.assertEqual(str(p._param_dict.get('QUARTZ_PRESSURE_SENSOR_RANGE')),'300.0')
        self.assertEqual(str(p._param_dict.get('TOTAL_RECORDED_TIDE_MEASUREMENTS')),'5982.0')
        self.assertEqual(str(p._param_dict.get('TOTAL_RECORDED_WAVE_BURSTS')),'4525.0')
        self.assertEqual(str(p._param_dict.get('WAVE_SAMPLES_SCANS_PER_SECOND')),'4.0')
        self.assertEqual(str(p._param_dict.get('MAX_PERIOD_IN_AUTO_SPECTRUM')),'1000000.0')
        self.assertEqual(str(p._param_dict.get('USERINFO')),'OOI')
        self.assertEqual(str(p._param_dict.get('VLITH_V')),'9.0')
        self.assertEqual(str(p._param_dict.get('SERIAL_NUMBER')),'1329')
        self.assertEqual(str(p._param_dict.get('VMAIN_V')),'16.2')
        self.assertEqual(p._param_dict.get('AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR'), None)


        attrs = {'update.return_value': 'FAKE IGNORED RETURN'}
        _param_dict_mock = Mock(**attrs)

        p._param_dict = _param_dict_mock

        ret = p._parse_ds_response(SAMPLE_DS, Prompt.COMMAND)
        #self.assertEqual(ret, None)
        self.assertEqual(ret, 'SBE 26plus V 6.1e  SN 1329    05 Oct 2012  17:19:27\r\nuser info=ooi\r\nquartz pressure sensor: serial number = 122094, range = 300 psia\r\ninternal temperature sensor\r\nconductivity = NO\r\niop =  7.4 ma  vmain = 16.2 V  vlith =  9.0 V\r\nlast sample: p = 14.5361, t = 23.8155\r\n\r\ntide measurement: interval = 3.000 minutes, duration = 60 seconds\r\nmeasure waves every 6 tide samples\r\n512 wave samples/burst at 4.00 scans/sec, duration = 128 seconds\r\nlogging start time = do not use start time\r\nlogging stop time = do not use stop time\r\n\r\ntide samples/day = 480.000\r\nwave bursts/day = 80.000\r\nmemory endurance = 258.0 days\r\nnominal alkaline battery endurance = 272.8 days\r\ntotal recorded tide measurements = 5982\r\ntotal recorded wave bursts = 4525\r\ntide measurements since last start = 11\r\nwave bursts since last start = 1\r\n\r\ntransmit real-time tide data = YES\r\ntransmit real-time wave burst data = YES\r\ntransmit real-time wave statistics = YES\r\nreal-time wave statistics settings:\r\n  number of wave samples per burst to use for wave statistics = 512\r\n  use measured temperature for density calculation\r\n  height of pressure sensor from bottom (meters) = 10.0\r\n  number of spectral estimates for each frequency band = 5\r\n  minimum allowable attenuation = 0.0025\r\n  minimum period (seconds) to use in auto-spectrum = 0.0e+00\r\n  maximum period (seconds) to use in auto-spectrum = 1.0e+06\r\n  hanning window cutoff = 0.10\r\n  show progress messages\r\n\r\nstatus = stopped by user\r\nlogging = NO, send start command to begin logging')

        # verify it passed all 44 lines to the update func
        self.assertEqual(len(_param_dict_mock.mock_calls), 44)

    def test_parse_dc_response(self):
        """
        Verify that the driver can parse output from DC command.
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol


        ret = p._parse_dc_response(SAMPLE_DC, Prompt.COMMAND)
        log.debug("RET = " + str(ret))
        # assert that we know of 76 params
        self.assertEqual(len(p._param_dict.get_keys()), 46) #76

        # get
        #
        dic = self.convert_enum_to_dict(Parameter)

        """
        for k in p._param_dict.get_keys():
            if p._param_dict.get(k) is None:
                print "self.assertEqual(p._param_dict.get('" + k + "'), None)"
            else:
                print "self.assertEqual(str(p._param_dict.get('" + k + "')),'" + str(p._param_dict.get(k)) + "')"
        """
        #DC#self.assertEqual(str(p._param_dict.get('TA0')),'0.0002557341')
        self.assertEqual(p._param_dict.get('HANNING_WINDOW_CUTOFF'), None)
        #DC#self.assertEqual(str(p._param_dict.get('FACTORY_M')),'41943.0')
        #DC#self.assertEqual(str(p._param_dict.get('FACTORY_B')),'2796.2')
        self.assertEqual(p._param_dict.get('TIDE_MEASUREMENTS_SINCE_LAST_START'), None)
        #DC#self.assertEqual(str(p._param_dict.get('PY2')),'-10829.41')
        #DC#self.assertEqual(str(p._param_dict.get('PY3')),'0.0')
        self.assertEqual(p._param_dict.get('TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS'), None)
        self.assertEqual(p._param_dict.get('USE_STOP_TIME'), None)
        self.assertEqual(p._param_dict.get('DateTime'), None)
        self.assertEqual(p._param_dict.get('NOMINAL_ALKALINE_BATTERY_ENDURANCE'), None)
        self.assertEqual(p._param_dict.get('TIDE_INTERVAL'), None)
        self.assertEqual(p._param_dict.get('USE_START_TIME'), None)
        self.assertEqual(p._param_dict.get('IOP_MA'), None)
        self.assertEqual(p._param_dict.get('QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER'), None)
        #DC#self.assertEqual(str(p._param_dict.get('PU0')),'5.827424')
        #DC#self.assertEqual(str(p._param_dict.get('TA1')),'0.0002493547')
        self.assertEqual(p._param_dict.get('CONDUCTIVITY'), None)
        #DC#self.assertEqual(p._param_dict.get('CSLOPE'), None)
        #DC#self.assertEqual(str(p._param_dict.get('PT4')),'31.09619')
        #DC#self.assertEqual(str(p._param_dict.get('PY1')),'-3845.795')
        #DC#self.assertEqual(p._param_dict.get('CCALDATE'), None)
        #DC#self.assertEqual(str(p._param_dict.get('POFFSET')),'-0.1877')
        self.assertEqual(p._param_dict.get('MEMORY_ENDURANCE'), None)
        #DC#self.assertEqual(str(p._param_dict.get('TCALDATE')),'(30, 3, 2012)')
        self.assertEqual(p._param_dict.get('WAVE_BURSTS_PER_DAY'), None)
        #DC#self.assertEqual(str(p._param_dict.get('PD2')),'0.0')
        #DC#self.assertEqual(str(p._param_dict.get('PD1')),'0.025294')
        #DC#self.assertEqual(str(p._param_dict.get('PT1')),'27.77282')
        self.assertEqual(p._param_dict.get('DEVICE_VERSION'), None)
        self.assertEqual(p._param_dict.get('WAVE_SAMPLES_PER_BURST'), None)
        self.assertEqual(p._param_dict.get('PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM'), None)
        self.assertEqual(p._param_dict.get('LAST_SAMPLE_T'), None)
        self.assertEqual(p._param_dict.get('NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS'), None)
        self.assertEqual(p._param_dict.get('LAST_SAMPLE_P'), None)
        self.assertEqual(p._param_dict.get('LAST_SAMPLE_S'), None)
        self.assertEqual(p._param_dict.get('TIDE_SAMPLES_PER_DAY'), None)
        self.assertEqual(p._param_dict.get('STATUS'), None)
        #DC#self.assertEqual(p._param_dict.get('CJ'), None)
        self.assertEqual(p._param_dict.get('AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR'), None)
        #DC#self.assertEqual(p._param_dict.get('CH'), None)
        self.assertEqual(p._param_dict.get('LOGGING'), None)
        self.assertEqual(p._param_dict.get('TxTide'), None)
        #DC#self.assertEqual(str(p._param_dict.get('TA2')),'-1.567218e-06')
        #DC#self.assertEqual(str(p._param_dict.get('TA3')),'1.508124e-07')
        self.assertEqual(p._param_dict.get('TIDE_MEASUREMENT_DURATION'), None)
        #DC#self.assertEqual(p._param_dict.get('CG'), None)
        self.assertEqual(p._param_dict.get('ExternalTemperature'), None)
        #DC#self.assertEqual(p._param_dict.get('CTCOR'), None)
        self.assertEqual(p._param_dict.get('MIN_PERIOD_IN_AUTO_SPECTRUM'), None)
        self.assertEqual(p._param_dict.get('SHOW_PROGRESS_MESSAGES'), None)
        self.assertEqual(p._param_dict.get('TxWave'), None)
        self.assertEqual(p._param_dict.get('WAVE_BURSTS_SINCE_LAST_START'), None)
        #DC#self.assertEqual(str(p._param_dict.get('PC1')),'2123.771')
        self.assertEqual(p._param_dict.get('MIN_ALLOWABLE_ATTENUATION'), None)
        self.assertEqual(p._param_dict.get('TXWAVESTATS'), None)
        #DC#self.assertEqual(str(p._param_dict.get('PT3')),'17.52851')
        #DC#self.assertEqual(str(p._param_dict.get('PT2')),'0.391138')
        self.assertEqual(p._param_dict.get('USE_MEASURED_TEMP_FOR_DENSITY_CALC'), None)
        self.assertEqual(p._param_dict.get('SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND'), None)
        #DC#self.assertEqual(str(p._param_dict.get('PCALDATE')),'(2, 4, 2012)')
        self.assertEqual(p._param_dict.get('QUARTZ_PRESSURE_SENSOR_RANGE'), None)
        self.assertEqual(p._param_dict.get('TOTAL_RECORDED_TIDE_MEASUREMENTS'), None)
        self.assertEqual(p._param_dict.get('TOTAL_RECORDED_WAVE_BURSTS'), None)
        #DC#self.assertEqual(str(p._param_dict.get('PC2')),'37.41653')
        #DC#self.assertEqual(str(p._param_dict.get('PC3')),'-4014.654')
        self.assertEqual(p._param_dict.get('USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC'), None)
        #DC#self.assertEqual(p._param_dict.get('CI'), None)
        self.assertEqual(p._param_dict.get('WAVE_SAMPLES_SCANS_PER_SECOND'), None)
        self.assertEqual(p._param_dict.get('MAX_PERIOD_IN_AUTO_SPECTRUM'), None)
        #DC#self.assertEqual(p._param_dict.get('CPCOR'), None)
        self.assertEqual(p._param_dict.get('USERINFO'), None)
        self.assertEqual(p._param_dict.get('VLITH_V'), None)
        self.assertEqual(p._param_dict.get('SERIAL_NUMBER'), None)
        self.assertEqual(p._param_dict.get('VMAIN_V'), None)
        self.assertEqual(p._param_dict.get('AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR'), None)

        attrs = {'update.return_value': 'FAKE IGNORED RETURN'}
        _param_dict_mock = Mock(**attrs)

        p._param_dict = _param_dict_mock

        ret = p._parse_dc_response(SAMPLE_DS, Prompt.COMMAND)
        self.assertEqual(ret, None)
        # verify it passed all 44 lines to the update func
        self.assertEqual(len(_param_dict_mock.mock_calls), 0)

    def test_build_set_command(self):
        """
        verify the build set command performs correctly
        should return var=value\r\n
        test for float, string, date, Boolean
        PU0 FLOAT 5.827424
        SHOW_PROGRESS_MESSAGES True Boolean
        self.assertEqual(str(p._param_dict.get('TCALDATE')),'(30, 3, 2012)')
        USER_INFO OOI str,
        TIDE_INTERVAL
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        # Float
        ret = p._build_set_command("irrelevant", Parameter.MIN_ALLOWABLE_ATTENUATION, 5.827424)
        self.assertEqual(ret, 'MIN_ALLOWABLE_ATTENUATION=5.827424\r\n')

        # Boolean - Yes/No
        ret = p._build_set_command("irrelevant", Parameter.SHOW_PROGRESS_MESSAGES, True)
        self.assertEqual(ret, 'SHOW_PROGRESS_MESSAGES=y\r\n')

        # String
        ret = p._build_set_command("irrelevant", Parameter.USER_INFO, 'ooi_test')
        self.assertEqual(ret, 'USERINFO=ooi_test\r\n')

        # Not used now DC set power removed.
        # Date (Tuple)
        # ret = p._build_set_command("irrelevant", Parameter.TCALDATE, (30, 8, 2012))
        # self.assertEqual(ret, 'TCALDATE=30-Aug-12\r\n')

    def test_handler_command_set(self):
        """
        Verify that we can set parameters
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol


        attrs = {'return_value': '_do_cmd_resp was returned'}
        _do_cmd_resp_mock = Mock(**attrs)
        _update_params_mock = Mock()

        p._do_cmd_resp = _do_cmd_resp_mock
        p._update_params = _update_params_mock

        params = {
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : 5,
            #DC#Parameter.PD1 : int(1),
            #DC#Parameter.PD2 : True,
            }
        args = params
        kwargs = {}

        (next_state, result) = p._handler_command_set(args, **kwargs)
        self.assertEqual(str(_do_cmd_resp_mock.mock_calls),"[call('set', 'ExternalTemperature', 5)]")
        self.assertEqual(str(_update_params_mock.mock_calls), "[call()]")
        self.assertEqual(next_state, None)
        self.assertEqual(str(result), "_do_cmd_resp was returned")

        ex_caught = False
        try:
            (next_state, result) = p._handler_command_set("WRONG", **kwargs)
        except InstrumentParameterException:
            ex_caught = True
        self.assertTrue(ex_caught)

        args = []
        ex_caught = False
        try:
            (next_state, result) = p._handler_command_set(*args, **kwargs)
        except InstrumentParameterException:
            ex_caught = True
        self.assertTrue(ex_caught)

    def test_parse_setsampling_response(self):
        """
        verify setsampling works properly
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        # Fill the DC/DS response
        p._parse_dc_response(SAMPLE_DC, Prompt.COMMAND)
        p._parse_ds_response(SAMPLE_DS, Prompt.COMMAND)

        p.fake_responses = [(", new value = ", "tide interval (integer minutes) = 3, new value ="),
                            (", new value = ", "tide measurement duration (seconds) = 60, new value ="),
                            (", new value = ", "measure wave burst after every N tide samples: N = 6, new value ="),
                            (", new value = ", "number of wave samples per burst (multiple of 4) = 512, new value ="),
                            (", new value = ", "wave Sample duration (0.25, 0.50, 0.75, 1.0) seconds = 0.25, new value ="),
                            (", new value = ", "use start time (y/n) = n, new value ="),
                            (", new value = ", "use stop time (y/n) = n, new value ="),
                            (", new value = ", "TXWAVESTATS (real-time wave statistics) (y/n) = y, new value ="),
                            #(", new value = ", "the remaining prompts apply to real-time wave statistics"),
                            (", new value = ", "show progress messages (y/n) = y, new value ="),
                            (", new value = ", "number of wave samples per burst to use for wave statistics = 512, new value ="),
                            (", new value = ", "use measured temperature for density calculation (y/n) = y, new value ="),
                            (", new value = ", "height of pressure sensor from bottom (meters) = 10.0, new value ="),
                            (", new value = ", "number of spectral estimates for each frequency band = 5, new value ="),
                            (", new value = ", "minimum allowable attenuation = 0.0025, new value ="),
                            (", new value = ", "minimum period (seconds) to use in auto-spectrum = 0.0e+00, new value ="),
                            (", new value = ", "maximum period (seconds) to use in auto-spectrum = 1.0e+06, new value ="),
                            (", new value = ", "hanning window cutoff = 0.10, new value ="),
                            (Prompt.COMMAND, "")]

        # First time is with no values to send (accept defaults)
        p._sampling_args = {}

        def _get_response_mock(expected_prompt):
            try:
                resp = p.fake_responses.pop(0)
            except:
                resp = (Prompt.COMMAND, "out of data")
                print resp
            return resp
        p._get_response = _get_response_mock
        _update_params_mock = Mock()
        p._update_params = _update_params_mock
        _connection_mock = Mock()
        p._connection = _connection_mock
        p._parse_setsampling_response("IGNORED", "IGNORED")

        self.assertEqual(len(_connection_mock.mock_calls),17)
        self.assertEqual(len(_update_params_mock.mock_calls),1)

        # Now with values to update
        p._sampling_args = {
            Parameter.TIDE_INTERVAL : 3, #1,
            Parameter.TIDE_MEASUREMENT_DURATION : 60,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 6,
            Parameter.WAVE_SAMPLES_PER_BURST : 512,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(4.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
            Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC : False,
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: 10.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : 5,
            Parameter.MIN_ALLOWABLE_ATTENUATION : 0.0025,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : 0.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : 1000000.0,
            Parameter.HANNING_WINDOW_CUTOFF : 0.1
        }
        p.fake_responses = [(", new value = ", "tide interval (integer minutes) = 3, new value ="),
                            (", new value = ", "tide measurement duration (seconds) = 60, new value ="),
                            (", new value = ", "measure wave burst after every N tide samples: N = 6, new value ="),
                            (", new value = ", "number of wave samples per burst (multiple of 4) = 512, new value ="),
                            (", new value = ", "wave Sample duration (0.25, 0.50, 0.75, 1.0) seconds = 0.25, new value ="),
                            (", new value = ", "use start time (y/n) = n, new value ="),
                            (", new value = ", "use stop time (y/n) = n, new value ="),
                            (", new value = ", "TXWAVESTATS (real-time wave statistics) (y/n) = y, new value ="),
                            (", new value = ", "the remaining prompts apply to real-time wave statistics\r\nshow progress messages (y/n) = y, new value ="),
                            (", new value = ", "number of wave samples per burst to use for wave statistics = 512, new value ="),
                            (", new value = ", "use measured temperature for density calculation (y/n) = y, new value ="),
                            (", new value = ", "height of pressure sensor from bottom (meters) = 10.0, new value ="),
                            (", new value = ", "number of spectral estimates for each frequency band = 5, new value ="),
                            (", new value = ", "minimum allowable attenuation = 0.0025, new value ="),
                            (", new value = ", "minimum period (seconds) to use in auto-spectrum = 0.0e+00, new value ="),
                            (", new value = ", "maximum period (seconds) to use in auto-spectrum = 1.0e+06, new value ="),
                            (", new value = ", "hanning window cutoff = 0.10, new value ="),
                            (Prompt.COMMAND, "")]
        p._get_response = _get_response_mock
        _update_params_mock = Mock()
        p._update_params = _update_params_mock
        _connection_mock = Mock()
        p._connection = _connection_mock
        p._parse_setsampling_response("IGNORED", "IGNORED")

        self.assertEqual(len(_connection_mock.mock_calls),17)
        self.assertEqual(len(_update_params_mock.mock_calls),1)

    def test_handler_command_autosample_test_get(self):
        """
        Verify that we are able to get back a variable setting correctly
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol

        # Fill the DC/DS response
        p._parse_dc_response(SAMPLE_DC, Prompt.COMMAND)
        p._parse_ds_response(SAMPLE_DS, Prompt.COMMAND)

        kwargs = {}
        p._handler_command_autosample_test_get(DriverParameter.ALL, **kwargs)

        args = [Parameter.TXREALTIME]
        kwargs = {}
        (next_state, result) = p._handler_command_autosample_test_get(args, **kwargs)
        self.assertEqual(next_state, None)
        self.assertEqual(result, {'TxTide': True})

    def test_handler_command_start_autosample(self):
        """
        verify startautosample sends the start command to the instrument.
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock

        _connection_mock = Mock(spec="_connection")
        _connection_send_mock = Mock(spec="_connection_send")
        _do_cmd_resp_mock = Mock(spec="_do_cmd_resp")
        p._connection = _connection_mock
        p._connection.send = _connection_send_mock
        p._do_cmd_resp = _do_cmd_resp_mock
        args = []
        kwargs = {}
        (next_state, result) = p._handler_command_start_autosample(*args, **kwargs)
        self.assertEqual(next_state,  ProtocolState.AUTOSAMPLE)
        self.assertEqual(result, ('RESOURCE_AGENT_STATE_STREAMING', None))
        self.assertEqual(str(_connection_send_mock.mock_calls), "[call('start\\r\\n')]")

    def test_handler_command_quit_session(self):
        """
        verify quit session sends the qs command to the instrument.
        """
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        _wakeup_mock = Mock(spec="wakeup_mock")
        p._wakeup = _wakeup_mock

        _connection_mock = Mock(spec="_connection")
        _connection_send_mock = Mock(spec="_connection")
        p._connection = _connection_mock
        p._connection.send = _connection_send_mock
        args = []
        kwargs = {}
        (next_state, result) = p._handler_command_quit_session(*args, **kwargs)
        self.assertEqual(next_state,  None)
        self.assertEqual(result, None)
        self.assertEqual(str(_connection_send_mock.mock_calls), "[call('qs\\r\\n')]")

    def test_get_resource_capabilities(self):
        ID = InstrumentDriver(self.my_event_callback)
        ID._build_protocol()
        p = ID._protocol
        args = []
        kwargs = {}

        # Force State UNKNOWN
        ID._protocol._protocol_fsm.current_state = ProtocolState.UNKNOWN

        ret = ID.get_resource_capabilities(*args, **kwargs)
        self.assertEqual(ret[0], [])

        # Force State COMMAND
        ID._protocol._protocol_fsm.current_state = ProtocolState.COMMAND

        ret = ID.get_resource_capabilities(*args, **kwargs)
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS', 'DRIVER_EVENT_ACQUIRE_SAMPLE',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:

            self.assertTrue(state in ret[0])
        self.assertEqual(len(ret[0]), 4)




        # Force State AUTOSAMPLE
        ID._protocol._protocol_fsm.current_state = ProtocolState.AUTOSAMPLE

        ret = ID.get_resource_capabilities(*args, **kwargs)
        for state in ['DRIVER_EVENT_STOP_AUTOSAMPLE']:
            self.assertTrue(state in ret[0])
        self.assertEqual(len(ret[0]), 1)

        # Force State DIRECT_ACCESS
        ID._protocol._protocol_fsm.current_state = ProtocolState.DIRECT_ACCESS

        ret = ID.get_resource_capabilities(*args, **kwargs)
        self.assertEqual(ret[0], [])

    def test_chunker(self):
        """
        Tests the chunker
        """
        # This will want to be created in the driver eventually...
        self._chunker = StringChunker(Protocol.sieve_function)

        self._chunker.add_chunk("p = 429337.7812, t = -3.2164" + NEWLINE +
                                "tide: start time = 23 Oct 2012 01:08:08, p = 429337.8750, pt = 421107.187, t = -3.2164" + NEWLINE +
                                "tide: start time = 22 Oct 2012 23:47:18, p = 429337.9687, pt = 421106.562, t = -3.2164, c = -1.05525, s = 0.000" + NEWLINE +
                                SAMPLE_DATA)

        #result = self._chunker.get_next_data()
        #self.assertEquals(result, 'p = 429337.7812, t = -3.2164\r\n')

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 23 Oct 2012 01:08:08, p = 429337.8750, pt = 421107.187, t = -3.2164\r\n')

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 22 Oct 2012 23:47:18, p = 429337.9687, pt = 421106.562, t = -3.2164, c = -1.05525, s = 0.000\r\n')

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 05 Oct 2012 00:55:54, p = 14.5348, pt = 24.250, t = 23.9046\r\n')

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 05 Oct 2012 00:58:54, p = 14.5367, pt = 24.242, t = 23.8904\r\n')

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 05 Oct 2012 01:01:54, p = 14.5387, pt = 24.250, t = 23.8778\r\n')

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 05 Oct 2012 01:04:54, p = 14.5346, pt = 24.228, t = 23.8664\r\n')

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 05 Oct 2012 01:07:54, p = 14.5364, pt = 24.205, t = 23.8575\r\n')

        # long record
        result = self._chunker.get_next_data()

        result = self._chunker.get_next_data()
        self.assertEquals(result,  'tide: start time = 05 Oct 2012 01:10:54, p = 14.5385, pt = 24.228, t = 23.8404\r\n')

        # stat record
        result = self._chunker.get_next_data()

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 05 Oct 2012 01:13:54, p = 14.5384, pt = 24.205, t = 23.8363\r\n')

        result = self._chunker.get_next_data()
        self.assertEquals(result, None)

        #self.assertTrue(False) # to enable debug output

    def test_chunker_line_by_line(self):
        # This will want to be created in the driver eventually...
        self._chunker = StringChunker(Protocol.sieve_function)

        for line in SAMPLE_DATA.split(NEWLINE):
            log.debug(repr(line + NEWLINE))
            self._chunker.add_chunk(line + NEWLINE)

            result = self._chunker.get_next_data(clean=True)
            log.debug("RESULT ============================================================================================================================================================= " + repr(result))

            result = self._chunker.get_next_data(clean=True)
            log.debug("RESULT ============================================================================================================================================================= " + repr(result))

        #self.assertTrue(False) # to enable debug output

    def test_short_chunker_feed(self):
        # This will want to be created in the driver eventually...
        self._chunker = StringChunker(Protocol.sieve_function)

        result = self._chunker.get_next_data()
        self.assertEquals(result, None)
        '''
        SL/SLO removed.
        self._chunker.add_chunk("p = 429337.7")

        result = self._chunker.get_next_data()
        self.assertEquals(result, None)

        self._chunker.add_chunk("812, t = -3.21")

        result = self._chunker.get_next_data()
        self.assertEquals(result, None)

        self._chunker.add_chunk("64" + NEWLINE)

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'p = 429337.7812, t = -3.2164\r\n')

        '''
        self._chunker.add_chunk("tide: start time = 23 Oct 2012 01:08:08, p = 429")


        result = self._chunker.get_next_data()
        self.assertEquals(result, None)

        # add the tail of one + the head of another
        self._chunker.add_chunk("337.8750, pt = 421107.187, t = -3.2164" + NEWLINE +
                                "tide: start time = 22 Oct 2012 23:47:18, p = 429")

        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 23 Oct 2012 01:08:08, p = 429337.8750, pt = 421107.187, t = -3.2164\r\n')


        # empty add
        self._chunker.add_chunk("")

        result = self._chunker.get_next_data()
        self.assertEquals(result, None)

        self._chunker.add_chunk("337.9687, pt = 421106.562, t = -3.2164, c = -1.05525, s = 0.000" + NEWLINE)


        result = self._chunker.get_next_data()
        self.assertEquals(result, 'tide: start time = 22 Oct 2012 23:47:18, p = 429337.9687, pt = 421106.562, t = -3.2164, c = -1.05525, s = 0.000\r\n')




###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SBE26PlusIntFromIDK(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    ###
    #    Add instrument specific integration tests
    ###

    def assertParamDict(self, pd, all_params=False):
        """
        Verify all device parameters exist and are correct type.
        """

        # Make it loop through once to warn with debugging of issues, 2nd time can send the exception
        # PARAMS is the master type list

        if all_params:
            log.debug("DICT 1 *********" + str(pd.keys()))
            log.debug("DICT 2 *********" + str(PARAMS.keys()))
            self.assertEqual(set(pd.keys()), set(PARAMS.keys()))

            for (key, type_val) in PARAMS.iteritems():
                self.assertTrue(isinstance(pd[key], type_val))
        else:
            for (key, val) in pd.iteritems():
                self.assertTrue(PARAMS.has_key(key))

                if val is not None: # If its not defined, lets just skip it, only catch wrong type assignments.
                    log.debug("Asserting that " + key +  " is of type " + str(PARAMS[key]))
                    self.assertTrue(isinstance(val, PARAMS[key]))
                else:
                    log.debug("*** Skipping " + key + " Because value is None ***")

    # need to rename this to a better name
    def assert_returned_parameters_match_set_parameters(self, params, reply):
        for label in params.keys():
            log.debug("ASSERTING " + label + " = " + str(params[label]) + " == " + str(reply[label]))
            try:
                self.assertEqual(params[label], reply[label])
            except:
                log.debug(label + " WAS NOT IN 'reply' " + str(reply))

    # WORKS TUE
    def test_get_set(self):
        """
        Test device parameter access.
        """

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)
        
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Test 1 Conductivity = Y, small subset of possible parameters.

        log.debug("get/set Test 1 - Conductivity = Y, small subset of possible parameters.")
        params = {
            Parameter.CONDUCTIVITY : True,
            Parameter.TXWAVESTATS : False
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 2 - Conductivity = N, small subset of possible parameters.")
        params = {
            Parameter.CONDUCTIVITY : False,
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 3 - internal temperature sensor, small subset of possible parameters.")
        params = {
            Parameter.DS_DEVICE_DATE_TIME : time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime()))),
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : False,
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 4 - external temperature sensor, small subset of possible parameters.")
        params = {
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : True,
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)

        log.debug("get/set Test 5 - get master set of possible parameters.")
        params = [
            # DS
            Parameter.DEVICE_VERSION,
            Parameter.SERIAL_NUMBER,
            Parameter.DS_DEVICE_DATE_TIME,
            Parameter.USER_INFO,
            Parameter.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER,
            Parameter.QUARTZ_PRESSURE_SENSOR_RANGE,
            Parameter.EXTERNAL_TEMPERATURE_SENSOR,
            Parameter.CONDUCTIVITY,
            Parameter.IOP_MA,
            Parameter.VMAIN_V,
            Parameter.VLITH_V,
            Parameter.LAST_SAMPLE_P,
            Parameter.LAST_SAMPLE_T,
            Parameter.LAST_SAMPLE_S,

            # DS/SETSAMPLING
            Parameter.TIDE_INTERVAL,
            Parameter.TIDE_MEASUREMENT_DURATION,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS,
            Parameter.WAVE_SAMPLES_PER_BURST,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND,
            Parameter.USE_START_TIME,
            #Parameter.START_TIME,
            Parameter.USE_STOP_TIME,
            #Parameter.STOP_TIME,
            Parameter.TXWAVESTATS,
            Parameter.TIDE_SAMPLES_PER_DAY,
            Parameter.WAVE_BURSTS_PER_DAY,
            Parameter.MEMORY_ENDURANCE,
            Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE,
            Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS,
            Parameter.TOTAL_RECORDED_WAVE_BURSTS,
            Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START,
            Parameter.WAVE_BURSTS_SINCE_LAST_START,
            Parameter.TXREALTIME,
            Parameter.TXWAVEBURST,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC,
            Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR,
            Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR,
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND,
            Parameter.MIN_ALLOWABLE_ATTENUATION,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM,
            Parameter.HANNING_WINDOW_CUTOFF,
            Parameter.SHOW_PROGRESS_MESSAGES,
            Parameter.STATUS,
            Parameter.LOGGING,
        ]

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)

        log.debug("get/set Test 6 - get master set of possible parameters using array containing Parameter.ALL")


        params3 = [
            Parameter.ALL
        ]

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 7 - Negative testing, broken values. Should get exception")
        params = {
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : 5,

        }
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set_resource', params)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)


        log.debug("get/set Test 8 - Negative testing, broken labels. Should get exception")
        params = {
            "ROGER" : 5,
            "PETER RABBIT" : True,
            "WEB" : float(2.0),
        }
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set_resource', params)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)


        log.debug("get/set Test 9 - Negative testing, empty params dict")
        params = {
        }

        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


        log.debug("get/set Test 10 - Negative testing, None instead of dict")
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set_resource', None)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)



        log.debug("get/set Test N - Conductivity = Y, full set of set variables to known sane values.")
        params = {
            Parameter.DS_DEVICE_DATE_TIME : time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime()))),
            Parameter.USER_INFO : "whoi",
            Parameter.TXREALTIME : True,
            Parameter.TXWAVEBURST : True,
            Parameter.CONDUCTIVITY : True,
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : True,
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assertParamDict(reply)


    # WORKS TUE
    def test_set_sampling(self):
        """
        @brief Test device setsampling.

        setsampling functionality now handled via set.  Below test converted to use set.
        """
        parameter_all = [
            Parameter.ALL
        ]

        # Test the driver is in state unconfigured.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.UNCONFIGURED)

        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, DriverConnectionState.DISCONNECTED)

        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.UNKNOWN)

        reply = self.driver_client.cmd_dvr('discover_state')
        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        # Critical that for this test conductivity be in a known state.
        # Need to add a second testing section to test with Conductivity = False
        new_params = {
            Parameter.CONDUCTIVITY : True,
        }
        reply = self.driver_client.cmd_dvr('set_resource', new_params)

        # POSITIVE TESTING

        log.debug("setsampling Test 1 - TXWAVESTATS = N, small subset of possible parameters.")

        sampling_params = {
            Parameter.TIDE_INTERVAL : 18,
            Parameter.TXWAVESTATS : False,
            }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.SETSAMPLING, sampling_params)

        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', parameter_all)




        """
        Test 1: TXWAVESTATS = N
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000
                * Number of wave samples per burst
                    - Range 4 - 60,000
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0]
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
        """

        log.debug("TEST 2 - TXWAVESTATS = N, full set of possible parameters")

        sampling_params = {
            Parameter.TIDE_INTERVAL : 9,
            Parameter.TIDE_MEASUREMENT_DURATION : 540,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(4.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False,
        }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)
        reply = self.driver_client.cmd_dvr('set_resource', sampling_params)

        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', parameter_all)

        """
        Test 2: TXWAVESTATS = Y
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000
                * Number of wave samples per burst
                    - Range 4 - 60,000
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0]
                    - USE WAVE_SAMPLES_SCANS_PER_SECOND instead
                      where WAVE_SAMPLES_SCANS_PER_SECOND = 1 / wave_sample_duration
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
                    - Range [y, n]
                    OPTIONAL DEPENDING ON TXWAVESTATS
                    * Show progress messages
                      - Range [y, n]
                    * Number of wave samples per burst to use for wave
                      statistics
                      - Range > 512, power of 2...
                    * Use measured temperature and conductivity for
                      density calculation
                      - Range [y,n]
                    * Average water temperature above the pressure sensor
                      - Degrees C
                    * Height of pressure sensor from bottom
                      - Distance Meters
                    * Number of spectral estimates for each frequency
                      band
                      - You may have used Plan Deployment to determine
                        desired value
                    * Minimum allowable attenuation
                    * Minimum period (seconds) to use in auto-spectrum
                      Minimum of the two following
                      - frequency where (measured pressure / pressure at
                        surface) < (minimum allowable attenuation / wave
                        sample duration).
                      - (1 / minimum period). Frequencies > fmax are not
                        processed.
                    * Maximum period (seconds) to use in auto-spectrum
                       - ( 1 / maximum period). Frequencies < fmin are
                         not processed.
                    * Hanning window cutoff
                       - Hanning window suppresses spectral leakage that
                         occurs when time series to be Fourier transformed
                         contains periodic signal that does not correspond
                         to one of exact frequencies of FFT.
        """
        for x in range(0,3):
            log.debug("***")
        log.debug("TEST 2 - TXWAVESTATS = N")
        for x in range(0,3):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 18, #1,
            Parameter.TIDE_MEASUREMENT_DURATION : 1080,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : True,
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: 10.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION : 1.0,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.HANNING_WINDOW_CUTOFF : 1.0
            }



        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        #reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.SETSAMPLING, sampling_params)
        reply = self.driver_client.cmd_dvr('set_resource', sampling_params)

        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', parameter_all)

        """
        Test 3: These 2 prompts appears only if you enter N for using measured T and C for density calculation
                Average water temperature above the pressure sensor (Deg C) = 15.0, new value =
                Average salinity above the pressure sensor (PSU) = 35.0, new value =

        """
        for x in range(0,3):
            log.debug("***")
        log.debug("TEST 3 - TXWAVESTATS = N, USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC=N")
        for x in range(0,3):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 18, #4,
            Parameter.TIDE_MEASUREMENT_DURATION : 1080, #40,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 1,
            Parameter.WAVE_SAMPLES_PER_BURST : 1024,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(1.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : True,
            Parameter.SHOW_PROGRESS_MESSAGES : True,
            Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS : 512,
            Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC : False,
            Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR : float(15.0),
            Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR : float(37.6),
            Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: 10.0,
            Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND : 1,
            Parameter.MIN_ALLOWABLE_ATTENUATION : 1.0,
            Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM : 1.0,
            Parameter.HANNING_WINDOW_CUTOFF : 1.0
        }



        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.SETSAMPLING, sampling_params)

        self.assertEqual(reply, None)

        # Alternate specification for all params
        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        """

        Test 1B: TXWAVESTATS = N, NEGATIVE TESTING
            Set:
                * Tide interval (integer minutes)
                    - Range 1 - 720 (SEND OUT OF RANGE HIGH)
                * Tide measurement duration (seconds)
                    - Range: 10 - 43200 sec (SEND OUT OF RANGE LOW)
                * Measure wave burst after every N tide samples
                    - Range 1 - 10,000 (SEND OUT OF RANGE HIGH)
                * Number of wave samples per burst
                    - Range 4 - 60,000 (SEND OUT OF RANGE LOW)
                * wave sample duration
                    - Range [0.25, 0.5, 0.75, 1.0] (SEND OUT OF RANGE HIGH)
                    - USE WAVE_SAMPLES_SCANS_PER_SECOND instead
                      where WAVE_SAMPLES_SCANS_PER_SECOND = 1 / wave_sample_duration
                * use start time
                    - Range [y, n]
                * use stop time
                    - Range [y, n]
                * TXWAVESTATS (real-time wave statistics)
        """

        for x in range(0,30):
            log.debug("***")
        log.debug("Test 1B: TXWAVESTATS = N, NEGATIVE TESTING")
        log.debug("Need to decide to test and throw exception on out of range, or what?")
        for x in range(0,30):
            log.debug("***")
        sampling_params = {
            Parameter.TIDE_INTERVAL : 800,
            Parameter.TIDE_MEASUREMENT_DURATION : 1,
            Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS : 20000,
            Parameter.WAVE_SAMPLES_PER_BURST : 1,
            Parameter.WAVE_SAMPLES_SCANS_PER_SECOND : float(2.0),
            Parameter.USE_START_TIME : False,
            Parameter.USE_STOP_TIME : False,
            Parameter.TXWAVESTATS : False,
            }

        # Set parameters and verify.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)

        exception = False
        try:
            #reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.SETSAMPLING, sampling_params)
            reply = self.driver_client.cmd_dvr('set_resource', sampling_params)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)

        reply = self.driver_client.cmd_dvr('get_resource', parameter_all)

    # WORKS TUE
    def test_take_sample(self):
        """
        @brief Test device parameter access.
        """

        self.put_instrument_in_command_mode()

        # take a sample.
        sample = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
        TS_REGEX = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)' # .*?\r\n
        TS_REGEX_MATCHER = re.compile(TS_REGEX)
        matches = TS_REGEX_MATCHER.match(sample)

        log.debug("COUNT = " + str(len(matches.groups())))
        self.assertEqual(3, len(matches.groups()))

    # WORKS TUE
    def test_init_logging(self):
        """
        @brief Test initialize logging command.
        """
        self.put_instrument_in_command_mode()

        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.INIT_LOGGING)

        self.assertTrue(reply)

    # WORKS TUE
    def test_quit_session(self):
        """
        @brief Test quit session command.
        """

        self.put_instrument_in_command_mode()


        # Note quit session just sleeps the device, so its safe to remain in COMMAND mode.
        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.QUIT_SESSION)

        self.assertEqual(reply, None)

        # Must stay in COMMAND state (but sleeping)
        self.check_state(ProtocolState.COMMAND)
        # now can we return to command state?

        params = [
            Parameter.ALL
        ]
        reply = self.driver_client.cmd_dvr('get_resource', params)
        self.assertParamDict(reply)

    # WORKS TUE
    def test_get_resource_capabilities(self):
        """
        Test get resource capabilities.
        """
        # Test the driver is in state unconfigured.
        self.put_instrument_in_command_mode()

        # COMMAND
        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS', 'DRIVER_EVENT_ACQUIRE_SAMPLE',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 4)

        # Verify all paramaters are present in res_params

        # DS
        self.assertTrue(Parameter.DEVICE_VERSION in res_params)
        self.assertTrue(Parameter.SERIAL_NUMBER in res_params)
        self.assertTrue(Parameter.DS_DEVICE_DATE_TIME in res_params)
        self.assertTrue(Parameter.USER_INFO in res_params)
        self.assertTrue(Parameter.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER in res_params)
        self.assertTrue(Parameter.QUARTZ_PRESSURE_SENSOR_RANGE in res_params)
        self.assertTrue(Parameter.EXTERNAL_TEMPERATURE_SENSOR in res_params)
        self.assertTrue(Parameter.CONDUCTIVITY in res_params)
        self.assertTrue(Parameter.IOP_MA in res_params)
        self.assertTrue(Parameter.VMAIN_V in res_params)
        self.assertTrue(Parameter.VLITH_V in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_P in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_T in res_params)
        self.assertTrue(Parameter.LAST_SAMPLE_S in res_params)

        # DS/SETSAMPLING
        self.assertTrue(Parameter.TIDE_INTERVAL in res_params)
        self.assertTrue(Parameter.TIDE_MEASUREMENT_DURATION in res_params)
        self.assertTrue(Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS in res_params)
        self.assertTrue(Parameter.WAVE_SAMPLES_PER_BURST in res_params)
        self.assertTrue(Parameter.WAVE_SAMPLES_SCANS_PER_SECOND in res_params)
        self.assertTrue(Parameter.USE_START_TIME in res_params)
        #Parameter.START_TIME,
        self.assertTrue(Parameter.USE_STOP_TIME in res_params)
        #Parameter.STOP_TIME,
        self.assertTrue(Parameter.TXWAVESTATS in res_params)
        self.assertTrue(Parameter.TIDE_SAMPLES_PER_DAY in res_params)
        self.assertTrue(Parameter.WAVE_BURSTS_PER_DAY in res_params)
        self.assertTrue(Parameter.MEMORY_ENDURANCE in res_params)
        self.assertTrue(Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE in res_params)
        self.assertTrue(Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS in res_params)
        self.assertTrue(Parameter.TOTAL_RECORDED_WAVE_BURSTS in res_params)
        self.assertTrue(Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START in res_params)
        self.assertTrue(Parameter.WAVE_BURSTS_SINCE_LAST_START in res_params)
        self.assertTrue(Parameter.TXREALTIME in res_params)
        self.assertTrue(Parameter.TXWAVEBURST in res_params)
        self.assertTrue(Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS in res_params)
        self.assertTrue(Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC in res_params)
        self.assertTrue(Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC in res_params)
        self.assertTrue(Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR in res_params)
        self.assertTrue(Parameter.AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR in res_params)
        self.assertTrue(Parameter.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM in res_params)
        self.assertTrue(Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND in res_params)
        self.assertTrue(Parameter.MIN_ALLOWABLE_ATTENUATION in res_params)
        self.assertTrue(Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM in res_params)
        self.assertTrue(Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM in res_params)
        self.assertTrue(Parameter.HANNING_WINDOW_CUTOFF in res_params)
        self.assertTrue(Parameter.SHOW_PROGRESS_MESSAGES in res_params)
        self.assertTrue(Parameter.STATUS in res_params)
        self.assertTrue(Parameter.LOGGING in res_params)

        reply = self.driver_client.cmd_dvr('execute_resource', Capability.START_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.AUTOSAMPLE)


        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_STOP_AUTOSAMPLE']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 1)
        reply = self.driver_client.cmd_dvr('execute_resource', Capability.STOP_AUTOSAMPLE)

        # Test the driver is in command mode.
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, ProtocolState.COMMAND)


        (res_cmds, res_params) = self.driver_client.cmd_dvr('get_resource_capabilities')
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS', 'DRIVER_EVENT_ACQUIRE_SAMPLE',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:
            self.assertTrue(state in res_cmds)
        self.assertEqual(len(res_cmds), 4)

    # WORKS TUE
    def test_connect_configure_disconnect(self):
        """
        @ BRIEF connect and then disconnect, verify state
        """

        self.put_instrument_in_command_mode()

        reply = self.driver_client.cmd_dvr('disconnect')
        self.assertEqual(reply, None)

        self.check_state(DriverConnectionState.DISCONNECTED)

    # WORKS TUE
    def test_bad_commands(self):
        """
        @brief test that bad commands are handled with grace and style.
        """

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Test bad commands in UNCONFIGURED state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr('conquer_the_world')
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("1 - conquer_the_world - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

        # Test the driver is configured for comms.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        self.check_state(DriverConnectionState.DISCONNECTED)

        # Test bad commands in DISCONNECTED state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr('test_the_waters')
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("2 - test_the_waters - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)


        # Test the driver is in unknown state.
        reply = self.driver_client.cmd_dvr('connect')
        self.check_state(ProtocolState.UNKNOWN)

        # Test bad commands in UNKNOWN state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr("skip_to_the_loo")
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("3 - skip_to_the_loo - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)



        # Test the driver is in command mode.
        reply = self.driver_client.cmd_dvr('discover_state')

        self.check_state(ProtocolState.COMMAND)


        # Test bad commands in COMMAND state.

        exception_happened = False
        try:
            state = self.driver_client.cmd_dvr("... --- ..., ... --- ...")
        except InstrumentCommandException as ex:
            exception_happened = True
            log.debug("4 - ... --- ..., ... --- ... - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

    # FAILS TUE
    def assert_sample_dict(self, sample):
        """
        @brief validate that a sample contains the correct fields.
        """
        log.error("SAMPLE = " + repr(sample))
        self.assertTrue('stream_name' in sample.keys())
        self.assertTrue('parsed' in sample.keys())
        self.assertTrue('p' in sample['parsed'].keys())
        self.assertTrue('t' in sample['parsed'].keys())
        self.assertTrue('pt' in sample['parsed'].keys())

    # FAILS TUE
    def test_poll(self):
        """
        @brief Test sample polling commands and events.
        also tests execute_resource
        """
        # Test the driver is in state unconfigured.
        self.put_instrument_in_command_mode()


        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE = " + repr(reply[1]))
        self.assert_sample_dict(reply[1])

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE = " + repr(reply))
        self.assert_sample_dict(reply)

        # Poll for a sample and confirm result.
        reply = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE = " + repr(reply))
        self.assert_sample_dict(reply)

        # Confirm that 3 samples arrived as published events.
        gevent.sleep(1)
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]
        # @TODO Set this properly (3) when only one set of events are sent
        self.assertEqual(len(sample_events), 6)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

    # WORKS TUE
    def test_connect(self):
        """
        Test configuring and connecting to the device through the port
        agent. Discover device state.
        """
        log.info("test_connect test started")
        self.put_instrument_in_command_mode()

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Initialize the driver and transition to unconfigured.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

    # WORKS TUE
    def test_clock_sync(self):
        self.put_instrument_in_command_mode()
        self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.CLOCK_SYNC)
        self.check_state(ProtocolState.COMMAND)

    def check_state(self, desired_state):
        state = self.driver_client.cmd_dvr('get_resource_state')
        self.assertEqual(state, desired_state)

    def put_instrument_in_command_mode(self):
        log.info("test_connect test started")

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('configure', self.port_agent_comm_config())

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('connect')

        # Test the driver is in unknown state.
        self.check_state(ProtocolState.UNKNOWN)

        # Configure driver for comms and transition to disconnected.
        reply = self.driver_client.cmd_dvr('discover_state')

        # Test the driver is in command mode.
        self.check_state(ProtocolState.COMMAND)


###############################################################################
#                            QUALIFICATION TESTS                              #
# Device specific qualification tests are for                                 #
# testing device specific capabilities                                        #
###############################################################################
@attr('QUAL', group='mi')
class SBE26PlusQualFromIDK(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def check_state(self, desired_state):
        current_state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(current_state, desired_state)

    def assertSampleDataParticle(self, potential_sample):
        # NEED TO WRITE THIS USING
        # https://github.com/ooici/marine-integrations/blob/master/mi/instrument/satlantic/par_ser_600m/test/test_driver.py as a guide.



        """
        SBE26plusTakeSampleDataParticle
        {
            "driver_timestamp": 3560540410.0512133,
            "pkt_format_id": "JSON_Data",
            "pkt_version": 1,
            "preferred_timestamp": "driver_timestamp",
            "quality_flag": "ok",
            "stream_name": "parsed",
            "values": [
                {"value": -158.5166, "value_id": "preasure"},
                {"value": -8392.3, "value_id": "preasure_temp"},
                {"value": -3.2164, "value_id": "temperature"},
                {"value": -1.02535, "value_id": "conductivity"},
                {"value": 0.0, "value_id": "salinity"}
            ]
        }

        SBE26plusTideSampleDataParticle
        {
            "driver_timestamp": 3560627929.598382,
            "pkt_format_id": "JSON_Data",
            "pkt_version": 1,
            "preferred_timestamp": "driver_timestamp",
            "quality_flag": "ok",
            "stream_name": "parsed",
            "values": [
                {"value": 3560653116.0, "value_id": "timestamp"},
                {"value": 429339.0312, "value_id": "pressure"},
                {"value": 421097.5, "value_id": "pressure_temp"},
                {"value": -3.2164, "value_id": "temperature"},
                {"value": -1.05525, "value_id": "conductivity"},
                {"value": 0.0, "value_id": "salinity"}
            ]
        }

        SBE26plusWaveBurstDataParticle

        ????

        SBE26plusStatisticsDataParticle

        ????

        SBE26plusDeviceCalibrationDataParticle
        {
            "driver_timestamp": 3560540530.089334,
            "pkt_format_id": "JSON_Data",
            "pkt_version": 1,
            "preferred_timestamp": "driver_timestamp",
            "quality_flag": "ok",
            "stream_name": "parsed",
            "values": [
                {"value": 41943.0, "value_id": "FACTORY_M"},
                {"value": 2796.2, "value_id": "FACTORY_B"},
                {"value": -3845.795, "value_id": "PY1"},
                {"value": -10829.41, "value_id": "PY2"},
                {"value": 0.0, "value_id": "PY3"},
                {"value": [2, 4, 2012], "value_id": "PCALDATE"},
                {"value": null, "value_id": "CPCOR"},
                {"value": 5.827424, "value_id": "PU0"},
                {"value": null, "value_id": "CSLOPE"},
                {"value": null, "value_id": "CCALDATE"},
                {"value": -0.1877, "value_id": "POFFSET"},
                {"value": [30, 3, 2012], "value_id": "TCALDATE"},
                {"value": 0.0, "value_id": "PD2"},
                {"value": 0.025294, "value_id": "PD1"},
                {"value": null, "value_id": "CJ"},
                {"value": null, "value_id": "CI"},
                {"value": null, "value_id": "CH"},
                {"value": 0.0002557341, "value_id": "TA0"},
                {"value": 0.0002493547, "value_id": "TA1"},
                {"value": -1.567218e-06, "value_id": "TA2"},
                {"value": 1.508124e-07, "value_id": "TA3"},
                {"value": null, "value_id": "CG"},
                {"value": null, "value_id": "CTCOR"},
                {"value": 31.09619, "value_id": "PT4"},
                {"value": 17.52851, "value_id": "PT3"},
                {"value": 0.391138, "value_id": "PT2"},
                {"value": 27.77282, "value_id": "PT1"},
                {"value": 37.41653, "value_id": "PC2"},
                {"value": -4014.654, "value_id": "PC3"},
                {"value": 2123.771, "value_id": "PC1"}
            ]
        }

        SBE26plusDeviceStatusDataParticle

        {
            "driver_timestamp": 3560540530.18097,
            "pkt_format_id": "JSON_Data",
            "pkt_version": 1,
            "preferred_timestamp": "driver_timestamp",
            "quality_flag": "ok",
            "stream_name": "parsed",
            "values": [
                {"value": 0.1, "value_id": "HANNING_WINDOW_CUTOFF"},
                {"value": 300.0, "value_id": "QUARTZ_PRESSURE_SENSOR_RANGE"},
                {"value": 11.0, "value_id": "TIDE_MEASUREMENTS_SINCE_LAST_START"},
                {"value": 6.0, "value_id": "TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS"},
                {"value": false, "value_id": "USE_STOP_TIME"},
                {"value": "05 OCT 2012  17:19:27", "value_id": "DateTime"},
                {"value": 272.8, "value_id": "NOMINAL_ALKALINE_BATTERY_ENDURANCE"},
                {"value": 3, "value_id": "TIDE_INTERVAL"},
                {"value": 4.0, "value_id": "WAVE_SAMPLES_SCANS_PER_SECOND"},
                {"value": 1000000.0, "value_id": "MAX_PERIOD_IN_AUTO_SPECTRUM"},
                {"value": 122094.0, "value_id": "QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER"},
                {"value": false, "value_id": "CONDUCTIVITY"},
                {"value": 258.0, "value_id": "MEMORY_ENDURANCE"},
                {"value": 80.0, "value_id": "WAVE_BURSTS_PER_DAY"},
                {"value": "6.1E", "value_id": "DEVICE_VERSION"},
                {"value": true, "value_id": "TxTide"},
                {"value": 10.0, "value_id": "PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM"},
                {"value": 23.8155, "value_id": "LAST_SAMPLE_T"},
                {"value": 512, "value_id": "NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS"},
                {"value": 14.5361, "value_id": "LAST_SAMPLE_P"},
                {"value": null, "value_id": "LAST_SAMPLE_S"},
                {"value": 5, "value_id": "SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND"},
                {"value": "STOPPED", "value_id": "STATUS"},
                {"value": null, "value_id": "AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR"},
                {"value": false, "value_id": "LOGGING"},
                {"value": 512, "value_id": "WAVE_SAMPLES_PER_BURST"},
                {"value": 60, "value_id": "TIDE_MEASUREMENT_DURATION"},
                {"value": 0.0, "value_id": "MIN_PERIOD_IN_AUTO_SPECTRUM"},
                {"value": true, "value_id": "SHOW_PROGRESS_MESSAGES"},
                {"value": true, "value_id": "TxWave"},
                {"value": 1.0, "value_id": "WAVE_BURSTS_SINCE_LAST_START"},
                {"value": 0.0025, "value_id": "MIN_ALLOWABLE_ATTENUATION"},
                {"value": true, "value_id": "TXWAVESTATS"},
                {"value": false, "value_id": "USE_MEASURED_TEMP_FOR_DENSITY_CALC"},
                {"value": false, "value_id": "ExternalTemperature"},
                {"value": 5982.0, "value_id": "TOTAL_RECORDED_TIDE_MEASUREMENTS"},
                {"value": 4525.0, "value_id": "TOTAL_RECORDED_WAVE_BURSTS"},
                {"value": null, "value_id": "USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC"},
                {"value": false, "value_id": "USE_START_TIME"},
                {"value": 7.4, "value_id": "IOP_MA"},
                {"value": "OOI", "value_id": "USERINFO"},
                {"value": 9.0, "value_id": "VLITH_V"},
                {"value": "1329", "value_id": "SERIAL_NUMBER"},
                {"value": 480.0, "value_id": "TIDE_SAMPLES_PER_DAY"},
                {"value": 16.2, "value_id": "VMAIN_V"},
                {"value": null, "value_id": "AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR"}
            ]
        }
        """









        if (isinstance(potential_sample, SBE26plusTakeSampleDataParticle)):
            particle_instance = True
            log.debug("GOT A SBE26plusTakeSampleDataParticle")
            sample_dict = json.loads(val.generate_parsed())

            self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
                DataParticleValue.PARSED)
            self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
                DataParticleValue.JSON_DATA)
            self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
            self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
                list))
            self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
            self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

            for x in sample_dict['values']:
                self.assertTrue(x['value_id'] in ['preasure', 'preasure_temp', 'temperature', 'conductivity', 'salinity'])
                self.assertTrue(isinstance(x['value'], float))


        elif (isinstance(potential_sample, SBE26plusTideSampleDataParticle)):
            particle_instance = True
            log.debug("GOT A SBE26plusTideSampleDataParticle")
            sample_dict = json.loads(val.generate_parsed())

            self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
                DataParticleValue.PARSED)
            self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
                DataParticleValue.JSON_DATA)
            self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
            self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
                list))
            self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
            self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

            for x in sample_dict['values']:
                self.assertTrue(x['value_id'] in ['timestamp', 'preasure', 'preasure_temp', 'temperature', 'conductivity', 'salinity'])
                self.assertTrue(isinstance(x['value'], float))


        elif (isinstance(potential_sample, SBE26plusWaveBurstDataParticle)):
            particle_instance = True
            log.debug("GOT A SBE26plusWaveBurstDataParticle")
            sample_dict = json.loads(val.generate_parsed())

            self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
                DataParticleValue.PARSED)
            self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
                DataParticleValue.JSON_DATA)
            self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
            self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
                list))
            self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
            self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

            for x in sample_dict['values']:
                self.assertTrue(x['value_id'] in ['timestamp', 'ptfreq', 'ptraw'])
                if x['value_id'] != 'ptraw':
                    self.assertTrue(isinstance(x['value'], float))
                else:
                    self.assertTrue(isinstance(x['value'], list))


        elif (isinstance(potential_sample, SBE26plusStatisticsDataParticle)):
            particle_instance = True
            log.debug("GOT A SBE26plusStatisticsDataParticle")
            sample_dict = json.loads(val.generate_parsed())

            self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
                DataParticleValue.PARSED)
            self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
                DataParticleValue.JSON_DATA)
            self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
            self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
                list))
            self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
            self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

            for x in sample_dict['values']:
                self.assertTrue(x['value_id'] in ["depth", "temperature", "salinity","density", "nAvgBand",
                                                  "total_variance", "total_energy", "significant_period",
                                                  "significant_wave_height", "tss_wave_integration_time",
                                                  "tss_number_of_waves", "tss_total_variance", "tss_total_energy",
                                                  "tss_average_wave_height", "tss_average_wave_period",
                                                  "tss_maximum_wave_height", "tss_significant_wave_height",
                                                  "tss_significant_wave_period", "tss_height_highest_10_percent_waves",
                                                  "tss_height_highest_1_percent_waves"])
                self.assertTrue(isinstance(x['value'], float))




        elif (isinstance(potential_sample, SBE26plusDeviceCalibrationDataParticle)):
            particle_instance = True
            log.debug("GOT A SBE26plusDeviceCalibrationDataParticle")
            sample_dict = json.loads(val.generate_parsed())

            self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
                DataParticleValue.PARSED)
            self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
                DataParticleValue.JSON_DATA)
            self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
            self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
                list))
            self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
            self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

            for x in sample_dict['values']:
                self.assertTrue(x['value_id'] in ['PCALDATE', 'PU0', 'PY1', 'PY2', 'PY3', 'PC1'
                                                  'PC2', 'PC3', 'PD1', 'PD2', 'PT1', 'PT2', 'PT3',
                                                  'PT4', 'FACTORY_M', 'FACTORY_B', 'POFFSET',
                                                  'TCALDATE', 'TA0', 'TA1', 'TA2', 'TA3',
                                                  'CCALDATE', 'CG', 'CH', 'CI', 'CJ', 'CTCOR',
                                                  'CPCOR', 'CSLOPE'])
                if x['value_id'] in ['PCALDATE', 'TCALDATE', 'CCALDATE']:
                    self.assertTrue(isinstance(x['value'], tuple))
                else:
                    self.assertTrue(isinstance(x['value'], float))


        elif (isinstance(potential_sample, SBE26plusDeviceStatusDataParticle)):
            particle_instance = True
            log.debug("GOT A SBE26plusDeviceStatusDataParticle")
            sample_dict = json.loads(val.generate_parsed())

            self.assertTrue(sample_dict[DataParticleKey.STREAM_NAME],
                DataParticleValue.PARSED)
            self.assertTrue(sample_dict[DataParticleKey.PKT_FORMAT_ID],
                DataParticleValue.JSON_DATA)
            self.assertTrue(sample_dict[DataParticleKey.PKT_VERSION], 1)
            self.assertTrue(isinstance(sample_dict[DataParticleKey.VALUES],
                list))
            self.assertTrue(isinstance(sample_dict.get(DataParticleKey.DRIVER_TIMESTAMP), float))
            self.assertTrue(sample_dict.get(DataParticleKey.PREFERRED_TIMESTAMP))

            for x in sample_dict['values']:
                self.assertTrue(x['value_id'] in [
                    'QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER', 'QUARTZ_PRESSURE_SENSOR_RANGE', 'IOP_MA',
                    'VMAIN_V', 'VLITH_V', 'LAST_SAMPLE_P', 'LAST_SAMPLE_T', 'LAST_SAMPLE_S',
                    'WAVE_SAMPLES_PER_BURST', 'WAVE_SAMPLES_SCANS_PER_SECOND', 'TIDE_SAMPLES_PER_DAY',
                    'WAVE_BURSTS_PER_DAY', 'MEMORY_ENDURANCE', 'NOMINAL_ALKALINE_BATTERY_ENDURANCE',
                    'TOTAL_RECORDED_TIDE_MEASUREMENTS', 'TOTAL_RECORDED_WAVE_BURSTS',
                    'TIDE_MEASUREMENTS_SINCE_LAST_START', 'WAVE_BURSTS_SINCE_LAST_START',
                    'PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM', 'MIN_ALLOWABLE_ATTENUATION',
                    'MIN_PERIOD_IN_AUTO_SPECTRUM', 'MAX_PERIOD_IN_AUTO_SPECTRUM',
                    'HANNING_WINDOW_CUTOFF',
                    'AVERAGE_WATER_TEMPERATURE_ABOVE_PRESSURE_SENSOR',
                    'AVERAGE_SALINITY_ABOVE_PRESSURE_SENSOR',
                    'DEVICE_VERSION', 'SERIAL_NUMBER', 'DateTime',
                    'USERINFO', 'STATUS',
                    'ExternalTemperature', 'CONDUCTIVITY', 'USE_START_TIME',
                    'USE_STOP_TIME', 'TXWAVESTATS', 'TxTide', 'TxWave',
                    'USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC',
                    'SHOW_PROGRESS_MESSAGES', 'LOGGING',
                    'USE_MEASURED_TEMP_FOR_DENSITY_CALC',
                    'TIDE_INTERVAL', 'TIDE_MEASUREMENT_DURATION',
                    'TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS',
                    'NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS',
                    'SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND'
                ])
                if x['value_id'] in [
                    'DEVICE_VERSION', 'SERIAL_NUMBER', 'DateTime',
                    'USERINFO', 'STATUS'
                ]:
                    self.assertTrue(isinstance(x['value'], str))
                elif x['value_id'] in [
                    'ExternalTemperature', 'CONDUCTIVITY', 'USE_START_TIME',
                    'USE_STOP_TIME', 'TXWAVESTATS', 'TxTide', 'TxWave',
                    'USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC',
                    'SHOW_PROGRESS_MESSAGES', 'LOGGING',
                    'USE_MEASURED_TEMP_FOR_DENSITY_CALC'
                ]:
                    self.assertTrue(isinstance(x['value'], bool))
                elif x['value_id'] in [
                    'TIDE_INTERVAL', 'TIDE_MEASUREMENT_DURATION',
                    'TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS',
                    'NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS',
                    'SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND'
                ]:
                    self.assertTrue(isinstance(x['value'], int))
                else:
                    self.assertTrue(isinstance(x['value'], float))


        else:
            particle_instance = False
            log.debug("Was not a known particle instance!")
            log.debug("POTENTIAL_SAMPLE_PARTICLE = " + str(potential_sample))

    ###
    #    Add instrument specific qualification tests
    ###


    # AUTO SAMPLE IS VERY SLOW.
    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 6000}}})
    # TUE BROKE - may have been in autosample mode already
    def test_autosample(self):
        """
        @brief Test instrument driver execute interface to start and stop streaming
        mode.

        @TODO needs to be fixed once the IDK data_subscribers and event_subscribers are fixed
        """

        log.debug("INFO BULLETIN, THIS JUST IN, starting data subscribers")
        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)


        self.assert_enter_command_mode()

        params = {
            Parameter.TIDE_INTERVAL : 3,
            Parameter.TXWAVESTATS : False,
            Parameter.USER_INFO : "KILROY WAZ HERE"
        }

        self.instrument_agent_client.set_resource(params)


        self.data_subscribers.no_samples = 3

        # Begin streaming.
        cmd = AgentCommand(command=ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)



        non_accurate_seconds_count = 0
        log.debug("INFO BULLETIN, THIS JUST IN, Clearing the que")
        self.data_subscribers.clear_sample_queue(DataParticleValue.PARSED)
        log.debug("INFO BULLETIN, THIS JUST IN, que cleared")

        while len(self.data_subscribers.samples_received) <= self.data_subscribers.no_samples and non_accurate_seconds_count < 1200:
            gevent.sleep(10)
            #log.debug("SAMPLES RECEIVED => " + str(self.data_subscribers.__dict__)) # .keys()
            #log.debug("EVENTS RECEIVED => " + str(self.event_subscribers.__dict__))

            log.debug("INFO BULLETIN, THIS JUST IN, I should be holding until I get 1 sample in...")
            samples = self.data_subscribers.get_samples(DataParticleValue.PARSED, 1, timeout=120)

            log.debug("len(samples) => " + str(len(samples)))

            non_accurate_seconds_count = non_accurate_seconds_count + 10


        # Halt streaming.
        cmd = AgentCommand(command=ProtocolEvent.STOP_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        # Assert we got some samples.
        #self.assertTrue(self.data_subscribers.samples_received > self.data_subscribers.no_samples)
        #self.assertTrue(non_accurate_seconds_count < 1200)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

    # WORKS TUE
    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_direct_access_start_telnet()
        self.assertTrue(self.tcp_client)

        self.tcp_client.send_data("\r\n")
        self.tcp_client.expect("S>")

        self.assert_direct_access_stop_telnet()

    # WORKS TUE (has timeout fix for other funcs)
    def test_get_capabilities(self):
        """
        @brief Verify that the correct capabilities are returned from get_capabilities
        at various driver/agent states.
        """
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        agent_capabilities = []
        unknown = []
        driver_capabilities = []
        driver_vars = []
        retval = self.instrument_agent_client.get_capabilities()
        for x in retval:
            if x.cap_type == 1:
                agent_capabilities.append(x.name)
            elif x.cap_type == 2:
                unknown.append(x.name)
            elif x.cap_type == 3:
                driver_capabilities.append(x.name)
            elif x.cap_type == 4:
                driver_vars.append(x.name)
            else:
                log.debug("*UNKNOWN* " + str(repr(x)))

        #--- Verify the following for ResourceAgentState.UNINITIALIZED
        self.assertEqual(agent_capabilities, ['RESOURCE_AGENT_EVENT_INITIALIZE'])
        self.assertEqual(unknown, ['example'])
        self.assertEqual(driver_capabilities, [])
        self.assertEqual(driver_vars, [])

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)


        agent_capabilities = []
        unknown = []
        driver_capabilities = []
        driver_vars = []
        retval = self.instrument_agent_client.get_capabilities()

        for x in retval:
            if x.cap_type == 1:
                agent_capabilities.append(x.name)
            elif x.cap_type == 2:
                unknown.append(x.name)
            elif x.cap_type == 3:
                driver_capabilities.append(x.name)
            elif x.cap_type == 4:
                driver_vars.append(x.name)
            else:
                log.debug("*UNKNOWN* " + str(repr(x)))

        #--- Verify the following for ResourceAgentState.INACTIVE
        self.assertEqual(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_ACTIVE', 'RESOURCE_AGENT_EVENT_RESET'])
        self.assertEqual(unknown, ['example'])
        self.assertEqual(driver_capabilities, [])
        self.assertEqual(driver_vars, [])


        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=30)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)


        agent_capabilities = []
        unknown = []
        driver_capabilities = []
        driver_vars = []
        retval = self.instrument_agent_client.get_capabilities()

        for x in retval:
            if x.cap_type == 1:
                agent_capabilities.append(x.name)
            elif x.cap_type == 2:
                unknown.append(x.name)
            elif x.cap_type == 3:
                driver_capabilities.append(x.name)
            elif x.cap_type == 4:
                driver_vars.append(x.name)
            else:
                log.debug("*UNKNOWN* " + str(repr(x)))

        #--- Verify the following for ResourceAgentState.IDLE
        self.assertEqual(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_INACTIVE', 'RESOURCE_AGENT_EVENT_RESET',
                                              'RESOURCE_AGENT_EVENT_RUN'])
        self.assertEqual(unknown, ['example'])
        self.assertEqual(driver_capabilities, [])
        self.assertEqual(driver_vars, [])

        cmd = AgentCommand(command=ResourceAgentEvent.RUN)
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        agent_capabilities = []
        unknown = []
        driver_capabilities = []
        driver_vars = []
        retval = self.instrument_agent_client.get_capabilities()

        for x in retval:
            if x.cap_type == 1:
                agent_capabilities.append(x.name)
            elif x.cap_type == 2:
                unknown.append(x.name)
            elif x.cap_type == 3:
                driver_capabilities.append(x.name)
            elif x.cap_type == 4:
                driver_vars.append(x.name)
            else:
                log.debug("*UNKNOWN* " + str(repr(x)))

        #--- Verify the following for ResourceAgentState.COMMAND
        self.assertEqual(agent_capabilities, ['RESOURCE_AGENT_EVENT_CLEAR', 'RESOURCE_AGENT_EVENT_RESET',
                                              'RESOURCE_AGENT_EVENT_GO_DIRECT_ACCESS',
                                              'RESOURCE_AGENT_EVENT_GO_INACTIVE',
                                              'RESOURCE_AGENT_EVENT_PAUSE'])
        self.assertEqual(unknown, ['example'])
        self.assertEqual(driver_capabilities, ['DRIVER_EVENT_ACQUIRE_STATUS',
                                               'DRIVER_EVENT_ACQUIRE_SAMPLE',
                                               #'DRIVER_EVENT_SET', 'DRIVER_EVENT_GET',
                                               'DRIVER_EVENT_START_AUTOSAMPLE',
                                               'DRIVER_EVENT_CLOCK_SYNC'])
        # Assert all PARAMS are present.
        for p in PARAMS.keys():
            self.assertTrue(p in driver_vars)


        cmd = AgentCommand(command=ResourceAgentEvent.GO_DIRECT_ACCESS,
            kwargs={'session_type': DirectAccessTypes.telnet,
                    #kwargs={'session_type':DirectAccessTypes.vsp,
                    'session_timeout':600,
                    'inactivity_timeout':600})
        retval = self.instrument_agent_client.execute_agent(cmd)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.DIRECT_ACCESS)

        agent_capabilities = []
        unknown = []
        driver_capabilities = []
        driver_vars = []
        retval = self.instrument_agent_client.get_capabilities()

        for x in retval:
            if x.cap_type == 1:
                agent_capabilities.append(x.name)
            elif x.cap_type == 2:
                unknown.append(x.name)
            elif x.cap_type == 3:
                driver_capabilities.append(x.name)
            elif x.cap_type == 4:
                driver_vars.append(x.name)
            else:
                log.debug("*UNKNOWN* " + str(repr(x)))

        #--- Verify the following for ResourceAgentState.COMMAND
        log.debug("HEREHEREHERE" + str(agent_capabilities))
        self.assertEqual(agent_capabilities, ['RESOURCE_AGENT_EVENT_GO_COMMAND'])

    # WORKS TUE
    def test_execute_capability_from_invalid_state(self):
        """
        @brief Perform netative testing that capabilitys utilized
        from wrong states are caught and handled gracefully.
        """
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        # Lets try GO_ACTIVE too early....

        exception_happened = False
        try:
            cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
            retval = self.instrument_agent_client.execute_agent(cmd)
        except Conflict as ex:
            exception_happened = True
            log.debug("1 - GO_ACTIVE - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        # Lets try RUN too early....

        exception_happened = False
        try:
            cmd = AgentCommand(command=ResourceAgentEvent.RUN)
            retval = self.instrument_agent_client.execute_agent(cmd)
        except Conflict as ex:
            exception_happened = True
            log.debug("2 - RUN - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

        # Now advance to next state

        cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE) #*****
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.check_state(ResourceAgentState.INACTIVE)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.INACTIVE)

        # Lets try RUN too early....

        exception_happened = False
        try:
            cmd = AgentCommand(command=ResourceAgentEvent.RUN)
            retval = self.instrument_agent_client.execute_agent(cmd)
        except Conflict as ex:
            exception_happened = True
            log.debug("3 - RUN - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.INACTIVE)

        cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=30)
        self.check_state(ResourceAgentState.IDLE)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.IDLE)

        # Lets try INITIALIZE too late....

        exception_happened = False
        try:
            cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
            retval = self.instrument_agent_client.execute_agent(cmd)
        except Conflict as ex:
            exception_happened = True
            log.debug("4 - INITIALIZE - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)
        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.IDLE)

        cmd = AgentCommand(command=ResourceAgentEvent.RUN) #*****
        retval = self.instrument_agent_client.execute_agent(cmd)
        self.check_state(ResourceAgentState.COMMAND)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.COMMAND)

        # Lets try RUN too when in COMMAND....

        exception_happened = False
        try:
            cmd = AgentCommand(command=ResourceAgentEvent.RUN)
            retval = self.instrument_agent_client.execute_agent(cmd)
        except Conflict as ex:
            exception_happened = True
            log.debug("5 - RUN - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)
        self.check_state(ResourceAgentState.COMMAND)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.COMMAND)

        # Lets try INITIALIZE too late....

        exception_happened = False
        try:
            cmd = AgentCommand(command=ResourceAgentEvent.INITIALIZE)
            retval = self.instrument_agent_client.execute_agent(cmd)
        except Conflict as ex:
            exception_happened = True
            log.debug("6 - INITIALIZE - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)
        self.check_state(ResourceAgentState.COMMAND)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.COMMAND)

        # Lets try GO_ACTIVE too late....

        exception_happened = False
        try:
            cmd = AgentCommand(command=ResourceAgentEvent.GO_ACTIVE)
            retval = self.instrument_agent_client.execute_agent(cmd)
        except Conflict as ex:
            exception_happened = True
            log.debug("7 - GO_ACTIVE - Caught expected exception = " + str(ex.__class__.__name__))
        self.assertTrue(exception_happened)

        self.check_state(ResourceAgentState.COMMAND)
        #state = self.instrument_agent_client.get_agent_state()
        #self.assertEqual(state, ResourceAgentState.COMMAND)

    # WORKS TUE
    def test_execute_reset(self):
        """
        @brief Walk the driver into command mode and perform a reset
        verifying it goes back to UNINITIALIZED, then walk it back to
        COMMAND to test there are no glitches in RESET
        """
        self.assert_enter_command_mode()

        # Test RESET

        self.assert_reset()

        self.assert_enter_command_mode()

    # WORKS TUE REQUIRES PATCH.DICT STILL
    @patch.dict(CFG, {'endpoint':{'receive':{'timeout': 120}}})
    def test_acquire_sample(self):
        """
        @brief Acquire a sample.
        """

        self.assert_enter_command_mode()

        cmd = AgentCommand(command=Capability.ACQUIRE_SAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd) # TIMESOUT ON THIS COMMAND (times out after it sends the sample back...)
        sample = retval.result
        log.debug("RETVALUE = " + str(sample))

        TS_REGEX = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)' # .*?\r\n
        TS_REGEX_MATCHER = re.compile(TS_REGEX)
        matches = TS_REGEX_MATCHER.match(sample)

        log.debug("COUNT = " + str(len(matches.groups())))
        self.assertEqual(3, len(matches.groups()))

    # WORKS TUE
    def test_connect_disconnect(self):

        self.assert_enter_command_mode()

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        self.check_state(ResourceAgentState.UNINITIALIZED)

    # WORKS TUE
    def test_execute_set_time_parameter(self):
        """
        @brief Set the clock to a bogus date/time, then verify that after
        a discover opoeration it reverts to the system time.
        """

        self.assert_enter_command_mode()

        params = {
            Parameter.DS_DEVICE_DATE_TIME : "01 Jan 2001 01:01:01",
        }

        self.instrument_agent_client.set_resource(params)

        params = [
            Parameter.DS_DEVICE_DATE_TIME,
        ]
        check_new_params = self.instrument_agent_client.get_resource(params)
        log.debug("TESTING TIME = " + repr(check_new_params))

        # assert that we altered the time.
        self.assertTrue('01 JAN 2001  01:' in check_new_params[Parameter.DS_DEVICE_DATE_TIME])

        # now put it back to normal

        params = {
            Parameter.DS_DEVICE_DATE_TIME : time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        }

        self.instrument_agent_client.set_resource(params)

        params = [
            Parameter.DS_DEVICE_DATE_TIME,
        ]
        check_new_params = self.instrument_agent_client.get_resource(params)
        log.debug("REAL TIME = " + repr(check_new_params))

    # WORKS TUE
    def test_execute_clock_sync(self):
        """
        @brief Test Test EXECUTE_CLOCK_SYNC command.
        """

        self.assert_enter_command_mode()

        self.assert_switch_driver_state(ProtocolEvent.CLOCK_SYNC, ProtocolState.COMMAND)

    #
    # Test that this returns text of ds, as well as publishes a ds particle.
    #ProtocolEvent.ACQUIRE_STATUS
    #