"""
@package mi.instrument.noaa.lily.ooicore.driver
@file marine-integrations/mi/instrument/noaa/lily/ooicore/driver.py
@author David Everett
@brief Driver for the ooicore
Release notes:

Driver for LILY TILT on the RSN-BOTPT instrument (v.6)

"""

__author__ = 'David Everett'
__license__ = 'Apache 2.0'

#import string
import re
import time
#import datetime
import ntplib
import threading
import json

from mi.core.log import get_logger

log = get_logger()

from mi.core.common import BaseEnum
from mi.core.instrument.instrument_protocol import CommandResponseInstrumentProtocol
#from mi.core.instrument.instrument_protocol import DEFAULT_CMD_TIMEOUT
from mi.core.instrument.instrument_protocol import DEFAULT_WRITE_DELAY
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


# DHE: Might need this if we use multiline regex
#from mi.instrument.noaa.driver import BOTPTParticle

from mi.core.exceptions import InstrumentProtocolException
from mi.core.exceptions import InstrumentTimeoutException
from mi.core.exceptions import SampleException

###
#    Driver Constant Definitions
###

# newline.
NL = '\x0a'
LILY_STRING = 'LILY,'
LILY_COMMAND_STRING = '*9900XY'
LILY_DATA_ON = 'C2'  # turns on continuous data
LILY_DATA_OFF = 'C-OFF'  # turns off continuous data
LILY_DUMP_01 = '-DUMP-SETTINGS'  # outputs current settings
LILY_DUMP_02 = '-DUMP2'  # outputs current extended settings
LILY_LEVEL_ON = '-LEVEL,1'
LILY_LEVEL_OFF = '-LEVEL,0'

STATUS_LEVELED = 'Leveled!'  # LILY reports leveled

# default timeout.
TIMEOUT = 10
DEFAULT_CMD_TIMEOUT = 120
#LEVELING_TIMEOUT = 60
LEVELING_TIMEOUT = 2

DEFAULT_XTILT_TRIGGER = 300
DEFAULT_YTILT_TRIGGER = 300
DEFAULT_AUTO_RELEVEL = True  # default to be true

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
    COMMAND_LEVELING = 'LILY_DRIVER_STATE_COMMAND_LEVELING'
    AUTOSAMPLE_LEVELING = 'LILY_DRIVER_STATE_AUTOSAMPLE_LEVELING'


class ExportedInstrumentCommand(BaseEnum):
    DUMP_01 = "EXPORTED_INSTRUMENT_DUMP_SETTINGS"
    DUMP_02 = "EXPORTED_INSTRUMENT_DUMP_EXTENDED_SETTINGS"
    START_LEVELING = "EXPORTED_INSTRUMENT_START_LEVELING"
    RESUME_LEVELING = "EXPORTED_INSTRUMENT_RESUME_LEVELING"
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
    RESUME_LEVELING = ExportedInstrumentCommand.RESUME_LEVELING
    STOP_LEVELING = ExportedInstrumentCommand.STOP_LEVELING
    LEVELING_COMPLETE = "PROTOCOL_EVENT_LEVELING_COMPLETE"
    LEVELING_TIMEOUT = "PROTOCOL_EVENT_LEVELING_TIMEOUT"


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


class AsyncEventSender(object):
    _protocol_fsm = None

    @classmethod
    def __my_init__(cls, protocol_fsm):
        cls._protocol_fsm = protocol_fsm

    @classmethod
    def send_event(cls, event):
        """
        Start a separate thread that can block (without affecting this thread)
        on the on_event() method.
        """
        async_event_thread = threading.Thread(
            target=cls._protocol_fsm.on_event,
            args=(event, ))
        async_event_thread.start()


###############################################################################
# Command Response (not a particle but uses regex and chunker to parse command
# responses rather than the normal get_response() method)
###############################################################################

class InstrumentCommand(BaseEnum):
    """
    Instrument command strings
    """
    DATA_ON = LILY_STRING + LILY_COMMAND_STRING + LILY_DATA_ON + NL  # turns on continuous data
    DATA_OFF = LILY_STRING + LILY_COMMAND_STRING + LILY_DATA_OFF + NL  # turns off continuous data
    DUMP_SETTINGS_01 = LILY_STRING + LILY_COMMAND_STRING + LILY_DUMP_01 + NL  # outputs current settings
    DUMP_SETTINGS_02 = LILY_STRING + LILY_COMMAND_STRING + LILY_DUMP_02 + NL  # outputs current extended settings
    START_LEVELING = LILY_STRING + LILY_COMMAND_STRING + LILY_LEVEL_ON + NL  # starts leveling
    STOP_LEVELING = LILY_STRING + LILY_COMMAND_STRING + LILY_LEVEL_OFF + NL  # stops leveling


class LILYCoarseChunk():
    def __init__(self, raw_data):
        """ 
        Construct a LILYCoarseChunk object 
        
        @param raw_data The raw data used in the particle
        """
        self.raw_data = raw_data

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'LILY,'  # pattern starts with LILY '
        pattern += r'.*'  # group 1: time
        pattern += NL
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(LILYCoarseChunk.regex())


class LILYCommandResponse():
    def __init__(self, raw_data):
        """ 
        Construct a LILYCommandResponse object 
        
        @param raw_data The raw data used in the particle
        """
        self.raw_data = raw_data
        self.lily_command_response = None

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'LILY,'  # pattern starts with LILY '
        pattern += r'(.*),'  # group 1: time
        pattern += r'\*9900XY'  # generic part of LILY command
        pattern += r'(.*)'  # group 2: echoed command
        pattern += NL
        return pattern

    @staticmethod
    def regex_compiled():
        """
        get the compiled regex pattern
        @return: compiled re
        """
        return re.compile(LILYCommandResponse.regex())

    def check_command_response(self, expected_response):
        """
        Generic command response method; the expected response
        is passed in as a parameter; that is used to check 
        whether the response from the sensor is valid (positive)
        or not.
        """
        return_value = False

        match = LILYCommandResponse.regex_compiled().match(self.raw_data)

        if not match:
            raise SampleException("No regex match of command response: [%s]" %
                                  self.raw_data)
        try:
            resp_time = match.group(1)
            time.strptime(resp_time, "%Y/%m/%d %H:%M:%S")
            self.lily_command_response = match.group(2)
            if expected_response is not None:
                if self.lily_command_response == expected_response:
                    return_value = True
            else:
                return_value = True

        except ValueError:
            raise SampleException("check_command_response: ValueError" +
                                  " while converting data: [%s]" %
                                  self.raw_data)

        return return_value


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

    def __init__(self, raw_data, auto_relevel,
                 port_timestamp=None,
                 internal_timestamp=None,
                 preferred_timestamp=DataParticleKey.PORT_TIMESTAMP):

        super(LILYDataParticle, self).__init__(raw_data,
                                               port_timestamp,
                                               internal_timestamp,
                                               preferred_timestamp)
        self.auto_relevel = auto_relevel

    @staticmethod
    def regex():
        """
        Regular expression to match a sample pattern
        @return: regex string
        """
        pattern = r'LILY,'  # pattern starts with LILY '
        pattern += r'(.*),'  # 1 time
        pattern += r'(.*-*[.0-9]+),'  # 2 x-tilt
        pattern += r'( *-*[.0-9]+),'  # 3 y-tilt
        pattern += r'(.*),'  # 4 Magnetic Compass (degrees)
        pattern += r'(.*),'  # 5 temp
        pattern += r'(.*),'  # 6 SupplyVolts
        pattern += r'(.*)'  # 7 serial number
        pattern += NL
        return pattern

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

            # If AUTO_RELEVEL is on, test the x_tilt and y_tilt; we might have to
            # initiate relevel.

            if self.auto_relevel:
                if (abs(x_tilt) > LevelingTriggers.xtilt_relevel_trigger
                    or abs(y_tilt) > LevelingTriggers.ytilt_relevel_trigger):

                    # initiate auto releveling
                    log.info("x_tilt: %f; y_tilt: %f.  Initiating relevel operation.", x_tilt, y_tilt)
                    AsyncEventSender.send_event(ProtocolEvent.START_LEVELING)
                else:
                    log.debug("NOT INITIATING RELEVEL: %d, %d",
                              LevelingTriggers.xtilt_relevel_trigger,
                              LevelingTriggers.ytilt_relevel_trigger)

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
        pattern += NL
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
        pattern += r'baud FV- *?' + NL
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
        pattern += r'\*01: Advanced Memory Mode: Off, Delete with XY-MEMD: No' + NL
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
        pattern += r'(.*),'  # 1 time
        pattern += r'\*'  # star
        pattern += r'(.*),'  # 2 x-tilt
        pattern += r'(.*),'  # 3 y-tilt
        pattern += r'(.*),'  # 4 Magnetic Compass (degrees)
        pattern += r'(.*),'  # 5 temp
        pattern += r'(.*|,.*),'  # 6 SupplyVolts/status
        pattern += r'(.*)'  # 7 serial number
        pattern += NL
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
            supply_volts = match.group(6)
            if supply_volts.startswith(','):
                log.debug('found leveling status update')
                status, supply_volts = supply_volts.split('!')
            supply_volts = float(supply_volts)
            sn = str(match.group(7))

        except ValueError:
            raise SampleException("ValueError while converting data: [%s]" %
                                  self.raw_data)

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
        self._protocol = Protocol(Prompt, NL, self._driver_event)


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
                (ProtocolEvent.RESUME_LEVELING, self._handler_autosample_resume_leveling),
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
                (ProtocolEvent.RESUME_LEVELING, self._handler_command_resume_leveling),
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

        # Set up the chunkers: this driver uses the chunker in a hierarchical way.  The coarse
        # chunker filters the LILY messages from the BOTPT firehose, and the other chunkers
        # work with what the coarse chunker matches.
        self._coarse_chunker = StringChunker(Protocol.coarse_sieve_function)
        self._command_autosample_chunker = StringChunker(Protocol.command_autosample_sieve_function)
        self._leveling_chunker = StringChunker(Protocol.leveling_sieve_function)

        # set up the regexes now so we don't have to do it repeatedly
        self.data_regex = LILYDataParticle.regex_compiled()
        self.cmd_rsp_regex = LILYCommandResponse.regex_compiled()
        self.signon_regex = LILYStatusSignOnParticle.regex_compiled()
        self.status_01_regex = LILYStatus01Particle.regex_compiled()
        self.status_02_regex = LILYStatus02Particle.regex_compiled()
        self.leveling_regex = LILYLevelingParticle.regex_compiled()

        self._auto_relevel = DEFAULT_AUTO_RELEVEL
        self._xtilt_relevel_trigger = DEFAULT_XTILT_TRIGGER
        self._ytilt_relevel_trigger = DEFAULT_YTILT_TRIGGER
        self._last_data_timestamp = 0

        self.initialize_scheduler()

        # Initialize the AsyncEventSender object with the protocol_fsm
        AsyncEventSender.__my_init__(self._protocol_fsm)

    @staticmethod
    def coarse_sieve_function(raw_data):
        """
        The method that filters LILY coarse chunks
        """
        matchers = []
        return_list = []

        matchers.append(LILYCoarseChunk.regex_compiled())

        for matcher in matchers:
            for match in matcher.finditer(raw_data):
                return_list.append((match.start(), match.end()))

        return return_list

    @staticmethod
    def leveling_sieve_function(raw_data):
        """
        The method that splits samples
        """

        matchers = []
        return_list = []

        # would be nice to be able to do this.
        # matchers.append(self.leveling_regex)
        # matchers.append(self.cmd_rsp_regex)

        # This is a way to label the chunks.  However, the chunker needs
        # to change because it is dependent upon the return list.
        #
        # Maybe do this:  (label, result) = self.sieve(self.buffer[start_index:])
        # (see code in the chunker)

        match_tuple = ("CMD", LILYCommandResponse.regex_compiled())
        matchers.append(match_tuple)
        #matchers.append(LILYCommandResponse.regex_compiled())
        match_tuple = ("LVL", LILYLevelingParticle.regex_compiled())
        matchers.append(match_tuple)
        #matchers.append(LILYLevelingParticle.regex_compiled())

        for matcher in matchers:
            for match in matcher[1].finditer(raw_data):
                log.debug("Found %s chunk.", matcher[0])
                return_list.append((match.start(), match.end()))

        return return_list

    @staticmethod
    def command_autosample_sieve_function(raw_data):
        """
        The method that splits samples
        """
        matchers = []
        return_list = []

        matchers.append(LILYDataParticle.regex_compiled())
        matchers.append(LILYCommandResponse.regex_compiled())
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

    def add_to_buffer(self, data):
        """
        Overridden because most of the data coming to this driver
        isn't meant for it.  I'm only adding to the buffer when
        a chunk arrives (see my_add_to_buffer, below), so this
        method does nothing.

        @param data: bytes to add to the buffer
        """
        pass

    def _my_add_to_buffer(self, data):
        """
        Replaces add_to_buffer. Most data coming to this driver isn't meant
        for it.  I'm only adding to the buffer when data meant for this 
        driver arrives.  That is accomplished using the chunker mechanism. This
        method would normally collect any data fragments that are then searched by
        the get_response method in the context of a synchronous command sent
        from the observatory.  However, because so much data arrives here that
        is not applicable, the add_to_buffer method has been overridden to do
        nothing.
        
        @param data: bytes to add to the buffer
        """

        # Update the line and prompt buffers; first acquire mutex.
        promptbuf_mutex.acquire()
        self._linebuf += data
        self._promptbuf += data
        promptbuf_mutex.release()

        self._last_data_timestamp = time.time()

    ########################################################################
    # Incoming data (for parsing) callback.
    ########################################################################            
    def got_data(self, port_agent_packet):
        """
        Called by the instrument connection when data is available.
        This is overridden from the base class because this is where
        we filter the LILY data from the firehose of BOTPT data.
        
        In this method all we do is call the coarse chunker.
        """
        data_length = port_agent_packet.get_data_length()
        data = port_agent_packet.get_data()
        timestamp = port_agent_packet.get_timestamp()

        log.debug("LILY Got Data: %s" % data)
        log.debug("LILY Add Port Agent Timestamp: %s" % timestamp)

        if data_length > 0:
            self._coarse_chunker.add_chunk(data, timestamp)
            (timestamp, chunk) = self._coarse_chunker.get_next_data()
            while chunk:
                self._got_coarse_chunk(chunk, timestamp)
                (timestamp, chunk) = self._coarse_chunker.get_next_data()

    def _got_coarse_chunk(self, coarse_chunk, timestamp):
        """
        Got a course chunk: that is, a complete message from the LILY sensor
        has been filtered out of the firehose of BOTPT data.  At this point
        we don't know the purpose of the chunk.
        """
        log.debug("_got_coarse_chunk: %s", coarse_chunk)
        current_state = self._protocol_fsm.get_current_state()

        if current_state in [ProtocolState.COMMAND, ProtocolState.AUTOSAMPLE]:
            self._command_autosample_chunker.add_chunk(coarse_chunk, timestamp)
            timestamp, chunk = self._command_autosample_chunker.get_next_data()
            while chunk:
                self._got_command_autosample_chunk(chunk, timestamp)
                timestamp, chunk = self._command_autosample_chunker.get_next_data()
        elif current_state in [ProtocolState.COMMAND_LEVELING, ProtocolState.AUTOSAMPLE_LEVELING]:
            self._leveling_chunker.add_chunk(coarse_chunk, timestamp)
            timestamp, chunk = self._leveling_chunker.get_next_data()
            while chunk:
                self._got_leveling_chunk(chunk, timestamp)
                timestamp, chunk = self._leveling_chunker.get_next_data()
        else:
            log.error("_got_coarse_chunk: current state not recognized")

    def async_send_event(self, event):
        """
        Start a separate thread that can block (without affecting this thread)
        on the on_event() method.
        """
        async_event_thread = threading.Thread(
            target=self._protocol_fsm.on_event,
            args=(event, ))
        async_event_thread.start()

    def _got_leveling_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Invoke
        this driver's _my_add_to_buffer, or pass it to extract_sample
        with the appropriate particle objects and REGEXes.  We need to invoke
        _my_add_to_buffer, because we've overridden the base class
        add_to_buffer that is called from got_data().  The reason is explained
        in comments in _my_add_to_buffer.
        """

        if self.leveling_regex.match(chunk):
            # This is a leveling status message; doesn't need to be added to
            # prompt_buf, but we might neet to take action on it, depending
            # upon what it is.
            log.debug("leveling_regex match: %s.", chunk)
            if STATUS_LEVELED in chunk:
                log.info("got_leveling_chunk(): sending event %s to fsm",
                         ProtocolEvent.LEVELING_COMPLETE)
                self.async_send_event(ProtocolEvent.LEVELING_COMPLETE)

        elif self.cmd_rsp_regex.match(chunk):
            # This is a command response: add to the prompt_buf so do_cmd_resp
            # can react to it.
            log.error("cmd_rsp_regex match: %s", chunk)
            self._my_add_to_buffer(chunk)
        else:
            log.error("chunk doesn't match cmd_rsp_regex or leveling_regex: %s", chunk)
            if not self._extract_sample(LILYDataParticle,
                                        self.data_regex,
                                        chunk, timestamp):
                raise InstrumentProtocolException("Unhandled chunk")

    def _got_command_autosample_chunk(self, chunk, timestamp):
        """
        The base class got_data has gotten a chunk from the chunker.  Invoke
        this driver's _my_add_to_buffer, or pass it to extract_sample
        with the appropriate particle objects and REGEXes.  We need to invoke
        _my_add_to_buffer, because we've overridden the base class
        add_to_buffer that is called from got_data().  The reason is explained
        in comments in _my_add_to_buffer.
        """
        if self.cmd_rsp_regex.match(chunk) or self.status_01_regex.match(chunk) or self.status_02_regex.match(chunk):
            self._my_add_to_buffer(chunk)
        elif self.leveling_regex.match(chunk):
            # need to switch to leveling state here, including the timeout (we
            # might have just come active, and the instrument is already in
            # leveling)
            log.info("got_leveling_chunk() in command mode: sending event %s to fsm",
                     ProtocolEvent.RESUME_LEVELING)
            self.async_send_event(ProtocolEvent.RESUME_LEVELING)
        else:
            if not self._extract_sample(LILYDataParticle,
                                        self.data_regex,
                                        chunk, timestamp):
                raise InstrumentProtocolException("Unhandled chunk")

    def _extract_sample(self, particle_class, regex, line, timestamp, publish=True):
        """
        Extract sample from a response line if present and publish
        parsed particle

        @param particle_class The class to instantiate for this specific
            data particle. Parameterizing this allows for simple, standard
            behavior from this routine
        @param regex The regular expression that matches a data sample
        @param line string to match for sample.
        @param timestamp port agent timestamp to include with the particle
        @param publish boolean to publish samples (default True). If True,
               two different events are published: one to notify raw data and
               the other to notify parsed data.

        @retval dict of dicts {'parsed': parsed_sample, 'raw': raw_sample} if
                the line can be parsed for a sample. Otherwise, None.
        @todo Figure out how the agent wants the results for a single poll
            and return them that way from here
        """
        sample = None
        if regex.match(line):
            particle = particle_class(line, self._auto_relevel, port_timestamp=timestamp)
            parsed_sample = particle.generate()

            if publish and self._driver_event:
                self._driver_event(DriverAsyncEvent.SAMPLE, parsed_sample)

            sample = json.loads(parsed_sample)

        else:
            log.info("No regex match in extract_sample.")

        return sample

    def _build_command(self, cmd, *args, **kwargs):
        command = cmd + NL
        log.debug("_build_command: command is: %s", command)
        return command

    def _parse_data_on_off_resp(self, response, prompt):
        log.debug("_parse_data_on_off_resp: response: %r; prompt: %s", response, prompt)
        return response.lily_command_response

    def _parse_status_01_resp(self, response, prompt):
        log.debug("_parse_status_01_resp: response: %r; prompt: %s", response, prompt)
        return response.lily_status_response

    def _parse_status_02_resp(self, response, prompt):
        log.debug("_parse_status_02_resp: response: %r; prompt: %s", response, prompt)
        return response.lily_status_response

    def _wakeup(self, timeout, delay=1):
        """
        Overriding _wakeup; does not apply to this instrument
        """
        pass

    # """
    # Overriding this because it clears the promptbuf with no coordination with
    # another thread of execution that uses the same variable.
    # """
    def _do_cmd_resp(self, cmd, *args, **kwargs):
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

        # Get timeout and initialize response.
        timeout = kwargs.get('timeout', DEFAULT_CMD_TIMEOUT)
        expected_prompt = kwargs.get('expected_prompt', None)
        write_delay = kwargs.get('write_delay', DEFAULT_WRITE_DELAY)

        # Get the build handler.
        build_handler = self._build_handlers.get(cmd, None)
        if not build_handler:
            raise InstrumentProtocolException('Cannot build command: %s' % cmd)

        # noinspection PyCallingNonCallable
        cmd_line = build_handler(cmd, *args)

        # Wakeup the device, pass up exception if timeout

        self._wakeup(timeout)

        # Clear line and prompt buffers for result.
        self._linebuf = ''

        # Send command.
        log.debug('_do_cmd_resp: %s, timeout=%s, write_delay=%s, expected_prompt=%s,' %
                  (repr(cmd_line), timeout, write_delay, expected_prompt))

        if write_delay == 0:
            self._connection.send(cmd_line)
        else:
            for char in cmd_line:
                self._connection.send(char)
                time.sleep(write_delay)

        log.debug('done sending, getting response...')
        # Wait for the prompt, prepare result and return, timeout exception
        prompt, result = self._get_response(timeout, expected_prompt=expected_prompt)

        resp_handler = self._response_handlers.get((self.get_current_state(), cmd), None) or \
                       self._response_handlers.get(cmd, None)
        resp_result = None
        if resp_handler:
            # noinspection PyCallingNonCallable
            resp_result = resp_handler(result, prompt)

        return resp_result

    def _get_response(self, timeout=30, expected_prompt=None, response_regex=None):
        """
        Overriding _get_response: this one uses regex on chunks
        that have already been filtered by the chunker.  An improvement
        to the chunker could be metadata labeling the chunk so that we
        don't have to do another match, although I don't think it is that
        expensive once the chunk has been pulled out to match again
        
        @param timeout The timeout in seconds
        @param expected_prompt Only consider the specific expected prompt as
        presented by this string
        @throw InstrumentProtocolException on timeout
        """
        # Grab time for timeout and wait for response

        starttime = time.time()

        response = None

        # Spin around for <timeout> looking for the response to arrive
        continuing = True
        response = "no response"
        while continuing:
            if self.cmd_rsp_regex.match(self._promptbuf):
                response = LILYCommandResponse(self._promptbuf)
                log.debug("_get_response() matched CommandResponse. _promptbuf: %s",
                          self._promptbuf)
                response.check_command_response(expected_prompt)
                continuing = False
            elif self.status_01_regex.match(self._promptbuf):
                response = LILYStatus01Particle(self._promptbuf)
                log.debug("_get_response() matched Status_01_Response")
                response.build_response()
                continuing = False
            elif self.status_02_regex.match(self._promptbuf):
                response = LILYStatus02Particle(self._promptbuf)
                log.debug("_get_response() matched Status_02_Response")
                response.build_response()
                continuing = False
            else:
                time.sleep(.1)

            if timeout and time.time() > starttime + timeout:
                log.error("TIMEOUT IN GET RESPONSE!  LOOKING FOR %r in %s",
                          expected_prompt, self._promptbuf)
                raise InstrumentTimeoutException("in BOTPT LILY driver._get_response()")

        # Clear the promptbuf here; first acquire mutex
        promptbuf_mutex.acquire()
        log.debug("get_response deleting promptbuf: %s", self._promptbuf)
        self._promptbuf = ''
        promptbuf_mutex.release()

        return 'LILY_RESPONSE', response

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
        return ProtocolState.COMMAND, ResourceAgentState.IDLE

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
                        DriverSchedulerConfigKey.MINUTES: LEVELING_TIMEOUT
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
            log.critical("_handler_leveling_complete")

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
    # Handlers common to Command and Autosample States.
    ########################################################################

    def _handler_command_autosample_dump01(self, *args, **kwargs):
        """
        Get device status
        """
        return self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS_01,
                                             None,
                                             None,
                                             kwargs.get('timeout'))

    def _handler_command_autosample_dump02(self, *args, **kwargs):
        """
        Get device status
        """
        return self._handler_command_generic(InstrumentCommand.DUMP_SETTINGS_02,
                                             None,
                                             None,
                                             kwargs.get('timeout'))

    def _handler_command_start_leveling(self, *args, **kwargs):
        """
        Put instrument into leveling mode
        """
        return self._handler_command_generic(InstrumentCommand.START_LEVELING,
                                             ProtocolState.COMMAND_LEVELING,
                                             ResourceAgentState.CALIBRATE,
                                             kwargs.get('timeout'))

    def _handler_autosample_start_leveling(self, *args, **kwargs):
        """
        Put instrument into leveling mode
        """
        return self._handler_command_generic(InstrumentCommand.START_LEVELING,
                                             ProtocolState.AUTOSAMPLE_LEVELING,
                                             ResourceAgentState.CALIBRATE,
                                             kwargs.get('timeout'))

    def _handler_command_resume_leveling(self, *args, **kwargs):
        """
        Instrument was in leveling mode; sync up by putting driver in leveling
        state
        """
        log.debug("LILY handler_command_resume_leveling.")

        next_state = ProtocolState.COMMAND_LEVELING
        next_agent_state = ResourceAgentState.CALIBRATE
        result = None

        return next_state, (next_agent_state, result)

    def _handler_autosample_resume_leveling(self, *args, **kwargs):
        """
        Instrument was in leveling mode; sync up by putting driver in leveling
        state
        """
        log.debug("LILY handler_command_resume_leveling.")

        next_state = ProtocolState.AUTOSAMPLE_LEVELING
        next_agent_state = ResourceAgentState.CALIBRATE
        result = None

        return next_state, (next_agent_state, result)