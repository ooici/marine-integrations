"""
@package mi.instrument.seabird.sbe26plus.ooicore.driver
@file /Users/unwin/OOI/Workspace/code/marine-integrations/mi/instrument/seabird/sbe26plus/ooicore/driver.py
@author Roger Unwin
@brief Driver for the ooicore
Release notes:

None.
"""

__author__ = 'Roger Unwin'
__license__ = 'Apache 2.0'

import string

import re
import time
from mi.core.time import *
import ntplib

from mi.core.common import BaseEnum


from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import InstrumentFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter

from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import InstrumentParameterException
from mi.core.exceptions import SampleException
from mi.core.exceptions import InstrumentStateException
from mi.core.exceptions import InstrumentProtocolException

from mi.core.log import get_logger ; log = get_logger()

# Experimental
from mi.core.instrument.protocol_param_dict import ProtocolParameterDict
from mi.core.instrument.protocol_param_dict import ParameterDictVal
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.common import BaseEnum
from mi.core.instrument.port_agent_client import PortAgentPacket
from mi.core.instrument.instrument_driver import DriverAsyncEvent


from prototype.sci_data.stream_defs import ctd_stream_definition

from mi.core.instrument.data_particle import DataParticle, DataParticleKey, DataParticleValue
from mi.core.instrument.chunker import StringChunker

from mi.idk.unit_test import InstrumentDriverTestCase



#from mi.instrument.seabird.sbe26plus.range import Range

from pyon.agent.agent import ResourceAgentClient
from pyon.agent.agent import ResourceAgentState
from pyon.agent.agent import ResourceAgentEvent

from pyon.core.exception import BadRequest
from pyon.core.exception import Conflict
# newline.
NEWLINE = '\r\n'

# default timeout.
TIMEOUT = 40




#SAMPLE_REGEX = " DEFINED ELSEWHERE see self._sample_regexs"
#SAMPLE_REGEX_MATCHER = re.compile(SAMPLE_REGEX, re.MULTILINE)

TIDE_REGEX = r'(tide: start time = +\d+ [A-Za-z]{3} \d{4} \d+:\d+:\d+, p = +[\-\d.]+, pt = +[\-\d.]+, t = +[\-\d.]+.*?\r\n)'
TIDE_REGEX_MATCHER = re.compile(TIDE_REGEX, re.MULTILINE)

WAVE_REGEX = r'(wave: start time =.*?wave: end burst\r\n)'
WAVE_REGEX_MATCHER = re.compile(WAVE_REGEX, re.MULTILINE|re.DOTALL)

STATS_REGEX = r'(deMeanTrend.*?H1/100 = [\d.e+]+\r\n)'
STATS_REGEX_MATCHER = re.compile(STATS_REGEX, re.MULTILINE|re.DOTALL)

SL_SLO_REGEX = r'(^p = +[\-\d.]+, t = +[\-\d.]+.*?\r\n)'
SL_SLO_REGEX_MATCHER = re.compile(SL_SLO_REGEX, re.MULTILINE)

TS_REGEX = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)' # .*?\r\n
TS_REGEX_MATCHER = re.compile(TS_REGEX, re.MULTILINE)

# Packet config
STREAM_NAME_PARSED = DataParticleValue.PARSED
STREAM_NAME_RAW = DataParticleValue.RAW
PACKET_CONFIG = [STREAM_NAME_PARSED, STREAM_NAME_RAW]

PACKET_CONFIG = {
    STREAM_NAME_PARSED : 'ctd_parsed_param_dict',
    STREAM_NAME_RAW : 'ctd_raw_param_dict'
}

## Initialize the test parameters
InstrumentDriverTestCase.initialize(
    driver_module='mi.instrument.seabird.sbe26plus.ooicore.driver',
    driver_class="InstrumentDriver",

    instrument_agent_resource_id = '123xyz',
    instrument_agent_name = 'Agent007',
    instrument_agent_packet_config = PACKET_CONFIG,
    instrument_agent_stream_definition = ctd_stream_definition(stream_id=None)
)






# Device specific parameters.
class InstrumentCmds(BaseEnum):
    """
    Instrument Commands
    These are the commands that according to the science profile must be supported.
    """
    SETSAMPLING = 'setsampling'
    DISPLAY_STATUS = 'ds'
    QUIT_SESSION = 'qs'
    DISPLAY_CALIBRATION = 'dc'
    START_LOGGING = 'start'
    STOP_LOGGING = 'stop'
    #DISABLED# UPLOAD_DATA_ASCII_FORMAT = 'dd'
    SET = 'set'
    GET = 'get'
    #BAUD = 'baud'
    TAKE_SAMPLE = 'ts'
    INIT_LOGGING = 'initlogging'
    SET_TIME = "settime"

    SEND_LAST = 'sl'
    SEND_LAST_AND_SLEEP = 'slo'

class ProtocolState(BaseEnum):
    """
    Protocol states
    enum.
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    #TEST = DriverProtocolState.TEST                        # May cause problems
    #CALIBRATE = DriverProtocolState.CALIBRATE              # May cause problems
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS

class ProtocolEvent(BaseEnum):
    """
    Protocol events
    Should only have to define ones to ADD to the base class.  cannot remove from base class gracefully...
    """

    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    DISCOVER = DriverEvent.DISCOVER

    ACQUIRE_SAMPLE = DriverEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    SETSAMPLING = 'PROTOCOL_EVENT_SETSAMPLING'
    # SET_TIME = 'PROTOCOL_EVENT_SET_TIME'          # Disabling. This is inferior to using DateTime=
    #TEST = DriverEvent.TEST
    #RUN_TEST = DriverEvent.RUN_TEST
    #CALIBRATE = DriverEvent.CALIBRATE
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    FORCE_STATE = DriverEvent.FORCE_STATE
    #DISABLED#UPLOAD_ASCII = 'PROTOCOL_EVENT_UPLOAD_ASCII'
    QUIT_SESSION = 'PROTOCOL_EVENT_QUIT_SESSION'
    INIT_LOGGING = 'PROTOCOL_EVENT_INIT_LOGGING'
    START_DIRECT = DriverEvent.START_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT
    PING_DRIVER = DriverEvent.PING_DRIVER

    SEND_LAST = 'PROTOCOL_EVENT_SEND_LAST'
    SEND_LAST_AND_SLEEP = 'PROTOCOL_EVENT_SEND_LAST_AND_SLEEP'

    EXECUTE_CLOCK_SYNC = 'PROTOCOL_EVENT_EXECUTE_CLOCK_SYNC'
    # aquire status add....

class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    ACQUIRE_SAMPLE = ProtocolEvent.ACQUIRE_SAMPLE
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    #SETSAMPLING = ProtocolEvent.SETSAMPLING
    EXECUTE_CLOCK_SYNC = ProtocolEvent.EXECUTE_CLOCK_SYNC
    # aquire status add....

# Device specific parameters.
class Parameter(DriverParameter):
    """
    Device parameters
    """
    # DC
    '''
    PCALDATE = 'PCALDATE' # tuple,
    PU0 = 'PU0' # float,
    PY1 = 'PY1' # float,
    PY2 = 'PY2' # float,
    PY3 = 'PY3' # float,
    PC1 = 'PC1' # float,
    PC2 = 'PC2' # float,
    PC3 = 'PC3' # float,
    PD1 = 'PD1' # float,
    PD2 = 'PD2' # float,
    PT1 = 'PT1' # float,
    PT2 = 'PT2' # float,
    PT3 = 'PT3' # float,
    PT4 = 'PT4' # float,
    FACTORY_M = 'FACTORY_M' # float,
    FACTORY_B = 'FACTORY_B' # float,
    POFFSET = 'POFFSET' # float,
    TCALDATE = 'TCALDATE' # tuple,
    TA0 = 'TA0' # float,
    TA1 = 'TA1' # float,
    TA2 = 'TA2' # float,
    TA3 = 'TA3' # float,
    CCALDATE = 'CCALDATE' # tuple,
    CG = 'CG' # float,
    CH = 'CH' # float,
    CI = 'CI' # float,
    CJ = 'CJ' # float,
    CTCOR = 'CTCOR' # float,
    CPCOR = 'CPCOR' # float,
    CSLOPE = 'CSLOPE' # float,
    '''

    # DS
    DEVICE_VERSION = 'DEVICE_VERSION' # str,
    SERIAL_NUMBER = 'SERIAL_NUMBER' # str,
    DS_DEVICE_DATE_TIME = 'DateTime' # str for now, later ***
    USER_INFO = 'USERINFO' # str,
    QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER = 'QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER' # float,
    QUARTZ_PREASURE_SENSOR_RANGE = 'QUARTZ_PREASURE_SENSOR_RANGE' # float,
    EXTERNAL_TEMPERATURE_SENSOR = 'ExternalTemperature' # bool,
    CONDUCTIVITY = 'CONDUCTIVITY' # bool,
    IOP_MA = 'IOP_MA' # float,
    VMAIN_V = 'VMAIN_V' # float,
    VLITH_V = 'VLITH_V' # float,
    LAST_SAMPLE_P = 'LAST_SAMPLE_P' # float,
    LAST_SAMPLE_T = 'LAST_SAMPLE_T' # float,
    LAST_SAMPLE_S = 'LAST_SAMPLE_S' # float,

    # DS/SETSAMPLING
    TIDE_INTERVAL = 'TIDE_INTERVAL' # int,
    TIDE_MEASUREMENT_DURATION = 'TIDE_MEASUREMENT_DURATION' # int,
    TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS = 'TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS' # int,
    WAVE_SAMPLES_PER_BURST = 'WAVE_SAMPLES_PER_BURST' # float,
    WAVE_SAMPLES_SCANS_PER_SECOND = 'WAVE_SAMPLES_SCANS_PER_SECOND' # 4.0 = 0.25
    USE_START_TIME = 'USE_START_TIME' # bool,
    #START_TIME = 'START_TIME' # ***
    USE_STOP_TIME = 'USE_STOP_TIME' # bool,
    #STOP_TIME = 'STOP_TIME' # ***
    TXWAVESTATS = 'TXWAVESTATS' # bool,
    TIDE_SAMPLES_PER_DAY = 'TIDE_SAMPLES_PER_DAY' # float,
    WAVE_BURSTS_PER_DAY = 'WAVE_BURSTS_PER_DAY' # float,
    MEMORY_ENDURANCE = 'MEMORY_ENDURANCE' # float,
    NOMINAL_ALKALINE_BATTERY_ENDURANCE = 'NOMINAL_ALKALINE_BATTERY_ENDURANCE' # float,
    TOTAL_RECORDED_TIDE_MEASUREMENTS = 'TOTAL_RECORDED_TIDE_MEASUREMENTS' # float,
    TOTAL_RECORDED_WAVE_BURSTS = 'TOTAL_RECORDED_WAVE_BURSTS' # float,
    TIDE_MEASUREMENTS_SINCE_LAST_START = 'TIDE_MEASUREMENTS_SINCE_LAST_START' # float,
    WAVE_BURSTS_SINCE_LAST_START = 'WAVE_BURSTS_SINCE_LAST_START' # float,
    TXREALTIME = 'TxTide' # bool,
    TXWAVEBURST = 'TxWave' # bool,
    NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS = 'NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS' # int,
    USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC = 'USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC' # bool,
    USE_MEASURED_TEMP_FOR_DENSITY_CALC = 'USE_MEASURED_TEMP_FOR_DENSITY_CALC'
    AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR = 'AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR'
    AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR = 'AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR'
    PREASURE_SENSOR_HEIGHT_FROM_BOTTOM = 'PREASURE_SENSOR_HEIGHT_FROM_BOTTOM' # float,
    SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND = 'SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND' # int,
    MIN_ALLOWABLE_ATTENUATION = 'MIN_ALLOWABLE_ATTENUATION' # float,
    MIN_PERIOD_IN_AUTO_SPECTRUM = 'MIN_PERIOD_IN_AUTO_SPECTRUM' # float,
    MAX_PERIOD_IN_AUTO_SPECTRUM = 'MAX_PERIOD_IN_AUTO_SPECTRUM' # float,
    HANNING_WINDOW_CUTOFF = 'HANNING_WINDOW_CUTOFF' # float,
    SHOW_PROGRESS_MESSAGES = 'SHOW_PROGRESS_MESSAGES' # bool,
    STATUS = 'STATUS' # str,
    LOGGING = 'LOGGING' # bool,


    # *** Fields with *** Should be converted to use:
    #     ntp 4 64 bit timestamp http://stackoverflow.com/questions/8244204/ntp-timestamps-in-python

# Device prompts.
class Prompt(BaseEnum):
    """
    sbe26plus io prompts.
    """
    COMMAND = 'S>'
    BAD_COMMAND = '? cmd S>'
    AUTOSAMPLE = 'S>'
    CONFIRMATION_PROMPT = 'proceed Y/N ?'



###############################################################################
# Driver
###############################################################################

class InstrumentDriver(SingleConnectionInstrumentDriver):
    """
    InstrumentDriver subclass
    Subclasses SingleConnectionInstrumentDriver with connection state
    machine.
    """
    def __init__(self, evt_callback):
        """
        Driver constructor.
        @param evt_callback Driver process event callback.
        """
        #Construct superclass.
        SingleConnectionInstrumentDriver.__init__(self, evt_callback)

    ########################################################################
    # Superclass overrides for resource query.
    ########################################################################


    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)

###############################################################################
# Protocol
################################################################################


#remove TS stream,

class tsKey(BaseEnum):
    PREASURE = "preasure"           # p = calculated and stored pressure (psia).
    PREASURE_TEMP = "preasure_temp" # pt = calculated pressure temperature (not stored) (C).
    TEMPERATURE = "temperature"     # t = calculated and stored temperature (C).
    CONDUCTIVITY = "conductivity"   # c = calculated and stored conductivity (S/m)
    SALINITY = "salinity"           # s = calculated salinity (not stored) (psu).

class SBE26plusTakeSampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    # -158.9284 -8388.96  -3.2164
    ['p', 'pt', 't']
    # -158.5166 -8392.30  -3.2164 -1.02535   0.0000
    ['p', 'pt', 't', 'c', 's']
    """

    def _build_parsed_values(self):
        """
        Take something in the autosample format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

        pat1 = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)'
        regex1 = re.compile(pat1, re.MULTILINE|re.DOTALL)
        pat2 = r' +([\-\d.]+) +([\-\d.]+) +([\-\d.]+)'
        regex2 = re.compile(pat2, re.MULTILINE|re.DOTALL)

        count = 5
        match = regex1.match(self.raw_data)
        if not match:
            count = 3
            match = regex2.match(self.raw_data)
            if not match:
                raise SampleException("No regex match of parsed sample data: [%s]" %
                              self.raw_data)

        # initialize
        preasure = None
        preasure_temp = None
        temperature = None
        conductivity = None
        salinity = None

        if 2 < count:
            preasure = float(match.group(1))
            preasure_temp = float(match.group(2))
            temperature = float(match.group(3))


        if 5 == count:
            conductivity = float(match.group(4))
            salinity = float(match.group(5))



        result = [{DataParticleKey.VALUE_ID: SBE26plusTakeSampleDataParticleKey.PREASURE,
                   DataParticleKey.VALUE: preasure},
                  {DataParticleKey.VALUE_ID: SBE26plusTakeSampleDataParticleKey.PREASURE_TEMP,
                   DataParticleKey.VALUE: preasure_temp},
                  {DataParticleKey.VALUE_ID: SBE26plusTakeSampleDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: SBE26plusTakeSampleDataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: conductivity},
                  {DataParticleKey.VALUE_ID: SBE26plusTakeSampleDataParticleKey.SALINITY,
                   DataParticleKey.VALUE: salinity}]

        log.debug("in SBE26plusTakeSampleDataParticle._build_parsed_values result = " + repr(result))

        return result

class SBE26plusTideSampleDataParticleKey(BaseEnum):
    TIMESTAMP = "timestamp"
    PREASURE = "preasure"           # p = calculated and stored pressure (psia).
    PRESSURE_TEMP = "preasure_temp" # pt = calculated pressure temperature (not stored) (C).
    TEMPERATURE = "temperature"     # t = calculated and stored temperature (C).
    CONDUCTIVITY = "conductivity"   # c = calculated and stored conductivity (S/m)
    SALINITY = "salinity"           # s = calculated salinity (not stored) (psu).

class SBE26plusTideSampleDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """

    def _build_parsed_values(self):
        """
        Take something in the autosample format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

        pat1 = r'tide: start time = +(\d+ [A-Za-z]{3} \d{4} \d+:\d+:\d+), p = +([\-\d.]+), pt = +([\-\d.]+), t = +([\-\d.]+), c = +([\-\d.]+), s = +([\-\d.]+)\r\n'
        regex1 = re.compile(pat1)
        pat2 = r'tide: start time = +(\d+ [A-Za-z]{3} \d{4} \d+:\d+:\d+), p = +([\-\d.]+), pt = +([\-\d.]+), t = +([\-\d.]+)\r\n'
        regex2 = re.compile(pat2)

        match = regex1.match(self.raw_data)
        if not match:
            match = regex2.match(self.raw_data)
            if not match:
                raise SampleException("No regex match of parsed sample data: [%s]" %
                                     self.raw_data)

        # initialize
        timestamp = None
        pressure = None
        pressure_temp = None
        temperature = None
        conductivity = None
        salinity = None

        try:
            text_timestamp = match.group(1)
            py_timestamp = time.strptime(text_timestamp, "%d %b %Y %H:%M:%S")
            timestamp = ntplib.system_to_ntp_time(time.mktime(py_timestamp))

            pressure = float(match.group(2))
            pressure_temp = float(match.group(3))
            temperature = float(match.group(4))
        except ValueError:
            raise SampleException("ValueError while decoding floats in data: [%s]" %
                                  self.raw_data)

        try:
            conductivity = float(match.group(5))
            salinity = float(match.group(6))
        except ValueError:
            """
            These are optional. Quietly ignore if they dont occur.
            """


        result = [{DataParticleKey.VALUE_ID: SBE26plusTideSampleDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: SBE26plusTideSampleDataParticleKey.PRESSURE,
                   DataParticleKey.VALUE: pressure},
                  {DataParticleKey.VALUE_ID: SBE26plusTideSampleDataParticleKey.PRESSURE_TEMP,
                   DataParticleKey.VALUE: pressure_temp},
                  {DataParticleKey.VALUE_ID: SBE26plusTideSampleDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: SBE26plusTideSampleDataParticleKey.CONDUCTIVITY,
                   DataParticleKey.VALUE: conductivity},
                  {DataParticleKey.VALUE_ID: SBE26plusTideSampleDataParticleKey.SALINITY,
                   DataParticleKey.VALUE: salinity}]

        return result

class SBE26plusWaveBurstDataParticleKey(BaseEnum):
    TIMESTAMP = "timestamp"         # start time of wave measurement.
    PTFREQ = "ptfreq"               # ptfreq = pressure temperature frequency (Hz);
    PTRAW = "ptraw"                 # calculated pressure temperature number

class SBE26plusWaveBurstDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """
    def _build_parsed_values(self):
        """
        Take something in the autosample format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

        start_time_pat = r'wave: start time = +(\d+ [A-Za-z]{3} \d{4} \d+:\d+:\d+)'
        start_time_matcher = re.compile(start_time_pat)

        ptfreq_pat = r'wave: ptfreq = ([\d.]+)'
        ptfreq_matcher = re.compile(ptfreq_pat)

        ptraw_pat = r' +([\d.]+)'
        ptraw_matcher = re.compile(ptraw_pat)

        # initialize
        timestamp = None
        ptfreq = None
        ptraw = []

        for line in self.raw_data.split(NEWLINE):
            log.debug("SBE26plusWaveBurstDataParticle._build_parsed_values LINE = " + repr(line))
            matched = False

            match = start_time_matcher.match(line)
            if match:
                matched = True
                try:
                    text_timestamp = match.group(1)
                    py_timestamp = time.strptime(text_timestamp, "%d %b %Y %H:%M:%S")
                    timestamp = ntplib.system_to_ntp_time(time.mktime(py_timestamp))
                except ValueError:
                    raise SampleException("ValueError while decoding floats in data: [%s]" %
                                      self.raw_data)

            match = ptfreq_matcher.match(line)
            if match:
                matched = True
                try:
                    ptfreq = float(match.group(1))
                except ValueError:
                    raise SampleException("ValueError while decoding floats in data: [%s]" %
                                          self.raw_data)

            match = ptraw_matcher.match(line)
            if match:
                matched = True
                try:
                    ptraw.append(float(match.group(1)))
                except ValueError:
                    raise SampleException("ValueError while decoding floats in data: [%s]" %
                                          self.raw_data)

            if False == matched:
                raise SampleException("No regex match of parsed sample data: [%s]" %
                                      self.raw_data)

        result = [{DataParticleKey.VALUE_ID: SBE26plusWaveBurstDataParticleKey.TIMESTAMP,
                   DataParticleKey.VALUE: timestamp},
                  {DataParticleKey.VALUE_ID: SBE26plusWaveBurstDataParticleKey.PTFREQ,
                   DataParticleKey.VALUE: ptfreq},
                  {DataParticleKey.VALUE_ID: SBE26plusWaveBurstDataParticleKey.PTRAW,
                   DataParticleKey.VALUE: ptraw}]

        return result

class SBE26plusStatisticsDataParticleKey(BaseEnum):
    # deMeanTrend
    DEPTH = "depth"
    TEMPERATURE = "temperature"
    SALINITY = "salinity"
    DENSITY = "density"

    # Auto-Spectrum Statistics:
    N_AGV_BAND = "nAvgBand"
    TOTAL_VARIANCE = "total_variance"
    TOTAL_ENERGY = "total_energy"
    SIGNIFICANT_PERIOD = "significant_period"
    SIGNIFICANT_WAVE_HEIGHT = "significant_wave_height"

    # Time Series Statistics:
    TSS_WAVE_INTEGRATION_TIME = "tss_wave_integration_time"
    TSS_NUMBER_OF_WAVES = "tss_number_of_waves"
    TSS_TOTAL_VARIANCE = "tss_total_variance"
    TSS_TOTAL_ENERGY = "tss_total_energy"
    TSS_AVERAGE_WAVE_HEIGHT = "tss_average_wave_height"
    TSS_AVERAGE_WAVE_PERIOD = "tss_average_wave_period"
    TSS_MAXIMUM_WAVE_HEIGHT = "tss_maximum_wave_height"
    TSS_SIGNIFICANT_WAVE_HEIGHT = "tss_significant_wave_height"
    TSS_SIGNIFICANT_WAVE_PERIOD = "tss_significant_wave_period"
    TSS_H1_10 = "tss_height_highest_10_percent_waves"
    TSS_H1_100 = "tss_height_highest_1_percent_waves"

class SBE26plusStatisticsDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.
    """

    def _build_parsed_values(self):
        """
        Take something in the autosample format and split it into
        values with appropriate tags

        @throws SampleException If there is a problem with sample creation
        """

        '''

        "Auto-Spectrum Statistics:" + NEWLINE +\
        "   nAvgBand = 5" + NEWLINE +\
        "   total variance = 1.0896e-05" + NEWLINE +\
        "   total energy = 1.0939e-01" + NEWLINE +\
        "   significant period = 5.3782e-01" + NEWLINE +\
        "   significant wave height = 1.3204e-02" + NEWLINE +\
        "" + NEWLINE +\

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
        '''

        dtsd_matcher = re.compile(r'depth = +([\d.e+-]+), temperature = +([\d.e+-]+), salinity = +([\d.e+-]+), density = +([\d.e+-]+)')

        #going to err on the side of VERBOSE methinks...
        single_var_matchers  = {
            "nAvgBand":                 re.compile(r'   nAvgBand = (\d+)'),
            "total variance":           re.compile(r'   total variance = ([\d.e+-]+)'),
            "total energy":             re.compile(r'   total energy = ([\d.e+-]+)'),
            "significant period":       re.compile(r'   significant period = ([\d.e+-]+)'),
            "a significant wave height":re.compile(r'   significant wave height = ([\d.e+-]+)'),
            "wave integration time":    re.compile(r'   wave integration time = (\d+)'),
            "number of waves":          re.compile(r'   number of waves = (\d+)'),
            "total variance":           re.compile(r'   total variance = ([\d.e+-]+)'),
            "total energy":             re.compile(r'   total energy = ([\d.e+-]+)'),
            "average wave height":      re.compile(r'   average wave height = ([\d.e+-]+)'),
            "average wave period":      re.compile(r'   average wave period = ([\d.e+-]+)'),
            "maximum wave height":      re.compile(r'   maximum wave height = ([\d.e+-]+)'),
            "significant wave height":  re.compile(r'   significant wave height = ([\d.e+-]+)'),
            "t significant wave period":re.compile(r'   significant wave period = ([\d.e+-]+)'),
            "H1/10":                    re.compile(r'   H1/10 = ([\d.e+-]+)'),
            "H1/100":                   re.compile(r'   H1/100 = ([\d.e+-]+)')
        }

        # Initialize
        depth = None
        temperature = None
        salinity = None
        density = None
        single_var_matches  = {
            "nAvgBand":                 None,
            "total variance":           None,
            "total energy":             None,
            "significant period":       None,
            "a significant wave height":None,
            "wave integration time":    None,
            "number of waves":          None,
            "total variance":           None,
            "total energy":             None,
            "average wave height":      None,
            "average wave period":      None,
            "maximum wave height":      None,
            "significant wave height":  None,
            "t significant wave period":None,
            "H1/10":                    None,
            "H1/100":                   None
        }

        flip_key = None
        for line in self.raw_data.split(NEWLINE):
            if 'Auto-Spectrum Statistics:' in line:
                flip_key = 'a significant wave height'
            elif 'Time Series Statistics:' in line:
                flip_key = 't significant wave period'


            match = dtsd_matcher.match(line)
            if match:
                depth = float(match(1))
                temperature = float(match(2))
                salinity = float(match(3))
                density = float(match(4))

            for (key, matcher) in single_var_matchers:
                match = single_var_matchers[key].match(line)
                if match:
                    if key in ["nAvgBand", "wave integration time", "number of waves"]:
                        single_var_matches[key] = int(match(1))
                    else:
                        if "significant wave height" in line:
                            single_var_matches[flip_key] = float(match(1))
                        else:
                            single_var_matches[key] = float(match(1))


        result = [{DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.DEPTH,
                   DataParticleKey.VALUE: depth},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TEMPERATURE,
                   DataParticleKey.VALUE: temperature},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.SALINITY,
                   DataParticleKey.VALUE: salinity},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.DENSITY,
                   DataParticleKey.VALUE: density},

                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.N_AGV_BAND,
                   DataParticleKey.VALUE: single_var_matches["nAvgBand"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TOTAL_VARIANCE,
                   DataParticleKey.VALUE: single_var_matches["total variance"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TOTAL_ENERGY,
                   DataParticleKey.VALUE: single_var_matches["total energy"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.SIGNIFICANT_PERIOD,
                   DataParticleKey.VALUE: single_var_matches["significant period"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.SIGNIFICANT_WAVE_HEIGHT,
                   DataParticleKey.VALUE: single_var_matches["a significant wave height"]},

                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_WAVE_INTEGRATION_TIME,
                   DataParticleKey.VALUE: single_var_matches["wave integration time"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_NUMBER_OF_WAVES,
                   DataParticleKey.VALUE: single_var_matches["number of waves"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_TOTAL_VARIANCE,
                   DataParticleKey.VALUE: single_var_matches["total variance"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_TOTAL_ENERGY,
                   DataParticleKey.VALUE: single_var_matches["total energy"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_AVERAGE_WAVE_HEIGHT,
                   DataParticleKey.VALUE: single_var_matches["average wave height"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_AVERAGE_WAVE_PERIOD,
                   DataParticleKey.VALUE: single_var_matches["average wave period"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_MAXIMUM_WAVE_HEIGHT,
                   DataParticleKey.VALUE: single_var_matches["maximum wave height"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_SIGNIFICANT_WAVE_HEIGHT,
                   DataParticleKey.VALUE: single_var_matches["significant wave height"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_SIGNIFICANT_WAVE_PERIOD,
                   DataParticleKey.VALUE: single_var_matches["t significant wave period"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_H1_10,
                   DataParticleKey.VALUE: single_var_matches["H1/10"]},
                  {DataParticleKey.VALUE_ID: SBE26plusStatisticsDataParticleKey.TSS_H1_100,
                   DataParticleKey.VALUE: single_var_matches["H1/100"]}]

        return result


class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class for sbe26plus driver.
    Subclasses CommandResponseInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The sbe26plus newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build sbe26plus protocol state machine.
        self._protocol_fsm = InstrumentFSM(ProtocolState, ProtocolEvent, ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.ENTER,                  self._handler_unknown_enter)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.EXIT,                   self._handler_unknown_exit)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.DISCOVER,               self._handler_unknown_discover)
        self._protocol_fsm.add_handler(ProtocolState.UNKNOWN, ProtocolEvent.FORCE_STATE,            self._handler_unknown_force_state)

        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ENTER,                  self._handler_command_enter)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXIT,                   self._handler_command_exit)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.ACQUIRE_SAMPLE,         self._handler_command_acquire_sample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_AUTOSAMPLE,       self._handler_command_start_autosample)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.GET,                    self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SET,                    self._handler_command_set)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.SETSAMPLING,            self._handler_command_setsampling)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.EXECUTE_CLOCK_SYNC,     self._handler_execute_clock_sync)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.QUIT_SESSION,           self._handler_command_quit_session)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.INIT_LOGGING,           self._handler_command_init_logging)
        self._protocol_fsm.add_handler(ProtocolState.COMMAND, ProtocolEvent.START_DIRECT,           self._handler_command_start_direct)

        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.ENTER,               self._handler_autosample_enter)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.EXIT,                self._handler_autosample_exit)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.GET,                 self._handler_command_autosample_test_get)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SEND_LAST,           self._handler_command_autosample_send_last)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.SEND_LAST_AND_SLEEP, self._handler_command_autosample_send_last_and_sleep)
        self._protocol_fsm.add_handler(ProtocolState.AUTOSAMPLE, ProtocolEvent.STOP_AUTOSAMPLE,     self._handler_autosample_stop_autosample)

        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.ENTER,            self._handler_direct_access_enter)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXIT,             self._handler_direct_access_exit)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.EXECUTE_DIRECT,   self._handler_direct_access_execute_direct)
        self._protocol_fsm.add_handler(ProtocolState.DIRECT_ACCESS, ProtocolEvent.STOP_DIRECT,      self._handler_direct_access_stop_direct)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()



        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCmds.SETSAMPLING,                 self._build_setsampling_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_STATUS,              self._build_simple_command)
        self._add_build_handler(InstrumentCmds.QUIT_SESSION,                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.DISPLAY_CALIBRATION,         self._build_simple_command)
        self._add_build_handler(InstrumentCmds.START_LOGGING,               self._build_simple_command)
        self._add_build_handler(InstrumentCmds.STOP_LOGGING,                self._build_simple_command)

        self._add_build_handler(InstrumentCmds.SET,                         self._build_set_command)
        self._add_build_handler(InstrumentCmds.TAKE_SAMPLE,                 self._build_simple_command)
        self._add_build_handler(InstrumentCmds.INIT_LOGGING,                self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SEND_LAST_AND_SLEEP,         self._build_simple_command)
        self._add_build_handler(InstrumentCmds.SEND_LAST,                   self._build_simple_command)


        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCmds.SETSAMPLING,              self._parse_setsampling_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_STATUS,           self._parse_ds_response)
        self._add_response_handler(InstrumentCmds.DISPLAY_CALIBRATION,      self._parse_dc_response)
        self._add_response_handler(InstrumentCmds.SET,                      self._parse_set_response)
        self._add_response_handler(InstrumentCmds.TAKE_SAMPLE,              self._parse_ts_response)
        self._add_response_handler(InstrumentCmds.INIT_LOGGING,             self._parse_init_logging_response)
        self._add_response_handler(InstrumentCmds.SEND_LAST_AND_SLEEP,      self._parse_sl_slo_response)
        self._add_response_handler(InstrumentCmds.SEND_LAST,                self._parse_sl_slo_response)

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that splits samples
        """
        sieve_matchers = [TIDE_REGEX_MATCHER,
                          WAVE_REGEX_MATCHER,
                          STATS_REGEX_MATCHER,
                          SL_SLO_REGEX_MATCHER]

        return_list = []

        for matcher in sieve_matchers:
            for match in matcher.finditer(raw_data):
                #log.debug("GOT A MATCH!!!!   " +str((match.start(), match.end())) + str(raw_data[match.start(): match.end()]))

                return_list.append((match.start(), match.end()))

        return return_list

    def _filter_capabilities(self, events):
        """
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state; can be COMMAND or AUTOSAMPLE.
        @retval (next_state, result), (ProtocolState.COMMAND or
        State.AUTOSAMPLE, None) if successful.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentStateException if the device response does not correspond to
        an expected state.
        """

        timeout = kwargs.get('timeout', TIMEOUT)

        next_state = None
        result = None

        current_state = self._protocol_fsm.get_current_state()

        if current_state == ProtocolState.AUTOSAMPLE:
            result = ResourceAgentState.STREAMING

        elif current_state == ProtocolState.COMMAND:
            result = ResourceAgentState.IDLE

        elif current_state == ProtocolState.UNKNOWN:

            # Wakeup the device with timeout if passed.

            delay = 0.5

            prompt = self._wakeup(timeout=timeout, delay=delay)
            prompt = self._wakeup(timeout)

        # Set the state to change.
        # Raise if the prompt returned does not match command or autosample.

        self._do_cmd_resp(InstrumentCmds.DISPLAY_STATUS,timeout=timeout)
        self._do_cmd_resp(InstrumentCmds.DISPLAY_CALIBRATION,timeout=timeout)
        pd = self._param_dict.get_config()

        if pd[Parameter.LOGGING] == True:
            next_state = ProtocolState.AUTOSAMPLE
            result = ResourceAgentState.STREAMING
        elif pd[Parameter.LOGGING] == False:
            next_state = ProtocolState.COMMAND
            result = ResourceAgentState.IDLE
        else:
            raise InstrumentStateException('Unknown state.')

        return (next_state, result)

    def _handler_unknown_force_state(self, *args, **kwargs):
        """
        Force driver into a given state for the purposes of unit testing
        @param state=desired_state Required desired state to transition to.
        @raises InstrumentParameterException if no st'ate parameter.
        """
        log.debug("************* " + repr(kwargs))
        log.debug("************* in _handler_unknown_force_state()" + str(kwargs.get('state', None)))

        state = kwargs.get('state', None)  # via kwargs
        if state is None:
            raise InstrumentParameterException('Missing state parameter.')

        next_state = state
        result = state

        return (next_state, result)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """

        pass

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        # Command device to update parameters and send a config change event.

        self._restore_da_params()

        log.debug("*** IN _handler_command_enter(), updating params")
        self._update_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_acquire_sample(self, *args, **kwargs):
        """
        Acquire sample from SBE26 Plus.
        @retval (next_state, result) tuple, (None, sample dict).
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        @throws SampleException if a sample could not be extracted from result.
        """

        next_state = None
        next_agent_state = None
        result = None
        kwargs['timeout'] = 30
        result = self._do_cmd_resp('ts', *args, **kwargs)

        return (next_state, (next_agent_state, result))

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        pass

    def _handler_execute_clock_sync(self, *args, **kwargs):
        """
        execute a clock sync on the leading edge of a second change
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """

        next_state = None
        next_agent_state = None
        result = None

        timeout = kwargs.get('timeout', TIMEOUT)
        delay = 5
        prompt = self._wakeup(timeout=timeout, delay=delay)
        time.sleep(2)

        # lets clear out any past data so it doesnt confuse the command
        self._linebuf = ''
        self._promptbuf = ''
        '''
        t = time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        t_last = t

        while t == t_last:
            t_last = t
            t = time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime())))
        '''
        str_val = self._param_dict.format(Parameter.DS_DEVICE_DATE_TIME, get_timestamp_delayed("%d %b %Y %H:%M:%S"))
        set_cmd = '%s=%s' % (Parameter.DS_DEVICE_DATE_TIME, str_val) + NEWLINE
        self._do_cmd_direct(set_cmd)
        (prompt, response) = self._get_response(timeout=30)


        if response != set_cmd + Prompt.COMMAND:
            raise InstrumentProtocolException("_handler_execute_clock_sync - response != set_cmd")

        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException("_handler_execute_clock_sync - prompt != Prompt.COMMAND")


        return (next_state, (next_agent_state, result))

    ################################
    # SET / SETSAMPLING
    ################################

    def _handler_command_set(self, *args, **kwargs):
        """
        Perform a set command.
        @param args[0] parameter : value dict.
        @retval (next_state, result) tuple, (None, None).
        @throws InstrumentParameterException if missing set parameters, if set parameters not ALL and
        not a dict, or if paramter can't be properly formatted.
        @throws InstrumentTimeoutException if device cannot be woken for set command.
        @throws InstrumentProtocolException if set command could not be built or misunderstood.
        """
        next_state = None
        result = None
        # Retrieve required parameter.
        # Raise if no parameter provided, or not a dict.
        try:
            params = args[0]
            log.debug("######### params = " + str(repr(params)))


        except IndexError:
            raise InstrumentParameterException('Set command requires a parameter dict.')


        if not isinstance(params, dict):

            raise InstrumentParameterException('Set parameters not a dict.')

        # For each key, val in the dict, issue set command to device.
        # Raise if the command not understood.
        else:
            (set_params, ss_params) = self._split_params(**params)

            if set_params != {}:
                for (key, val) in set_params.iteritems():
                    log.debug("KEY = " + str(key) + " VALUE = " + str(val))
                    result = self._do_cmd_resp(InstrumentCmds.SET, key, val, **kwargs)
                    log.debug("**********************RESULT************* = " + str(result))

            if ss_params != {}:
                # ONLY do next if a param for it is present
                kwargs['expected_prompt'] = ", new value = "
                self._do_cmd_resp(InstrumentCmds.SETSAMPLING, ss_params, **kwargs)

            self._update_params()

        return (next_state, result)

    def _build_set_command(self, cmd, param, val):
        """
        Build handler for set commands. param=val followed by newline.
        String val constructed by param dict formatting function.
        @param param the parameter key to set.
        @param val the parameter value to set.
        @ retval The set command to be sent to the device.
        @ retval The set command to be sent to the device.
        @throws InstrumentProtocolException if the parameter is not valid or
        if the formatting function could not accept the value passed.
        """
        try:
            str_val = self._param_dict.format(param, val)
            set_cmd = '%s=%s' % (param, str_val)

            set_cmd = set_cmd + NEWLINE
        except KeyError:
            raise InstrumentParameterException('Unknown driver parameter %s' % param)

        return set_cmd

    def _parse_set_response(self, response, prompt):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """

        if prompt == Prompt.CONFIRMATION_PROMPT:
            self._connection.send("y")
            time.sleep(0.5)

        elif prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('Protocol._parse_set_response : Set command not recognized: %s' % response)

    def _handler_command_setsampling(self, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup and command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        next_state = None
        result = None

        kwargs['expected_prompt'] = ", new value = "

        result = self._do_cmd_resp(InstrumentCmds.SETSAMPLING, *args, **kwargs)
        log.debug("_handler_command_setsampling RESULT = " + str(result))
        return (next_state, result)

    def _build_setsampling_command(self, foo, *args, **kwargs):
        """
        Build handler for setsampling command.
        @param args[0] is a dict of the values to change
        @throws InstrumentParameterException if passed paramater is outside of allowed ranges.
        """
        log.debug("_build_setsampling_command setting _sampling_args")
        self._sampling_args = args[0]

        return InstrumentCmds.SETSAMPLING + NEWLINE

    def _parse_setsampling_response(self, response, prompt): #(self, cmd, *args, **kwargs):
        """
        Parse handler for set command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """



        desired_prompt = ", new value = "
        done = False
        while not done:
            (prompt, response) = self._get_response(expected_prompt=desired_prompt)
            self._promptbuf = ''
            self._linebuf = ''
            time.sleep(0.1)

            log.debug("prompt = " + str(prompt))
            log.debug("response = " + str(response))

            if "tide interval (integer minutes) " in response:
                if 'TIDE_INTERVAL' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['TIDE_INTERVAL']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "tide measurement duration (seconds)" in response:
                if 'TIDE_MEASUREMENT_DURATION' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['TIDE_MEASUREMENT_DURATION']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "measure wave burst after every N tide samples" in response:
                if 'TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "number of wave samples per burst (multiple of 4)" in response:
                if 'WAVE_SAMPLES_PER_BURST' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['WAVE_SAMPLES_PER_BURST']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "wave Sample duration (0.25, 0.50, 0.75, 1.0) seconds" in response:
                if 'WAVE_SAMPLES_SCANS_PER_SECOND' in self._sampling_args:
                    self._connection.send(self._float_to_string(1 / self._sampling_args['WAVE_SAMPLES_SCANS_PER_SECOND']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "use start time (y/n)" in response:
                if 'USE_START_TIME' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['USE_START_TIME']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "use stop time (y/n)" in response:
                if 'USE_STOP_TIME' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['USE_STOP_TIME']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "TXWAVESTATS (real-time wave statistics) (y/n)" in response:
                if 'TXWAVESTATS' in self._sampling_args:
                    if self._sampling_args['TXWAVESTATS'] == False:
                        done = True
                    self._connection.send(self._true_false_to_string(self._sampling_args['TXWAVESTATS']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "show progress messages (y/n) = " in response:
                if 'SHOW_PROGRESS_MESSAGES' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['SHOW_PROGRESS_MESSAGES']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "number of wave samples per burst to use for wave statistics = " in response:
                if 'NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "use measured temperature and conductivity for density calculation (y/n) = " in response:
                if 'USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "use measured temperature for density calculation " in response:
                if 'USE_MEASURED_TEMP_FOR_DENSITY_CALC' in self._sampling_args:
                    self._connection.send(self._true_false_to_string(self._sampling_args['USE_MEASURED_TEMP_FOR_DENSITY_CALC']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "average water temperature above the pressure sensor (deg C) = " in response:
                if 'AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)

            elif "average salinity above the pressure sensor (PSU) = " in response:
                if 'AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)

            elif "height of pressure sensor from bottom (meters) = " in response:
                if 'PREASURE_SENSOR_HEIGHT_FROM_BOTTOM' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['PREASURE_SENSOR_HEIGHT_FROM_BOTTOM']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "number of spectral estimates for each frequency band = " in response:
                if 'SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND' in self._sampling_args:
                    self._connection.send(self._int_to_string(self._sampling_args['SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "minimum allowable attenuation = " in response:
                if 'MIN_ALLOWABLE_ATTENUATION' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['MIN_ALLOWABLE_ATTENUATION']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "minimum period (seconds) to use in auto-spectrum = " in response:
                if 'MIN_PERIOD_IN_AUTO_SPECTRUM' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['MIN_PERIOD_IN_AUTO_SPECTRUM']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "maximum period (seconds) to use in auto-spectrum = " in response:
                if 'MAX_PERIOD_IN_AUTO_SPECTRUM' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['MAX_PERIOD_IN_AUTO_SPECTRUM']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
            elif "hanning window cutoff = " in response:
                done = True
                if 'HANNING_WINDOW_CUTOFF' in self._sampling_args:
                    self._connection.send(self._float_to_string(self._sampling_args['HANNING_WINDOW_CUTOFF']) + NEWLINE)
                else:
                    self._connection.send(NEWLINE)
                """
                the remaining prompts apply to real-time wave statistics
                    show progress messages (y/n) = n, new value = y
                    number of wave samples per burst to use for wave statistics = 512, new value = 555
                    use measured temperature and conductivity for density calculation (y/n) = y, new value =
                    height of pressure sensor from bottom (meters) = 600.0, new value = 55
                    number of spectral estimates for each frequency band = 5, new value =
                    minimum allowable attenuation = 0.0025, new value =
                    minimum period (seconds) to use in auto-spectrum = 0.0e+00, new value =
                    maximum period (seconds) to use in auto-spectrum = 1.0e+06, new value =
                    hanning window cutoff = 0.10, new value =
                resetting number of wave samples per burst to 512
                resetting number of samples to use for wave statistics to 512
                """
            else:

                raise InstrumentProtocolException('HOW DID I GET HERE! %s' % str(response) + str(prompt))




        prompt = ""
        while prompt != Prompt.COMMAND:
            (prompt, response) = self._get_response(expected_prompt=Prompt.COMMAND)

            log.debug("WARNING!!! UNEXPECTED RESPONSE " + repr(response))

        '''
        # Update params after changing them.

        self._update_params()

        # Verify that paramaters set via set are matching in the latest parameter scan.


        device_parameters = self._param_dict.get_config()
        for k in self._sampling_args.keys():
            try:
                log.debug("self._sampling_args " + k + " = " + str(self._sampling_args[k]))
            except:
                log.debug("self._sampling_args " + k + " = ERROR")
            try:
                log.debug("device_parameters " + k + " = " + str(device_parameters[k]))
            except:
                log.debug("device_parameters " + k + " = ERROR")
            if self._sampling_args[k] != device_parameters[k]:
                log.debug("FAILURE: " + str(k) + " was " + str(device_parameters[k]) + " and should have been " + str(self._sampling_args[k]))
                raise InstrumentParameterException("FAILURE: " + str(k) + " was " + str(device_parameters[k]) + " and should have been " + str(self._sampling_args[k]))
        '''


    def _split_params(self, **params):
        log.debug("PARAMS = " + str(params))
        ss_params = {}
        set_params = {}
        ss_keys = ['TIDE_INTERVAL',
                'TIDE_MEASUREMENT_DURATION',
                'TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS',
                'WAVE_SAMPLES_PER_BURST',
                'WAVE_SAMPLES_SCANS_PER_SECOND',
                'USE_START_TIME',
                'USE_STOP_TIME',
                'TXWAVESTATS',
                'SHOW_PROGRESS_MESSAGES',
                'NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS',
                'USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC',
                'USE_MEASURED_TEMP_FOR_DENSITY_CALC',
                'AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR',
                'AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR',
                'PREASURE_SENSOR_HEIGHT_FROM_BOTTOM',
                'SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND',
                'MIN_ALLOWABLE_ATTENUATION',
                'MIN_PERIOD_IN_AUTO_SPECTRUM',
                'MAX_PERIOD_IN_AUTO_SPECTRUM',
                'HANNING_WINDOW_CUTOFF']

        for (key, value) in params.iteritems():
            if key in ss_keys:
                ss_params[key] = value
            else:
                set_params[key] = value

        return(set_params, ss_params)


    ###############################
    # Init Logging
    ###############################

    def _handler_command_init_logging(self, *args, **kwargs):

        log.debug("in _handler_command_init_logging")

        next_state = None
        result = None

        kwargs['expected_prompt'] = "S>"
        log.debug("WANT " + repr(kwargs['expected_prompt']))
        result = self._do_cmd_resp(InstrumentCmds.INIT_LOGGING, *args, **kwargs)

        return (next_state, result)

    def _parse_init_logging_response(self, response, prompt):
        """
        Parse handler for init_logging command.
        @param response command response string.
        @param prompt prompt following command response.
        @throws InstrumentProtocolException if set command misunderstood.
        """

        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('Initlogging command not recognized: %s' % response)

        return True

    ########################################################################
    # Quit Session.
    ########################################################################

    def _handler_command_quit_session(self, *args, **kwargs):
        """
        Perform a command-response on the device.
        @param cmd The command to execute.
        @param args positional arguments to pass to the build handler.
        @param timeout=timeout optional wakeup and command timeout.
        @retval resp_result The (possibly parsed) response result.
        @raises InstrumentTimeoutException if the response did not occur in time.
        @raises InstrumentProtocolException if command could not be built or if response
        was not recognized.
        """

        next_state = None
        result = None

        result = self._do_cmd_no_resp(InstrumentCmds.QUIT_SESSION, *args, **kwargs)
        return (next_state, result)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.

        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Switch into autosample mode.
        @retval (next_state, result) tuple, (ProtocolState.AUTOSAMPLE,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command could not be built or misunderstood.
        """
        kwargs['expected_prompt'] = Prompt.COMMAND
        kwargs['timeout'] = 30
        log.info("SYNCING TIME WITH SENSOR")
        #self._do_cmd_resp(InstrumentCmds.SET, Parameter.DS_DEVICE_DATE_TIME, time.strftime("%d %b %Y %H:%M:%S", time.gmtime(time.mktime(time.localtime()))), **kwargs)
        self._do_cmd_resp(InstrumentCmds.SET, Parameter.DS_DEVICE_DATE_TIME, get_timestamp_delayed("%d %b %Y %H:%M:%S"), **kwargs)

        next_state = None
        result = None


        # Issue start command and switch to autosample if successful.
        self._do_cmd_no_resp(InstrumentCmds.START_LOGGING, *args, **kwargs)

        next_state = ProtocolState.AUTOSAMPLE
        next_agent_state = ResourceAgentState.STREAMING

        return (next_state, (next_agent_state, result))

    def _handler_command_autosample_test_get(self, *args, **kwargs):
        """
        Get device parameters from the parameter dict.
        @param args[0] list of parameters to retrieve, or DriverParameter.ALL.
        @throws InstrumentParameterException if missing or invalid parameter.
        """
        next_state = None
        result = None


        log.debug
        # Retrieve the required parameter, raise if not present.
        try:
            params = args[0]

        except IndexError:
            raise InstrumentParameterException('Get command requires a parameter list or tuple.')

        # If all params requested, retrieve config.
        if params == DriverParameter.ALL or DriverParameter.ALL in params:
            result = self._param_dict.get_config()

        # If not all params, confirm a list or tuple of params to retrieve.
        # Raise if not a list or tuple.
        # Retireve each key in the list, raise if any are invalid.

        else:
            if not isinstance(params, (list, tuple)):
                raise InstrumentParameterException('Get argument not a list or tuple.')
            result = {}
            for key in params:
                val = self._param_dict.get(key)
                result[key] = val

        return (next_state, result)

    def _handler_command_autosample_send_last_and_sleep(self, *args, **kwargs):
        """
        """
        next_state = None
        next_agent_state = None
        result = None

        log.debug("self._promptbuf = " + repr(self._promptbuf))
        log.debug("self._linebuf = " + repr(self._linebuf))
        self._linebuf = ''
        self._promptbuf = ''

        kwargs['timeout'] = 60
        kwargs['expected_prompt'] = "\r\n"
        result = self._do_cmd_resp(InstrumentCmds.SEND_LAST_AND_SLEEP, *args, **kwargs)
        log.debug("result = " + repr(result))
        return (next_state, (next_agent_state, result))

    def _handler_command_autosample_send_last(self, *args, **kwargs):
        """
        """
        next_state = None
        next_agent_state = None
        result = None


        log.debug("self._promptbuf = " + repr(self._promptbuf))
        log.debug("self._linebuf = " + repr(self._linebuf))
        self._linebuf = ''
        self._promptbuf = ''

        kwargs['timeout'] = 60
        kwargs['expected_prompt'] = "S>"
        log.debug(":::::::::::::::::::::::::::::::::::::::::::::BEFORE")
        result = self._do_cmd_resp(InstrumentCmds.SEND_LAST, *args, **kwargs)
        log.debug("result = " + repr(result))
        log.debug(":::::::::::::::::::::::::::::::::::::::::::::AFTER")
        return (next_state, (next_agent_state, result))

    def _parse_sl_slo_response(self, response, prompt):
        """
        Response handler for ts command.
        @param response command response string.
        @param prompt prompt following command response.
        @retval sample dictionary containig c, t, d values.
        @throws InstrumentProtocolException if ts command misunderstood.
        @throws InstrumentSampleException if response did not contain a sample
        """
        log.debug("************ in _parse_sl_slo_response ")

        log.debug("PROMPT = " + str(prompt) + " WANTED " + str(Prompt.COMMAND))
        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('sl/slo command not recognized: %s', response)
        log.debug("response = " + repr(response))


        log.debug("self._promptbuf = " + repr(self._promptbuf))
        log.debug("self._linebuf = " + repr(self._linebuf))

    def _handler_autosample_stop_autosample(self, *args, **kwargs):
        """
        Stop autosample and switch back to command mode.
        @retval (next_state, result) tuple, (ProtocolState.COMMAND,
        None) if successful.
        @throws InstrumentTimeoutException if device cannot be woken for command.
        @throws InstrumentProtocolException if command misunderstood or
        incorrect prompt received.
        """
        next_state = None
        result = None

        # Wake up the device, continuing until autosample prompt seen.
        timeout = kwargs.get('timeout', TIMEOUT)
        self._wakeup_until(timeout, Prompt.AUTOSAMPLE)

        # Issue the stop command.
        self._do_cmd_resp(InstrumentCmds.STOP_LOGGING, *args, **kwargs)

        # Prompt device until command prompt is seen.
        self._wakeup_until(timeout, Prompt.COMMAND)

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit autosample state.
        """
        pass

    ########################################################################
    # Common handlers.
    ########################################################################

    ########################################################################
    # Test handlers.
    ########################################################################


    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_command_start_direct(self, *args, **kwargs):
        """
        """

        next_state = None
        result = None

        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """

        self._save_da_params()

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)
        self._sent_cmds = []

    def _save_da_params(self):
        # Doing the ds command here causes issues.  I think we have to trust the last value that we
        # fetched from a ds/dc

        #self._do_cmd_resp(InstrumentCmds.DISPLAY_STATUS, timeout=kwargs.get('timeout', TIMEOUT))

        pd = self._param_dict.get_config()

        self._da_save_dict = {}
        for p in [Parameter.EXTERNAL_TEMPERATURE_SENSOR,
                  Parameter.CONDUCTIVITY,
                  Parameter.TXREALTIME,
                  Parameter.TXWAVEBURST]:
            self._da_save_dict[p] = pd[p]
            log.debug("DIRECT ACCESS PARAM SAVE " + str(p) + " = " + str(self._da_save_dict[p]))

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        next_state = None
        result = None
        next_agent_state = None

        self._do_cmd_direct(data)

        # add sent command to list for 'echo' filtering in callback
        self._sent_cmds.append(data)

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """

        next_state = None
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return (next_state, (next_agent_state, result))

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    def _restore_da_params(self):
        """
        called from _handler_command_enter, as it behaves poorly
        if caled from _handler_direct_access_exit
        @return:
        """
        run = True
        try:
            if self._da_save_dict == None:
                run = False
        except:
            run = False

        if run == True:
            # clear out the last command.
            self._promptbuf = ''
            self._linebuf = ''

            for k in self._da_save_dict.keys():
                v = self._da_save_dict[k]

                try:
                    str_val = self._param_dict.format(k, v)
                    set_cmd = '%s=%s' % (k, str_val) + NEWLINE
                    log.debug("DIRECT ACCESS PARAM RESTORE " + str(k) + "=" + str_val)
                except KeyError:
                    raise InstrumentParameterException('Unknown driver parameter %s' % param)

                # clear out the last command.
                self._promptbuf = ''
                self._linebuf = ''
                self._do_cmd_direct(set_cmd)

                (prompt, response) = self._get_response(timeout=30)
                while prompt != Prompt.COMMAND:
                    if prompt == Prompt.CONFIRMATION_PROMPT:
                        # clear out the last command.
                        self._promptbuf = ''
                        self._linebuf = ''
                        self._do_cmd_direct("y" + NEWLINE)
                        (prompt, response) = self._get_response(timeout=30)
                    else:
                        (prompt, response) = self._get_response(timeout=30)

            self._da_save_dict = None
            # clear out the last command.
            self._promptbuf = ''
            self._linebuf = ''

    ########################################################################
    # Private helpers.
    ########################################################################

    def _send_wakeup(self):
        """
        Send a newline to attempt to wake the sbe26plus device.
        """

        self._connection.send(NEWLINE)

    def _build_simple_command(self, cmd):
        """
        Build handler for basic sbe26plus commands.
        @param cmd the simple sbe37 command to format.
        @retval The command to be sent to the device.
        """

        return cmd + NEWLINE

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with sbe26plus parameters.
        For each parameter key, add match stirng, match lambda function,
        and value formatting function for set commands.

        """
        # Add parameter handlers to parameter dict.

        # DS

        ds_line_01 = r'SBE 26plus V ([\w.]+) +SN (\d+) +(\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)' # NOT DONE #
        ds_line_02 = r'user info=(.*)$'
        ds_line_03 = r'quartz pressure sensor: serial number = ([\d.\-]+), range = ([\d.\-]+) psia'

        ds_line_04 = r'(external|internal) temperature sensor' # NOT DONE #
        ds_line_05 = r'conductivity = (YES|NO)'
        ds_line_06 = r'iop = +([\d.\-]+) ma  vmain = +([\d.\-]+) V  vlith = +([\d.\-]+) V'

        ds_line_07a = r'last sample: p = +([\d.\-]+), t = +([\d.\-]+), s = +([\d.\-]+)'
        ds_line_07b = r'last sample: p = +([\d.\-]+), t = +([\d.\-]+)'

        ds_line_08 = r'tide measurement: interval = (\d+).000 minutes, duration = ([\d.\-]+) seconds'
        ds_line_09 = r'measure waves every ([\d.\-]+) tide samples'
        ds_line_10 = r'([\d.\-]+) wave samples/burst at ([\d.\-]+) scans/sec, duration = ([\d.\-]+) seconds'
        ds_line_11 = r'logging start time =  (\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)' # NOT DONE #

        ds_line_11b = r'logging start time = (do not) use start time'
        ds_line_12 = r'logging stop time =  (\d{2} [a-zA-Z]{3,4} \d{4} +[\d:]+)' # NOT DONE #
        ds_line_12b = r'logging stop time = (do not) use stop time'

        ds_line_13 = r'tide samples/day = (\d+.\d+)'
        ds_line_14 = r'wave bursts/day = (\d+.\d+)'
        ds_line_15 = r'memory endurance = (\d+.\d+) days'
        ds_line_16 = r'nominal alkaline battery endurance = (\d+.\d+) days'
        ds_line_16_b = r'deployments longer than 2 years are not recommended with alkaline batteries'
        ds_line_17 = r'total recorded tide measurements = ([\d.\-]+)'
        ds_line_18 = r'total recorded wave bursts = ([\d.\-]+)'
        ds_line_19 = r'tide measurements since last start = ([\d.\-]+)'
        ds_line_20 = r'wave bursts since last start = ([\d.\-]+)'

        ds_line_21 = r'transmit real-time tide data = (YES|NO)'
        ds_line_22 = r'transmit real-time wave burst data = (YES|NO)'
        ds_line_23 = r'transmit real-time wave statistics = (YES|NO)'
        # real-time wave statistics settings:
        ds_line_24 = r' +number of wave samples per burst to use for wave statistics = (\d+)'

        ds_line_25_a = r' +(do not|) use measured temperature and conductivity for density calculation'
        ds_line_25_b = r' +(do not|) use measured temperature for density calculation'

        ds_line_26 = r' +average water temperature above the pressure sensor \(deg C\) = ([\d.]+)' # float
        ds_line_27 = r' +average salinity above the pressure sensor \(PSU\) = ([\d.]+)' # float
        ds_line_28 = r' +height of pressure sensor from bottom \(meters\) = ([\d.]+)'
        ds_line_29 = r' +number of spectral estimates for each frequency band = (\d+)'
        ds_line_30 = r' +minimum allowable attenuation = ([\d.]+)'
        ds_line_31 = r' +minimum period \(seconds\) to use in auto-spectrum = (-?[\d.e\-\+]+)'
        ds_line_32 = r' +maximum period \(seconds\) to use in auto-spectrum = (-?[\d.e\-\+]+)'
        ds_line_33 = r' +hanning window cutoff = ([\d.]+)'
        ds_line_34 = r' +(do not show|show) progress messages' # NOT DONE #

        ds_line_35 = r'status = (logging|waiting|stopped)' # status = stopped by user
        ds_line_36 = r'logging = (YES|NO)' # logging = NO, send start command to begin logging

        #
        # Next 2 work together to pull 2 values out of a single line.
        #
        self._param_dict.add(Parameter.DEVICE_VERSION,
            ds_line_01,
            lambda match : string.upper(match.group(1)),
            self._string_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.SERIAL_NUMBER,
            ds_line_01,
            lambda match : string.upper(match.group(2)),
            self._string_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.DS_DEVICE_DATE_TIME,
            ds_line_01,
            lambda match : string.upper(match.group(3)),
            self._string_to_numeric_date_time_string,
            multi_match=True) # will need to make this a date time once that is sorted out

        self._param_dict.add(Parameter.USER_INFO,
            ds_line_02,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        #
        # Next 2 work together to pull 2 values out of a single line.
        #
        self._param_dict.add(Parameter.QUARTZ_PREASURE_SENSOR_SERIAL_NUMBER,
            ds_line_03,
            lambda match : float(match.group(1)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.QUARTZ_PREASURE_SENSOR_RANGE,
            ds_line_03,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.EXTERNAL_TEMPERATURE_SENSOR,
            ds_line_04,
            lambda match : False if (match.group(1)=='internal') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.CONDUCTIVITY,
            ds_line_05,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        #
        # Next 3 work together to pull 3 values out of a single line.
        #
        self._param_dict.add(Parameter.IOP_MA,
            ds_line_06,
            lambda match : float(match.group(1)),
            self._float_to_string,
            multi_match=True)
        self._param_dict.add(Parameter.VMAIN_V,
            ds_line_06,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)
        self._param_dict.add(Parameter.VLITH_V,
            ds_line_06,
            lambda match : float(match.group(3)),
            self._float_to_string,
            multi_match=True)

        #
        # Next 3 work together to pull 3 values out of a single line.
        #
        self._param_dict.add(Parameter.LAST_SAMPLE_P,
            ds_line_07a,
            lambda match : float(match.group(1)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.LAST_SAMPLE_T,
            ds_line_07a,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.LAST_SAMPLE_S,
            ds_line_07a,
            lambda match : float(match.group(3)),
            self._float_to_string,
            multi_match=True)

        #
        # Altewrnate for when S is not present
        #
        self._param_dict.add(Parameter.LAST_SAMPLE_P,
            ds_line_07b,
            lambda match : float(match.group(1)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.LAST_SAMPLE_T,
            ds_line_07b,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)

        #
        # Next 2 work together to pull 2 values out of a single line.
        #
        self._param_dict.add(Parameter.TIDE_INTERVAL,
            ds_line_08,
            lambda match : int(match.group(1)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.TIDE_MEASUREMENT_DURATION,
            ds_line_08,
            lambda match : int(match.group(2)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.TIDE_SAMPLES_BETWEEN_WAVE_BURST_MEASUREMENTS,
            ds_line_09,
            lambda match : float(match.group(1)),
            self._float_to_string)

        #
        # Next 3 work together to pull 3 values out of a single line.
        #
        self._param_dict.add(Parameter.WAVE_SAMPLES_PER_BURST,
            ds_line_10,
            lambda match : int(match.group(1)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.WAVE_SAMPLES_SCANS_PER_SECOND,
            ds_line_10,
            lambda match : float(match.group(2)),
            self._float_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS,
            ds_line_10,
            lambda match : int(match.group(3)),
            self._int_to_string,
            multi_match=True)

        self._param_dict.add(Parameter.USE_START_TIME,
            ds_line_11b,
            lambda match : False if (match.group(1)=='do not') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.USE_STOP_TIME,
            ds_line_12b,
            lambda match : False if (match.group(1)=='do not') else True,
            self._true_false_to_string)

        #self._param_dict.add(Parameter.START_TIME,
        #    ds_line_11,
        #    lambda match : string.upper(match.group(1)),
        #    self._string_to_string) # will need to make this a date time once that is sorted out

        #self._param_dict.add(Parameter.STOP_TIME,
        #    ds_line_12,
        #    lambda match : string.upper(match.group(1)),
        #    self._string_to_string) # will need to make this a date time once that is sorted out

        self._param_dict.add(Parameter.TIDE_SAMPLES_PER_DAY,
            ds_line_13,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.WAVE_BURSTS_PER_DAY,
            ds_line_14,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.MEMORY_ENDURANCE,
            ds_line_15,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.NOMINAL_ALKALINE_BATTERY_ENDURANCE,
            ds_line_16,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TOTAL_RECORDED_TIDE_MEASUREMENTS,
            ds_line_17,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TOTAL_RECORDED_WAVE_BURSTS,
            ds_line_18,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TIDE_MEASUREMENTS_SINCE_LAST_START,
            ds_line_19,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.WAVE_BURSTS_SINCE_LAST_START,
            ds_line_20,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TXREALTIME,
            ds_line_21,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.TXWAVEBURST,
            ds_line_22,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.TXWAVESTATS,
            ds_line_23,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.NUM_WAVE_SAMPLES_PER_BURST_FOR_WAVE_STASTICS,
            ds_line_24,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.USE_MEASURED_TEMP_AND_CONDUCTIVITY_FOR_DENSITY_CALC,
            ds_line_25_a,
            lambda match : False if (match.group(1)=='do not') else True,
            self._true_false_to_string)

        self._param_dict.add(Parameter.USE_MEASURED_TEMP_FOR_DENSITY_CALC,
            ds_line_25_b,
            lambda match : True if (match.group(1)=='do not') else False,
            self._true_false_to_string)

        self._param_dict.add(Parameter.AVERAGE_WATER_TEMPERATURE_ABOVE_PREASURE_SENSOR,
            ds_line_26,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.AVERAGE_SALINITY_ABOVE_PREASURE_SENSOR,
            ds_line_27,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PREASURE_SENSOR_HEIGHT_FROM_BOTTOM,
            ds_line_28,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.SPECTRAL_ESTIMATES_FOR_EACH_FREQUENCY_BAND,
            ds_line_29,
            lambda match : int(match.group(1)),
            self._int_to_string)

        self._param_dict.add(Parameter.MIN_ALLOWABLE_ATTENUATION,
            ds_line_30,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.MIN_PERIOD_IN_AUTO_SPECTRUM,
            ds_line_31,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.MAX_PERIOD_IN_AUTO_SPECTRUM,
            ds_line_32,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.HANNING_WINDOW_CUTOFF,
            ds_line_33,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.SHOW_PROGRESS_MESSAGES,
            ds_line_34,
            lambda match : True if (match.group(1)=='show') else False,
            self._true_false_to_string)

        self._param_dict.add(Parameter.STATUS,
            ds_line_35,
            lambda match : string.upper(match.group(1)),
            self._string_to_string)

        self._param_dict.add(Parameter.LOGGING,
            ds_line_36,
            lambda match : False if (match.group(1)=='NO') else True,
            self._true_false_to_string)
        ################################################

        # dc
        dc_line_01 = r'Pressure coefficients: +(\d+-[a-zA-Z]+-\d+)'
        dc_line_02 = r' +U0 = (-?[\d.e\-\+]+)'
        dc_line_03 = r' +Y1 = (-?[\d.e\-\+]+)'
        dc_line_04 = r' +Y2 = (-?[\d.e\-\+]+)'
        dc_line_05 = r' +Y3 = (-?[\d.e\-\+]+)'
        dc_line_06 = r' +C1 = (-?[\d.e\-\+]+)'
        dc_line_07 = r' +C2 = (-?[\d.e\-\+]+)'
        dc_line_08 = r' +C3 = (-?[\d.e\-\+]+)'
        dc_line_09 = r' +D1 = (-?[\d.e\-\+]+)'
        dc_line_10 = r' +D2 = (-?[\d.e\-\+]+)'
        dc_line_11 = r' +T1 = (-?[\d.e\-\+]+)'
        dc_line_12 = r' +T2 = (-?[\d.e\-\+]+)'
        dc_line_13 = r' +T3 = (-?[\d.e\-\+]+)'
        dc_line_14 = r' +T4 = (-?[\d.e\-\+]+)'
        dc_line_15 = r' +M = ([\d.]+)'
        dc_line_16 = r' +B = ([\d.]+)'
        dc_line_17 = r' +OFFSET = (-?[\d.e\-\+]+)'
        dc_line_18 = r'Temperature coefficients: +(\d+-[a-zA-Z]+-\d+)'
        dc_line_19 = r' +TA0 = (-?[\d.e\-\+]+)'
        dc_line_20 = r' +TA1 = (-?[\d.e\-\+]+)'
        dc_line_21 = r' +TA2 = (-?[\d.e\-\+]+)'
        dc_line_22 = r' +TA3 = (-?[\d.e\-\+]+)'
        dc_line_23 = r'Conductivity coefficients: +(\d+-[a-zA-Z]+-\d+)'
        dc_line_24 = r' +CG = (-?[\d.e\-\+]+)'
        dc_line_25 = r' +CH = (-?[\d.e\-\+]+)'
        dc_line_26 = r' +CI = (-?[\d.e\-\+]+)'
        dc_line_27 = r' +CJ = (-?[\d.e\-\+]+)'
        dc_line_28 = r' +CTCOR = (-?[\d.e\-\+]+)'
        dc_line_29 = r' +CPCOR = (-?[\d.e\-\+]+)'
        dc_line_30 = r' +CSLOPE = (-?[\d.e\-\+]+)'
        # S>


        # DC
        self._param_dict.add(Parameter.PCALDATE,
            dc_line_01,
            lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
            self._date_to_string)

        self._param_dict.add(Parameter.PU0,
            dc_line_02,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY1,
            dc_line_03,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY2,
            dc_line_04,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PY3,
            dc_line_05,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC1,
            dc_line_06,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC2,
            dc_line_07,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PC3,
            dc_line_08,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PD1,
            dc_line_09,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PD2,
            dc_line_10,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT1,
            dc_line_11,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT2,
            dc_line_12,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT3,
            dc_line_13,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.PT4,
            dc_line_14,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.FACTORY_M,
            dc_line_15,
            lambda match : float(match.group(1)),
            self._float_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.FACTORY_B,
            dc_line_16,
            lambda match : float(match.group(1)),
            self._float_to_string,
            visibility=ParameterDictVisibility.READ_ONLY)

        self._param_dict.add(Parameter.POFFSET,
            dc_line_17,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TCALDATE,
            dc_line_18,
            lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
            self._date_to_string)

        self._param_dict.add(Parameter.TA0,
            dc_line_19,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TA1,
            dc_line_20,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TA2,
            dc_line_21,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.TA3,
            dc_line_22,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CCALDATE,
            dc_line_23,
            lambda match : self._string_to_date(match.group(1), '%d-%b-%y'),
            self._date_to_string)

        self._param_dict.add(Parameter.CG,
            dc_line_24,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CH,
            dc_line_25,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CI,
            dc_line_26,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CJ,
            dc_line_27,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CTCOR,
            dc_line_28,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CPCOR,
            dc_line_29,
            lambda match : float(match.group(1)),
            self._float_to_string)

        self._param_dict.add(Parameter.CSLOPE,
            dc_line_30,
            lambda match : float(match.group(1)),
            self._float_to_string)

    def _update_params(self, *args, **kwargs):
        """
        Update the parameter dictionary. Wake the device then issue
        display status and display calibration commands. The parameter
        dict will match line output and udpate itself.
        @throws InstrumentTimeoutException if device cannot be timely woken.
        @throws InstrumentProtocolException if ds/dc misunderstood.
        """


        # Get old param dict config.
        old_config = self._param_dict.get_config()

        # Issue display commands and parse results.
        timeout = kwargs.get('timeout', TIMEOUT)
        self._do_cmd_resp(InstrumentCmds.DISPLAY_STATUS, timeout=timeout)
        self._do_cmd_resp(InstrumentCmds.DISPLAY_CALIBRATION, timeout=timeout)

        # Get new param dict config. If it differs from the old config,
        # tell driver superclass to publish a config change event.
        new_config = self._param_dict.get_config()
        if new_config != old_config:
            self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)

    def _parse_ds_response(self, response, prompt):
        """
        Response handler for ds command
        """
        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(NEWLINE):
            hit_count = self._param_dict.multi_match_update(line)
            #log.debug("MATCH COUNT = " + str(hit_count))

    def _parse_dc_response(self, response, prompt):
        """
        Response handler for dc command
        """
        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('dsdc command not recognized: %s.' % response)

        for line in response.split(NEWLINE):
            hit_count = self._param_dict.multi_match_update(line)
            #log.debug("MATCH COUNT = " + str(hit_count))

    def _parse_ts_response(self, response, prompt):
        """
        Response handler for ts command.
        @param response command response string.
        @param prompt prompt following command response.
        @retval sample dictionary containig c, t, d values.
        @throws InstrumentProtocolException if ts command misunderstood.
        @throws InstrumentSampleException if response did not contain a sample
        """
        log.debug("************ in _parse_ts_response ")

        log.debug("PROMPT = " + str(prompt) + " WANTED " + str(Prompt.COMMAND))
        if prompt != Prompt.COMMAND:
            raise InstrumentProtocolException('ts command not recognized: %s', response)

        sample = None
        for line in response.split(NEWLINE):
            sample = self._extract_sample(SBE26plusTakeSampleDataParticle, TS_REGEX_MATCHER, line, True)
            if sample:
                break

        if not sample:
            raise SampleException('Response did not contain sample: %s' % repr(response))

        return sample

    def got_data(self, paPacket):
        """
        Callback for receiving new data from the device.
        """

        paLength = paPacket.get_data_size()
        paData = paPacket.get_data()



        if self.get_current_state() == ProtocolState.DIRECT_ACCESS:
            # direct access mode
            if paLength > 0:
                if len(self._sent_cmds) > 0:
                    # there are sent commands that need to have there echoes filtered out
                    oldest_sent_cmd = self._sent_cmds[0]
                    if string.count(paData, oldest_sent_cmd) > 0:
                        # found a command echo, so remove it from data and delete the command form list
                        paData = string.replace(paData, oldest_sent_cmd, "", 1)
                        self._sent_cmds.pop(0)
                if len(paData) > 0 and self._driver_event:
                    self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, paData)
                    # TODO: what about logging this as an event?
            return

        if paLength > 0:
            # Call the superclass to update line and prompt buffers.
            CommandResponseInstrumentProtocol.got_data(self, paData)

            # If in streaming mode, process the buffer for samples to publish.
            cur_state = self.get_current_state()
            if cur_state == ProtocolState.AUTOSAMPLE:
                # if in autosample mode, hand data to chunker by default, unless... a SL SLO is detected...

                self._chunker.add_chunk(paData)
                chunk = self._chunker.get_next_data()
                if chunk != None:
                    # Determine what particle type it is and push accordingly

                    self._extract_sample(SBE26plusTideSampleDataParticle, TIDE_REGEX_MATCHER, chunk)
                    self._extract_sample(SBE26plusWaveBurstDataParticle, WAVE_REGEX_MATCHER, chunk)
                    self._extract_sample(SBE26plusStatisticsDataParticle, STATS_REGEX_MATCHER, chunk)

                    # Need to catch if its SL/SLO and return that result (publishing optional.
                    #self._extract_sample(SBE26plus__________DataParticle, SL_SLO_REGEX_MATCHER, chunk)

    ########################################################################
    # Static helpers to format set commands.
    ########################################################################

    @staticmethod
    def _string_to_string(v):
        return v

    @staticmethod
    # Should be renamed boolen_to_string for consistency
    def _true_false_to_string(v):
        """
        Write a boolean value to string formatted for sbe37 set operations.
        @param v a boolean value.
        @retval A yes/no string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value not a bool.
        """

        if not isinstance(v,bool):
            raise InstrumentParameterException('Value %s is not a bool.' % str(v))
        if v:
            return 'y'
        else:
            return 'n'

    @staticmethod
    def _int_to_string(v):
        """
        Write an int value to string formatted for sbe37 set operations.
        @param v An int val.
        @retval an int string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value not an int.
        """

        if not isinstance(v,int):
            raise InstrumentParameterException('Value %s is not an int.' % str(v))
        else:
            return '%i' % v

    @staticmethod
    def _float_to_string(v):
        """
        Write a float value to string formatted for sbe37 set operations.
        @param v A float val.
        @retval a float string formatted for sbe37 set operations.
        @throws InstrumentParameterException if value is not a float.
        """


        if not isinstance(v, float):
            raise InstrumentParameterException('Value %s is not a float.' % v)
        else:
            #return '%e' % v #This returns a exponential formatted float
            # every time. not what is needed
            return str(v) #return a simple float

    @staticmethod
    def _date_to_string(v):
        """
        Write a date tuple to string formatted for sbe37 set operations.
        @param v a date tuple: (day,month,year).
        @retval A date string formatted for sbe37 set operations.
        @throws InstrumentParameterException if date tuple is not valid.
        """

        if not isinstance(v,(list,tuple)):
            raise InstrumentParameterException('Value %s is not a list, tuple.' % str(v))

        if not len(v)==3:
            raise InstrumentParameterException('Value %s is not length 3.' % str(v))

        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep',
                  'Oct','Nov','Dec']
        day = v[0]
        month = v[1]
        year = v[2]

        if len(str(year)) > 2:
            year = int(str(year)[-2:])

        if not isinstance(day,int) or day < 1 or day > 31:
            raise InstrumentParameterException('Value %s is not a day of month.' % str(day))

        if not isinstance(month,int) or month < 1 or month > 12:
            raise InstrumentParameterException('Value %s is not a month.' % str(month))

        if not isinstance(year,int) or year < 0 or year > 99:
            raise InstrumentParameterException('Value %s is not a 0-99 year.' % str(year))

        return '%02i-%s-%02i' % (day,months[month-1],year)

    @staticmethod
    def _string_to_date(datestr, fmt):
        """
        Extract a date tuple from an sbe37 date string.
        @param str a string containing date information in sbe37 format.
        @retval a date tuple.
        @throws InstrumentParameterException if datestr cannot be formatted to
        a date.
        """

        if not isinstance(datestr, str):
            raise InstrumentParameterException('Value %s is not a string.' % str(datestr))
        try:
            date_time = time.strptime(datestr, fmt)
            date = (date_time[2],date_time[1],date_time[0])

        except ValueError:
            raise InstrumentParameterException('Value %s could not be formatted to a date.' % str(datestr))

        return date

    @staticmethod
    def _string_to_numeric_date_time_string(date_time_string):
        """
        convert string from "21 AUG 2012  09:51:55" to numeric "mmddyyyyhhmmss"
        """

        return time.strftime("%m%d%Y%H%M%S", time.strptime(date_time_string, "%d %b %Y %H:%M:%S"))

