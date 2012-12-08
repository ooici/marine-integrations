"""
@package mi.instrument.seabird.sbe26plus.test.test_driver
@file marine-integrations/mi/instrument/seabird/sbe26plus/driver.py
@author Roger Unwin
@brief Test cases for ooicore driver

USAGE:
 Make tests verbose and provide stdout
   * From the IDK
       $ bin/test_driver
       $ bin/test_driver -u
       $ bin/test_driver -i
       $ bin/test_driver -q
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

from gevent import monkey; monkey.patch_all()
import gevent
import time
import re
from mock import Mock

from mi.core.common import BaseEnum
from mi.core.log import get_logger ; log = get_logger()
from nose.plugins.attrib import attr
from mi.idk.unit_test import InstrumentDriverDataParticleMixin
from mi.idk.unit_test import InstrumentDriverUnitTestCase
from mi.idk.unit_test import InstrumentDriverIntegrationTestCase
from mi.idk.unit_test import InstrumentDriverQualificationTestCase
from interface.objects import AgentCommand
from ion.agents.instrument.direct_access.direct_access_server import DirectAccessTypes
from mi.instrument.seabird.sbe26plus.driver import DataParticleType
from mi.instrument.seabird.sbe26plus.driver import InstrumentDriver
from mi.instrument.seabird.sbe26plus.driver import ProtocolState
from mi.instrument.seabird.sbe26plus.driver import Parameter
from mi.instrument.seabird.sbe26plus.driver import ProtocolEvent
from mi.instrument.seabird.sbe26plus.driver import Capability
from mi.instrument.seabird.sbe26plus.driver import Prompt
from mi.instrument.seabird.sbe26plus.driver import Protocol
from mi.instrument.seabird.sbe26plus.driver import InstrumentCmds
from mi.instrument.seabird.sbe26plus.driver import NEWLINE
from mi.instrument.seabird.sbe26plus.driver import SBE26plusTideSampleDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusWaveBurstDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusStatisticsDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceCalibrationDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceStatusDataParticle
from mi.instrument.seabird.sbe26plus.driver import SBE26plusTideSampleDataParticleKey
from mi.instrument.seabird.sbe26plus.driver import SBE26plusWaveBurstDataParticleKey
from mi.instrument.seabird.sbe26plus.driver import SBE26plusStatisticsDataParticleKey
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceCalibrationDataParticleKey
from mi.instrument.seabird.sbe26plus.driver import SBE26plusDeviceStatusDataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.data_particle import DataParticleKey, DataParticleValue
from mi.core.instrument.instrument_driver import DriverParameter, DriverConnectionState, DriverAsyncEvent
from mi.core.instrument.instrument_protocol import DriverProtocolState
from mi.core.exceptions import SampleException, InstrumentParameterException, InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException, InstrumentCommandException
from pyon.core.exception import Conflict
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

# Globals
raw_stream_received = False
parsed_stream_received = False

###
#   Driver parameters for the tests
###

PARAMS = {
    # DS # parameters - contains all setsampling parameters
    Parameter.DEVICE_VERSION : str,
    Parameter.SERIAL_NUMBER : str,
    Parameter.DS_DEVICE_DATE_TIME : str,
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
    Parameter.USE_STOP_TIME : bool,
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
}


SAMPLE_TIDE_DATA = "tide: start time = 05 Oct 2012 01:10:54, p = 14.5385, pt = 24.228, t = 23.8404" + NEWLINE

SAMPLE_DEVICE_STATUS =\
"SBE 26plus V 6.1e  SN 1329    05 Oct 2012  17:19:27" + NEWLINE +\
"user info=ooi" + NEWLINE +\
"quartz pressure sensor: serial number = 122094, range = 300 psia" + NEWLINE +\
"internal temperature sensor" + NEWLINE +\
"conductivity = NO" + NEWLINE +\
"iop =  7.4 ma  vmain = 16.2 V  vlith =  9.0 V" + NEWLINE +\
"last sample: p = 14.5361, t = 23.8155, s =  0.0000" + NEWLINE +\
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
"logging = NO, send start command to begin logging" + NEWLINE

SAMPLE_DEVICE_CALIBRATION =\
"Pressure coefficients:  02-apr-13" + NEWLINE +\
"    U0 = 5.100000e+00" + NEWLINE +\
"    Y1 = -3.910859e+03" + NEWLINE +\
"    Y2 = -1.070825e+04" + NEWLINE +\
"    Y3 = 0.000000e+00" + NEWLINE +\
"    C1 = 6.072786e+02" + NEWLINE +\
"    C2 = 1.000000e+00" + NEWLINE +\
"    C3 = -1.024374e+03" + NEWLINE +\
"    D1 = 2.928000e-02" + NEWLINE +\
"    D2 = 0.000000e+00" + NEWLINE +\
"    T1 = 2.783369e+01" + NEWLINE +\
"    T2 = 6.072020e-01" + NEWLINE +\
"    T3 = 1.821885e+01" + NEWLINE +\
"    T4 = 2.790597e+01" + NEWLINE +\
"    M = 41943.0" + NEWLINE +\
"    B = 2796.2" + NEWLINE +\
"    OFFSET = -1.374000e-01" + NEWLINE +\
"Temperature coefficients:  02-apr-13" + NEWLINE +\
"    TA0 = 1.200000e-04" + NEWLINE +\
"    TA1 = 2.558000e-04" + NEWLINE +\
"    TA2 = -2.073449e-06" + NEWLINE +\
"    TA3 = 1.640089e-07" + NEWLINE +\
"Conductivity coefficients:  28-mar-12" + NEWLINE +\
"    CG = -1.025348e+01" + NEWLINE +\
"    CH = 1.557569e+00" + NEWLINE +\
"    CI = -1.737200e-03" + NEWLINE +\
"    CJ = 2.268000e-04" + NEWLINE +\
"    CTCOR = 3.250000e-06" + NEWLINE +\
"    CPCOR = -9.570000e-08" + NEWLINE +\
"    CSLOPE = 1.000000e+00" + NEWLINE

SAMPLE_WAVE_BURST =\
"wave: start time = 05 Oct 2012 01:10:54" + NEWLINE +\
"wave: ptfreq = 171791.359" + NEWLINE +\
"  14.5102" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5078" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5078" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5188" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5097" + NEWLINE + "  14.5134" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5036" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5134" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5036" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5134" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE + "  14.5165" + NEWLINE +\
"  14.5064" + NEWLINE + "  14.5165" + NEWLINE + "  14.5064" + NEWLINE + "  14.5165" + NEWLINE +\
"wave: end burst" + NEWLINE

SAMPLE_STATISTICS =\
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
"   H1/100 = 0.0000e+00" + NEWLINE

SAMPLE_DS =\
"SBE 26plus" + NEWLINE +\
"S>ds" + NEWLINE +\
"ds" + NEWLINE + SAMPLE_DEVICE_STATUS +\
"S>" + NEWLINE

SAMPLE_DC =\
"S>dc" + NEWLINE +\
"dc" + NEWLINE + SAMPLE_DEVICE_CALIBRATION +\
"S>"

class DataParticleMixin(InstrumentDriverDataParticleMixin):
    '''
    Mixin class used for storing data particle constance and common data assertion methods.
    '''
    ###
    #   Particle Parameter and Type Definitions
    ###

    _tide_sample_parameters = {
        SBE26plusTideSampleDataParticleKey.TIMESTAMP: { 'type': float, 'value': 3558413454.0 },
        SBE26plusTideSampleDataParticleKey.PRESSURE: { 'type': float, 'value': 14.5385 },
        SBE26plusTideSampleDataParticleKey.PRESSURE_TEMP: { 'type': float, 'value': 24.228 },
        SBE26plusTideSampleDataParticleKey.TEMPERATURE: { 'type': float, 'value': 23.8404 },
        SBE26plusTideSampleDataParticleKey.CONDUCTIVITY: { 'type': float, 'required': False },
        SBE26plusTideSampleDataParticleKey.SALINITY: { 'type': float, 'required': False }
    }

    _wave_sample_parameters = {
        SBE26plusWaveBurstDataParticleKey.TIMESTAMP: { 'type': float, 'value': 3558413454.0 },
        SBE26plusWaveBurstDataParticleKey.PTFREQ: { 'type': float, 'value': 171791.359 },
        SBE26plusWaveBurstDataParticleKey.PTRAW: { 'type': list }
    }

    _statistics_sample_parameters = {
        SBE26plusStatisticsDataParticleKey.DEPTH: { 'type': float, 'value': 0.0 },
        SBE26plusStatisticsDataParticleKey.TEMPERATURE: { 'type': float, 'value': 23.840 },
        SBE26plusStatisticsDataParticleKey.SALINITY: { 'type': float, 'value': 35.000 },
        SBE26plusStatisticsDataParticleKey.DENSITY: { 'type': float, 'value': 1023.690 },
        SBE26plusStatisticsDataParticleKey.N_AGV_BAND: { 'type': int, 'value': 5 },
        SBE26plusStatisticsDataParticleKey.TOTAL_VARIANCE: { 'type': float, 'value': 1.0896e-05 },
        SBE26plusStatisticsDataParticleKey.TOTAL_ENERGY: { 'type': float, 'value': 1.0939e-01 },
        SBE26plusStatisticsDataParticleKey.SIGNIFICANT_PERIOD: { 'type': float, 'value': 5.3782e-01 },
        SBE26plusStatisticsDataParticleKey.SIGNIFICANT_WAVE_HEIGHT: { 'type': float, 'value': 1.3204e-02 },
        SBE26plusStatisticsDataParticleKey.TSS_WAVE_INTEGRATION_TIME: { 'type': int, 'value': 128 },
        SBE26plusStatisticsDataParticleKey.TSS_NUMBER_OF_WAVES: { 'type': float, 'value': 0 },
        SBE26plusStatisticsDataParticleKey.TSS_TOTAL_VARIANCE: { 'type': float, 'value': 1.1595e-05 },
        SBE26plusStatisticsDataParticleKey.TSS_TOTAL_ENERGY: { 'type': float, 'value': 1.1640e-01 },
        SBE26plusStatisticsDataParticleKey.TSS_AVERAGE_WAVE_HEIGHT: { 'type': float, 'value': 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_AVERAGE_WAVE_PERIOD: { 'type': float, 'value': 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_MAXIMUM_WAVE_HEIGHT: { 'type': float, 'value': 1.0893e-02 },
        SBE26plusStatisticsDataParticleKey.TSS_SIGNIFICANT_WAVE_HEIGHT: { 'type': float, 'value': 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_SIGNIFICANT_WAVE_PERIOD: { 'type': float, 'value': 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_H1_10: { 'type': float, 'value': 0.0000e+00 },
        SBE26plusStatisticsDataParticleKey.TSS_H1_100: { 'type': float, 'value': 0.0000e+00 }
    }

    _calibration_sample_parameters = {
        SBE26plusDeviceCalibrationDataParticleKey.PCALDATE: { 'type': list, 'value': [2, 4, 2013] },
        SBE26plusDeviceCalibrationDataParticleKey.PU0: { 'type': float, 'value': 5.100000e+00 },
        SBE26plusDeviceCalibrationDataParticleKey.PY1: { 'type': float, 'value': -3.910859e+03 },
        SBE26plusDeviceCalibrationDataParticleKey.PY2: { 'type': float, 'value': -1.070825e+04 },
        SBE26plusDeviceCalibrationDataParticleKey.PY3: { 'type': float, 'value':  0.000000e+00  },
        SBE26plusDeviceCalibrationDataParticleKey.PC1: { 'type': float, 'value': 6.072786e+02 },
        SBE26plusDeviceCalibrationDataParticleKey.PC2: { 'type': float, 'value': 1.000000e+00 },
        SBE26plusDeviceCalibrationDataParticleKey.PC3: { 'type': float, 'value': -1.024374e+03 },
        SBE26plusDeviceCalibrationDataParticleKey.PD1: { 'type': float, 'value':  2.928000e-02 },
        SBE26plusDeviceCalibrationDataParticleKey.PD2: { 'type': float, 'value': 0.000000e+00 },
        SBE26plusDeviceCalibrationDataParticleKey.PT1: { 'type': float, 'value': 2.783369e+01 },
        SBE26plusDeviceCalibrationDataParticleKey.PT2: { 'type': float, 'value': 6.072020e-01 },
        SBE26plusDeviceCalibrationDataParticleKey.PT3: { 'type': float, 'value': 1.821885e+01 },
        SBE26plusDeviceCalibrationDataParticleKey.PT4: { 'type': float, 'value': 2.790597e+01 },
        SBE26plusDeviceCalibrationDataParticleKey.FACTORY_M: { 'type': float, 'value': 41943.0 },
        SBE26plusDeviceCalibrationDataParticleKey.FACTORY_B: { 'type': float, 'value': 2796.2 },
        SBE26plusDeviceCalibrationDataParticleKey.POFFSET: { 'type': float, 'value': -1.374000e-01 },
        SBE26plusDeviceCalibrationDataParticleKey.TCALDATE: { 'type': list, 'value': [2, 4, 2013] },
        SBE26plusDeviceCalibrationDataParticleKey.TA0: { 'type': float, 'value': 1.200000e-04 },
        SBE26plusDeviceCalibrationDataParticleKey.TA1: { 'type': float, 'value': 2.558000e-04 },
        SBE26plusDeviceCalibrationDataParticleKey.TA2: { 'type': float, 'value': -2.073449e-06 },
        SBE26plusDeviceCalibrationDataParticleKey.TA3: { 'type': float, 'value': 1.640089e-07 },
        SBE26plusDeviceCalibrationDataParticleKey.CCALDATE: { 'type': list, 'value': [28, 3, 2012] },
        SBE26plusDeviceCalibrationDataParticleKey.CG: { 'type': float, 'value': -1.025348e+01 },
        SBE26plusDeviceCalibrationDataParticleKey.CH: { 'type': float, 'value': 1.557569e+00 },
        SBE26plusDeviceCalibrationDataParticleKey.CI: { 'type': float, 'value': -1.737200e-03 },
        SBE26plusDeviceCalibrationDataParticleKey.CJ: { 'type': float, 'value': 2.268000e-04 },
        SBE26plusDeviceCalibrationDataParticleKey.CTCOR: { 'type': float, 'value': 3.250000e-06 },
        SBE26plusDeviceCalibrationDataParticleKey.CPCOR: { 'type': float, 'value': -9.570000e-08 },
        SBE26plusDeviceCalibrationDataParticleKey.CSLOPE: { 'type': float, 'value': 1.000000e+00 }
    }

    _status_sample_parameters = {
        SBE26plusDeviceStatusDataParticleKey.DEVICE_VERSION: { 'type': unicode, 'value': u'6.1e' },
        SBE26plusDeviceStatusDataParticleKey.SERIAL_NUMBER: { 'type': unicode, 'value': u'1329' },
        SBE26plusDeviceStatusDataParticleKey.DS_DEVICE_DATE_TIME: { 'type': unicode, 'value': u'05 Oct 2012  17:19:27' },
        SBE26plusDeviceStatusDataParticleKey.USER_INFO: { 'type': unicode, 'value': u'ooi' },
        SBE26plusDeviceStatusDataParticleKey.QUARTZ_PRESSURE_SENSOR_SERIAL_NUMBER: { 'type': float, 'value': 122094 },
        SBE26plusDeviceStatusDataParticleKey.QUARTZ_PRESSURE_SENSOR_RANGE: { 'type': float, 'value': 300 },
        SBE26plusDeviceStatusDataParticleKey.EXTERNAL_TEMPERATURE_SENSOR: { 'type': bool, 'value': False },
        SBE26plusDeviceStatusDataParticleKey.CONDUCTIVITY: { 'type': bool, 'value': False },
        SBE26plusDeviceStatusDataParticleKey.IOP_MA: { 'type': float, 'value': 7.4 },
        SBE26plusDeviceStatusDataParticleKey.VMAIN_V: { 'type': float, 'value': 16.2 },
        SBE26plusDeviceStatusDataParticleKey.VLITH_V: { 'type': float, 'value': 9.0 },
        SBE26plusDeviceStatusDataParticleKey.LAST_SAMPLE_P: { 'type': float, 'value': 14.5361 },
        SBE26plusDeviceStatusDataParticleKey.LAST_SAMPLE_T: { 'type': float, 'value': 23.8155 },
        SBE26plusDeviceStatusDataParticleKey.LAST_SAMPLE_S: { 'type': float, 'value': 0.0 },
        SBE26plusDeviceStatusDataParticleKey.TIDE_INTERVAL: { 'type': int, 'value': 3.0 },
        SBE26plusDeviceStatusDataParticleKey.TIDE_MEASUREMENT_DURATION: { 'type': int, 'value': 60 },
        SBE26plusDeviceStatusDataParticleKey.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS: { 'type': int, 'value': 6 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_SAMPLES_PER_BURST: { 'type': int, 'value': 512 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_SAMPLES_SCANS_PER_SECOND: { 'type': float, 'value': 4.0 },
        SBE26plusDeviceStatusDataParticleKey.USE_START_TIME: { 'type': bool, 'value': False },
        SBE26plusDeviceStatusDataParticleKey.USE_STOP_TIME: { 'type': bool, 'value': False },
        SBE26plusDeviceStatusDataParticleKey.TIDE_SAMPLES_PER_DAY: { 'type': float, 'value': 480.0 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_BURSTS_PER_DAY: { 'type': float, 'value': 80.0 },
        SBE26plusDeviceStatusDataParticleKey.MEMORY_ENDURANCE: { 'type': float, 'value': 258.0 },
        SBE26plusDeviceStatusDataParticleKey.NOMINAL_ALKALINE_BATTERY_ENDURANCE: { 'type': float, 'value': 272.8 },
        SBE26plusDeviceStatusDataParticleKey.TOTAL_RECORDED_TIDE_MEASUREMENTS: { 'type': float, 'value': 5982 },
        SBE26plusDeviceStatusDataParticleKey.TOTAL_RECORDED_WAVE_BURSTS: { 'type': float, 'value': 4525 },
        SBE26plusDeviceStatusDataParticleKey.TIDE_MEASUREMENTS_SINCE_LAST_START: { 'type': float, 'value': 11 },
        SBE26plusDeviceStatusDataParticleKey.WAVE_BURSTS_SINCE_LAST_START: { 'type': float, 'value': 1 },
        SBE26plusDeviceStatusDataParticleKey.TXREALTIME: { 'type': bool, 'value': True },
        SBE26plusDeviceStatusDataParticleKey.TXWAVEBURST: { 'type': bool, 'value': True },
        SBE26plusDeviceStatusDataParticleKey.TXWAVESTATS: { 'type': bool, 'value': True },
        SBE26plusDeviceStatusDataParticleKey.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS: { 'type': int, 'value': 512 },
        SBE26plusDeviceStatusDataParticleKey.USE_MEASURED_TEMP_FOR_DENSITY_CALC: { 'type': bool, 'value': False  },
        SBE26plusDeviceStatusDataParticleKey.PRESSURE_SENSOR_HEIGHT_FROM_BOTTOM: { 'type': float, 'value': 10.0 },
        SBE26plusDeviceStatusDataParticleKey.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND: { 'type': int, 'value': 5 },
        SBE26plusDeviceStatusDataParticleKey.MIN_ALLOWABLE_ATTENUATION: { 'type': float, 'value': 0.0025 },
        SBE26plusDeviceStatusDataParticleKey.MIN_PERIOD_IN_AUTO_SPECTRUM: { 'type': float, 'value': 0.0e+00 },
        SBE26plusDeviceStatusDataParticleKey.MAX_PERIOD_IN_AUTO_SPECTRUM: { 'type': float, 'value': 1.0e+06 },
        SBE26plusDeviceStatusDataParticleKey.HANNING_WINDOW_CUTOFF: { 'type': float, 'value': 0.10 },
        SBE26plusDeviceStatusDataParticleKey.SHOW_PROGRESS_MESSAGES: { 'type': bool, 'value': True },
        SBE26plusDeviceStatusDataParticleKey.STATUS: { 'type': unicode, 'value': u'stopped by user' },
        SBE26plusDeviceStatusDataParticleKey.LOGGING: { 'type': bool, 'value': False },
    }

    def assertSampleDataParticle(self, data_particle):
        '''
        Verify a particle is a know particle to this driver and verify the particle is
        correct
        @param data_particle: Data particle of unkown type produced by the driver
        '''
        if (isinstance(data_particle, SBE26plusTideSampleDataParticle)):
            self.assert_particle_tide_sample(data_particle)
        elif (isinstance(data_particle, SBE26plusWaveBurstDataParticle)):
            self.assert_particle_wave_burst(data_particle)
        elif (isinstance(data_particle, SBE26plusStatisticsDataParticle)):
            self.assert_particle_statistics(data_particle)
        elif (isinstance(data_particle, SBE26plusDeviceCalibrationDataParticle)):
            self.assert_particle_device_calibration(data_particle)
        elif (isinstance(data_particle, SBE26plusDeviceStatusDataParticle)):
            self.assert_particle_device_status(data_particle)
        else:
            log.error("Unknown Particle Detected: %s" % data_particle)
            self.assertFalse(True)

    def assert_particle_tide_sample(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusTideSampleDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.TIDE_PARSED)
        self.assert_data_particle_parameters(data_particle, self._tide_sample_parameters, verify_values)


    def assert_particle_wave_burst(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusWaveBurstDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.WAVE_BURST)
        self.assert_data_particle_parameters(data_particle, self._wave_sample_parameters, verify_values)

    def assert_particle_statistics(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusStatisticsDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.STATISTICS)
        self.assert_data_particle_parameters(data_particle, self._statistics_sample_parameters, verify_values)

    def assert_particle_device_calibration(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusDeviceCalibrationDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_CALIBRATION)
        self.assert_data_particle_parameters(data_particle, self._calibration_sample_parameters, verify_values)

    def assert_particle_device_status(self, data_particle, verify_values = False):
        '''
        Verify a take sample data particle
        @param data_particle:  SBE26plusDeviceStatusDataParticle data particle
        @param verify_values:  bool, should we verify parameter values
        '''
        self.assert_data_particle_header(data_particle, DataParticleType.DEVICE_STATUS)
        self.assert_data_particle_parameters(data_particle, self._status_sample_parameters, verify_values)


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
@attr('UNIT', group='mi')
class SBE26PlusUnitTest(InstrumentDriverUnitTestCase, DataParticleMixin):
    def setUp(self):
        InstrumentDriverUnitTestCase.setUp(self)

    def test_driver_enums(self):
        """
        Verify that all driver enumeration has no duplicate values that might cause confusion.  Also
        do a little extra validation for the Capabilites
        """
        self.assert_enum_has_no_duplicates(DataParticleType())
        self.assert_enum_has_no_duplicates(InstrumentCmds())
        self.assert_enum_has_no_duplicates(ProtocolState())
        self.assert_enum_has_no_duplicates(ProtocolEvent())
        self.assert_enum_has_no_duplicates(Parameter())

        # Test capabilites for duplicates, them verify that capabilities is a subset of proto events
        self.assert_enum_has_no_duplicates(Capability())
        self.assert_enum_complete(Capability(), ProtocolEvent())

    def test_chunker(self):
        """
        Test the chunker and verify the particles created.
        """
        chunker = StringChunker(Protocol.sieve_function)

        self.assert_chunker_sample(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_TIDE_DATA)
        self.assert_chunker_combined_sample(chunker, SAMPLE_TIDE_DATA)

        self.assert_chunker_sample(chunker, SAMPLE_WAVE_BURST)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_WAVE_BURST)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_WAVE_BURST, 1024)
        self.assert_chunker_combined_sample(chunker, SAMPLE_WAVE_BURST)

        self.assert_chunker_sample(chunker, SAMPLE_STATISTICS)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_STATISTICS)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_STATISTICS, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_STATISTICS)

        self.assert_chunker_sample(chunker, SAMPLE_DEVICE_CALIBRATION)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_DEVICE_CALIBRATION)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_DEVICE_CALIBRATION, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_DEVICE_CALIBRATION)

        self.assert_chunker_sample(chunker, SAMPLE_DEVICE_STATUS)
        self.assert_chunker_sample_with_noise(chunker, SAMPLE_DEVICE_STATUS)
        self.assert_chunker_fragmented_sample(chunker, SAMPLE_DEVICE_STATUS, 512)
        self.assert_chunker_combined_sample(chunker, SAMPLE_DEVICE_STATUS)

    def test_got_data(self):
        """
        Verify sample data passed through the got data method produces the correct data particles
        """
        # Create and initialize the instrument driver with a mock port agent
        driver = InstrumentDriver(self._got_data_event_callback)
        self.assert_initialize_driver(driver)

        # Start validating data particles
        self.assert_particle_published(driver, SAMPLE_TIDE_DATA, self.assert_particle_tide_sample, True)
        self.assert_particle_published(driver, SAMPLE_WAVE_BURST, self.assert_particle_wave_burst, True)
        self.assert_particle_published(driver, SAMPLE_STATISTICS, self.assert_particle_statistics, True)
        self.assert_particle_published(driver, SAMPLE_DEVICE_CALIBRATION, self.assert_particle_device_calibration, True)
        self.assert_particle_published(driver, SAMPLE_DEVICE_STATUS, self.assert_particle_device_status, True)


    def test_protocol_filter_capabilities(self):
        """
        This tests driver filter_capabilities.
        Iterate through available capabilities, and verify that they can pass successfully through the filter.
        Test silly made up capabilities to verify they are blocked by filter.
        """
        my_event_callback = Mock(spec="UNKNOWN WHAT SHOULD GO HERE FOR evt_callback")
        protocol = Protocol(Prompt, NEWLINE, my_event_callback)
        driver_capabilities = Capability().list()
        test_capabilities = Capability().list()

        # Add a bogus capability that will be filtered out.
        test_capabilities.append("BOGUS_CAPABILITY")

        # Verify "BOGUS_CAPABILITY was filtered out
        self.assertEquals(driver_capabilities, protocol._filter_capabilities(test_capabilities))


    def test_get_resource_capabilities(self):
        driver = InstrumentDriver(self._got_data_event_callback)
        driver._build_protocol()
        p = driver._protocol
        args = []
        kwargs = {}

        # Force State UNKNOWN
        driver.set_test_mode(True)
        driver.test_force_state(state = DriverProtocolState.UNKNOWN)

        ret = driver.get_resource_capabilities(*args, **kwargs)
        self.assertEqual(ret[0], [])

        # Force State COMMAND
        driver.test_force_state(state = DriverProtocolState.COMMAND)

        ret = driver.get_resource_capabilities(*args, **kwargs)
        for state in ['DRIVER_EVENT_ACQUIRE_STATUS', 'DRIVER_EVENT_ACQUIRE_SAMPLE',
                      'DRIVER_EVENT_START_AUTOSAMPLE', 'DRIVER_EVENT_CLOCK_SYNC']:

            self.assertTrue(state in ret[0])
        self.assertEqual(len(ret[0]), 4)

        # Force State AUTOSAMPLE
        driver.test_force_state(state = DriverProtocolState.AUTOSAMPLE)

        ret = driver.get_resource_capabilities(*args, **kwargs)
        for state in ['DRIVER_EVENT_STOP_AUTOSAMPLE']:
            self.assertTrue(state in ret[0])
        self.assertEqual(len(ret[0]), 1)

        # Force State DIRECT_ACCESS
        driver.test_force_state(state = DriverProtocolState.DIRECT_ACCESS)

        ret = driver.get_resource_capabilities(*args, **kwargs)
        self.assertEqual(ret[0], [])




###############################################################################
#                            INTEGRATION TESTS                                #
#     Integration test test the direct driver / instrument interaction        #
#     but making direct calls via zeromq.                                     #
#     - Common Integration tests test the driver through the instrument agent #
#     and common for all drivers (minimum requirement for ION ingestion)      #
###############################################################################
@attr('INT', group='mi')
class SBE26PlusIntegrationTest(InstrumentDriverIntegrationTestCase):
    def setUp(self):
        InstrumentDriverIntegrationTestCase.setUp(self)

    ###
    #    Add instrument specific integration tests
    ###

    def assert_param_dict(self, pd, all_params=False):
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
        self.assert_param_dict(reply)


        log.debug("get/set Test 2 - Conductivity = N, small subset of possible parameters.")
        params = {
            Parameter.CONDUCTIVITY : False,
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply)


        log.debug("get/set Test 3 - internal temperature sensor, small subset of possible parameters.")
        params = {
            Parameter.DS_DEVICE_DATE_TIME : time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime()))),
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : False,
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply)


        log.debug("get/set Test 4 - external temperature sensor, small subset of possible parameters.")
        params = {
            Parameter.EXTERNAL_TEMPERATURE_SENSOR : True,
        }
        reply = self.driver_client.cmd_dvr('set_resource', params)
        self.assertEqual(reply, None)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply)

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
        self.assert_param_dict(reply)

        log.debug("get/set Test 6 - get master set of possible parameters using array containing Parameter.ALL")


        params3 = [
            Parameter.ALL
        ]

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply)


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
        self.assert_param_dict(reply)


        log.debug("get/set Test 10 - Negative testing, None instead of dict")
        exception = False
        try:
            reply = self.driver_client.cmd_dvr('set_resource', None)
        except InstrumentParameterException:
            exception = True
        self.assertTrue(exception)

        reply = self.driver_client.cmd_dvr('get_resource', Parameter.ALL)
        self.assert_param_dict(reply)



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
        self.assert_param_dict(reply)


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

    def test_take_sample(self):
        """
        @brief execute the take_sample (ts) command and verify that a line with at
        least 3 floats is returned, indicating a acceptable sample.
        """

        self.put_instrument_in_command_mode()

        # take a sample.
        sample = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.ACQUIRE_SAMPLE)
        log.debug("sample = " + repr(sample[1]))
        TS_REGEX = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)'
        TS_REGEX_MATCHER = re.compile(TS_REGEX)
        matches = TS_REGEX_MATCHER.match(sample[1])

        log.debug("COUNT = " + str(len(matches.groups())))
        self.assertEqual(3, len(matches.groups()))

    def test_init_logging(self):
        """
        @brief Test initialize logging command.
        """
        self.put_instrument_in_command_mode()

        reply = self.driver_client.cmd_dvr('execute_resource', ProtocolEvent.INIT_LOGGING)

        self.assertTrue(reply)

    def test_quit_session(self):
        """
        @brief Test quit session command.
        quit session causes the instrument to enter a timedout state where it uses less power.

        this test wakes it up after placing it in the timedout (quit session) state, then
        verifies it can obtain paramaters to assert the instrument is working.
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
        self.assert_param_dict(reply)

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

    def test_connect_configure_disconnect(self):
        """
        @ BRIEF connect and then disconnect, verify state
        """

        self.put_instrument_in_command_mode()

        reply = self.driver_client.cmd_dvr('disconnect')
        self.assertEqual(reply, None)

        self.check_state(DriverConnectionState.DISCONNECTED)

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

    def test_poll(self):
        """
        @brief Test sample polling commands and events.
        also tests execute_resource
        """
        # Test the driver is in state unconfigured.
        self.put_instrument_in_command_mode()


        # Poll for a sample and confirm result.
        sample1 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE1 = " + str(sample1[1]))

        # Poll for a sample and confirm result.
        sample2 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE2 = " + str(sample2[1]))

        # Poll for a sample and confirm result.
        sample3 = self.driver_client.cmd_dvr('execute_resource', Capability.ACQUIRE_SAMPLE)
        log.debug("SAMPLE3 = " + str(sample3[1]))

        TS_REGEX = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)'
        TS_REGEX_MATCHER = re.compile(TS_REGEX)

        matches1 = TS_REGEX_MATCHER.match(sample1[1])
        self.assertEqual(3, len(matches1.groups()))

        matches2 = TS_REGEX_MATCHER.match(sample2[1])
        self.assertEqual(3, len(matches2.groups()))

        matches3 = TS_REGEX_MATCHER.match(sample3[1])
        self.assertEqual(3, len(matches3.groups()))




        # Confirm that 3 samples arrived as published events.
        gevent.sleep(1)
        sample_events = [evt for evt in self.events if evt['type']==DriverAsyncEvent.SAMPLE]

        self.assertEqual(len(sample_events), 12)

        # Disconnect from the port agent.
        reply = self.driver_client.cmd_dvr('disconnect')

        # Test the driver is configured for comms.
        self.check_state(DriverConnectionState.DISCONNECTED)

        # Deconfigure the driver.
        reply = self.driver_client.cmd_dvr('initialize')

        # Test the driver is in state unconfigured.
        self.check_state(DriverConnectionState.UNCONFIGURED)

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
class SBE26PlusQualificationTest(InstrumentDriverQualificationTestCase):
    def setUp(self):
        InstrumentDriverQualificationTestCase.setUp(self)

    def check_state(self, desired_state):
        current_state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(current_state, desired_state)



    ###
    #    Add instrument specific qualification tests
    ###

    def test_autosample(self):
        """
        @brief Test instrument driver execute interface to start and stop streaming
        mode.
        """

        self.data_subscribers.start_data_subscribers()
        self.addCleanup(self.data_subscribers.stop_data_subscribers)


        self.assert_enter_command_mode()

        params = {
            Parameter.TIDE_INTERVAL : 1,
            Parameter.TXWAVESTATS : False,
            Parameter.USER_INFO : "KILROY WAZ HERE"
        }

        self.instrument_agent_client.set_resource(params, timeout=60)

        #self.data_subscribers.no_samples = 3

        # Begin streaming.
        cmd = AgentCommand(command=ProtocolEvent.START_AUTOSAMPLE)
        retval = self.instrument_agent_client.execute_resource(cmd)

        self.data_subscribers.clear_sample_queue(DataParticleValue.PARSED)

        # wait for 3 samples, then test them!
        samples = self.data_subscribers.get_samples('parsed', 3, timeout=300) # 6 minutes
        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())
        self.assertSampleDataParticle(samples.pop())

        # Halt streaming.
        cmd = AgentCommand(command=ProtocolEvent.STOP_AUTOSAMPLE)
        # could be in a tide sample cycle... long timeout
        retval = self.instrument_agent_client.execute_resource(cmd, timeout=600)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.COMMAND)

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd, timeout=60)

        state = self.instrument_agent_client.get_agent_state()
        self.assertEqual(state, ResourceAgentState.UNINITIALIZED)

    def test_direct_access_telnet_mode(self):
        """
        @brief This test manually tests that the Instrument Driver properly supports direct access to the physical instrument. (telnet mode)
        """
        self.assert_enter_command_mode()
        params = [Parameter.EXTERNAL_TEMPERATURE_SENSOR]
        check_new_params = self.instrument_agent_client.get_resource(params)
        self.assertTrue(check_new_params[Parameter.EXTERNAL_TEMPERATURE_SENSOR])

        # go into direct access, and muck up a setting.
        self.assert_direct_access_start_telnet(timeout=600)
        self.assertTrue(self.tcp_client)
        self.tcp_client.send_data(Parameter.EXTERNAL_TEMPERATURE_SENSOR + "=N\r\n")
        self.tcp_client.expect("S>")

        self.assert_direct_access_stop_telnet()

        # verify the setting got restored.
        self.assert_enter_command_mode()
        params = [Parameter.EXTERNAL_TEMPERATURE_SENSOR]
        check_new_params = self.instrument_agent_client.get_resource(params)
        self.assertTrue(check_new_params[Parameter.EXTERNAL_TEMPERATURE_SENSOR])

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
        self.assertEqual(agent_capabilities, [])

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

    def test_acquire_sample(self):
        """
        """
        self.assert_sample_polled(self.assertSampleDataParticle, 'parsed', timeout=30)

    def test_connect_disconnect(self):

        self.assert_enter_command_mode()

        cmd = AgentCommand(command=ResourceAgentEvent.RESET)
        retval = self.instrument_agent_client.execute_agent(cmd)

        self.check_state(ResourceAgentState.UNINITIALIZED)

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

        # Now verify that at least the date matches
        lt = time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        self.assertTrue(lt[:12].upper() in check_new_params[Parameter.DS_DEVICE_DATE_TIME].upper())

    def test_execute_clock_sync(self):
        """
        @brief Test Test EXECUTE_CLOCK_SYNC command.
        """

        self.assert_enter_command_mode()

        self.assert_switch_driver_state(ProtocolEvent.CLOCK_SYNC, ProtocolState.COMMAND)

        # Now verify that at least the date matches
        params = [Parameter.DS_DEVICE_DATE_TIME]
        check_new_params = self.instrument_agent_client.get_resource(params)
        lt = time.strftime("%d %b %Y  %H:%M:%S", time.gmtime(time.mktime(time.localtime())))

        self.assertTrue(lt[:12].upper() in check_new_params[Parameter.DS_DEVICE_DATE_TIME].upper())

