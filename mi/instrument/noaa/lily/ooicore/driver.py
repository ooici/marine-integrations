"""
@package mi.instrument.noaa.lily.ooicore.driver
@file marine-integrations/mi/instrument/noaa/lily/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for LILY TILT on the RSN-BOTPT instrument (v.6)

"""

# TODO - leveling failures
# TODO - parse status
# TODO - leveling timeout as parameter
# TODO -

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

#import string
import re
import time
#import datetime
import ntplib
import threading

from mi.core.log import get_logger

log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
from mi.core.instrument.instrument_fsm import ThreadSafeFSM
from mi.core.instrument.instrument_driver import SingleConnectionInstrumentDriver
from mi.core.instrument.instrument_driver import DriverEvent
from mi.core.instrument.instrument_driver import DriverAsyncEvent
from mi.core.instrument.instrument_driver import DriverProtocolState
from mi.core.instrument.instrument_driver import DriverParameter
from mi.core.instrument.instrument_driver import ResourceAgentState
from mi.core.instrument.protocol_cmd_dict import ProtocolCommandDict
from mi.core.instrument.protocol_param_dict import ParameterDictVisibility
from mi.core.instrument.protocol_param_dict import ParameterDictType
from mi.core.instrument.data_particle import DataParticle
from mi.core.instrument.data_particle import DataParticleKey
from mi.core.instrument.chunker import StringChunker
from mi.core.instrument.instrument_driver import DriverConfigKey
from mi.core.driver_scheduler import DriverSchedulerConfigKey
from mi.core.driver_scheduler import TriggerType

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import SampleException

###
#    Driver Constant Definitions
###

# newline.
NEWLINE = '\x0a'
MAX_BUFFER_LENGTH = 10
LILY_STRING = 'LILY,'
LILY_COMMAND_STRING = '*9900XY'
LILY_DATA_ON = 'C2'  # turns on continuous data
LILY_DATA_OFF = 'C-OFF'  # turns off continuous data
LILY_DUMP_01 = '-DUMP-SETTINGS'  # outputs current settings
LILY_DUMP_02 = '-DUMP2'  # outputs current extended settings
LILY_LEVEL_ON = '-LEVEL,1'
LILY_LEVEL_OFF = '-LEVEL,0'

LILY_TIME_REGEX = r'(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d)'
FLOAT_REGEX = r'(-?\d*\.\d*)'
WORD_REGEX = r'(\S+)'

# default timeout.
TIMEOUT = 10

DEFAULT_LEVELING_TIMEOUT = 120
DEFAULT_XTILT_TRIGGER = 300
DEFAULT_YTILT_TRIGGER = 300
DEFAULT_AUTO_RELEVEL = True  # default to be true

DISCOVER_REGEX = re.compile(r'(LILY,.*%s)' % NEWLINE)

promptbuf_mutex = threading.Lock()


class ScheduledJob(BaseEnum):
    LEVELING_TIMEOUT = 'leveling_timeout'


class ProtocolState(BaseEnum):
    """
    Instrument protocol states
    """
    UNKNOWN = DriverProtocolState.UNKNOWN
    COMMAND = DriverProtocolState.COMMAND
    AUTOSAMPLE = DriverProtocolState.AUTOSAMPLE
    DIRECT_ACCESS = DriverProtocolState.DIRECT_ACCESS
    COMMAND_LEVELING = 'LILY_DRIVER_STATE_COMMAND_LEVELING'
    AUTOSAMPLE_LEVELING = 'LILY_DRIVER_STATE_AUTOSAMPLE_LEVELING'


class ExportedInstrumentCommand(BaseEnum):
    DUMP_01 = "EXPORTED_INSTRUMENT_DUMP_SETTINGS"
    DUMP_02 = "EXPORTED_INSTRUMENT_DUMP_EXTENDED_SETTINGS"
    START_LEVELING = "EXPORTED_INSTRUMENT_START_LEVELING"
    STOP_LEVELING = "EXPORTED_INSTRUMENT_STOP_LEVELING"


class ProtocolEvent(BaseEnum):
    """
    Protocol events
    """
    ENTER = DriverEvent.ENTER
    EXIT = DriverEvent.EXIT
    GET = DriverEvent.GET
    SET = DriverEvent.SET
    START_AUTOSAMPLE = DriverEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = DriverEvent.STOP_AUTOSAMPLE
    DISCOVER = DriverEvent.DISCOVER
    DUMP_01 = ExportedInstrumentCommand.DUMP_01
    DUMP_02 = ExportedInstrumentCommand.DUMP_02
    START_LEVELING = ExportedInstrumentCommand.START_LEVELING
    STOP_LEVELING = ExportedInstrumentCommand.STOP_LEVELING
    LEVELING_COMPLETE = "PROTOCOL_EVENT_LEVELING_COMPLETE"
    LEVELING_TIMEOUT = "PROTOCOL_EVENT_LEVELING_TIMEOUT"
    START_DIRECT = DriverEvent.START_DIRECT
    EXECUTE_DIRECT = DriverEvent.EXECUTE_DIRECT
    STOP_DIRECT = DriverEvent.STOP_DIRECT


class Capability(BaseEnum):
    """
    Protocol events that should be exposed to users (subset of above).
    """
    GET = ProtocolEvent.GET
    SET = ProtocolEvent.SET
    START_AUTOSAMPLE = ProtocolEvent.START_AUTOSAMPLE
    STOP_AUTOSAMPLE = ProtocolEvent.STOP_AUTOSAMPLE
    DUMP_01 = ProtocolEvent.DUMP_01
    DUMP_02 = ProtocolEvent.DUMP_02
    START_LEVELING = ProtocolEvent.START_LEVELING
    STOP_LEVELING = ProtocolEvent.STOP_LEVELING


class Parameter(DriverParameter):
    """
    Device specific parameters.
    """
    AUTO_RELEVEL = "auto_relevel"  # Auto-relevel mode
    XTILT_RELEVEL_TRIGGER = "xtilt_relevel_trigger"
    YTILT_RELEVEL_TRIGGER = "ytilt_relevel_trigger"


class Prompt(BaseEnum):
    """
    Device i/o prompts..
    """


class LevelingTriggers(object):
    xtilt_relevel_trigger = DEFAULT_XTILT_TRIGGER
    ytilt_relevel_trigger = DEFAULT_YTILT_TRIGGER


###############################################################################
# Command Response (not a particle but uses regex and chunker to parse command
# responses rather than the normal get_response() method)
###############################################################################

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    DATA_ON = LILY_STRING + LILY_COMMAND_STRING + LILY_DATA_ON  # turns on continuous data
    DATA_OFF = LILY_STRING + LILY_COMMAND_STRING + LILY_DATA_OFF  # turns off continuous data
    DUMP_SETTINGS_01 = LILY_STRING + LILY_COMMAND_STRING + LILY_DUMP_01  # outputs current settings
    DUMP_SETTINGS_02 = LILY_STRING + LILY_COMMAND_STRING + LILY_DUMP_02  # outputs current extended settings
    START_LEVELING = LILY_STRING + LILY_COMMAND_STRING + LILY_LEVEL_ON  # starts leveling
    STOP_LEVELING = LILY_STRING + LILY_COMMAND_STRING + LILY_LEVEL_OFF  # stops leveling


###############################################################################
# Data Particles
###############################################################################

class DataParticleType(BaseEnum):
    LILY_PARSED = 'botpt_lily_sample'
    LILY_STATUS = 'botpt_lily_status'
    LILY_RE_LEVELING = 'lily_re-leveling'


class LILYDataParticleKey(BaseEnum):
    TIME = "lily_time"
    X_TILT = "lily_x_tilt"
    Y_TILT = "lily_y_tilt"
    MAG_COMPASS = "lily_mag_compass"
    TEMP = "temperature"
    SUPPLY_VOLTS = "supply_voltage"
    SN = "serial_number"


class LILYDataParticle(DataParticle):
    """
    Routines for parsing raw data into a data particle structure. Override
    the building of values, and the rest should come along for free.

    Sample:
       LILY,2013/06/24 23:22:00,-236.026,  25.666,194.25, 26.01,11.96,N9655
       LILY,2013/06/24 23:22:02,-236.051,  25.611,194.25, 26.02,11.96,N9655
    Format:
       IIII,YYYY/MM/DD hh:mm:ss,xxx.xxx,yyy.yyy,mmm.mm,tt.tt,vv.vv,sn

        ID = IIII = LILY
        Year = YYYY
        Month = MM
        Day = DD
        Hour = hh
        Minutes = mm
        Seconds = ss
        NOTE: The above time expression is all grouped into one string.
        X_TILT = x.xxxx (float degrees)
        Y_TILT = y.yyyy (float degrees)
        MagCompass = mmm.mm
        Temp = tt.tt (float degrees C)
        SupplyVolts = vv.vv
        Serial Number = sn
    """
    _data_particle_type = DataParticleType.LILY_PARSED
    _compiled_regex = None

    def __init__(self, raw_data,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP):

        super(LILYDataParticle, self).__init__(raw_data,
                                               port_timestamp,
                                               internal_timestamp,
                                               preferred_timestamp)

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = [
            'LILY',
            LILY_TIME_REGEX,  # 1 time
            FLOAT_REGEX,  # 2 x-tilt
            FLOAT_REGEX,  # 3 y-tilt
            FLOAT_REGEX,  # 4 Magnetic Compass (degrees)
            FLOAT_REGEX,  # 5 temp
            FLOAT_REGEX,  # 6 SupplyVolts
            WORD_REGEX,  # 7 serial number
        ]
        return r'\s*,\s*'.join(pattern) + NEWLINE

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if LILYDataParticle._compiled_regex is None:
            LILYDataParticle._compiled_regex = re.compile(LILYDataParticle.regex())
        return LILYDataParticle._compiled_regex

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)
        
        @throws SampleException If there is a problem with sample creation
        """
        match = LILYDataParticle.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        log.error("_build_parsed_values")

        try:
            lily_time = match.group(1)
            timestamp = time.strptime(lily_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            x_tilt = float(match.group(2))
            y_tilt = float(match.group(3))
            mag_compass = float(match.group(4))
            temperature = float(match.group(5))
            supply_volts = float(match.group(6))
            sn = str(match.group(7))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.TIME,
             DataParticleKey.VALUE: ntp_timestamp},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.X_TILT,
             DataParticleKey.VALUE: x_tilt},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.Y_TILT,
             DataParticleKey.VALUE: y_tilt},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.MAG_COMPASS,
             DataParticleKey.VALUE: mag_compass},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.SUPPLY_VOLTS,
             DataParticleKey.VALUE: supply_volts},
            {DataParticleKey.VALUE_ID: LILYDataParticleKey.SN,
             DataParticleKey.VALUE: sn}
        ]

        return result


###############################################################################
# Status Particles
###############################################################################
class LILYStatusSignOnParticleKey(BaseEnum):
    MODEL = "model"
    SN = "serial_number"
    FIRMWARE_VERSION = "firmware_version"
    IDENTITY = "identity"
    TIME = "lily_time"


class LILYStatusSignOnParticle(DataParticle):
    _data_particle_type = DataParticleType.LILY_STATUS
    _compiled_regex = None

    @staticmethod
    def regex():
        """
        Example of output from display signon command (Note: we don't issue this command,
        but the output is prepended to the DUMP-SETTINGS command):
        
        LILY,2013/06/12 18:03:44,*APPLIED GEOMECHANICS Model MD900-T Firmware V5.2 SN-N8642 ID01
        """

        pattern = r'LILY,'  # pattern starts with LILY '
        pattern += r'(.*?),'  # group 1: time
        pattern += r'\*APPLIED GEOMECHANICS'
        pattern += r'.*?'  # non-greedy match of all the junk between
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        if LILYStatusSignOnParticle._compiled_regex is None:
            LILYStatusSignOnParticle._compiled_regex = re.compile(LILYStatusSignOnParticle.regex())
        return LILYStatusSignOnParticle._compiled_regex

    def _build_parsed_values(self):
        """        
        @throws SampleException If there is a problem with sample creation
        """
        match = LILYStatusSignOnParticle.regex_compiled().match(self.raw_data)

        try:
            lily_time = match.group(1)
            timestamp = time.strptime(lily_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

        result = [
            {DataParticleKey.VALUE_ID: LILYStatusSignOnParticleKey.TIME,
             DataParticleKey.VALUE: ntp_timestamp},
        ]

        return result


class LILYStatus01Particle(DataParticle):
    _data_particle_type = DataParticleType.LILY_STATUS
    _compiled_regex = None
    lily_status_response = "No response found."

    @staticmethod
    def regex():
        """
        Example of output from DUMP-SETTINGS command:
        
        LILY,2013/06/24 23:35:41,*APPLIED GEOMECHANICS LILY Firmware V2.1 SN-N9655 ID01
        LILY,2013/06/24 23:35:41,*01: Vbias= 0.0000 0.0000 0.0000 0.0000
        LILY,2013/06/24 23:35:41,*01: Vgain= 0.0000 0.0000 0.0000 0.0000
        LILY,2013/06/24 23:35:41,*01: Vmin:  -2.50  -2.50   2.50   2.50
        LILY,2013/06/24 23:35:41,*01: Vmax:   2.50   2.50   2.50   2.50
        LILY,2013/06/24 23:35:41,*01: a0=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/24 23:35:41,*01: a1=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/24 23:35:41,*01: a2=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/24 23:35:41,*01: a3=    0.00000    0.00000    0.00000    0.00000    0.00000    0.00000
        LILY,2013/06/24 23:35:41,*01: Tcoef 0: Ks=           0 Kz=           0 Tcal=           0
        LILY,2013/06/24 23:35:41,*01: Tcoef 1: Ks=           0 Kz=           0 Tcal=           0
        LILY,2013/06/24 23:35:41,*01: N_SAMP= 360 Xzero=  0.00 Yzero=  0.00
        LILY,2013/06/24 23:35:41,*01: TR-PASH-OFF E99-ON  SO-NMEA-SIM XY-EP 19200 baud FV-   
        """

        pattern = r'LILY,'  # pattern starts with LILY '
        pattern += r'(.*?),'  # group 1: time
        pattern += r'\*APPLIED GEOMECHANICS'
        pattern += r'.*?'  # non-greedy match of all the junk between
        pattern += r'baud FV- *?' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        if LILYStatus01Particle._compiled_regex is None:
            LILYStatus01Particle._compiled_regex = re.compile(LILYStatus01Particle.regex(), re.DOTALL)
        return LILYStatus01Particle._compiled_regex

    def _build_parsed_values(self):
        pass

    def build_response(self):
        """
        build the response to the command that initiated this status.  In this 
        case just assign the string to the lily_status_response.  In the   
        future, we might want to cook the string, as in remove some
        of the other sensor's chunks.
        
        The lily_status_response is pulled out later when do_cmd_resp calls
        the response handler.  The response handler gets passed the particle
        object, and it then uses that to access the objects attribute that
        contains the response string.
        """
        self.lily_status_response = self.raw_data


# noinspection PyMethodMayBeStatic
class LILYStatus02Particle(DataParticle):
    _data_particle_type = DataParticleType.LILY_STATUS
    _compiled_regex = None
    lily_status_response = "No response found."

    @staticmethod
    def regex():
        """
        Example of output from DUMP2 command:
        LILY,2013/06/24 23:36:05,*01: TBias: 5.00 
        LILY,2013/06/24 23:36:05,*01: Above 0.00(KZMinTemp): kz[0]=           0, kz[1]=           0
        LILY,2013/06/24 23:36:05,*01: Below 0.00(KZMinTemp): kz[2]=           0, kz[3]=           0
        LILY,2013/06/24 23:36:05,*01: ADCDelay:  310 
        LILY,2013/06/24 23:36:05,*01: PCA Model: 84833-14
        LILY,2013/06/24 23:36:05,*01: Firmware Version: 2.1 Rev D
        LILY,2013/06/24 23:36:05,*01: X Ch Gain= 1.0000, Y Ch Gain= 1.0000, Temperature Gain= 1.0000
        LILY,2013/06/24 23:36:05,*01: Calibrated in uRadian, Current Output Mode: uRadian
        LILY,2013/06/24 23:36:05,*01: Using RS232
        LILY,2013/06/24 23:36:05,*01: Real Time Clock: Installed
        LILY,2013/06/24 23:36:05,*01: Use RTC for Timing: Yes
        LILY,2013/06/24 23:36:05,*01: External Flash: 2162688 Bytes Installed
        LILY,2013/06/24 23:36:05,*01: Flash Status (in Samples) (Used/Total): (-1/55424)
        LILY,2013/06/24 23:36:05,*01: Low Power Logger Data Rate: -1 Seconds per Sample
        LILY,2013/06/24 23:36:05,*01: Calibration method: Dynamic 
        LILY,2013/06/24 23:36:05,*01: Positive Limit=330.00   Negative Limit=-330.00 
        IRIS,2013/06/24 23:36:05, -0.0680, -0.3284,28.07,N3616
        LILY,2013/06/24 23:36:05,*01: Calibration Points:023  X: Enabled  Y: Enabled
        LILY,2013/06/24 23:36:05,*01: Uniaxial (x2) Sensor Type (1)
        LILY,2013/06/24 23:36:05,*01: ADC: 16-bit(external)
        LILY,2013/06/24 23:36:05,*01: Compass: Installed   Magnetic Declination: 0.000000
        LILY,2013/06/24 23:36:05,*01: Compass: Xoffset:   12, Yoffset:  210, Xrange: 1371, Yrange: 1307
        LILY,2013/06/24 23:36:05,*01: PID Coeff: iMax:100.0, iMin:-100.0, iGain:0.0150, pGain: 2.50, dGain: 10.0
        LILY,2013/06/24 23:36:05,*01: Motor I_limit: 90.0mA
        LILY,2013/06/24 23:36:05,*01: Current Time: 01/11/00 02:12:32
        LILY,2013/06/24 23:36:06,*01: Supply Voltage: 11.96 Volts
        LILY,2013/06/24 23:36:06,*01: Memory Save Mode: Off
        LILY,2013/06/24 23:36:06,*01: Outputting Data: Yes
        LILY,2013/06/24 23:36:06,*01: Auto Power-Off Recovery Mode: Off
        LILY,2013/06/24 23:36:06,*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No
        """
        pattern = r'LILY,'  # pattern starts with LILY '
        pattern += r'(.*?),'  # group 1: time
        pattern += r'\*01: TBias:'  # unique identifier for status
        pattern += r'.*?'  # non-greedy match of all the junk between
        pattern += r'\*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No' + NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        if LILYStatus02Particle._compiled_regex is None:
            LILYStatus02Particle._compiled_regex = re.compile(LILYStatus02Particle.regex(), re.DOTALL)
        return LILYStatus02Particle._compiled_regex

    def encoders(self):
        return {}

    def _build_parsed_values(self):
        pass

    def build_response(self):
        """
        build the response to the command that initiated this status.  In this 
        case just assign the string to the lily_status_response.  In the   
        future, we might want to cook the string, as in remove some
        of the other sensor's chunks.
        
        The lily_status_response is pulled out later when do_cmd_resp calls
        the response handler.  The response handler gets passed the particle
        object, and it then uses that to access the objects attribute that
        contains the response string.
        """
        self.lily_status_response = self.raw_data


###############################################################################
# Leveling Particles
###############################################################################

class LILYLevelingParticleKey(BaseEnum):
    TIME = "lily_leveling_time"
    X_TILT = "lily_leveling_x_tilt"
    Y_TILT = "lily_leveling_y_tilt"
    MAG_COMPASS = "lily_leveling_mag_compass"
    TEMP = "leveling_temperature"
    SUPPLY_VOLTS = "leveling_supply_voltage"
    SN = "leveling_serial_number"
    STATUS = "lily_leveling_status"


class LILYLevelingParticle(DataParticle):
    _data_particle_type = DataParticleType.LILY_RE_LEVELING
    _compiled_regex = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string

        Sample Data:
        LILY,2013/07/24 19:37:12,*  -7.625, 108.257,185.26, 28.14,11.87,N9651
        LILY,2013/06/28 18:04:41,*  -7.390, -14.063,190.91, 25.83,,Switching to Y!11.87,N9651
        LILY,2013/06/28 17:29:21,*  -2.277,  -2.165,190.81, 25.69,,Leveled!11.87,N9651
        LILY,2013/07/02 23:41:27,*  -5.296,  -2.640,185.18, 28.44,,Leveled!11.87,N9651
        LILY,2013/03/22 19:07:28,*-330.000,-330.000,185.45, -6.45,,X Axis out of range, switching to Y!11.37,N9651
        LILY,2013/03/22 19:07:29,*-330.000,-330.000,184.63, -6.43,,Y Axis out of range!11.34,N9651
        """

        pattern = r'LILY,'  # pattern starts with LILY '
        pattern += r'(.*?),'  # 1 time
        pattern += r'\*'  # star
        pattern += r'(.*?),'  # 2 x-tilt
        pattern += r'(.*?),'  # 3 y-tilt
        pattern += r'(.*?),'  # 4 Magnetic Compass (degrees)
        pattern += r'(.*?),'  # 5 temp
        pattern += r'(.*|,.*),'  # 6 SupplyVolts/status
        pattern += r'(.*)'  # 7 serial number
        pattern += NEWLINE
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        if LILYLevelingParticle._compiled_regex is None:
            LILYLevelingParticle._compiled_regex = re.compile(LILYLevelingParticle.regex())
        return LILYLevelingParticle._compiled_regex

    def _build_parsed_values(self):
        """
        Take something in the autosample/TS format and split it into
        C, T, and D values (with appropriate tags)

        @throws SampleException If there is a problem with sample creation
        """
        match = LILYLevelingParticle.regex_compiled().match(self.raw_data)
        status = None

        if not match:
            raise SampleException("No regex match of parsed sample data: [%s]" %
                                  self.raw_data)

        try:
            lily_time = match.group(1)
            timestamp = time.strptime(lily_time, "%Y/%m/%d %H:%M:%S")
            self.set_internal_timestamp(unix_time=time.mktime(timestamp))
            ntp_timestamp = ntplib.system_to_ntp_time(time.mktime(timestamp))
            x_tilt = float(match.group(2))
            y_tilt = float(match.group(3))
            mag_compass = float(match.group(4))
            temperature = float(match.group(5))
            supply_volts = match.group(6)
            if supply_volts.startswith(','):
                log.debug('found leveling status update')
                status, supply_volts = supply_volts.split('!')
            supply_volts = float(supply_volts)
            sn = str(match.group(7))

        except ValueError as e:
            raise SampleException("ValueError while converting data: [%r], [%r]" %
                                  (self.raw_data, e))

        result = [
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.TIME,
             DataParticleKey.VALUE: ntp_timestamp},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.X_TILT,
             DataParticleKey.VALUE: x_tilt},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.Y_TILT,
             DataParticleKey.VALUE: y_tilt},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.MAG_COMPASS,
             DataParticleKey.VALUE: mag_compass},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.TEMP,
             DataParticleKey.VALUE: temperature},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.SUPPLY_VOLTS,
             DataParticleKey.VALUE: supply_volts},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.STATUS,
             DataParticleKey.VALUE: status},
            {DataParticleKey.VALUE_ID: LILYLevelingParticleKey.SN,
             DataParticleKey.VALUE: sn}
        ]
        return result


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

    # noinspection PyMethodMayBeStatic
    def get_resource_params(self):
        """
        Return list of device parameters available.
        """
        return Parameter.list()

    ########################################################################
    # Protocol builder.
    ########################################################################

    def _build_protocol(self):
        """
        Construct the driver protocol state machine.
        """
        self._protocol = Protocol(Prompt, NEWLINE, self._driver_event)


###########################################################################
# Protocol
###########################################################################

# noinspection PyUnusedLocal,PyMethodMayBeStatic
class Protocol(CommandResponseInstrumentProtocol):
    """
    Instrument protocol class
    Subclasses CommandResponseInstrumentProtocol
    """

    def __init__(self, prompts, newline, driver_event):
        """
        Protocol constructor.
        @param prompts A BaseEnum class containing instrument prompts.
        @param newline The newline.
        @param driver_event Driver process event callback.
        """
        # Construct protocol superclass.
        CommandResponseInstrumentProtocol.__init__(self, prompts, newline, driver_event)

        # Build protocol state machine.
        self._protocol_fsm = ThreadSafeFSM(ProtocolState, ProtocolEvent,
                                           ProtocolEvent.ENTER, ProtocolEvent.EXIT)

        # Add event handlers for protocol state machine.
        handlers = {
            ProtocolState.UNKNOWN: [
                (ProtocolEvent.ENTER, self._handler_unknown_enter),
                (ProtocolEvent.EXIT, self._handler_unknown_exit),
                (ProtocolEvent.DISCOVER, self._handler_unknown_discover),
            ],
            ProtocolState.AUTOSAMPLE: [
                (ProtocolEvent.ENTER, self._handler_autosample_enter),
                (ProtocolEvent.EXIT, self._handler_autosample_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.DUMP_01, self._handler_command_autosample_dump01),
                (ProtocolEvent.DUMP_02, self._handler_command_autosample_dump02),
                (ProtocolEvent.STOP_AUTOSAMPLE, self._handler_autosample_stop_autosample),
                (ProtocolEvent.START_LEVELING, self._handler_autosample_start_leveling),
                (ProtocolEvent.STOP_LEVELING, self._handler_autosample_leveling_stop_leveling),
            ],
            ProtocolState.COMMAND: [
                (ProtocolEvent.ENTER, self._handler_command_enter),
                (ProtocolEvent.EXIT, self._handler_command_exit),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.DUMP_01, self._handler_command_autosample_dump01),
                (ProtocolEvent.DUMP_02, self._handler_command_autosample_dump02),
                (ProtocolEvent.START_AUTOSAMPLE, self._handler_command_start_autosample),
                (ProtocolEvent.START_LEVELING, self._handler_command_start_leveling),
                (ProtocolEvent.STOP_LEVELING, self._handler_command_leveling_stop_leveling),
                (ProtocolEvent.START_DIRECT, self._handler_command_start_direct),
            ],
            ProtocolState.DIRECT_ACCESS: [
                (ProtocolEvent.ENTER, self._handler_direct_access_enter),
                (ProtocolEvent.EXIT, self._handler_direct_access_exit),
                (ProtocolEvent.EXECUTE_DIRECT, self._handler_direct_access_execute_direct),
                (ProtocolEvent.STOP_DIRECT, self._handler_direct_access_stop_direct),
            ],
            ProtocolState.COMMAND_LEVELING: [
                (ProtocolEvent.ENTER, self._handler_leveling_enter),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.STOP_LEVELING, self._handler_command_leveling_stop_leveling),
                (ProtocolEvent.LEVELING_COMPLETE, self._handler_leveling_complete(ProtocolState.COMMAND)),
                (ProtocolEvent.LEVELING_TIMEOUT, self._handler_leveling_timeout(ProtocolState.COMMAND)),
            ],
            ProtocolState.AUTOSAMPLE_LEVELING: [
                (ProtocolEvent.ENTER, self._handler_leveling_enter),
                (ProtocolEvent.GET, self._handler_command_get),
                (ProtocolEvent.SET, self._handler_command_set),
                (ProtocolEvent.STOP_LEVELING, self._handler_autosample_leveling_stop_leveling),
                (ProtocolEvent.LEVELING_COMPLETE, self._handler_leveling_complete(ProtocolState.AUTOSAMPLE)),
                (ProtocolEvent.LEVELING_TIMEOUT, self._handler_leveling_timeout(ProtocolState.AUTOSAMPLE)),
            ]
        }

        for state in handlers:
            for event, handler in handlers[state]:
                self._protocol_fsm.add_handler(state, event, handler)

        # Construct the parameter dictionary containing device parameters,
        # current parameter values, and set formatting functions.
        self._build_param_dict()

        # Add build handlers for device commands.
        self._add_build_handler(InstrumentCommand.DATA_ON, self._build_command)
        self._add_build_handler(InstrumentCommand.DATA_OFF, self._build_command)
        self._add_build_handler(InstrumentCommand.DUMP_SETTINGS_01, self._build_command)
        self._add_build_handler(InstrumentCommand.DUMP_SETTINGS_02, self._build_command)
        self._add_build_handler(InstrumentCommand.START_LEVELING, self._build_command)
        self._add_build_handler(InstrumentCommand.STOP_LEVELING, self._build_command)

        # Add response handlers for device commands.
        self._add_response_handler(InstrumentCommand.DATA_ON, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DATA_OFF, self._parse_data_on_off_resp)
        self._add_response_handler(InstrumentCommand.DUMP_SETTINGS_01, self._parse_status_01_resp)
        self._add_response_handler(InstrumentCommand.DUMP_SETTINGS_02, self._parse_status_02_resp)

        # Add sample handlers.

        # State state machine in UNKNOWN state.
        self._protocol_fsm.start(ProtocolState.UNKNOWN)

        # commands sent to device to be filtered in responses for telnet DA
        self._sent_cmds = []

        self._chunker = StringChunker(Protocol.sieve_function)

        # set up the regexes now so we don't have to do it repeatedly
        self.data_regex = LILYDataParticle.regex_compiled()
        self.signon_regex = LILYStatusSignOnParticle.regex_compiled()
        self.status_01_regex = LILYStatus01Particle.regex_compiled()
        self.status_02_regex = LILYStatus02Particle.regex_compiled()
        self.leveling_regex = LILYLevelingParticle.regex_compiled()

        self._auto_relevel = DEFAULT_AUTO_RELEVEL
        self._xtilt_relevel_trigger = DEFAULT_XTILT_TRIGGER
        self._ytilt_relevel_trigger = DEFAULT_YTILT_TRIGGER
        self._leveling_timeout = DEFAULT_LEVELING_TIMEOUT
        self._last_data_timestamp = 0

        self.initialize_scheduler()

    @staticmethod
    def sieve_function(raw_data):
        """
        The method that filters LILY chunks
        """
        matchers = []
        return_list = []

        matchers.append(LILYLevelingParticle.regex_compiled())
        matchers.append(LILYDataParticle.regex_compiled())
        matchers.append(LILYStatus01Particle.regex_compiled())
        matchers.append(LILYStatus02Particle.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    def _handler_command_generic(self, command, next_state, next_agent_state, timeout, expected_prompt=None):
        """
        Generic method to command the instrument
        """
        log.debug('_handler_command: %s %s %s %s', command, next_state, next_agent_state, timeout)

        if timeout is None:
            result = self._do_cmd_resp(command, expected_prompt=expected_prompt)
        else:
            result = self._do_cmd_resp(command, expected_prompt=expected_prompt, timeout=timeout)

        log.debug('%s response: %s', command, result)
        return next_state, (next_agent_state, result)

    def _filter_capabilities(self, events):
        """
        Return a list of currently available capabilities.
        """
        events_out = [x for x in events if Capability.has(x)]
        return events_out

    def _build_cmd_dict(self):
        """
        Populate the command dictionary with NOAA LILY Driver metadata information. 
        Currently LILY only supports DATA_ON and DATA_OFF.
        """
        self._cmd_dict = ProtocolCommandDict()

    def _build_param_dict(self):
        """
        Populate the parameter dictionary with parameters.
        For each parameter key, add match string, match lambda function,
        and value formatting function for set commands.
        """
        # Add parameter handlers to parameter dict.
        self._param_dict.add(Parameter.AUTO_RELEVEL,
                             r'Not used. This is just to satisfy the param_dict',
                             None,
                             None,
                             type=ParameterDictType.BOOL,
                             display_name="Automatically Re-level",
                             multi_match=False,
                             default_value=True,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.XTILT_RELEVEL_TRIGGER,
                             r'Not used. This is just to satisfy the param_dict',
                             None,
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name="X-TILT Automatic Re-level Trigger",
                             multi_match=False,
                             default_value=300.00,
                             visibility=ParameterDictVisibility.READ_WRITE)
        self._param_dict.add(Parameter.YTILT_RELEVEL_TRIGGER,
                             r'Not used. This is just to satisfy the param_dict',
                             None,
                             None,
                             type=ParameterDictType.FLOAT,
                             display_name="Y-TILT Automatic Re-level Trigger",
                             multi_match=False,
                             default_value=300.00,
                             visibility=ParameterDictVisibility.READ_WRITE)

    def got_raw(self, port_agent_packet):
        """
        Overridden, this driver shall not generate raw particles
        """
        pass

    def _filter_lily_only(self, data):
        """
        BOTPT puts out lots of data not destined for LILY.  Filter it out.
        """
        my_filter = lambda s: (s.startswith(LILY_STRING) or len(s) == 0)
        lines = data.split(NEWLINE)
        lines = filter(my_filter, lines)
        return NEWLINE.join(lines)

    def got_data(self, port_agent_packet):
        """
        Called by the instrument connection when data is available.
        Append line and prompt buffers.

        Also add data to the chunker and when received call got_chunk
        to publish results.
        """
        data_length = port_agent_packet.get_data_length()
        data = self._filter_lily_only(port_agent_packet.get_data())
        timestamp = port_agent_packet.get_timestamp()

        log.debug("Got Data: %s" % data)
        log.debug("Add Port Agent Timestamp: %s" % timestamp)

        if data_length > 0:
            if self.get_current_state() == DriverProtocolState.DIRECT_ACCESS:
                self._driver_event(DriverAsyncEvent.DIRECT_ACCESS, data)

            self.add_to_buffer(data)

            self._chunker.add_chunk(data, timestamp)
            timestamp, chunk = self._chunker.get_next_data()
            while chunk:
                self._got_chunk(chunk, timestamp)
                timestamp, chunk = self._chunker.get_next_data()

    def _clean_buffer(self, my_buffer):
        return NEWLINE.join(my_buffer.split(NEWLINE)[-MAX_BUFFER_LENGTH:])

    def add_to_buffer(self, data):
        """
        Add a chunk of data to the internal data buffers, filtering out data not for this sensor.
        Limit buffer length to MAX_BUFFER_LENGTH lines
        @param data: bytes to add to the buffer
        """
        # Update the line and prompt buffers.
        self._linebuf += data
        self._promptbuf += data
        self._linebuf = self._clean_buffer(self._linebuf)
        self._promptbuf = self._clean_buffer(self._promptbuf)
        self._last_data_timestamp = time.time()

        log.debug("LINE BUF: %s", self._linebuf)
        log.debug("PROMPT BUF: %s", self._promptbuf)

    def _got_chunk(self, chunk, timestamp):
        log.debug('_got_chunk: %r', chunk)

        particles = [
            (LILYDataParticle, self._check_for_autolevel),
            (LILYLevelingParticle, self._check_completed_leveling),
            (LILYStatus01Particle, None),
            (LILYStatus02Particle, None),
        ]

        for particle_type, func in particles:
            sample = self._extract_sample(particle_type, particle_type.regex_compiled(), chunk, timestamp)
            if sample:
                if func:
                    func(sample)
                return

        raise InstrumentProtocolException('unhandled chunk received by _got_chunk: [%r]', chunk)

    def _check_for_autolevel(self, sample):
        if self._auto_relevel:
            relevel = False
            values = sample.get(u'values', [])
            for each in values:
                value_id = each.get(u'value_id')
                value = each.get(u'value')
                if value_id == LILYDataParticleKey.X_TILT:
                    if abs(value) > self._xtilt_relevel_trigger:
                        relevel = True
                        break
                elif value_id == LILYDataParticleKey.Y_TILT:
                    if abs(value) > self._ytilt_relevel_trigger:
                        relevel = True
                        break
            if relevel:
                self._async_raise_fsm_event(ProtocolEvent.START_LEVELING)

    def _check_completed_leveling(self, sample):
        values = sample.get(u'values', [])
        for each in values:
            value_id = each.get(u'value_id')
            value = each.get(u'value')
            if value_id == LILYLevelingParticleKey.STATUS:
                if value is not None and 'Leveled' in value:
                    self._async_raise_fsm_event(ProtocolEvent.STOP_LEVELING)

    def _build_command(self, cmd, *args, **kwargs):
        command = cmd + NEWLINE
        log.debug("_build_command: command is: %s", command)
        return command

    def _parse_data_on_off_resp(self, response, prompt):
        log.debug("_parse_data_on_off_resp: response: %r; prompt: %s", response, prompt)
        return response

    def _parse_status_01_resp(self, response, prompt):
        log.debug("_parse_status_01_resp: response: %r; prompt: %s", response, prompt)
        return response

    def _parse_status_02_resp(self, response, prompt):
        log.debug("_parse_status_02_resp: response: %r; prompt: %s", response, prompt)
        return response

    def _wakeup(self, timeout, delay=1):
        """
        Overriding _wakeup; does not apply to this instrument
        """
        pass

    ########################################################################
    # Unknown handlers.
    ########################################################################

    def _handler_unknown_enter(self, *args, **kwargs):
        """
        Enter unknown state.
        """
        log.debug("_handler_unknown_enter")

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_unknown_exit(self, *args, **kwargs):
        """
        Exit unknown state.
        """
        log.debug("_handler_unknown_exit")

    def _handler_unknown_discover(self, *args, **kwargs):
        """
        Discover current state
        @retval (next_state, result)
        """
        try:
            response = self._get_response(timeout=1, response_regex=DISCOVER_REGEX)[0]
            log.debug('_handler_unknown_discover: response: [%r]', response)
            if LILYDataParticle.regex_compiled().search(response):
                next_state = ProtocolState.AUTOSAMPLE
                next_agent_state = ResourceAgentState.STREAMING
                result = ProtocolState.AUTOSAMPLE
            elif LILYLevelingParticle.regex_compiled().search(response):
                next_state, next_agent_state = self._handler_command_leveling_stop_leveling()
                next_agent_state, result = next_agent_state
            else:
                next_state = ProtocolState.COMMAND
                next_agent_state = ResourceAgentState.COMMAND
                result = ProtocolState.COMMAND
        except InstrumentTimeoutException:
            next_state = ProtocolState.COMMAND
            next_agent_state = ResourceAgentState.COMMAND
            result = ProtocolState.COMMAND
        return next_state, (next_agent_state, result)

    ########################################################################
    # Autosample handlers.
    ########################################################################

    def _handler_autosample_enter(self, *args, **kwargs):
        """
        Enter autosample state.
        """
        log.debug("_handler_autosample_enter")

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_autosample_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        log.debug("_handler_autosample_exit")

    def _handler_autosample_stop_autosample(self):
        """
        Turn the lily data off
        """
        return self._handler_command_generic(InstrumentCommand.DATA_OFF,
                                             ProtocolState.COMMAND,
                                             ResourceAgentState.COMMAND,
                                             None,
                                             expected_prompt=LILY_DATA_OFF)

    ########################################################################
    # Command handlers.
    ########################################################################

    def _handler_command_enter(self, *args, **kwargs):
        """
        Enter command state.
        @throws InstrumentTimeoutException if the device cannot be woken.
        @throws InstrumentProtocolException if the update commands and not recognized.
        """
        log.debug("_handler_command_enter")

        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

    def _handler_command_get(self, *args, **kwargs):
        """
        Get parameter
        """
        log.debug("_handler_command_get")

        next_state = None

        param_list = args[0]
        if param_list == Parameter.ALL:
            param_list = [Parameter.AUTO_RELEVEL, Parameter.XTILT_RELEVEL_TRIGGER, Parameter.YTILT_RELEVEL_TRIGGER]

        result = {}

        log.error("_handler_command_get: AUTO_RELEVEL: %s, len(%d)", Parameter.AUTO_RELEVEL,
                  len(Parameter.AUTO_RELEVEL))

        for param in param_list:
            if param == Parameter.AUTO_RELEVEL:
                result[param] = self._auto_relevel
            elif param == Parameter.XTILT_RELEVEL_TRIGGER:
                result[param] = self._xtilt_relevel_trigger
            elif param == Parameter.YTILT_RELEVEL_TRIGGER:
                result[param] = self._ytilt_relevel_trigger
            else:
                log.error("_handler_command_get: Unknown parameter: %s", param)
                raise InstrumentProtocolException("Unknown parameter: %s" % param)

        return next_state, result

    def _handler_command_set(self, *args, **kwargs):
        """
        Set parameter
        """
        log.debug("_handler_command_set")

        next_state = None
        result = None

        param_list = args[0]

        for param in param_list:
            if param == Parameter.AUTO_RELEVEL:
                new_auto_relevel = param_list[Parameter.AUTO_RELEVEL]
                if new_auto_relevel != self._auto_relevel:
                    log.info("BOTPT LILY Driver: setting auto_relevel from %d to %d", self._auto_relevel,
                             new_auto_relevel)
                    self._auto_relevel = new_auto_relevel
                    self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                else:
                    log.info("BOTPT LILY Driver: auto_relevel already %d; not changing.", new_auto_relevel)
            elif param == Parameter.XTILT_RELEVEL_TRIGGER:
                new_xtilt_relevel_trigger = param_list[Parameter.XTILT_RELEVEL_TRIGGER]
                if new_xtilt_relevel_trigger != self._xtilt_relevel_trigger:
                    log.info("BOTPT LILY Driver: setting xtilt_relevel_trigger from %d to %d",
                             self._xtilt_relevel_trigger, new_xtilt_relevel_trigger)
                    LevelingTriggers.xtilt_relevel_trigger = new_xtilt_relevel_trigger
                    self._xtilt_relevel_trigger = new_xtilt_relevel_trigger
                    self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                else:
                    log.info("BOTPT LILY Driver: xtilt_relevel_trigger already %f; not changing.",
                             new_xtilt_relevel_trigger)
            elif param == Parameter.YTILT_RELEVEL_TRIGGER:
                new_ytilt_relevel_trigger = param_list[Parameter.YTILT_RELEVEL_TRIGGER]
                if new_ytilt_relevel_trigger != self._ytilt_relevel_trigger:
                    log.info("BOTPT LILY Driver: setting ytilt_relevel_trigger from %d to %d",
                             self._ytilt_relevel_trigger, new_ytilt_relevel_trigger)
                    LevelingTriggers.ytilt_relevel_trigger = new_ytilt_relevel_trigger
                    self._ytilt_relevel_trigger = new_ytilt_relevel_trigger
                    self._driver_event(DriverAsyncEvent.CONFIG_CHANGE)
                else:
                    log.info("BOTPT LILY Driver: ytilt_relevel_trigger already %f; not changing.",
                             new_ytilt_relevel_trigger)
            else:
                log.error("_handler_command_set: Unknown parameter: %s", param)
                raise InstrumentProtocolException("Unknown parameter: %s" % param)

        return next_state, result

    def _handler_command_start_autosample(self, *args, **kwargs):
        """
        Turn the lily data on
        """
        return self._handler_command_generic(InstrumentCommand.DATA_ON,
                                             ProtocolState.AUTOSAMPLE,
                                             ResourceAgentState.STREAMING,
                                             None,
                                             expected_prompt=LILY_DATA_ON)

    def _handler_command_exit(self, *args, **kwargs):
        """
        Exit command state.
        """
        log.debug("_handler_command_exit")

    def _handler_command_start_direct(self):
        """
        Start direct access
        """
        next_state = ProtocolState.DIRECT_ACCESS
        next_agent_state = ResourceAgentState.DIRECT_ACCESS
        result = None
        log.debug("_handler_command_start_direct: entering DA mode")
        return next_state, (next_agent_state, result)

    ########################################################################
    # Leveling Handlers
    ########################################################################

    def _handler_leveling_enter(self, *args, **kwargs):
        """
        Set up a leveling timer to make sure we don't stay in
        leveling state forever if something goes wrong
        """
        log.debug("_handler_leveling_enter")

        job_name = 'leveling_timeout'
        config = {
            DriverConfigKey.SCHEDULER: {
                job_name: {
                    DriverSchedulerConfigKey.TRIGGER: {
                        DriverSchedulerConfigKey.TRIGGER_TYPE: TriggerType.INTERVAL,
                        DriverSchedulerConfigKey.SECONDS: self._leveling_timeout
                    },
                }
            }
        }

        self.set_init_params(config)
        self._add_scheduler_event(ScheduledJob.LEVELING_TIMEOUT, ProtocolEvent.LEVELING_TIMEOUT)

    def _handler_autosample_leveling_stop_leveling(self, *args, **kwargs):
        """
        Take instrument out of leveling mode, returning to the previous state
        """

        self._handler_command_generic(InstrumentCommand.STOP_LEVELING,
                                      ProtocolState.AUTOSAMPLE,
                                      ResourceAgentState.STREAMING,
                                      None,
                                      expected_prompt=LILY_LEVEL_OFF)

        return self._handler_command_start_autosample()

    def _handler_command_leveling_stop_leveling(self, *args, **kwargs):
        """
        Take instrument out of leveling mode, return to COMMAND
        """
        return self._handler_command_generic(InstrumentCommand.STOP_LEVELING,
                                             ProtocolState.COMMAND,
                                             ResourceAgentState.COMMAND,
                                             None,
                                             expected_prompt=LILY_LEVEL_OFF)

    def _handler_leveling_complete(self, parent_state=ProtocolState.COMMAND):
        if parent_state == ProtocolState.COMMAND:
            f = self._handler_command_leveling_stop_leveling
        elif parent_state == ProtocolState.AUTOSAMPLE:
            f = self._handler_autosample_leveling_stop_leveling

        def inner(*args, **kwds):

            try:
                self._remove_scheduler(ScheduledJob.LEVELING_TIMEOUT)
            except KeyError:
                log.error("_remove_scheduler could not find: %s", ScheduledJob.LEVELING_TIMEOUT)

            return f()

        return inner

    def _handler_leveling_timeout(self, parent_state=ProtocolState.COMMAND):
        """
        The LILY leveling operation has timed out.  Do the following:
        - Send Stop Leveling command to LILY
        - Enter Autosample (or a similar state as Autosample, but 
          that knows the axis is out of range)
        - Send Alert to Marine Operator (?)
        - Flag subsequent data as "Axis out of range"
        """
        if parent_state == ProtocolState.COMMAND:
            next_agent_state = ResourceAgentState.COMMAND
        else:
            next_agent_state = ResourceAgentState.STREAMING

        def inner(*args, **kwargs):
            self._remove_scheduler(ScheduledJob.LEVELING_TIMEOUT)
            result = None

            log.info("LILY leveling operation timed out: sending STOP LEVELING.")
            result = self._do_cmd_resp(InstrumentCommand.STOP_LEVELING, expected_prompt=LILY_LEVEL_OFF)

            log.info("LILY leveling operation timed out: sending DATA_ON.")
            result = self._do_cmd_resp(InstrumentCommand.DATA_ON, expected_prompt=LILY_DATA_ON)
            return parent_state, (next_agent_state, result)

        return inner

    ########################################################################
    # Direct access handlers.
    ########################################################################

    def _handler_direct_access_enter(self, *args, **kwargs):
        """
        Enter direct access state.
        """
        # Tell driver superclass to send a state change event.
        # Superclass will query the state.
        self._driver_event(DriverAsyncEvent.STATE_CHANGE)

        self._sent_cmds = []

    def _handler_direct_access_exit(self, *args, **kwargs):
        """
        Exit direct access state.
        """
        pass

    def _handler_direct_access_execute_direct(self, data):
        """
        """
        next_state = None
        result = None
        next_agent_state = None

        # Only allow HEAT commands
        commands = data.split(NEWLINE)
        commands = [x for x in commands if x.startswith('LILY')]

        for command in commands:
            self._do_cmd_direct(command)

            # add sent command to list for 'echo' filtering in callback
            self._sent_cmds.append(command)

        return next_state, (next_agent_state, result)

    def _handler_direct_access_stop_direct(self):
        """
        @throw InstrumentProtocolException on invalid command
        """
        result = None

        next_state = ProtocolState.COMMAND
        next_agent_state = ResourceAgentState.COMMAND

        return next_state, (next_agent_state, result)

    ########################################################################
    # Handlers common to Command and Autosample States.
    ########################################################################

    def _handler_command_autosample_dump01(self, *args, **kwargs):
        """
        Get device status
        """
        return self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS_01,
                                             None,
                                             None,
                                             kwargs.get('timeout'),
                                             expected_prompt=LILY_DUMP_01)

    def _handler_command_autosample_dump02(self, *args, **kwargs):
        """
        Get device status
        """
        return self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS_02,
                                             None,
                                             None,
                                             kwargs.get('timeout'),
                                             expected_prompt=LILY_DUMP_02)

    def _handler_command_start_leveling(self, *args, **kwargs):
        """
        Put instrument into leveling mode
        """
        return self._handler_command_generic(InstrumentCommand.START_LEVELING,
                                             ProtocolState.COMMAND_LEVELING,
                                             ResourceAgentState.CALIBRATE,
                                             kwargs.get('timeout'),
                                             expected_prompt=LILY_LEVEL_ON)

    def _handler_autosample_start_leveling(self, *args, **kwargs):
        """
        Put instrument into leveling mode
        """
        return self._handler_command_generic(InstrumentCommand.START_LEVELING,
                                             ProtocolState.AUTOSAMPLE_LEVELING,
                                             ResourceAgentState.CALIBRATE,
                                             kwargs.get('timeout'),
                                             expected_prompt=LILY_LEVEL_ON)